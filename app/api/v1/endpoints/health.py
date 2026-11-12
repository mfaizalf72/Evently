"""
Health Check Endpoint
Provides real-time system and database health diagnostics.
"""

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.database.session import check_db_connection, get_db
from app.schemas.health import HealthResponse

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="System and Database Health Check",
    description="Inspects the backend service status and verifies PostgreSQL database connectivity.",
)
async def get_health(
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> HealthResponse:
    db_status = await check_db_connection(session=db)

    is_healthy = db_status.get("status") == "healthy"
    if not is_healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return HealthResponse(
        status="ok" if is_healthy else "degraded",
        version=settings.VERSION,
        environment=settings.ENVIRONMENT,
        database=db_status,
    )
