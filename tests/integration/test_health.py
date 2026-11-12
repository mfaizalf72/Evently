"""
Integration Tests for Health Check and Core System Endpoints
"""

import pytest
from httpx import AsyncClient
from app.core.config import settings


@pytest.mark.asyncio
async def test_root_endpoint(async_client: AsyncClient):
    """
    Test that the root endpoint returns a 200 status code and helpful application metadata.
    """
    response = await async_client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert data["version"] == settings.VERSION
    assert data["docs"] == f"{settings.API_V1_STR}/docs"
    assert data["health"] == f"{settings.API_V1_STR}/health"


@pytest.mark.asyncio
async def test_health_check_endpoint(async_client: AsyncClient):
    """
    Test that the /api/v1/health endpoint connects to PostgreSQL and reports healthy status.
    """
    response = await async_client.get(f"{settings.API_V1_STR}/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["version"] == settings.VERSION
    assert data["environment"] == settings.ENVIRONMENT
    assert "timestamp" in data
    assert data["database"]["status"] == "healthy"
    assert data["database"]["database"] == "connected"


@pytest.mark.asyncio
async def test_openapi_docs_endpoint(async_client: AsyncClient):
    """
    Test that the OpenAPI JSON specification is generated properly by FastAPI.
    """
    response = await async_client.get(f"{settings.API_V1_STR}/openapi.json")
    assert response.status_code == 200
    data = response.json()
    assert data["info"]["title"] == settings.PROJECT_NAME
    assert data["info"]["version"] == settings.VERSION
    assert f"{settings.API_V1_STR}/health" in data["paths"]
