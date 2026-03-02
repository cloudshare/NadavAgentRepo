"""Pydantic v2 models for classification results.

ClassificationResult is the output of the classification engine
(rule_engine.py or llm_client.py) for a single failing test.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

# Union of all possible root-cause categories including "uncertain" fallback
ClassificationCategory = Literal[
    "test_design_issue",
    "product_regression",
    "infrastructure_instability",
    "cloud_provisioning_delay",
    "data_pollution",
    "auth_session_issue",
    "race_condition",
    "non_deterministic_ai",
    "uncertain",
]


class ClassificationResult(BaseModel):
    """Classification output for one failing or flaky test.

    Produced by either rule_engine (deterministic, fast) or LLM (for ambiguous
    cases where rule confidence falls below RULE_CONFIDENCE_THRESHOLD).
    """

    test_title: str
    full_title: str
    category: ClassificationCategory
    probability: float  # 0.0–1.0 confidence score
    method: Literal["rule_engine", "llm_haiku", "llm_sonnet"]
    fix_recommendation: str
    summary_paragraph: str
    reasoning_chain: list[str]  # log-line citations; empty for rule_engine
    tokens_used: int  # 0 for rule_engine; actual from response.usage for LLM
