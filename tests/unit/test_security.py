"""
Unit Tests for Cryptographic Security Functions
Tests bcrypt password hashing and PyJWT token generation and verification.
"""

from datetime import timedelta
import uuid
import jwt
import pytest

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_password_hashing_and_verification():
    """Verify that bcrypt hashes passwords securely and verifies them accurately."""
    raw_password = "MySecurePassword123!"
    hashed = hash_password(raw_password)

    assert hashed != raw_password
    assert hashed.startswith("$2b$")
    assert verify_password(raw_password, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False


def test_password_salting_randomness():
    """Verify that hashing the same password twice yields distinct salts/hashes."""
    raw_password = "IdenticalPassword99#"
    hash_1 = hash_password(raw_password)
    hash_2 = hash_password(raw_password)

    assert hash_1 != hash_2
    assert verify_password(raw_password, hash_1) is True
    assert verify_password(raw_password, hash_2) is True


def test_jwt_access_token_generation_and_decoding():
    """Verify JWT access token issuance, signature verification, and claims decoding."""
    user_id = uuid.uuid4()
    token = create_access_token(subject=user_id, role="organizer")

    payload = decode_token(token)
    assert payload["sub"] == str(user_id)
    assert payload["role"] == "organizer"
    assert payload["type"] == "access"
    assert "exp" in payload
    assert "iat" in payload


def test_jwt_refresh_token_claims():
    """Verify JWT refresh token claims."""
    user_id = uuid.uuid4()
    token = create_refresh_token(subject=user_id)

    payload = decode_token(token)
    assert payload["sub"] == str(user_id)
    assert payload["type"] == "refresh"


def test_jwt_tampered_token_rejection():
    """Verify that tampered tokens fail cryptographic verification."""
    user_id = uuid.uuid4()
    token = create_access_token(subject=user_id, role="customer")
    tampered_token = token[:-5] + "abcde"

    with pytest.raises(jwt.PyJWTError):
        decode_token(tampered_token)


def test_jwt_expired_token_rejection():
    """Verify that expired tokens raise jwt.ExpiredSignatureError."""
    user_id = uuid.uuid4()
    expired_token = create_access_token(
        subject=user_id,
        role="customer",
        expires_delta=timedelta(seconds=-10),  # expired 10 seconds ago
    )

    with pytest.raises(jwt.ExpiredSignatureError):
        decode_token(expired_token)
