"""Async SQLite persistence helpers for analysis runs, test results, and flakiness.

Uses aiosqlite for non-blocking I/O. All public functions are async and accept
an optional db_path for test isolation.

IMPORTANT: No GENERATED ALWAYS AS computed columns — fails on Python 3.9's
bundled SQLite. Compute failure_rate in SELECT queries instead.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import aiosqlite

DB_PATH = Path("analysis.db")

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS analysis_runs (
    run_id              TEXT PRIMARY KEY,
    build_id            INTEGER NOT NULL,
    created_at          TEXT NOT NULL,
    total_tests         INTEGER DEFAULT 0,
    failed_tests        INTEGER DEFAULT 0,
    total_input_tokens  INTEGER DEFAULT 0,
    total_output_tokens INTEGER DEFAULT 0,
    estimated_cost_usd  REAL DEFAULT 0.0,
    report_json         TEXT
);

CREATE TABLE IF NOT EXISTS test_results (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          TEXT NOT NULL,
    test_title      TEXT NOT NULL,
    full_title      TEXT NOT NULL,
    status          TEXT NOT NULL,
    category        TEXT,
    probability     REAL DEFAULT 0.0,
    retry_count     INTEGER DEFAULT 0,
    passed_on_retry INTEGER DEFAULT 0,
    FOREIGN KEY (run_id) REFERENCES analysis_runs(run_id)
);

CREATE TABLE IF NOT EXISTS flakiness_index (
    test_full_title TEXT PRIMARY KEY,
    total_runs      INTEGER DEFAULT 0,
    failure_count   INTEGER DEFAULT 0,
    flaky_count     INTEGER DEFAULT 0,
    last_updated    TEXT NOT NULL
);
"""


async def init_db(db_path: Path = DB_PATH) -> None:
    """Create all tables if they do not exist.

    Safe to call on every startup — idempotent due to IF NOT EXISTS.
    """
    async with aiosqlite.connect(db_path) as db:
        await db.executescript(_SCHEMA_SQL)
        await db.commit()


async def store_result(
    run_id: str,
    result: object,
    passed_on_retry: bool = False,
    db_path: Path = DB_PATH,
) -> None:
    """Persist a ClassificationResult to test_results table.

    Args:
        run_id: The analysis run identifier.
        result: A ClassificationResult instance.
        passed_on_retry: True if the test passed on a later retry.
        db_path: SQLite database path (use /tmp/ path in tests).
    """
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            INSERT INTO test_results
                (run_id, test_title, full_title, status, category, probability,
                 retry_count, passed_on_retry)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                getattr(result, "test_title", ""),
                getattr(result, "full_title", ""),
                "unexpected",
                getattr(result, "category", None),
                getattr(result, "probability", 0.0),
                getattr(result, "retry_count", 0),
                1 if passed_on_retry else 0,
            ),
        )
        await db.commit()


async def upsert_flakiness(
    test_full_title: str,
    failed: bool,
    flaky: bool,
    db_path: Path = DB_PATH,
) -> None:
    """Increment flakiness counters for a test.

    Uses read-then-INSERT OR REPLACE to avoid resetting AUTOINCREMENT primary key.
    """
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(db_path) as db:
        async with db.execute(
            "SELECT total_runs, failure_count, flaky_count FROM flakiness_index WHERE test_full_title = ?",
            (test_full_title,),
        ) as cur:
            row = await cur.fetchone()

        if row is None:
            total_runs, failure_count, flaky_count = 0, 0, 0
        else:
            total_runs, failure_count, flaky_count = row

        total_runs += 1
        if failed:
            failure_count += 1
        if flaky:
            flaky_count += 1

        await db.execute(
            """
            INSERT OR REPLACE INTO flakiness_index
                (test_full_title, total_runs, failure_count, flaky_count, last_updated)
            VALUES (?, ?, ?, ?, ?)
            """,
            (test_full_title, total_runs, failure_count, flaky_count, now),
        )
        await db.commit()


async def store_run_cost(
    run_id: str,
    build_id: int,
    total_input_tokens: int,
    total_output_tokens: int,
    estimated_cost_usd: float,
    total_tests: int,
    failed_tests: int,
    report_json: str = "",
    db_path: Path = DB_PATH,
) -> None:
    """Persist run-level token usage and cost to analysis_runs table."""
    created_at = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            INSERT OR REPLACE INTO analysis_runs
                (run_id, build_id, created_at, total_tests, failed_tests,
                 total_input_tokens, total_output_tokens, estimated_cost_usd, report_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                build_id,
                created_at,
                total_tests,
                failed_tests,
                total_input_tokens,
                total_output_tokens,
                estimated_cost_usd,
                report_json,
            ),
        )
        await db.commit()


async def get_run_cost(
    run_id: str,
    db_path: Path = DB_PATH,
) -> Optional[dict]:
    """Retrieve run-level metadata by run_id.

    Returns:
        dict with all analysis_runs columns, or None if run_id not found.
    """
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM analysis_runs WHERE run_id = ?", (run_id,)
        ) as cur:
            row = await cur.fetchone()
    if row is None:
        return None
    return dict(row)
