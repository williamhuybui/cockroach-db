"""Health-check endpoint for the FastAPI application."""

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from database import get_database_connection


router = APIRouter(
    tags=["health"],
)

logger = logging.getLogger(__name__)


@router.get("/health")
async def health():
    """
    Confirm that the application can query CockroachDB.
    """

    try:
        async with get_database_connection() as connection:
            await connection.execute("SELECT 1")

    except Exception:
        logger.exception(
            "CockroachDB health check failed."
        )

        return JSONResponse(
            status_code=503,
            content={
                "application": "degraded",
                "database": "disconnected",
            },
        )

    return JSONResponse(
        status_code=200,
        content={
            "application": "healthy",
            "database": "connected",
        },
    )