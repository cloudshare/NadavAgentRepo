"""LLM-based classification client using forced tool_use.

When the rule engine confidence falls below RULE_CONFIDENCE_THRESHOLD, this
module invokes the Anthropic API with a forced tool_use call to classify the
failing test. The tool schema ensures structured output without prompt engineering.

Important: tool_choice type="tool" is incompatible with extended thinking.
Do NOT enable thinking={"type":"enabled"} here (Pitfall 2 in RESEARCH.md).
"""

from __future__ import annotations

import re
from typing import Optional

import anthropic

from src.classifier.models import ClassificationResult
from src.classifier.rule_engine import (
    LLM_UNCERTAIN_FLOOR,
    RULE_CONFIDENCE_THRESHOLD,
    run_rule_engine,
)
from src.knowledge_graph.models import CorrelatedTest
from src.parsers.models import ParsedSpecAnalysis, ParsedTest

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_LOG_CHARS: int = 8_000  # 8000 chars / 4 chars-per-token ≈ 2000 tokens
HAIKU_MODEL: str = "claude-haiku-4-5"
SONNET_MODEL: str = "claude-sonnet-4-6"

_SEVERITY_RE = re.compile(r"\b(ERROR|WARN|FATAL|EXCEPTION|Traceback)\b", re.IGNORECASE)

# ---------------------------------------------------------------------------
# Tool schema — forced tool_use for structured classification output
# ---------------------------------------------------------------------------

_CLASSIFY_TOOL: dict = {
    "name": "classify_test",
    "description": (
        "Classify a failing test into exactly one root cause category. "
        "Cite the specific log lines that support your classification in reasoning_chain. "
        "Set probability to your confidence (0.0-1.0). "
        "If probability < 0.6, set category to 'uncertain'."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "category": {
                "type": "string",
                "enum": [
                    "test_design_issue",
                    "product_regression",
                    "infrastructure_instability",
                    "cloud_provisioning_delay",
                    "data_pollution",
                    "auth_session_issue",
                    "race_condition",
                    "non_deterministic_ai",
                    "uncertain",
                ],
                "description": "The root cause category. Use 'uncertain' if probability < 0.6.",
            },
            "probability": {
                "type": "number",
                "description": "Confidence score 0.0-1.0. Use < 0.6 for uncertain.",
            },
            "reasoning_chain": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Ordered list of reasoning steps. Each step should cite a "
                    "specific log line or signal. Example: "
                    "'Line 42: ESX timeout error matches infrastructure_instability pattern'"
                ),
            },
            "fix_recommendation": {
                "type": "string",
                "description": "Actionable fix recommendation for CloudShare domain.",
            },
            "summary_paragraph": {
                "type": "string",
                "description": "Natural language root cause summary paragraph.",
            },
        },
        "required": [
            "category",
            "probability",
            "reasoning_chain",
            "fix_recommendation",
            "summary_paragraph",
        ],
    },
}

# ---------------------------------------------------------------------------
# Fix recommendations for rule-engine-classified tests
# ---------------------------------------------------------------------------

_RULE_FIX_MAP: dict[str, str] = {
    "infrastructure_instability": (
        "Check CSC/PCS infrastructure logs for VMware ESX or storage errors; "
        "consider adding retry logic with exponential backoff for this endpoint."
    ),
    "cloud_provisioning_delay": (
        "Increase timeout threshold for async provisioning operations or add explicit "
        "wait-for-ready polling before assertion."
    ),
    "auth_session_issue": (
        "Verify auth token refresh before test; check session expiry configuration "
        "and add token pre-warm step in beforeAll hook."
    ),
    "test_design_issue": (
        "Replace fragile locators with stable data-testid attributes; "
        "replace hard-coded waits with explicit condition polling."
    ),
    "race_condition": (
        "Add mutex/lock around shared test state; use page.waitForSelector() instead "
        "of fixed timeouts; run tests in isolation."
    ),
    "data_pollution": (
        "Add teardown cleanup for test-created entities; use unique prefixes per test "
        "run to prevent data collisions."
    ),
    "product_regression": (
        "Review recent commits touching this endpoint or feature; add to regression "
        "suite and create a bug report."
    ),
    "non_deterministic_ai": (
        "Add retry with response validation; define acceptance criteria range instead "
        "of exact match for AI-generated outputs."
    ),
    "uncertain": (
        "Review full test log manually; insufficient signals for automated classification."
    ),
}


# ---------------------------------------------------------------------------
# Log context extraction
# ---------------------------------------------------------------------------


def extract_log_context(
    error_message: Optional[str],
    error_stack: Optional[str],
    retry_errors: list[str],
) -> str:
    """Return filtered, truncated log context string for LLM consumption.

    Concatenates all error text, filters to lines with ERROR/WARN/FATAL/EXCEPTION,
    then truncates to MAX_LOG_CHARS using character-based heuristic.
    Falls back to full text if no severity lines are found.
    """
    all_text = "\n".join(filter(None, [error_message, error_stack, *retry_errors]))
    lines = all_text.splitlines()
    filtered = [line for line in lines if _SEVERITY_RE.search(line)]
    # If no severity lines found, fall back to full text (some test formats lack markers)
    if not filtered:
        filtered = lines
    context = "\n".join(filtered)
    return context[:MAX_LOG_CHARS]


# ---------------------------------------------------------------------------
# LLM classification
# ---------------------------------------------------------------------------


async def classify_with_llm(
    test_title: str,
    log_context: str,
    use_sonnet: bool,
) -> dict:
    """Call LLM with forced tool use for structured classification output.

    Args:
        test_title: The full test title for context.
        log_context: Pre-filtered, truncated error log text.
        use_sonnet: True to use claude-sonnet-4-6; False for claude-haiku-4-5.

    Returns:
        dict with keys: category, probability, reasoning_chain, fix_recommendation,
        summary_paragraph, usage (from response.usage).
    """
    client = anthropic.AsyncAnthropic()
    model = SONNET_MODEL if use_sonnet else HAIKU_MODEL

    response = await client.messages.create(
        model=model,
        max_tokens=1024,
        tools=[_CLASSIFY_TOOL],
        tool_choice={"type": "tool", "name": "classify_test"},
        messages=[
            {
                "role": "user",
                "content": (
                    f"Classify this failing test: {test_title}\n\n"
                    f"Log context (ERROR/WARN lines only):\n{log_context}"
                ),
            }
        ],
    )

    # With tool_choice type="tool", the response always contains a tool_use block
    tool_use_block = next(b for b in response.content if b.type == "tool_use")
    result: dict = dict(tool_use_block.input)

    # Apply LLM_UNCERTAIN_FLOOR: low-confidence classifications become "uncertain"
    if result.get("probability", 0.0) < LLM_UNCERTAIN_FLOOR:
        result["category"] = "uncertain"

    result["usage"] = response.usage
    return result


# ---------------------------------------------------------------------------
# Full classification pipeline
# ---------------------------------------------------------------------------


async def classify_test(
    ct: CorrelatedTest,
    pt: ParsedTest,
    sa: Optional[ParsedSpecAnalysis],
) -> ClassificationResult:
    """Full classification pipeline: rule engine first, LLM escalation if needed.

    Steps:
    1. Run deterministic rule engine (no I/O, fast).
    2. If rule engine confident (>= RULE_CONFIDENCE_THRESHOLD): return result.
    3. Else: extract log context, call LLM, apply uncertain floor, return result.

    Args:
        ct: CorrelatedTest from Phase 3 (contains infra/auth/async signals).
        pt: ParsedTest from Phase 2 (contains error text, retry info).
        sa: Optional ParsedSpecAnalysis from Phase 2 (spec static analysis).

    Returns:
        ClassificationResult with category, probability, method, and explanations.
    """
    # Step 1: Rule engine (deterministic, no API cost)
    rule_category, rule_conf = run_rule_engine(ct, pt, sa)

    if rule_category is not None:
        # Count matched signals for summary paragraph
        from src.classifier.rule_engine import SIGNALS

        matching_count = sum(
            1
            for s in SIGNALS
            if s.category == rule_category and s.predicate(ct, pt, sa)
        )
        return ClassificationResult(
            test_title=pt.title,
            full_title=pt.full_title,
            category=rule_category,  # type: ignore[arg-type]
            probability=rule_conf,
            method="rule_engine",
            fix_recommendation=_RULE_FIX_MAP.get(
                rule_category, "Review test and application logs."
            ),
            summary_paragraph=(
                f"Rule engine classified this test as {rule_category} with "
                f"{rule_conf:.0%} confidence based on {matching_count} matched signal(s)."
            ),
            reasoning_chain=[],
            tokens_used=0,
        )

    # Step 2: LLM escalation
    log_context = extract_log_context(
        pt.first_error_message,
        pt.first_error_stack,
        [r.error_message or "" for r in pt.retries],
    )

    # Use sonnet when KG had no match (correlation_confidence < 1.0 means uncertain context)
    use_sonnet = ct.correlation_confidence < 1.0
    method = "llm_sonnet" if use_sonnet else "llm_haiku"

    llm_result = await classify_with_llm(pt.full_title, log_context, use_sonnet)

    usage = llm_result.get("usage")
    tokens_used = 0
    if usage is not None:
        tokens_used = (
            getattr(usage, "input_tokens", 0) + getattr(usage, "output_tokens", 0)
        )

    return ClassificationResult(
        test_title=pt.title,
        full_title=pt.full_title,
        category=llm_result["category"],  # type: ignore[arg-type]
        probability=llm_result["probability"],
        method=method,  # type: ignore[arg-type]
        fix_recommendation=llm_result.get(
            "fix_recommendation", "Review test and application logs."
        ),
        summary_paragraph=llm_result.get("summary_paragraph", ""),
        reasoning_chain=llm_result.get("reasoning_chain", []),
        tokens_used=tokens_used,
    )
