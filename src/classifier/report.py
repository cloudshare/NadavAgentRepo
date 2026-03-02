"""Structured JSON report generator and token accumulator.

OUT-01: structured JSON report per failing test with all required fields.
OUT-02: total tokens used and estimated cost per analysis run.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Token accumulator
# ---------------------------------------------------------------------------


@dataclass
class RunTokenAccumulator:
    """Accumulates token usage across all ClassificationResults in a run."""

    total_input_tokens: int = 0
    haiku_calls: int = 0
    sonnet_calls: int = 0

    def add(self, result: object) -> None:
        """Add token usage from a ClassificationResult."""
        method = getattr(result, "method", "")
        tokens_used = getattr(result, "tokens_used", 0)
        if method == "llm_haiku":
            self.haiku_calls += 1
        elif method == "llm_sonnet":
            self.sonnet_calls += 1
        self.total_input_tokens += tokens_used

    @property
    def total_tokens(self) -> int:
        return self.total_input_tokens

    def estimated_cost_usd(self) -> float:
        """Conservative post-run cost estimate using haiku/sonnet call split."""
        from .cost_estimator import HAIKU_INPUT_COST_PER_M, SONNET_INPUT_COST_PER_M

        total_calls = self.haiku_calls + self.sonnet_calls
        if total_calls == 0:
            return 0.0
        haiku_fraction = self.haiku_calls / total_calls
        avg_cost_per_m = (
            haiku_fraction * HAIKU_INPUT_COST_PER_M
            + (1 - haiku_fraction) * SONNET_INPUT_COST_PER_M
        )
        return round((self.total_input_tokens / 1_000_000) * avg_cost_per_m, 4)


# ---------------------------------------------------------------------------
# Report generator
# ---------------------------------------------------------------------------


def generate_report(
    classifications: list,
    run_id: str,
    accumulator: RunTokenAccumulator,
) -> dict:
    """Build structured JSON report for an analysis run.

    Returns a JSON-serializable dict (OUT-01 format) containing per-test
    details and a run-level summary with token usage.

    Args:
        classifications: list[ClassificationResult]
        run_id: Analysis run identifier.
        accumulator: RunTokenAccumulator already populated via .add() for each result.

    Returns:
        dict with "run_id", "summary", and "tests" keys.
    """
    by_category: dict[str, int] = {}
    by_method: dict[str, int] = {}

    for r in classifications:
        cat = getattr(r, "category", "uncertain")
        method = getattr(r, "method", "unknown")
        by_category[cat] = by_category.get(cat, 0) + 1
        by_method[method] = by_method.get(method, 0) + 1

    report: dict = {
        "run_id": run_id,
        "summary": {
            "total_classified": len(classifications),
            "by_category": by_category,
            "by_method": by_method,
            "token_usage": {
                "total_tokens": accumulator.total_tokens,
                "haiku_calls": accumulator.haiku_calls,
                "sonnet_calls": accumulator.sonnet_calls,
                "estimated_cost_usd": accumulator.estimated_cost_usd(),
            },
        },
        "tests": [
            {
                "test_title": getattr(r, "test_title", ""),
                "full_title": getattr(r, "full_title", ""),
                "category": getattr(r, "category", "uncertain"),
                "probability": getattr(r, "probability", 0.0),
                "method": getattr(r, "method", "unknown"),
                "fix_recommendation": getattr(r, "fix_recommendation", ""),
                "summary_paragraph": getattr(r, "summary_paragraph", ""),
                "reasoning_chain": getattr(r, "reasoning_chain", []),
            }
            for r in classifications
        ],
    }

    # Verify serializability (raises TypeError if any value is not JSON-compatible)
    json.dumps(report)
    return report
