"""
Evently Backend Application Entry Point
FastAPI application initialization with lifecycle hooks, middleware, and routing.
"""

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.database.session import AsyncSessionLocal, async_engine, check_db_connection
from app.services.booking_service import BookingService

# Configure structured logging
logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("evently")


async def _booking_expiration_worker():
    """
    Background worker loop that periodically sweeps and releases expired pending reservations.
    Runs at configured interval with graceful task cancellation.
    """
    logger.info(
        "Booking expiration background worker started (interval=%ds, hold_time=%dm).",
        settings.BOOKING_EXPIRATION_SWEEP_INTERVAL_SECONDS,
        settings.BOOKING_HOLD_MINUTES,
    )
    while True:
        try:
            await asyncio.sleep(settings.BOOKING_EXPIRATION_SWEEP_INTERVAL_SECONDS)
            async with AsyncSessionLocal() as session:
                service = BookingService(db=session)
                expired_count, released_seats = await service.expire_pending_bookings()
                if expired_count > 0:
                    logger.info(
                        "Auto-expired %d reservations, replenished %d seats.",
                        expired_count,
                        released_seats,
                    )
        except asyncio.CancelledError:
            logger.info("Booking expiration background worker stopped.")
            break
        except Exception as exc:
            logger.error("Error in booking expiration worker loop: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan manager.
    Handles startup checks, background workers, and graceful shutdown cleanup.
    """
    logger.info("Starting up %s v%s in %s mode...", settings.PROJECT_NAME, settings.VERSION, settings.ENVIRONMENT)
    # Verify database connectivity on startup
    db_check = await check_db_connection()
    if db_check.get("status") == "healthy":
        logger.info("PostgreSQL database connection established successfully.")
    else:
        logger.error("Failed to connect to PostgreSQL database on startup: %s", db_check.get("error"))

    expiration_task = None
    if settings.ENABLE_EXPIRATION_WORKER:
        expiration_task = asyncio.create_task(_booking_expiration_worker())

    yield

    if expiration_task and not expiration_task.done():
        expiration_task.cancel()
        try:
            await expiration_task
        except asyncio.CancelledError:
            pass

    logger.info("Shutting down %s... Disposing database connection pool.", settings.PROJECT_NAME)
    await async_engine.dispose()
    logger.info("Database connection pool disposed. Goodbye!")


def create_application() -> FastAPI:
    """
    Application factory creating and configuring the FastAPI instance.
    """
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        description=(
            "Evently is an event management and ticket booking platform designed "
            "for community workshops and creators with database-level overbooking prevention."
        ),
        openapi_url=f"{settings.API_V1_STR}/openapi.json",
        docs_url=f"{settings.API_V1_STR}/docs",
        redoc_url=f"{settings.API_V1_STR}/redoc",
        lifespan=lifespan,
    )

    # Configure CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Restrict in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register domain exception handlers
    register_exception_handlers(app)

    # Root informational endpoint
    @app.get("/", tags=["Root"])
    async def root():
        return {
            "message": "Welcome to the Evently API",
            "version": settings.VERSION,
            "docs": f"{settings.API_V1_STR}/docs",
            "health": f"{settings.API_V1_STR}/health",
        }

    # Register API routers
    app.include_router(api_router, prefix=settings.API_V1_STR)

    return app


app = create_application()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)
