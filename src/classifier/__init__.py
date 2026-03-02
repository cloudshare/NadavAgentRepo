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

__all__ = [
    "ClassificationResult",
    "ClassificationCategory",
    "run_rule_engine",
    "RULE_CONFIDENCE_THRESHOLD",
    "LLM_UNCERTAIN_FLOOR",
    "SIGNAL_WEIGHTS",
]
