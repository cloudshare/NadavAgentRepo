"""Classification engine package.

Public API re-exports — all consumers should import from src.classifier
rather than from sub-modules directly.
"""

from .models import ClassificationResult, ClassificationCategory
from .rule_engine import (
    run_rule_engine,
    RULE_CONFIDENCE_THRESHOLD,
    LLM_UNCERTAIN_FLOOR,
    SIGNAL_WEIGHTS,
)
from .llm_client import classify_test, extract_log_context, classify_with_llm
from .cost_estimator import estimate_run_cost, print_cost_summary

__all__ = [
    "ClassificationResult",
    "ClassificationCategory",
    "run_rule_engine",
    "RULE_CONFIDENCE_THRESHOLD",
    "LLM_UNCERTAIN_FLOOR",
    "SIGNAL_WEIGHTS",
    "classify_test",
    "extract_log_context",
    "classify_with_llm",
    "estimate_run_cost",
    "print_cost_summary",
]
