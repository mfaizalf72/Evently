"""
Authentication Service Module
Handles user registration, credential verification, JWT token issuance, and token refresh.
"""

import uuid
import jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import (
    AuthenticationException,
    BusinessRuleViolationException,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.token import Token
from app.schemas.user import UserCreate, UserLogin, UserResponse


class AuthService:
    """
    Service managing identity, authentication, and JWT lifecycle.
    """
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repository = UserRepository(db=db)

    async def register_user(self, data: UserCreate) -> UserResponse:
        """
        Registers a new user with hashed credentials.
        """
        existing_user = await self.repository.get_by_email(data.email)
        if existing_user:
            raise BusinessRuleViolationException(
                message=f"An account with email '{data.email}' already exists.",
                code="EMAIL_ALREADY_EXISTS",
            )

        hashed = hash_password(data.password)

        user = User(
            email=data.email.lower().strip(),
            hashed_password=hashed,
            full_name=data.full_name.strip(),
            role=data.role.value,
            is_active=True,
        )

        created_user = await self.repository.create(user)
        await self.db.commit()
        return UserResponse.model_validate(created_user)

    async def authenticate_user(self, data: UserLogin) -> Token:
        """
        Authenticates user credentials and returns signed access and refresh tokens.
        """
        user = await self.repository.get_by_email(data.email)
        if not user or not verify_password(data.password, user.hashed_password):
            raise AuthenticationException(
                message="Incorrect email or password.",
                code="INVALID_CREDENTIALS",
            )

        if not user.is_active:
            raise AuthenticationException(
                message="User account is inactive. Please contact support.",
                code="USER_INACTIVE",
            )

        access_token = create_access_token(subject=user.id, role=user.role)
        refresh_token = create_refresh_token(subject=user.id)

        return Token(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    async def refresh_access_token(self, refresh_token_str: str) -> Token:
        """
        Validates a refresh token and issues a new access token.
        """
        try:
            payload = decode_token(refresh_token_str)
        except jwt.PyJWTError:
            raise AuthenticationException(
                message="Invalid or expired refresh token.",
                code="INVALID_REFRESH_TOKEN",
            )

        if payload.get("type") != "refresh":
            raise AuthenticationException(
                message="Token is not a valid refresh token.",
                code="INVALID_TOKEN_TYPE",
            )

        user_id_str = payload.get("sub")
        try:
            user_id = uuid.UUID(user_id_str)
        except (ValueError, TypeError):
            raise AuthenticationException(
                message="Invalid subject claim in token.",
                code="INVALID_TOKEN_SUBJECT",
            )

        user = await self.repository.get_by_id(user_id)
        if not user or not user.is_active:
            raise AuthenticationException(
                message="User is inactive or no longer exists.",
                code="USER_NOT_FOUND",
            )

        new_access_token = create_access_token(subject=user.id, role=user.role)
        new_refresh_token = create_refresh_token(subject=user.id)

        return Token(
            access_token=new_access_token,
            refresh_token=new_refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )
