"""
API v1 Router Aggregator
Combines all v1 endpoint routers into a unified APIRouter.
"""

from fastapi import APIRouter
from app.api.v1.endpoints import health

api_router = APIRouter()

api_router.include_router(health.router, tags=["Health"])
