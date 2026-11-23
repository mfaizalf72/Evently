"""
Payment API Endpoints
RESTful routes for initiating checkout, processing verified webhooks,
and querying payment transaction status.
"""

from typing import Optional
import uuid
from fastapi import APIRouter, Depends, Header, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.database.session import get_db
from app.models.user import User
from app.schemas.payment import (
    CheckoutSessionResponse,
    PaymentResponse,
    WebhookResponse,
)
from app.services.payment_service import PaymentService

router = APIRouter(tags=["Payments"])


def get_payment_service(db: AsyncSession = Depends(get_db)) -> PaymentService:
    return PaymentService(db=db)


@router.post(
    "/payments/checkout/{booking_id}",
    response_model=CheckoutSessionResponse,
    status_code=status.HTTP_200_OK,
    summary="Initiate Checkout Session",
    description="Creates or retrieves a payment intent with the provider for a reserved pending booking.",
)
async def checkout_booking(
    booking_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    service: PaymentService = Depends(get_payment_service),
) -> CheckoutSessionResponse:
    return await service.initiate_checkout(
        booking_id=booking_id,
        current_user=current_user,
    )


@router.post(
    "/payments/webhook",
    response_model=WebhookResponse,
    status_code=status.HTTP_200_OK,
    summary="Process Payment Provider Webhook",
    description="Receives cryptographically signed webhooks from payment provider and confirms bookings.",
)
async def payment_webhook(
    request: Request,
    stripe_signature: Optional[str] = Header(None, alias="Stripe-Signature"),
    x_signature: Optional[str] = Header(None, alias="X-Signature"),
    service: PaymentService = Depends(get_payment_service),
) -> WebhookResponse:
    # Accept Stripe-Signature or generic X-Signature
    signature = stripe_signature or x_signature or ""
    raw_payload = await request.body()
    return await service.process_webhook(
        raw_payload=raw_payload,
        signature_header=signature,
    )


@router.get(
    "/payments/{payment_id}",
    response_model=PaymentResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Payment Transaction Details",
    description="Retrieves transaction details and status. Requires order ownership or event organizer role.",
)
async def get_payment(
    payment_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    service: PaymentService = Depends(get_payment_service),
) -> PaymentResponse:
    return await service.get_payment_by_id(
        payment_id=payment_id,
        current_user=current_user,
    )
