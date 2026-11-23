"""
Unit Tests for Cryptographic Webhook Signatures
Verifies HMAC-SHA256 signature generation, constant-time verification,
timestamp tolerance, replay attack protection, and tampering detection.
"""

import json
import time
import pytest

from app.core.config import settings
from app.core.exceptions import (
    AuthenticationException,
    BusinessRuleViolationException,
)
from app.integrations.payment.stripe_provider import StripePaymentGateway


def test_valid_webhook_signature_verification():
    """
    Test that a validly signed payload passes cryptographic verification.
    """
    gateway = StripePaymentGateway(
        secret_key="sk_test",
        webhook_secret="whsec_test_secret_12345",
    )
    payload_dict = {
        "id": "evt_test_123",
        "type": "payment_intent.succeeded",
        "data": {"object": {"id": "pi_test_abc"}},
    }
    payload_bytes = json.dumps(payload_dict).encode("utf-8")
    signature_header = StripePaymentGateway.generate_signature_header(
        payload_bytes=payload_bytes,
        secret="whsec_test_secret_12345",
    )

    parsed_event = gateway.verify_webhook_signature(
        payload_bytes=payload_bytes,
        signature_header=signature_header,
        secret="whsec_test_secret_12345",
    )

    assert parsed_event["id"] == "evt_test_123"
    assert parsed_event["type"] == "payment_intent.succeeded"
    assert parsed_event["data"]["object"]["id"] == "pi_test_abc"


def test_tampered_payload_signature_rejected():
    """
    Test that any byte alteration to the payload breaks the HMAC digest.
    """
    gateway = StripePaymentGateway(
        secret_key="sk_test",
        webhook_secret="whsec_test_secret_12345",
    )
    original_bytes = json.dumps({"amount": 5000}).encode("utf-8")
    signature_header = StripePaymentGateway.generate_signature_header(
        payload_bytes=original_bytes,
        secret="whsec_test_secret_12345",
    )

    # Attacker alters amount in body to 100
    tampered_bytes = json.dumps({"amount": 100}).encode("utf-8")

    with pytest.raises(AuthenticationException) as exc_info:
        gateway.verify_webhook_signature(
            payload_bytes=tampered_bytes,
            signature_header=signature_header,
            secret="whsec_test_secret_12345",
        )
    assert exc_info.value.code == "INVALID_WEBHOOK_SIGNATURE"


def test_wrong_secret_signature_rejected():
    """
    Test that signing with an untrusted or incorrect secret is rejected.
    """
    gateway = StripePaymentGateway(
        secret_key="sk_test",
        webhook_secret="whsec_legit_secret",
    )
    payload_bytes = json.dumps({"id": "evt_123"}).encode("utf-8")
    # Signed with wrong secret
    bad_signature_header = StripePaymentGateway.generate_signature_header(
        payload_bytes=payload_bytes,
        secret="whsec_imposter_secret",
    )

    with pytest.raises(AuthenticationException) as exc_info:
        gateway.verify_webhook_signature(
            payload_bytes=payload_bytes,
            signature_header=bad_signature_header,
            secret="whsec_legit_secret",
        )
    assert exc_info.value.code == "INVALID_WEBHOOK_SIGNATURE"


def test_expired_timestamp_replay_attack_rejected():
    """
    Test that webhooks with timestamps outside the tolerance window are rejected.
    """
    gateway = StripePaymentGateway(
        secret_key="sk_test",
        webhook_secret="whsec_test_secret",
    )
    payload_bytes = json.dumps({"id": "evt_replay"}).encode("utf-8")

    # Timestamp from 10 minutes (600 seconds) ago
    expired_timestamp = int(time.time()) - 600
    expired_signature_header = StripePaymentGateway.generate_signature_header(
        payload_bytes=payload_bytes,
        secret="whsec_test_secret",
        timestamp=expired_timestamp,
    )

    with pytest.raises(BusinessRuleViolationException) as exc_info:
        gateway.verify_webhook_signature(
            payload_bytes=payload_bytes,
            signature_header=expired_signature_header,
            secret="whsec_test_secret",
            tolerance_seconds=300,
        )
    assert exc_info.value.code == "WEBHOOK_TIMESTAMP_EXPIRED"


def test_missing_or_malformed_signature_header():
    """
    Test that missing or malformed signature headers are safely rejected.
    """
    gateway = StripePaymentGateway(
        secret_key="sk_test",
        webhook_secret="whsec_test_secret",
    )
    payload_bytes = b'{"id": "evt_1"}'

    with pytest.raises(AuthenticationException) as exc1:
        gateway.verify_webhook_signature(payload_bytes, "", "whsec_test_secret")
    assert exc1.value.code == "MISSING_WEBHOOK_SIGNATURE"

    with pytest.raises(AuthenticationException) as exc2:
        gateway.verify_webhook_signature(payload_bytes, "malformed_header_value", "whsec_test_secret")
    assert exc2.value.code == "MALFORMED_WEBHOOK_SIGNATURE"
