"""
Unit Tests for User Schemas
Validates registration constraints, email formatting, and password strength checks.
"""

import pytest
from pydantic import ValidationError

from app.schemas.user import UserCreate, UserLogin, UserRole


def test_valid_user_create():
    """Verify that valid registration input passes validation."""
    user_data = UserCreate(
        email="developer@evently.com",
        password="ValidPassword123!",
        full_name="   Jane Developer   ",
        role=UserRole.ORGANIZER,
    )
    assert user_data.email == "developer@evently.com"
    assert user_data.full_name == "Jane Developer"  # Stripped whitespace
    assert user_data.role == UserRole.ORGANIZER


def test_user_create_short_password_rejected():
    """Verify that passwords shorter than 8 characters are rejected."""
    with pytest.raises(ValidationError) as exc_info:
        UserCreate(
            email="short@evently.com",
            password="short",
            full_name="Short Pwd",
        )
    assert "at least 8 characters" in str(exc_info.value)


def test_user_create_invalid_email_rejected():
    """Verify that malformed email addresses raise ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        UserCreate(
            email="not-an-email",
            password="ValidPassword123!",
            full_name="Bad Email",
        )
    assert "email" in str(exc_info.value).lower()


def test_user_login_schema():
    """Verify UserLogin schema acceptance."""
    login_data = UserLogin(
        email="test@evently.com",
        password="MyPassword123!",
    )
    assert login_data.email == "test@evently.com"
    assert login_data.password == "MyPassword123!"
