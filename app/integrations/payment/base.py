"""
Abstract Payment Gateway Interface
Defines the contract for creating payment intents and cryptographically validating webhooks.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, Optional


@dataclass
class PaymentIntentResult:
    """Standardized result returned by a payment gateway provider."""
    provider_payment_intent_id: str
    client_secret: Optional[str]
    amount: Decimal
    currency: str
    status: str
    metadata: Optional[Dict[str, Any]] = None


class PaymentGateway(ABC):
    """
    Abstract payment gateway interface.
    """
    @abstractmethod
    async def create_payment_intent(
        self,
        amount: Decimal,
        currency: str = "usd",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> PaymentIntentResult:
        """Create a payment intent with the external gateway."""
        pass

    @abstractmethod
    def verify_webhook_signature(
        self,
        payload_bytes: bytes,
        signature_header: str,
        secret: str,
        tolerance_seconds: int = 300,
    ) -> Dict[str, Any]:
        """
        Cryptographically validates the webhook signature and returns parsed event payload.
        Raises an exception if signature is invalid or timestamp has expired.
        """
        pass
