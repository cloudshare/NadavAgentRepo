"""Pre-flight token counting and cost estimation for LLM classification calls.

Uses client.messages.count_tokens() which is free and does not consume inference
quota. Call this before running any actual LLM classification to report expected
cost to the operator.

Pattern:
    tests_needing_llm = [{"model": HAIKU_MODEL, "messages": [...]} ...]
    cost = await estimate_run_cost(tests_needing_llm)
    print_cost_summary(cost)
"""

from __future__ import annotations

import anthropic

from src.classifier.llm_client import HAIKU_MODEL, SONNET_MODEL, _CLASSIFY_TOOL

# ---------------------------------------------------------------------------
# Pricing constants (per million tokens, verified March 2026)
# ---------------------------------------------------------------------------

HAIKU_INPUT_COST_PER_M: float = 1.00
HAIKU_OUTPUT_COST_PER_M: float = 5.00
SONNET_INPUT_COST_PER_M: float = 3.00
SONNET_OUTPUT_COST_PER_M: float = 15.00

# Conservative output token estimate for tool_use responses (actual: ~300-500 tokens)
ESTIMATED_OUTPUT_TOKENS: int = 400


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def estimate_run_cost(tests_needing_llm: list[dict]) -> dict:
    """Count input tokens across all planned LLM calls and estimate total cost.

    Args:
        tests_needing_llm: List of dicts, each with:
            - "model": str — either HAIKU_MODEL or SONNET_MODEL
            - "messages": list[dict] — the messages list to send

    Returns:
        dict with keys:
            - haiku_calls: int
            - sonnet_calls: int
            - estimated_input_tokens: int
            - estimated_cost_usd: float
    """
    client = anthropic.AsyncAnthropic()
    total_haiku_input = 0
    total_sonnet_input = 0

    for item in tests_needing_llm:
        response = await client.messages.count_tokens(
            model=item["model"],
            tools=[_CLASSIFY_TOOL],
            messages=item["messages"],
        )
        if "haiku" in item["model"]:
            total_haiku_input += response.input_tokens
        else:
            total_sonnet_input += response.input_tokens

    haiku_calls = sum(1 for i in tests_needing_llm if "haiku" in i["model"])
    sonnet_calls = sum(1 for i in tests_needing_llm if "sonnet" in i["model"])

    haiku_cost = (
        (total_haiku_input / 1_000_000) * HAIKU_INPUT_COST_PER_M
        + haiku_calls * (ESTIMATED_OUTPUT_TOKENS / 1_000_000) * HAIKU_OUTPUT_COST_PER_M
    )
    sonnet_cost = (
        (total_sonnet_input / 1_000_000) * SONNET_INPUT_COST_PER_M
        + sonnet_calls
        * (ESTIMATED_OUTPUT_TOKENS / 1_000_000)
        * SONNET_OUTPUT_COST_PER_M
    )

    return {
        "haiku_calls": haiku_calls,
        "sonnet_calls": sonnet_calls,
        "estimated_input_tokens": total_haiku_input + total_sonnet_input,
        "estimated_cost_usd": round(haiku_cost + sonnet_cost, 4),
    }


def print_cost_summary(cost_dict: dict) -> None:
    """Print a human-readable cost summary to stdout.

    Example output:
        Pre-flight estimate: 12 haiku calls + 3 sonnet calls
          = ~15,000 input tokens + 6,000 estimated output tokens
          ≈ $0.0215 USD
    """
    haiku_calls: int = cost_dict.get("haiku_calls", 0)
    sonnet_calls: int = cost_dict.get("sonnet_calls", 0)
    input_tokens: int = cost_dict.get("estimated_input_tokens", 0)
    cost_usd: float = cost_dict.get("estimated_cost_usd", 0.0)

    total_calls = haiku_calls + sonnet_calls
    estimated_output = total_calls * ESTIMATED_OUTPUT_TOKENS

    print(
        f"Pre-flight estimate: {haiku_calls} haiku calls + {sonnet_calls} sonnet calls"
        f" = ~{input_tokens:,} input tokens"
        f" ≈ ${cost_usd:.4f}"
    )
    print(
        f"  (+ ~{estimated_output:,} estimated output tokens at "
        f"${HAIKU_OUTPUT_COST_PER_M}/M haiku / ${SONNET_OUTPUT_COST_PER_M}/M sonnet)"
    )
