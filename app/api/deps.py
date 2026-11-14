"""
FastAPI Authentication and Authorization Dependencies
Extracts and validates JWT bearer tokens, resolves current user, and enforces RBAC roles.
"""

from typing import List
import uuid
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
import jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AuthenticationException, AuthorizationException
from app.core.security import decode_token
from app.database.session import get_db
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserRole

# OAuth2 Bearer scheme for Swagger UI integration
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login",
    scheme_name="JWT",
)


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Decodes the Bearer token, validates claims, and retrieves the active user from PostgreSQL.
    """
    try:
        payload = decode_token(token)
    except jwt.ExpiredSignatureError:
        raise AuthenticationException(
            message="Token has expired. Please log in again.",
            code="TOKEN_EXPIRED",
        )
    except jwt.PyJWTError:
        raise AuthenticationException(
            message="Could not validate credentials.",
            code="INVALID_TOKEN",
        )

    if payload.get("type") != "access":
        raise AuthenticationException(
            message="Invalid token type.",
            code="INVALID_TOKEN_TYPE",
        )

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise AuthenticationException(
            message="Token payload is missing subject identifier.",
            code="INVALID_TOKEN_PAYLOAD",
        )

    try:
        user_id = uuid.UUID(user_id_str)
    except (ValueError, TypeError):
        raise AuthenticationException(
            message="Invalid user identifier format.",
            code="INVALID_USER_ID",
        )

    user_repo = UserRepository(db=db)
    user = await user_repo.get_by_id(user_id)
    if not user:
        raise AuthenticationException(
            message="User associated with token no longer exists.",
            code="USER_NOT_FOUND",
        )

    if not user.is_active:
        raise AuthenticationException(
            message="User account is inactive.",
            code="USER_INACTIVE",
        )

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Alias dependency for an active authenticated user."""
    return current_user


def require_role(allowed_roles: List[UserRole]):
    """
    Dependency factory that checks whether the authenticated user possesses one of the allowed roles.
    """
    allowed_values = [r.value for r in allowed_roles]

    async def role_checker(
        current_user: User = Depends(get_current_active_user),
    ) -> User:
        if current_user.role not in allowed_values:
            raise AuthorizationException(
                message=f"Access forbidden: Action requires one of {allowed_values} roles.",
                code="INSUFFICIENT_PERMISSIONS",
                details={"user_role": current_user.role, "required_roles": allowed_values},
            )
        return current_user

    return role_checker


# Role-specific dependency shortcuts
get_current_organizer = require_role([UserRole.ORGANIZER, UserRole.ADMIN])
get_current_admin = require_role([UserRole.ADMIN])
