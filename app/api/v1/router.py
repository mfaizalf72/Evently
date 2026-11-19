"""
API v1 Router Aggregator
Combines all v1 endpoint routers into a unified APIRouter.
"""

from fastapi import APIRouter
from app.api.v1.endpoints import auth, bookings, events, health, ticket_tiers

api_router = APIRouter()

api_router.include_router(health.router, tags=["Health"])
api_router.include_router(auth.router)
api_router.include_router(events.router)
api_router.include_router(ticket_tiers.router)
api_router.include_router(bookings.router)
