"""FastAPI application entrypoint for Contact Form Filler."""

import asyncio
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import mysql.connector

from app.api.routes import (
    analytics,
    campaigns,
    fields,
    health,
    notifications,
    settings as settings_routes,
    submissions,
    websites,
)
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.database.migrations import run_migrations

logger = setup_logging()
settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="2.0.0",
    description="Contact Form Filler — Automated Discovery, Mapping, and Campaign Execution API",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(mysql.connector.Error)
async def mysql_exception_handler(request: Request, exc: mysql.connector.Error):
    logger.error(f"Database error on {request.url.path}: {exc}")
    return JSONResponse(
        status_code=503,
        content={"detail": "Database is unavailable. Please ensure MySQL is running on port 3306."},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled error on {request.url.path}: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {str(exc)}"},
    )


@app.on_event("startup")
def on_startup() -> None:
    logger.info(f"Starting {settings.app_name} ({settings.app_env})")
    run_migrations()


app.include_router(health.router)
app.include_router(websites.router)
app.include_router(campaigns.router)
app.include_router(submissions.router)
app.include_router(analytics.router)
app.include_router(fields.router)
app.include_router(notifications.router)
app.include_router(settings_routes.router)
