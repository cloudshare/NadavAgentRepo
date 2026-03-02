"""Analytics generators for flakiness, endpoint heatmaps, and failure ratios.

All functions are pure Python (no pandas). Async functions use aiosqlite.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

import aiosqlite

from .db import DB_PATH

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MIN_RUNS_FOR_FLAKINESS = 3  # filter noise; see STATE.md calibration flag

# Category bucket mappings for failure ratio analysis
INFRA_CATEGORIES = frozenset({"infrastructure_instability", "cloud_provisioning_delay"})
TEST_DESIGN_CATEGORIES = frozenset({"test_design_issue", "race_condition", "non_deterministic_ai"})
APP_CATEGORIES = frozenset({"product_regression", "data_pollution", "auth_session_issue"})


# ---------------------------------------------------------------------------
# Flakiness index
# ---------------------------------------------------------------------------


async def get_flakiness_index(
    db_path: Path = DB_PATH,
    min_runs: int = MIN_RUNS_FOR_FLAKINESS,
) -> list[dict]:
    """Return tests with failure_rate computed in SQL, sorted descending.

    Filters to tests with total_runs >= min_runs to avoid noisy single-run results.
    failure_rate is computed as CAST(failure_count AS REAL) / total_runs.

    Returns:
        List of dicts with keys: test_full_title, total_runs, failure_count,
        flaky_count, last_updated, failure_rate.
    """
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT
                test_full_title,
                total_runs,
                failure_count,
                flaky_count,
                last_updated,
                CAST(failure_count AS REAL) / total_runs AS failure_rate
            FROM flakiness_index
            WHERE total_runs >= ?
            ORDER BY failure_rate DESC
            """,
            (min_runs,),
        ) as cur:
            rows = await cur.fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Endpoint reliability heatmap
# ---------------------------------------------------------------------------


def compute_endpoint_heatmap(correlated_tests: list) -> list[dict]:
    """Build endpoint × failure_rate heatmap from a list of CorrelatedTests.

    Pure Python — no SQLite, no pandas. Each CorrelatedTest contributes to
    the failure count for each of its matched KG endpoints.

    Args:
        correlated_tests: list[CorrelatedTest] — may have endpoint_matches list.

    Returns:
        List of dicts sorted by failure_rate descending:
        [{"endpoint": kg_id, "total_failing_tests": N, "failure_rate": 0.0-1.0}]
        failure_rate here represents relative frequency (count / total endpoints seen).
    """
    endpoint_totals: defaultdict[str, int] = defaultdict(int)
    endpoint_failures: defaultdict[str, int] = defaultdict(int)

    for ct in correlated_tests:
        endpoint_matches = getattr(ct, "endpoint_matches", [])
        for ep in endpoint_matches:
            kg_id = getattr(ep, "kg_id", None)
            if kg_id:
                endpoint_totals[kg_id] += 1
                endpoint_failures[kg_id] += 1  # every entry is a failing test

    total_all = sum(endpoint_totals.values()) or 1  # avoid ZeroDivisionError

    result = [
        {
            "endpoint": kg_id,
            "total_failing_tests": endpoint_totals[kg_id],
            "failure_rate": round(endpoint_failures[kg_id] / total_all, 4),
        }
        for kg_id in endpoint_totals
    ]
    result.sort(key=lambda x: x["failure_rate"], reverse=True)
    return result


# ---------------------------------------------------------------------------
# Failure ratio analysis
# ---------------------------------------------------------------------------


def compute_failure_ratios(classifications: list[dict]) -> dict:
    """Bucket failing tests into infra / app / test_design / uncertain ratios.

    Args:
        classifications: list of dicts, each with a "category" key (string).

    Returns:
        {
            "counts": {"infra": N, "app": N, "test_design": N, "uncertain": N},
            "ratios": {"infra": 0.0-1.0, ...},
            "total": N,
        }
    """
    counts: dict[str, int] = {"infra": 0, "app": 0, "test_design": 0, "uncertain": 0}

    for item in classifications:
        category = item.get("category", "uncertain")
        if category in INFRA_CATEGORIES:
            counts["infra"] += 1
        elif category in APP_CATEGORIES:
            counts["app"] += 1
        elif category in TEST_DESIGN_CATEGORIES:
            counts["test_design"] += 1
        else:
            counts["uncertain"] += 1

    total = sum(counts.values())
    if total == 0:
        ratios = {k: 0.0 for k in counts}
    else:
        ratios = {k: round(v / total, 4) for k, v in counts.items()}

    return {"counts": counts, "ratios": ratios, "total": total}
