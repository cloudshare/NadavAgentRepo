"""QA Intelligence Agent - FastAPI Application.

Main application with health check and webhook endpoints.
"""

import time
import logging
from fastapi import FastAPI, Request
from contextlib import asynccontextmanager

from src.config import get_settings
from src.models import (
    TeamCityWebhookPayload,
    HealthResponse,
    WebhookResponse,
)

# Load settings
settings = get_settings()

# Track start time for uptime calculation
_start_time = time.time()

# Logger
logger = logging.getLogger(__name__)


def setup_logging():
    """Configure logging format and level."""
    log_format = "%(asctime)s %(levelname)-8s %(name)s - %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    logging.basicConfig(
        level=getattr(logging, settings.logging.level),
        format=log_format,
        datefmt=date_format,
    )


def print_startup_banner():
    """Print startup banner with configuration details."""
    teamcity_url = settings.teamcity.url or "Not configured"
    branch_filters = ", ".join(settings.processing.branch_filters)

    banner = f"""
============================================
  {settings.service.name} v{settings.service.version}
  Port: {settings.service.port}
  TeamCity: {teamcity_url}
  Branch filters: {branch_filters}
============================================
"""
    logger.info(banner)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown events."""
    # Startup
    print_startup_banner()
    yield
    # Shutdown (if needed in future)


# Setup logging at import time
setup_logging()

# Create FastAPI application
app = FastAPI(
    title=settings.service.name,
    version=settings.service.version,
    lifespan=lifespan,
)


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint.

    Returns service status, uptime, and processing statistics.
    """
    uptime = time.time() - _start_time

    return HealthResponse(
        status="ok",
        uptime_seconds=uptime,
        last_processed_build=None,  # Will be populated in Plan 02
        queue_size=0,  # Will be populated in Plan 02
        processed_count=0,  # Will be populated in Plan 02
    )


@app.post("/webhook/teamcity", response_model=WebhookResponse, status_code=202)
async def webhook_teamcity(request: Request, payload: TeamCityWebhookPayload):
    """TeamCity webhook endpoint.

    Accepts TeamCity build webhook payloads and queues them for processing.
    Returns 202 Accepted immediately without blocking.

    Args:
        request: Raw request (for HMAC validation in Plan 02)
        payload: Parsed TeamCity webhook payload

    Returns:
        WebhookResponse with acceptance status
    """
    build = payload.build

    logger.info(
        f"Webhook received: build #{build.buildId} ({build.buildStatus}) "
        f"on branch {build.branchName or 'default'}"
    )

    # For now, just accept and log. Plan 02 will add:
    # - HMAC validation
    # - Branch filtering
    # - Deduplication
    # - Queue submission

    return WebhookResponse(
        status="accepted",
        build_id=build.buildId,
        message="Build queued for processing",
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=settings.service.port,
        reload=True,
    )
