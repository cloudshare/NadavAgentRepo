"""Classification engine package.

Public API re-exports — all consumers should import from src.classifier
rather than from sub-modules directly.
"""

from .models import ClassificationResult, ClassificationCategory
from .rule_engine import (
    run_rule_engine,
    _matched_signal_names,
    RULE_CONFIDENCE_THRESHOLD,
    LLM_UNCERTAIN_FLOOR,
    SIGNAL_WEIGHTS,
)
from .llm_client import classify_test, extract_log_context, classify_with_llm
from .cost_estimator import estimate_run_cost, print_cost_summary
from .recommendations import DOMAIN_FIX_RECOMMENDATIONS, generate_rule_summary
from .db import init_db, store_result, upsert_flakiness, store_run_cost, get_run_cost, DB_PATH
from .analytics import (
    get_flakiness_index,
    compute_endpoint_heatmap,
    compute_failure_ratios,
    MIN_RUNS_FOR_FLAKINESS,
)
from .report import generate_report, RunTokenAccumulator

__all__ = [
    "ClassificationResult",
    "ClassificationCategory",
    "run_rule_engine",
    "_matched_signal_names",
    "RULE_CONFIDENCE_THRESHOLD",
    "LLM_UNCERTAIN_FLOOR",
    "SIGNAL_WEIGHTS",
    "classify_test",
    "extract_log_context",
    "classify_with_llm",
    "estimate_run_cost",
    "print_cost_summary",
    "DOMAIN_FIX_RECOMMENDATIONS",
    "generate_rule_summary",
    "init_db",
    "store_result",
    "upsert_flakiness",
    "store_run_cost",
    "get_run_cost",
    "DB_PATH",
    "get_flakiness_index",
    "compute_endpoint_heatmap",
    "compute_failure_ratios",
    "MIN_RUNS_FOR_FLAKINESS",
    "generate_report",
    "RunTokenAccumulator",
]
