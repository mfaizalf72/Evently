"""
Integration Tests for Authentication REST APIs
Tests user registration, login, token refresh, and identity inspection.
"""

import pytest
from httpx import AsyncClient

from app.core.config import settings


@pytest.mark.asyncio
async def test_register_user_success(async_client: AsyncClient):
    """
    Test user registration returns 201 Created and excludes the password hash.
    """
    payload = {
        "email": "newuser@evently.com",
        "password": "StrongPassword123!",
        "full_name": "New User",
        "role": "customer",
    }
    response = await async_client.post(f"{settings.API_V1_STR}/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()

    assert "id" in data
    assert data["email"] == "newuser@evently.com"
    assert data["full_name"] == "New User"
    assert data["role"] == "customer"
    assert data["is_active"] is True
    assert "password" not in data
    assert "hashed_password" not in data


@pytest.mark.asyncio
async def test_register_duplicate_email_fails(async_client: AsyncClient):
    """
    Test registering with an existing email returns 400 Bad Request.
    """
    payload = {
        "email": "duplicate@evently.com",
        "password": "Password123!",
        "full_name": "First User",
    }
    # Register once
    res1 = await async_client.post(f"{settings.API_V1_STR}/auth/register", json=payload)
    assert res1.status_code == 201

    # Attempt to register again with same email
    res2 = await async_client.post(f"{settings.API_V1_STR}/auth/register", json=payload)
    assert res2.status_code == 400
    data = res2.json()
    assert data["error"]["code"] == "EMAIL_ALREADY_EXISTS"


@pytest.mark.asyncio
async def test_login_success(async_client: AsyncClient):
    """
    Test authenticating with valid credentials returns JWT tokens.
    """
    email = "login_test@evently.com"
    password = "CorrectPassword123!"

    # Register user
    await async_client.post(
        f"{settings.API_V1_STR}/auth/register",
        json={"email": email, "password": password, "full_name": "Login Tester"},
    )

    # Login
    response = await async_client.post(
        f"{settings.API_V1_STR}/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200
    data = response.json()

    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] == settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60


@pytest.mark.asyncio
async def test_login_invalid_password(async_client: AsyncClient):
    """
    Test that incorrect passwords return 401 Unauthorized.
    """
    email = "wrongpwd@evently.com"
    await async_client.post(
        f"{settings.API_V1_STR}/auth/register",
        json={"email": email, "password": "OriginalPassword123!", "full_name": "Tester"},
    )

    response = await async_client.post(
        f"{settings.API_V1_STR}/auth/login",
        json={"email": email, "password": "WrongPassword!"},
    )
    assert response.status_code == 401
    data = response.json()
    assert data["error"]["code"] == "INVALID_CREDENTIALS"


@pytest.mark.asyncio
async def test_login_nonexistent_user(async_client: AsyncClient):
    """
    Test that non-existent email accounts return 401 Unauthorized.
    """
    response = await async_client.post(
        f"{settings.API_V1_STR}/auth/login",
        json={"email": "nobody@evently.com", "password": "RandomPassword123!"},
    )
    assert response.status_code == 401
    data = response.json()
    assert data["error"]["code"] == "INVALID_CREDENTIALS"


@pytest.mark.asyncio
async def test_refresh_token_success(async_client: AsyncClient):
    """
    Test refreshing an access token using a valid refresh token.
    """
    email = "refreshtest@evently.com"
    password = "Password123!"
    await async_client.post(
        f"{settings.API_V1_STR}/auth/register",
        json={"email": email, "password": password, "full_name": "Refresh Tester"},
    )

    login_resp = await async_client.post(
        f"{settings.API_V1_STR}/auth/login",
        json={"email": email, "password": password},
    )
    refresh_token = login_resp.json()["refresh_token"]

    refresh_resp = await async_client.post(
        f"{settings.API_V1_STR}/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh_resp.status_code == 200
    data = refresh_resp.json()
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.asyncio
async def test_get_current_user_profile(async_client: AsyncClient):
    """
    Test inspecting current user profile with valid Bearer token.
    """
    email = "profile_test@evently.com"
    password = "Password123!"
    await async_client.post(
        f"{settings.API_V1_STR}/auth/register",
        json={"email": email, "password": password, "full_name": "Profile Tester"},
    )

    login_resp = await async_client.post(
        f"{settings.API_V1_STR}/auth/login",
        json={"email": email, "password": password},
    )
    token = login_resp.json()["access_token"]

    response = await async_client.get(
        f"{settings.API_V1_STR}/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == email
    assert data["full_name"] == "Profile Tester"


@pytest.mark.asyncio
async def test_get_current_user_unauthorized(async_client: AsyncClient):
    """
    Test inspecting profile without Bearer token returns 401 Unauthorized.
    """
    response = await async_client.get(f"{settings.API_V1_STR}/auth/me")
    assert response.status_code == 401
