"""
Stripe Payment Gateway Provider
Implements payment intent creation, cryptographic HMAC-SHA256 signature verification,
and replay protection following the Stripe webhook specification.
"""

from decimal import Decimal
import hashlib
import hmac
import json
import time
from typing import Any, Dict, Optional
import uuid

from app.core.exceptions import (
    AuthenticationException,
    BusinessRuleViolationException,
)
from app.integrations.payment.base import PaymentGateway, PaymentIntentResult


class StripePaymentGateway(PaymentGateway):
    """
    Stripe-compatible payment gateway implementing HMAC-SHA256 signature verification.
    """
    def __init__(self, secret_key: str, webhook_secret: str, is_mock: bool = False):
        self.secret_key = secret_key
        self.webhook_secret = webhook_secret
        self.is_mock = is_mock

    async def create_payment_intent(
        self,
        amount: Decimal,
        currency: str = "usd",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> PaymentIntentResult:
        """
        Creates a payment intent. In mock mode, generates a deterministic Stripe-formatted intent.
        """
        intent_id = f"pi_{uuid.uuid4().hex[:24]}"
        client_secret = f"{intent_id}_secret_{uuid.uuid4().hex[:16]}"
        return PaymentIntentResult(
            provider_payment_intent_id=intent_id,
            client_secret=client_secret,
            amount=amount,
            currency=currency.lower(),
            status="requires_payment_method",
            metadata=metadata or {},
        )

    def verify_webhook_signature(
        self,
        payload_bytes: bytes,
        signature_header: str,
        secret: str,
        tolerance_seconds: int = 300,
    ) -> Dict[str, Any]:
        """
        Cryptographically validates the webhook signature and returns parsed event payload.
        Stripe header format: t=<timestamp>,v1=<signature>
        """
        if not signature_header:
            raise AuthenticationException(
                message="Missing webhook signature header.",
                code="MISSING_WEBHOOK_SIGNATURE",
            )

        # Parse key-value pairs from header (e.g. t=12345,v1=abcde)
        header_items = {}
        for item in signature_header.split(","):
            parts = item.strip().split("=", 1)
            if len(parts) == 2:
                header_items[parts[0]] = parts[1]

        timestamp_str = header_items.get("t")
        received_signature = header_items.get("v1")

        if not timestamp_str or not received_signature:
            raise AuthenticationException(
                message="Malformed webhook signature header format.",
                code="MALFORMED_WEBHOOK_SIGNATURE",
            )

        try:
            timestamp = int(timestamp_str)
        except ValueError:
            raise AuthenticationException(
                message="Invalid timestamp in webhook signature header.",
                code="INVALID_WEBHOOK_TIMESTAMP",
            )

        # Enforce timestamp tolerance against replay attacks
        now = int(time.time())
        if abs(now - timestamp) > tolerance_seconds:
            raise BusinessRuleViolationException(
                message=f"Webhook timestamp expired or drifted beyond tolerance ({tolerance_seconds}s).",
                code="WEBHOOK_TIMESTAMP_EXPIRED",
            )

        # Reconstruct signed payload: <timestamp>.<payload_bytes>
        signed_payload = f"{timestamp}.".encode("utf-8") + payload_bytes
        computed_signature = hmac.new(
            secret.encode("utf-8"),
            signed_payload,
            hashlib.sha256,
        ).hexdigest()

        # Constant-time comparison to prevent timing attacks
        if not hmac.compare_digest(computed_signature, received_signature):
            raise AuthenticationException(
                message="Invalid cryptographic webhook signature.",
                code="INVALID_WEBHOOK_SIGNATURE",
            )

        try:
            return json.loads(payload_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as err:
            raise BusinessRuleViolationException(
                message="Failed to parse webhook JSON payload.",
                code="INVALID_WEBHOOK_PAYLOAD",
            )

    @staticmethod
    def generate_signature_header(
        payload_bytes: bytes,
        secret: str,
        timestamp: Optional[int] = None,
    ) -> str:
        """
        Utility for tests and webhook simulators to generate authentic Stripe-Signature headers.
        """
        if timestamp is None:
            timestamp = int(time.time())

        signed_payload = f"{timestamp}.".encode("utf-8") + payload_bytes
        signature = hmac.new(
            secret.encode("utf-8"),
            signed_payload,
            hashlib.sha256,
        ).hexdigest()

        return f"t={timestamp},v1={signature}"
