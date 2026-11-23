"""
Payment Schemas Module
Pydantic v2 schemas for Checkout, Payment transactions, and Webhook responses.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field


class PaymentCreate(BaseModel):
    """Payload to initiate checkout for a booking."""
    booking_id: uuid.UUID = Field(..., description="Target booking identifier to checkout")


class PaymentResponse(BaseModel):
    """Transaction details of a payment."""
    id: uuid.UUID = Field(..., description="Unique payment identifier")
    booking_id: uuid.UUID = Field(..., description="Associated booking identifier")
    provider: str = Field(..., description="Payment provider name (e.g. stripe, mock)")
    provider_payment_intent_id: str = Field(..., description="External payment provider intent ID")
    amount: Decimal = Field(..., description="Transaction amount")
    currency: str = Field(..., description="Transaction currency (e.g. usd)")
    status: str = Field(..., description="Payment status (pending, succeeded, failed, refunded)")
    client_secret: Optional[str] = Field(None, description="Client secret for frontend SDK integration")
    idempotency_key: Optional[str] = Field(None, description="Idempotency key for transaction")
    created_at: datetime = Field(..., description="Creation timestamp (UTC)")
    updated_at: datetime = Field(..., description="Last update timestamp (UTC)")

    model_config = ConfigDict(from_attributes=True)


class CheckoutSessionResponse(BaseModel):
    """Session envelope returned when checkout is initiated."""
    booking_id: uuid.UUID = Field(..., description="Booking identifier")
    payment_id: uuid.UUID = Field(..., description="Payment transaction identifier")
    provider: str = Field(..., description="Payment provider name")
    provider_payment_intent_id: str = Field(..., description="Provider payment intent identifier")
    client_secret: Optional[str] = Field(None, description="Client secret for payment confirmation")
    amount: Decimal = Field(..., description="Total charge amount")
    currency: str = Field(..., description="Payment currency")
    status: str = Field(..., description="Payment status")


class WebhookResponse(BaseModel):
    """Acknowledgement envelope returned to webhook callers."""
    received: bool = Field(True, description="Whether the webhook was received")
    event_id: str = Field(..., description="External event identifier processed")
    status: str = Field(..., description="Outcome status (PROCESSED, ALREADY_PROCESSED, IGNORED)")
    message: str = Field(..., description="Human-readable processing summary")
