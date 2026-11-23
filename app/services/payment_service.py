"""
Payment Service Module
Orchestrates payment checkout initiation, cryptographic webhook processing,
idempotent event ingestion, and atomic booking confirmation.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
import uuid
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import (
    AuthorizationException,
    BusinessRuleViolationException,
    EntityNotFoundException,
)
from app.integrations.payment.base import PaymentGateway
from app.integrations.payment.stripe_provider import StripePaymentGateway
from app.models.booking import BookingStatus
from app.models.payment import Payment, PaymentStatus, WebhookEvent
from app.models.user import User
from app.repositories.booking_repository import BookingRepository
from app.repositories.payment_repository import (
    PaymentRepository,
    WebhookEventRepository,
)
from app.schemas.payment import (
    CheckoutSessionResponse,
    PaymentResponse,
    WebhookResponse,
)


class PaymentService:
    """
    Coordinates checkout workflows and cryptographic webhook state transitions.
    """
    def __init__(
        self,
        db: AsyncSession,
        gateway: Optional[PaymentGateway] = None,
    ):
        self.db = db
        self.payment_repo = PaymentRepository(db=db)
        self.webhook_repo = WebhookEventRepository(db=db)
        self.booking_repo = BookingRepository(db=db)
        self.gateway = gateway or StripePaymentGateway(
            secret_key=settings.STRIPE_SECRET_KEY,
            webhook_secret=settings.PAYMENT_WEBHOOK_SECRET,
            is_mock=(settings.PAYMENT_PROVIDER == "mock"),
        )

    async def initiate_checkout(
        self,
        booking_id: uuid.UUID,
        current_user: User,
    ) -> CheckoutSessionResponse:
        """
        Initiates a payment checkout session for a reserved pending booking.
        Reuses existing pending intents if already created to maintain idempotency.
        """
        booking = await self.booking_repo.get_by_id(booking_id)
        if not booking:
            raise EntityNotFoundException(entity_name="Booking", entity_id=booking_id)

        # Enforce authorization
        if current_user.role != "admin" and booking.customer_id != current_user.id:
            raise AuthorizationException(
                message="You do not have permission to checkout this booking.",
                code="FORBIDDEN_BOOKING_ACCESS",
            )

        # Validate booking status
        if booking.status == BookingStatus.CONFIRMED.value:
            raise BusinessRuleViolationException(
                message="This booking is already confirmed.",
                code="BOOKING_ALREADY_CONFIRMED",
            )

        if booking.status in (BookingStatus.CANCELLED.value, BookingStatus.EXPIRED.value):
            raise BusinessRuleViolationException(
                message=f"Cannot initiate checkout for a {booking.status} booking.",
                code="BOOKING_INACTIVE",
            )

        # Enforce expiration deadline
        now = datetime.now(timezone.utc)
        if booking.expires_at and booking.expires_at <= now:
            raise BusinessRuleViolationException(
                message="The reservation hold for this booking has expired.",
                code="BOOKING_EXPIRED",
            )

        if booking.total_amount <= Decimal("0.00"):
            raise BusinessRuleViolationException(
                message="Free bookings are already confirmed and do not require payment.",
                code="FREE_BOOKING_NO_PAYMENT_REQUIRED",
            )

        # Check for existing active pending payment to prevent duplicate charges
        existing_payment = await self.payment_repo.get_pending_payment_for_booking(booking_id)
        if existing_payment:
            return CheckoutSessionResponse(
                booking_id=booking.id,
                payment_id=existing_payment.id,
                provider=existing_payment.provider,
                provider_payment_intent_id=existing_payment.provider_payment_intent_id,
                client_secret=existing_payment.client_secret,
                amount=existing_payment.amount,
                currency=existing_payment.currency,
                status=existing_payment.status,
            )

        # Create new payment intent with payment provider
        intent_result = await self.gateway.create_payment_intent(
            amount=booking.total_amount,
            currency="usd",
            metadata={"booking_id": str(booking.id), "customer_id": str(current_user.id)},
        )

        payment = Payment(
            booking_id=booking.id,
            provider=settings.PAYMENT_PROVIDER,
            provider_payment_intent_id=intent_result.provider_payment_intent_id,
            amount=booking.total_amount,
            currency=intent_result.currency,
            status=PaymentStatus.PENDING.value,
            client_secret=intent_result.client_secret,
        )

        created_payment = await self.payment_repo.create(payment)
        await self.db.commit()

        return CheckoutSessionResponse(
            booking_id=booking.id,
            payment_id=created_payment.id,
            provider=created_payment.provider,
            provider_payment_intent_id=created_payment.provider_payment_intent_id,
            client_secret=created_payment.client_secret,
            amount=created_payment.amount,
            currency=created_payment.currency,
            status=created_payment.status,
        )

    async def process_webhook(
        self,
        raw_payload: bytes,
        signature_header: str,
    ) -> WebhookResponse:
        """
        Cryptographically validates external webhook payload and performs atomic
        order state transitions from PENDING to CONFIRMED.
        """
        # 1. Cryptographically verify webhook signature and freshness
        event_data = self.gateway.verify_webhook_signature(
            payload_bytes=raw_payload,
            signature_header=signature_header,
            secret=settings.PAYMENT_WEBHOOK_SECRET,
            tolerance_seconds=settings.WEBHOOK_TOLERANCE_SECONDS,
        )

        event_id = event_data.get("id")
        event_type = event_data.get("type")

        if not event_id or not event_type:
            raise BusinessRuleViolationException(
                message="Webhook event missing required identifier or event type.",
                code="INVALID_WEBHOOK_EVENT",
            )

        # 2. Strict Webhook Idempotency Check
        existing_event = await self.webhook_repo.get_by_provider_event_id(event_id)
        if existing_event and existing_event.status == "PROCESSED":
            return WebhookResponse(
                received=True,
                event_id=event_id,
                status="ALREADY_PROCESSED",
                message="Webhook event was already processed previously.",
            )

        # Register audit event record
        if not existing_event:
            existing_event = WebhookEvent(
                provider="stripe",
                provider_event_id=event_id,
                event_type=event_type,
                payload=raw_payload.decode("utf-8", errors="replace"),
                status="PENDING",
            )
            await self.webhook_repo.create(existing_event)

        # 3. State Transitions
        if event_type == "payment_intent.succeeded":
            data_obj = event_data.get("data", {}).get("object", {})
            intent_id = data_obj.get("id")

            if not intent_id:
                raise BusinessRuleViolationException(
                    message="Missing payment_intent id in payload data.",
                    code="MALFORMED_WEBHOOK_DATA",
                )

            payment = await self.payment_repo.get_by_provider_payment_intent_id(intent_id)
            if not payment:
                raise EntityNotFoundException(entity_name="Payment", entity_id=intent_id)

            # Update Payment status
            payment.status = PaymentStatus.SUCCEEDED.value

            # Atomically confirm the Booking and clear expiration deadline
            booking = await self.booking_repo.get_by_id(payment.booking_id)
            if booking:
                booking.status = BookingStatus.CONFIRMED.value
                booking.expires_at = None

            existing_event.status = "PROCESSED"
            existing_event.processed_at = datetime.now(timezone.utc)
            await self.db.commit()

            return WebhookResponse(
                received=True,
                event_id=event_id,
                status="PROCESSED",
                message="Payment succeeded. Booking successfully confirmed.",
            )

        elif event_type == "payment_intent.payment_failed":
            data_obj = event_data.get("data", {}).get("object", {})
            intent_id = data_obj.get("id")

            if intent_id:
                payment = await self.payment_repo.get_by_provider_payment_intent_id(intent_id)
                if payment:
                    payment.status = PaymentStatus.FAILED.value

            existing_event.status = "PROCESSED"
            existing_event.processed_at = datetime.now(timezone.utc)
            await self.db.commit()

            return WebhookResponse(
                received=True,
                event_id=event_id,
                status="PROCESSED",
                message="Payment failure recorded.",
            )

        else:
            # Unhandled or informational event
            existing_event.status = "IGNORED"
            existing_event.processed_at = datetime.now(timezone.utc)
            await self.db.commit()

            return WebhookResponse(
                received=True,
                event_id=event_id,
                status="IGNORED",
                message=f"Ignored unhandled event type '{event_type}'.",
            )

    async def get_payment_by_id(
        self,
        payment_id: uuid.UUID,
        current_user: User,
    ) -> PaymentResponse:
        """
        Retrieves payment details with ownership authorization check.
        """
        payment = await self.payment_repo.get_by_id(payment_id)
        if not payment:
            raise EntityNotFoundException(entity_name="Payment", entity_id=payment_id)

        # Verify access: Customer owner, Event organizer, or Admin
        booking = await self.booking_repo.get_by_id(payment.booking_id)
        is_owner = booking.customer_id == current_user.id if booking else False
        is_organizer = (
            booking.event.organizer_id == current_user.id
            if booking and booking.event
            else False
        )
        is_admin = current_user.role == "admin"

        if not (is_owner or is_organizer or is_admin):
            raise AuthorizationException(
                message="You do not have permission to view this payment.",
                code="FORBIDDEN_PAYMENT_ACCESS",
            )

        return PaymentResponse.model_validate(payment)
