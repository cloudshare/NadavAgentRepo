"""Weighted signal accumulator rule engine for test failure classification.

Deterministic-first: given CorrelatedTest + ParsedTest + optional ParsedSpecAnalysis,
this module scores each of 8 failure categories based on named signal predicates and
returns a (category, confidence) pair. If confidence is below RULE_CONFIDENCE_THRESHOLD,
the caller should escalate to LLM classification.

All thresholds are named constants — do not hard-code 0.8 or 0.6 in rule logic.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Callable, Optional

from src.knowledge_graph.models import CorrelatedTest
from src.parsers.models import ParsedTest, ParsedSpecAnalysis

# ---------------------------------------------------------------------------
# Tuneable constants — calibrate against real log samples per STATE.md flag
# ---------------------------------------------------------------------------

# Rule engine must reach this normalised confidence to skip LLM escalation.
RULE_CONFIDENCE_THRESHOLD: float = 0.8

# LLM result below this floor means the model is uncertain — force "uncertain" category.
LLM_UNCERTAIN_FLOOR: float = 0.6

# Named weights for every signal — one dict key per signal name for traceability.
# Adjust values here to calibrate without touching predicate logic.
#
# Weight design principle: the primary (first) signal in each category is weighted
# so that when it fires alone, the normalised score exceeds RULE_CONFIDENCE_THRESHOLD
# (0.8). Secondary signals are supporting evidence with smaller weights. This ensures
# one strong signal is sufficient for classification while preventing many weak signals
# from beating a single strong one.
#
# With primary=0.9 and secondary=0.1, max_possible=1.0, primary alone → 0.9/1.0 = 0.9.
# With both signals firing → 1.0/1.0 = 1.0 (capped). This is the calibrated baseline.
SIGNAL_WEIGHTS: dict[str, float] = {
    # infrastructure_instability — KG-backed strong signal: 0.9 primary, 0.1 secondary.
    # max_possible = 1.0; single primary signal → 0.9 ≥ 0.8 threshold (confident).
    "infra_pattern_match": 0.9,
    "multi_infra_layer": 0.1,
    # auth_session_issue — KG-backed strong signal: same calibration.
    "auth_pattern_match": 0.9,
    "auth_keyword": 0.1,
    # cloud_provisioning_delay — async flow is a direct KG attribute (strong).
    "async_flow": 0.9,
    "async_with_timeout": 0.1,
    # test_design_issue — fragile locator from spec analysis is a direct observation (strong).
    "fragile_locator": 0.9,
    "hard_coded_wait": 0.1,
    # race_condition — passed_on_retry is a direct observation (strong).
    "passed_on_retry": 0.9,
    "timing_keyword": 0.1,
    # data_pollution — data keyword in error text is direct evidence (strong).
    "data_keyword": 0.9,
    "data_pattern_match": 0.1,
    # product_regression — catch-all signals; intentionally lower weights so that
    # absence-of-other-signals alone does NOT hit 0.8, requiring LLM escalation.
    # max_possible = 0.6 + 0.65 = 1.25; single signal: 0.6/1.25 = 0.48 < 0.8 (escalates).
    # Both signals together: 1.25/1.25 = 1.0 (confident classification).
    "no_infra_no_design": 0.6,
    "assertion_failure": 0.65,
    # non_deterministic_ai — keyword in error text is strong direct evidence.
    "ai_keyword": 0.9,
    "ai_pattern_match": 0.1,
}


# ---------------------------------------------------------------------------
# Signal definition
# ---------------------------------------------------------------------------


@dataclass
class Signal:
    """A single named classification signal with its category, weight, and predicate.

    predicate(ct, pt, sa) -> bool:
      ct: CorrelatedTest — contains infra/auth/async flags from Phase 3
      pt: ParsedTest — contains error text, retry info, status
      sa: ParsedSpecAnalysis | None — spec static analysis; MUST check sa is not None
    """

    name: str
    category: str
    weight: float
    predicate: Callable[
        [CorrelatedTest, ParsedTest, Optional[ParsedSpecAnalysis]], bool
    ]


# ---------------------------------------------------------------------------
# Signal definitions — at least 2 per category, all predicates guard sa is None
# ---------------------------------------------------------------------------

SIGNALS: list[Signal] = [
    # --- infrastructure_instability ---
    Signal(
        name="infra_pattern_match",
        category="infrastructure_instability",
        weight=SIGNAL_WEIGHTS["infra_pattern_match"],
        predicate=lambda ct, pt, sa: ct.has_infra_signal and not ct.has_auth_signal,
    ),
    Signal(
        name="multi_infra_layer",
        category="infrastructure_instability",
        weight=SIGNAL_WEIGHTS["multi_infra_layer"],
        predicate=lambda ct, pt, sa: len(ct.primary_infra_layers) >= 2,
    ),
    # --- auth_session_issue ---
    Signal(
        name="auth_pattern_match",
        category="auth_session_issue",
        weight=SIGNAL_WEIGHTS["auth_pattern_match"],
        predicate=lambda ct, pt, sa: ct.has_auth_signal,
    ),
    Signal(
        name="auth_keyword",
        category="auth_session_issue",
        weight=SIGNAL_WEIGHTS["auth_keyword"],
        predicate=lambda ct, pt, sa: (
            "401" in (pt.first_error_message or "")
            or "unauthorized" in (pt.first_error_message or "").lower()
        ),
    ),
    # --- cloud_provisioning_delay ---
    Signal(
        name="async_flow",
        category="cloud_provisioning_delay",
        weight=SIGNAL_WEIGHTS["async_flow"],
        predicate=lambda ct, pt, sa: ct.has_async_signal,
    ),
    Signal(
        name="async_with_timeout",
        category="cloud_provisioning_delay",
        weight=SIGNAL_WEIGHTS["async_with_timeout"],
        predicate=lambda ct, pt, sa: (
            ct.exercises_async_flow
            and "timeout" in (pt.first_error_message or "").lower()
        ),
    ),
    # --- test_design_issue ---
    Signal(
        name="fragile_locator",
        category="test_design_issue",
        weight=SIGNAL_WEIGHTS["fragile_locator"],
        predicate=lambda ct, pt, sa: (
            sa is not None and len(sa.fragile_locators) > 0
        ),
    ),
    Signal(
        name="hard_coded_wait",
        category="test_design_issue",
        weight=SIGNAL_WEIGHTS["hard_coded_wait"],
        predicate=lambda ct, pt, sa: (
            sa is not None and len(sa.hard_coded_wait_ms) > 0
        ),
    ),
    # --- race_condition ---
    Signal(
        name="passed_on_retry",
        category="race_condition",
        weight=SIGNAL_WEIGHTS["passed_on_retry"],
        predicate=lambda ct, pt, sa: (
            pt.retry_count > 0 and pt.status == "flaky"
        ),
    ),
    Signal(
        name="timing_keyword",
        category="race_condition",
        weight=SIGNAL_WEIGHTS["timing_keyword"],
        predicate=lambda ct, pt, sa: (
            "race" in (pt.first_error_message or "").lower()
            or "concurrent" in (pt.first_error_message or "").lower()
        ),
    ),
    # --- data_pollution ---
    Signal(
        name="data_keyword",
        category="data_pollution",
        weight=SIGNAL_WEIGHTS["data_keyword"],
        predicate=lambda ct, pt, sa: any(
            kw in (pt.first_error_message or "").lower()
            for kw in ["duplicate", "already exists", "constraint", "unique violation"]
        ),
    ),
    Signal(
        name="data_pattern_match",
        category="data_pollution",
        weight=SIGNAL_WEIGHTS["data_pattern_match"],
        predicate=lambda ct, pt, sa: any(
            fp.category == "data_pollution" for fp in ct.failure_pattern_matches
        ),
    ),
    # --- product_regression ---
    Signal(
        name="no_infra_no_design",
        category="product_regression",
        weight=SIGNAL_WEIGHTS["no_infra_no_design"],
        predicate=lambda ct, pt, sa: (
            not ct.has_infra_signal
            and not ct.has_auth_signal
            and (
                sa is None
                or (
                    len(sa.fragile_locators) == 0
                    and len(sa.hard_coded_wait_ms) == 0
                )
            )
            and pt.retry_count == 0
        ),
    ),
    Signal(
        name="assertion_failure",
        category="product_regression",
        weight=SIGNAL_WEIGHTS["assertion_failure"],
        predicate=lambda ct, pt, sa: (
            "AssertionError" in (pt.first_error_message or "")
            or "expect(" in (pt.first_error_stack or "")
        ),
    ),
    # --- non_deterministic_ai ---
    Signal(
        name="ai_keyword",
        category="non_deterministic_ai",
        weight=SIGNAL_WEIGHTS["ai_keyword"],
        predicate=lambda ct, pt, sa: any(
            kw in (pt.first_error_message or "").lower()
            for kw in [
                "non-deterministic",
                "hallucination",
                "ai response",
                "llm output",
            ]
        ),
    ),
    Signal(
        name="ai_pattern_match",
        category="non_deterministic_ai",
        weight=SIGNAL_WEIGHTS["ai_pattern_match"],
        predicate=lambda ct, pt, sa: any(
            fp.category == "non_deterministic_ai"
            for fp in ct.failure_pattern_matches
        ),
    ),
]


# ---------------------------------------------------------------------------
# Pre-compute max possible score per category (sum of all weights in category)
# ---------------------------------------------------------------------------

_MAX_POSSIBLE: dict[str, float] = defaultdict(float)
for _signal in SIGNALS:
    _MAX_POSSIBLE[_signal.category] += _signal.weight


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def run_rule_engine(
    ct: CorrelatedTest,
    pt: ParsedTest,
    sa: Optional[ParsedSpecAnalysis],
) -> tuple[str | None, float]:
    """Classify a failing test using weighted signal accumulation.

    Returns:
        (category, confidence) if normalised score >= RULE_CONFIDENCE_THRESHOLD.
        (None, winning_conf) if no category exceeds the threshold — caller should
        escalate to LLM classification.
        (None, 0.0) if no signals matched at all.

    All signal predicates guard against sa is None before accessing spec fields.
    Score normalisation prevents many weak signals from beating one strong signal.
    """
    scores: dict[str, float] = defaultdict(float)

    for signal in SIGNALS:
        try:
            if signal.predicate(ct, pt, sa):
                scores[signal.category] += signal.weight
        except Exception:
            # Predicate evaluation errors should not crash the pipeline
            pass

    if not scores:
        return None, 0.0

    # Normalise each category score by its maximum possible score
    normalised: dict[str, float] = {}
    for cat, score in scores.items():
        max_possible = _MAX_POSSIBLE.get(cat, 1.0)
        normalised[cat] = min(score / max_possible, 1.0)

    winning_cat = max(normalised, key=normalised.__getitem__)
    winning_conf = normalised[winning_cat]

    if winning_conf < RULE_CONFIDENCE_THRESHOLD:
        return None, winning_conf  # caller invokes LLM

    return winning_cat, winning_conf
