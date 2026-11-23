"""
Integration Tests for V8 Milestone: Payment Integration & Webhook Verification
Verifies checkout session initiation, cryptographic webhook processing,
idempotent event ingestion, atomic booking confirmation, and security guards.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
import time
import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import update

from app.core.config import settings
from app.core.security import create_access_token
from app.integrations.payment.stripe_provider import StripePaymentGateway
from app.models.booking import Booking, BookingStatus
from tests.conftest import TestAsyncSessionLocal


async def setup_event_and_pending_booking(
    client: AsyncClient,
    organizer_token: str,
    customer_token: str,
    price: str = "50.00",
    quantity: int = 2,
) -> tuple[str, str, str]:
    """Helper to create a published event, a ticket tier, and a customer booking."""
    start = (datetime.now(timezone.utc) + timedelta(days=6)).isoformat()
    end = (datetime.now(timezone.utc) + timedelta(days=6, hours=2)).isoformat()

    # 1. Create Event
    event_resp = await client.post(
        f"{settings.API_V1_STR}/events",
        headers={"Authorization": f"Bearer {organizer_token}"},
        json={
            "title": f"Payment Test Event {uuid.uuid4().hex[:6]}",
            "location": "Main Stage",
            "start_time": start,
            "end_time": end,
            "total_capacity": 30,
            "price": price,
            "is_published": True,
        },
    )
    event_id = event_resp.json()["id"]

    # 2. Create Tier
    tier_resp = await client.post(
        f"{settings.API_V1_STR}/events/{event_id}/tiers",
        headers={"Authorization": f"Bearer {organizer_token}"},
        json={
            "name": "General Admission",
            "price": price,
            "total_capacity": 30,
        },
    )
    tier_id = tier_resp.json()["id"]

    # 3. Create Booking
    booking_resp = await client.post(
        f"{settings.API_V1_STR}/events/{event_id}/bookings",
        headers={"Authorization": f"Bearer {customer_token}"},
        json={"items": [{"ticket_tier_id": tier_id, "quantity": quantity}]},
    )
    booking_id = booking_resp.json()["id"]
    return event_id, tier_id, booking_id


@pytest.mark.asyncio
async def test_checkout_session_initiation_success(
    async_client: AsyncClient,
    organizer_token: str,
    customer_token: str,
):
    """
    Test initiating checkout creates a pending payment intent with provider
    and returns client secret for frontend checkout.
    """
    _, _, booking_id = await setup_event_and_pending_booking(
        async_client,
        organizer_token,
        customer_token,
        price="50.00",
        quantity=2,
    )

    # Initiate checkout
    checkout_resp = await async_client.post(
        f"{settings.API_V1_STR}/payments/checkout/{booking_id}",
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert checkout_resp.status_code == 200
    data = checkout_resp.json()

    assert data["booking_id"] == booking_id
    assert "payment_id" in data
    assert data["provider"] == settings.PAYMENT_PROVIDER
    assert data["provider_payment_intent_id"].startswith("pi_")
    assert data["client_secret"] is not None
    assert data["amount"] == "100.00"
    assert data["status"] == "pending"

    # Idempotent re-checkout returns identical payment intent
    second_checkout = await async_client.post(
        f"{settings.API_V1_STR}/payments/checkout/{booking_id}",
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert second_checkout.status_code == 200
    second_data = second_checkout.json()
    assert second_data["payment_id"] == data["payment_id"]
    assert second_data["provider_payment_intent_id"] == data["provider_payment_intent_id"]


@pytest.mark.asyncio
async def test_checkout_authorization_guards(
    async_client: AsyncClient,
    organizer_token: str,
    customer_token: str,
):
    """
    Test that unauthenticated users or different customers cannot checkout another's booking.
    """
    _, _, booking_id = await setup_event_and_pending_booking(
        async_client,
        organizer_token,
        customer_token,
    )

    # 1. Unauthenticated checkout
    unauth_resp = await async_client.post(
        f"{settings.API_V1_STR}/payments/checkout/{booking_id}",
    )
    assert unauth_resp.status_code == 401

    # 2. Other customer attempts checkout
    other_email = f"other_{uuid.uuid4().hex[:6]}@evently.com"
    await async_client.post(
        f"{settings.API_V1_STR}/auth/register",
        json={
            "email": other_email,
            "password": "Password123!",
            "full_name": "Other Customer",
            "role": "customer",
        },
    )
    login_resp = await async_client.post(
        f"{settings.API_V1_STR}/auth/login",
        json={
            "email": other_email,
            "password": "Password123!",
        },
    )
    other_token = login_resp.json()["access_token"]

    forbidden_resp = await async_client.post(
        f"{settings.API_V1_STR}/payments/checkout/{booking_id}",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert forbidden_resp.status_code == 403
    assert forbidden_resp.json()["error"]["code"] == "FORBIDDEN_BOOKING_ACCESS"


@pytest.mark.asyncio
async def test_checkout_rejected_for_expired_booking(
    async_client: AsyncClient,
    organizer_token: str,
    customer_token: str,
):
    """
    Test that initiating checkout for an expired booking hold is rejected.
    """
    _, _, booking_id = await setup_event_and_pending_booking(
        async_client,
        organizer_token,
        customer_token,
    )

    # Simulate expired reservation
    past_time = datetime.now(timezone.utc) - timedelta(minutes=5)
    async with TestAsyncSessionLocal() as session:
        await session.execute(
            update(Booking)
            .where(Booking.id == uuid.UUID(booking_id))
            .values(expires_at=past_time)
        )
        await session.commit()

    checkout_resp = await async_client.post(
        f"{settings.API_V1_STR}/payments/checkout/{booking_id}",
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert checkout_resp.status_code == 400
    assert checkout_resp.json()["error"]["code"] == "BOOKING_EXPIRED"


@pytest.mark.asyncio
async def test_webhook_payment_succeeded_confirms_booking(
    async_client: AsyncClient,
    organizer_token: str,
    customer_token: str,
):
    """
    Test that receiving a cryptographically verified 'payment_intent.succeeded' webhook
    atomically transitions Booking status to 'confirmed', clears expires_at,
    and marks Payment as 'succeeded'.
    """
    _, _, booking_id = await setup_event_and_pending_booking(
        async_client,
        organizer_token,
        customer_token,
        price="75.00",
        quantity=1,
    )

    # 1. Customer initiates checkout
    checkout_resp = await async_client.post(
        f"{settings.API_V1_STR}/payments/checkout/{booking_id}",
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    checkout_data = checkout_resp.json()
    intent_id = checkout_data["provider_payment_intent_id"]
    payment_id = checkout_data["payment_id"]

    # 2. Simulate payment provider webhook event
    event_id = f"evt_{uuid.uuid4().hex[:16]}"
    webhook_payload = {
        "id": event_id,
        "type": "payment_intent.succeeded",
        "data": {
            "object": {
                "id": intent_id,
                "amount": 7500,
                "currency": "usd",
                "status": "succeeded",
            }
        },
    }
    raw_body = json.dumps(webhook_payload).encode("utf-8")
    signature_header = StripePaymentGateway.generate_signature_header(
        payload_bytes=raw_body,
        secret=settings.PAYMENT_WEBHOOK_SECRET,
    )

    # 3. Post webhook to backend
    webhook_resp = await async_client.post(
        f"{settings.API_V1_STR}/payments/webhook",
        headers={"Stripe-Signature": signature_header},
        content=raw_body,
    )
    assert webhook_resp.status_code == 200
    webhook_data = webhook_resp.json()
    assert webhook_data["received"] is True
    assert webhook_data["status"] == "PROCESSED"
    assert webhook_data["event_id"] == event_id

    # 4. Verify Booking is now CONFIRMED and expiration hold is cleared
    booking_check = await async_client.get(
        f"{settings.API_V1_STR}/bookings/{booking_id}",
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert booking_check.status_code == 200
    booking_state = booking_check.json()
    assert booking_state["status"] == "confirmed"
    assert booking_state["expires_at"] is None

    # 5. Verify Payment is now SUCCEEDED
    payment_check = await async_client.get(
        f"{settings.API_V1_STR}/payments/{payment_id}",
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert payment_check.status_code == 200
    assert payment_check.json()["status"] == "succeeded"


@pytest.mark.asyncio
async def test_webhook_idempotency_prevents_duplicate_processing(
    async_client: AsyncClient,
    organizer_token: str,
    customer_token: str,
):
    """
    Test that re-delivering the exact same webhook event ID returns 200 OK
    with ALREADY_PROCESSED status without executing duplicate database transitions.
    """
    _, _, booking_id = await setup_event_and_pending_booking(
        async_client,
        organizer_token,
        customer_token,
    )

    checkout_resp = await async_client.post(
        f"{settings.API_V1_STR}/payments/checkout/{booking_id}",
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    intent_id = checkout_resp.json()["provider_payment_intent_id"]

    event_id = f"evt_idempotent_{uuid.uuid4().hex[:12]}"
    webhook_payload = {
        "id": event_id,
        "type": "payment_intent.succeeded",
        "data": {
            "object": {
                "id": intent_id,
                "status": "succeeded",
            }
        },
    }
    raw_body = json.dumps(webhook_payload).encode("utf-8")
    sig = StripePaymentGateway.generate_signature_header(raw_body, settings.PAYMENT_WEBHOOK_SECRET)

    # First delivery
    resp1 = await async_client.post(
        f"{settings.API_V1_STR}/payments/webhook",
        headers={"Stripe-Signature": sig},
        content=raw_body,
    )
    assert resp1.status_code == 200
    assert resp1.json()["status"] == "PROCESSED"

    # Second delivery (gateway retry)
    resp2 = await async_client.post(
        f"{settings.API_V1_STR}/payments/webhook",
        headers={"Stripe-Signature": sig},
        content=raw_body,
    )
    assert resp2.status_code == 200
    assert resp2.json()["status"] == "ALREADY_PROCESSED"


@pytest.mark.asyncio
async def test_webhook_payment_failed_records_failure(
    async_client: AsyncClient,
    organizer_token: str,
    customer_token: str,
):
    """
    Test that receiving a 'payment_intent.payment_failed' webhook transitions
    Payment status to 'failed' while Booking remains 'pending'.
    """
    _, _, booking_id = await setup_event_and_pending_booking(
        async_client,
        organizer_token,
        customer_token,
    )

    checkout_resp = await async_client.post(
        f"{settings.API_V1_STR}/payments/checkout/{booking_id}",
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    intent_id = checkout_resp.json()["provider_payment_intent_id"]
    payment_id = checkout_resp.json()["payment_id"]

    event_id = f"evt_failed_{uuid.uuid4().hex[:12]}"
    webhook_payload = {
        "id": event_id,
        "type": "payment_intent.payment_failed",
        "data": {
            "object": {
                "id": intent_id,
                "status": "failed",
            }
        },
    }
    raw_body = json.dumps(webhook_payload).encode("utf-8")
    sig = StripePaymentGateway.generate_signature_header(raw_body, settings.PAYMENT_WEBHOOK_SECRET)

    resp = await async_client.post(
        f"{settings.API_V1_STR}/payments/webhook",
        headers={"Stripe-Signature": sig},
        content=raw_body,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "PROCESSED"

    # Payment is marked failed
    payment_check = await async_client.get(
        f"{settings.API_V1_STR}/payments/{payment_id}",
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert payment_check.json()["status"] == "failed"

    # Booking remains pending (customer can retry checkout)
    booking_check = await async_client.get(
        f"{settings.API_V1_STR}/bookings/{booking_id}",
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert booking_check.json()["status"] == "pending"


@pytest.mark.asyncio
async def test_webhook_invalid_signature_rejected(async_client: AsyncClient):
    """
    Test that an unsigned or forged webhook request is rejected with 401 Unauthorized.
    """
    raw_body = json.dumps({"id": "evt_fake", "type": "payment_intent.succeeded"}).encode("utf-8")

    # Missing signature
    resp_missing = await async_client.post(
        f"{settings.API_V1_STR}/payments/webhook",
        content=raw_body,
    )
    assert resp_missing.status_code == 401
    assert resp_missing.json()["error"]["code"] == "MISSING_WEBHOOK_SIGNATURE"

    # Forged signature with fresh timestamp
    now = int(time.time())
    resp_forged = await async_client.post(
        f"{settings.API_V1_STR}/payments/webhook",
        headers={"Stripe-Signature": f"t={now},v1=bad_hash_value"},
        content=raw_body,
    )
    assert resp_forged.status_code == 401
    assert resp_forged.json()["error"]["code"] == "INVALID_WEBHOOK_SIGNATURE"


@pytest.mark.asyncio
async def test_webhook_expired_timestamp_rejected(async_client: AsyncClient):
    """
    Test that a webhook with a timestamp older than tolerance (300s) is rejected
    to protect against replay attacks.
    """
    raw_body = json.dumps({"id": "evt_replay", "type": "payment_intent.succeeded"}).encode("utf-8")
    old_timestamp = int(time.time()) - 400
    sig = StripePaymentGateway.generate_signature_header(
        payload_bytes=raw_body,
        secret=settings.PAYMENT_WEBHOOK_SECRET,
        timestamp=old_timestamp,
    )

    resp = await async_client.post(
        f"{settings.API_V1_STR}/payments/webhook",
        headers={"Stripe-Signature": sig},
        content=raw_body,
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "WEBHOOK_TIMESTAMP_EXPIRED"
