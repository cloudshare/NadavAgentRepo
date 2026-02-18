"""Pydantic models for QA Intelligence Agent.

Defines data models for TeamCity webhooks, health responses, and webhook responses.
"""

from typing import Optional, Dict, Any
from pydantic import BaseModel, ConfigDict, Field


class TeamCityBuild(BaseModel):
    """TeamCity build information from webhook payload."""
    buildId: int
    buildTypeId: str
    buildName: str
    buildStatus: str  # SUCCESS, FAILURE, etc.
    branchName: str = ""
    buildNumber: str
    triggeredBy: Optional[str] = None
    buildResult: Optional[str] = None
    buildStatusText: Optional[str] = None

    model_config = ConfigDict(extra="allow")


class TeamCityWebhookPayload(BaseModel):
    """TeamCity webhook payload wrapper."""
    build: TeamCityBuild

    model_config = ConfigDict(extra="allow")


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    uptime_seconds: float
    last_processed_build: Optional[Dict[str, Any]] = None
    queue_size: int
    processed_count: int


class WebhookResponse(BaseModel):
    """Webhook processing response."""
    status: str  # "accepted" or "skipped"
    build_id: int
    message: str
