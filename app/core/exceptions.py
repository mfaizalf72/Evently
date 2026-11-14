"""
Evently Custom Domain Exceptions and Error Handlers
Standardized domain exceptions mapped to clean HTTP responses.
"""

from typing import Any, Optional
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse


class EventlyException(Exception):
    """Base domain exception for Evently application."""
    def __init__(self, message: str, code: str = "INTERNAL_SERVER_ERROR", details: Optional[Any] = None):
        self.message = message
        self.code = code
        self.details = details
        super().__init__(message)


class EntityNotFoundException(EventlyException):
    """Raised when a requested resource does not exist."""
    def __init__(self, entity_name: str, entity_id: Any):
        super().__init__(
            message=f"{entity_name} with identifier '{entity_id}' was not found.",
            code=f"{entity_name.upper()}_NOT_FOUND",
            details={"entity": entity_name, "id": str(entity_id)},
        )


class BusinessRuleViolationException(EventlyException):
    """Raised when a business rule or invariant is violated."""
    def __init__(self, message: str, code: str = "BUSINESS_RULE_VIOLATION", details: Optional[Any] = None):
        super().__init__(message=message, code=code, details=details)


class AuthenticationException(EventlyException):
    """Raised when authentication fails or credentials are invalid."""
    def __init__(self, message: str = "Invalid credentials or token expired.", code: str = "AUTHENTICATION_FAILED", details: Optional[Any] = None):
        super().__init__(message=message, code=code, details=details)


class AuthorizationException(EventlyException):
    """Raised when user lacks required permissions or role."""
    def __init__(self, message: str = "You do not have permission to perform this action.", code: str = "FORBIDDEN", details: Optional[Any] = None):
        super().__init__(message=message, code=code, details=details)


def register_exception_handlers(app: FastAPI) -> None:
    """
    Registers custom exception handlers on the FastAPI application instance.
    """
    @app.exception_handler(EntityNotFoundException)
    async def entity_not_found_handler(request: Request, exc: EntityNotFoundException):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                }
            },
        )

    @app.exception_handler(BusinessRuleViolationException)
    async def business_rule_violation_handler(request: Request, exc: BusinessRuleViolationException):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                }
            },
        )

    @app.exception_handler(AuthenticationException)
    async def authentication_exception_handler(request: Request, exc: AuthenticationException):
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            headers={"WWW-Authenticate": "Bearer"},
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                }
            },
        )

    @app.exception_handler(AuthorizationException)
    async def authorization_exception_handler(request: Request, exc: AuthorizationException):
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                }
            },
        )

    @app.exception_handler(EventlyException)
    async def evently_exception_handler(request: Request, exc: EventlyException):
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                }
            },
        )
