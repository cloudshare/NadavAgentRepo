"""QA Intelligence Agent - FastAPI Application.

Main application with health check and webhook endpoints.
"""

import time
import logging
import hmac
import hashlib
from fastapi import FastAPI, Request, HTTPException
from contextlib import asynccontextmanager

from src.config import get_settings
from src.models import (
    TeamCityWebhookPayload,
    HealthResponse,
    WebhookResponse,
)
from src.queue import build_queue

# Load settings
settings = get_settings()

# Track start time for uptime calculation
_start_time = time.time()

# Logger
logger = logging.getLogger(__name__)

# Track HMAC warning state
_hmac_warning_logged = False


def setup_logging():
    """Configure logging format and level."""
    log_format = "%(asctime)s %(levelname)-8s %(name)s - %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    logging.basicConfig(
        level=getattr(logging, settings.logging.level),
        format=log_format,
        datefmt=date_format,
    )


def verify_hmac(body: bytes, signature: str, secret: str) -> bool:
    """Verify HMAC-SHA256 signature of webhook payload.

    Args:
        body: Raw request body bytes
        signature: Signature from X-TeamCity-Signature header
        secret: Webhook secret for HMAC computation

    Returns:
        True if signature is valid, False otherwise
    """
    expected_signature = hmac.new(
        secret.encode(),
        body,
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected_signature, signature)


def print_startup_banner():
    """Print startup banner with configuration details."""
    teamcity_url = settings.teamcity.url or "Not configured"
    branch_filters = ", ".join(settings.processing.branch_filters)

    # HMAC status
    hmac_status = "enabled" if settings.webhook.secret else "DISABLED (no secret)"

    # Dedup window
    dedup_window = settings.webhook.dedup_window

    banner = f"""
============================================
  {settings.service.name} v{settings.service.version}
  Port: {settings.service.port}
  TeamCity: {teamcity_url}
  Branch filters: {branch_filters}
  HMAC validation: {hmac_status}
  Dedup window: {dedup_window}s
============================================
"""
    logger.info(banner)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown events."""
    global _hmac_warning_logged

    # Startup
    print_startup_banner()

    # Start build queue worker
    await build_queue.start()

    # Check for missed builds on startup
    await build_queue.check_missed_builds()

    # Log HMAC validation status once
    if not settings.webhook.secret:
        logger.warning("Webhook HMAC validation disabled — no secret configured")
        _hmac_warning_logged = True

    yield

    # Shutdown
    await build_queue.stop()


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
    queue_status = build_queue.get_status()

    return HealthResponse(
        status="ok",
        uptime_seconds=uptime,
        last_processed_build=queue_status["last_processed"],
        queue_size=queue_status["queue_size"],
        processed_count=queue_status["processed_count"],
    )


@app.post("/webhook/teamcity", response_model=WebhookResponse)
async def webhook_teamcity(request: Request):
    """TeamCity webhook endpoint.

    Accepts TeamCity build webhook payloads and queues them for processing.
    Validates HMAC signature, filters by branch, deduplicates, and queues builds.

    Args:
        request: Raw request (for body access and HMAC validation)

    Returns:
        WebhookResponse with processing status (202, 200, or 401)

    Raises:
        HTTPException: If HMAC validation fails (401)
    """
    # Read raw body for HMAC validation
    body = await request.body()

    # HMAC validation if secret is configured
    if settings.webhook.secret:
        signature = request.headers.get("X-TeamCity-Signature")
        if not signature:
            logger.warning("Webhook rejected: missing X-TeamCity-Signature header")
            raise HTTPException(
                status_code=401,
                detail={"error": "Invalid webhook signature"}
            )

        if not verify_hmac(body, signature, settings.webhook.secret):
            logger.warning("Webhook rejected: invalid HMAC signature")
            raise HTTPException(
                status_code=401,
                detail={"error": "Invalid webhook signature"}
            )

    # Parse payload
    try:
        payload = TeamCityWebhookPayload.model_validate_json(body)
    except Exception as e:
        logger.error(f"Invalid webhook payload: {e}")
        raise HTTPException(
            status_code=422,
            detail={"error": "Invalid payload format"}
        )

    build = payload.build

    logger.info(
        f"Webhook received: build #{build.buildId} ({build.buildStatus}) "
        f"on branch {build.branchName or 'default'}"
    )

    # Submit to queue (handles filtering and deduplication)
    result = await build_queue.submit(build)

    # Return appropriate response based on result
    if result["status"] == "queued":
        return WebhookResponse(
            status="accepted",
            build_id=build.buildId,
            message="Build queued for processing"
        )
    elif result["status"] == "duplicate":
        return WebhookResponse(
            status="skipped",
            build_id=build.buildId,
            message="Build already processed"
        )
    elif result["status"] == "filtered":
        return WebhookResponse(
            status="skipped",
            build_id=build.buildId,
            message="Branch not in filter list"
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=settings.service.port,
        reload=True,
    )
