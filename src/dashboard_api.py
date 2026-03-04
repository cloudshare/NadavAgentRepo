"""Dashboard API endpoints — submitted via React frontend."""
import datetime
import json
import uuid
import logging
import aiosqlite
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from src.classifier import DB_PATH, get_run_cost
from src.knowledge_graph import load_kg
from src.pipeline import run_analysis_pipeline

logger = logging.getLogger(__name__)

dashboard_router = APIRouter(prefix="/api", tags=["dashboard"])

# In-memory status: run_id -> "running" | "completed" | "failed"
# Survives within process; SQLite is the durable fallback on restart.
_run_status: dict[str, str] = {}


class RunRequest(BaseModel):
    test_folder: str
    log_folder: str


@dashboard_router.post("/runs", status_code=202)
async def start_run(req: RunRequest, background_tasks: BackgroundTasks):
    """Start a new analysis run. Returns run_id immediately."""
    run_id = str(uuid.uuid4())
    _run_status[run_id] = "running"
    background_tasks.add_task(
        run_analysis_pipeline,
        run_id,
        req.test_folder,
        req.log_folder,
        _run_status,
    )
    logger.info(f"Started run {run_id} for test_folder={req.test_folder}")
    return {"run_id": run_id, "status": "running"}


@dashboard_router.get("/runs")
async def list_runs():
    """List all completed runs from SQLite, newest first. Used for run history table."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT run_id, created_at, total_tests, failed_tests, estimated_cost_usd
            FROM analysis_runs
            ORDER BY created_at DESC
            LIMIT 50
            """
        ) as cur:
            rows = await cur.fetchall()
    return [dict(r) for r in rows]


@dashboard_router.get("/runs/{run_id}")
async def get_run(run_id: str):
    """Get run status. Checks in-memory first (fast path), falls back to SQLite."""
    # Fast path: in-memory for running state
    status = _run_status.get(run_id)
    if status == "running":
        return {"run_id": run_id, "status": "running"}

    # Fallback: SQLite for completed runs (survives server restart)
    row = await get_run_cost(run_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Run not found")

    report = {}
    if row.get("report_json"):
        report = json.loads(row["report_json"])

    return {
        "run_id": run_id,
        "status": "completed",
        "created_at": row["created_at"],
        "total_tests": row["total_tests"],
        "failed_tests": row["failed_tests"],
        "estimated_cost_usd": row["estimated_cost_usd"],
        "report": report,
    }


@dashboard_router.get("/kg-staleness")
async def kg_staleness():
    """Return KG last_updated date and days since last crawl (KG-03)."""
    kg = load_kg()
    last_updated_str = kg["metadata"]["last_updated"]  # "YYYY-MM-DD"
    last_updated = datetime.date.fromisoformat(last_updated_str)
    days_old = (datetime.date.today() - last_updated).days
    return {"last_updated": last_updated_str, "days_old": days_old}
