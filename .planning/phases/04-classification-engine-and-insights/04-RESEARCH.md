# Phase 4: Classification Engine and Insights - Research

**Researched:** 2026-03-01
**Domain:** Rule-based classification, LLM integration (Anthropic SDK), SQLite persistence, analytics aggregation
**Confidence:** HIGH (core SDK and model facts verified against official docs; architecture patterns verified from existing codebase)

---

## Summary

Phase 4 takes the `CorrelatedTestRun` produced by Phase 3 and produces a full classification result: each failing test gets a category from the 8-label taxonomy, a probability score, and a fix recommendation. The pipeline is deterministic-first: a weighted rule engine runs on the signals already populated in `CorrelatedTest` and `ParsedTest`; the LLM is invoked only when rule confidence falls below 0.8. Chain-of-thought with log-line citations comes from a `tool_use` forced call to `claude-haiku-4-5` (triage) or `claude-sonnet-4-6` (complex). Token cost is estimated using `client.messages.count_tokens()` (free, synchronous, returns `input_tokens`) before any inference is run. Flakiness, heatmap, and ratio analytics are computed from the SQLite database that Phase 1 established.

The critical calibration flag from STATE.md ("Rule engine confidence thresholds (0.8 cutoff) and flakiness baseline need calibration against real log samples") means the 0.8 threshold should be a **named constant at the module level**, not a hard-coded magic number, so it can be tuned without touching rule logic. The same applies to the 0.6 "uncertain" floor.

**Primary recommendation:** Build the rule engine as a weighted signal accumulator (not an if/elif chain), use `tool_choice={"type":"tool","name":"classify_test"}` for forced LLM output, use `aiosqlite` raw SQL for all DB writes (no ORM), and expose analytics as plain Python dicts/lists that serialize trivially to JSON.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| anthropic | 0.78+ | Claude API calls (haiku triage, sonnet complex) | Official SDK; already in project research docs |
| aiosqlite | 24.0+ | Async SQLite reads/writes for flakiness tracking | Already in requirements.txt; no extra dep needed |
| pydantic | 2.0+ | Output models for ClassificationResult, InsightReport | Already in project; v2 Rust core validates output schemas |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| orjson | 3.10+ | JSON serialization for OUT-01 structured JSON report | 10x faster than stdlib json; native Pydantic .model_dump() support |
| dataclasses (stdlib) | N/A | Rule definition structs (weight, category, predicate fn) | Zero-dep for internal rule engine; keep rules as data not code |

### Not Needed / Do Not Add
- No pandas: analytics are simple group-by counts, not matrix operations. Pure Python dicts suffice and avoid a heavy dependency.
- No SQLAlchemy ORM: aiosqlite raw SQL is simpler for 3-4 table operations and avoids async ORM session pitfalls.
- No LangChain: per locked decision, direct Anthropic SDK only.
- No plotly: frontend receives JSON data, not rendered plots.

### Installation
```bash
pip install anthropic aiosqlite orjson
# pydantic, fastapi, aiosqlite already in requirements.txt
```

---

## Architecture Patterns

### Recommended Module Structure
```
src/
├── classifier/
│   ├── __init__.py          # re-exports classify_test_run()
│   ├── models.py            # ClassificationResult, TestInsight, InsightReport Pydantic models
│   ├── rule_engine.py       # weighted signal accumulator; returns (category, confidence)
│   ├── llm_client.py        # tool_use wrappers for haiku triage + sonnet escalation
│   ├── cost_estimator.py    # count_tokens() pre-flight check, print_cost_summary()
│   ├── analytics.py         # flakiness_index(), heatmap_data(), ratio_data()
│   └── db.py                # async SQLite helpers: upsert_result(), upsert_flakiness(), store_run_cost()
```

### Pattern 1: Weighted Signal Accumulator (Rule Engine)

**What:** Each rule is a named weight+predicate. Predicates are plain functions `(CorrelatedTest, ParsedTest, ParsedSpecAnalysis | None) -> bool`. The engine sums matched weights per category, then normalises to [0,1]. The winning category wins only if its normalised score exceeds `RULE_CONFIDENCE_THRESHOLD = 0.8`.

**When to use:** Always first, before any LLM call. Deterministic, fast, reproducible.

**Why not if/elif chain:** An if/elif chain creates hidden priority ordering that is brittle when adding new categories. Weighted accumulation is explicit, tunable (change one weight constant), and all evidence contributes regardless of order.

```python
# Source: project architecture + official rule engine design patterns
from dataclasses import dataclass
from typing import Callable
from src.knowledge_graph.models import CorrelatedTest
from src.parsers.models import ParsedTest, ParsedSpecAnalysis

# Tuneable constants — calibrate against real samples per STATE.md flag
RULE_CONFIDENCE_THRESHOLD = 0.8
LLM_UNCERTAIN_FLOOR = 0.6

@dataclass
class Signal:
    name: str
    category: str        # one of the 8 canonical labels
    weight: float        # 0.0–1.0; sum across a category can exceed 1.0 before normalisation
    predicate: Callable[[CorrelatedTest, ParsedTest, "ParsedSpecAnalysis | None"], bool]

# Example signal definitions (partial list)
SIGNALS: list[Signal] = [
    Signal(
        "infra_pattern_match",
        "infrastructure_instability",
        weight=0.9,
        predicate=lambda ct, pt, sa: ct.has_infra_signal and not ct.has_auth_signal
    ),
    Signal(
        "auth_pattern_match",
        "auth_session_issue",
        weight=0.9,
        predicate=lambda ct, pt, sa: ct.has_auth_signal
    ),
    Signal(
        "async_flow_with_infra",
        "cloud_provisioning_delay",
        weight=0.85,
        predicate=lambda ct, pt, sa: ct.has_async_signal
    ),
    Signal(
        "fragile_locator",
        "test_design_issue",
        weight=0.7,
        predicate=lambda ct, pt, sa: sa is not None and len(sa.fragile_locators) > 0
    ),
    Signal(
        "hard_coded_wait",
        "test_design_issue",
        weight=0.6,
        predicate=lambda ct, pt, sa: sa is not None and len(sa.hard_coded_wait_ms) > 0
    ),
    Signal(
        "passed_on_retry",
        "race_condition",
        weight=0.75,
        predicate=lambda ct, pt, sa: pt.retry_count > 0 and pt.status == "flaky"
    ),
    # ... additional signals for data_pollution, product_regression,
    # non_deterministic_ai, race_condition based on error_message keywords
]


def run_rule_engine(
    ct: CorrelatedTest,
    pt: ParsedTest,
    sa: "ParsedSpecAnalysis | None",
) -> tuple[str | None, float]:
    """Return (category, confidence) or (None, 0.0) if below threshold.

    Returns None category when the winning score is below RULE_CONFIDENCE_THRESHOLD,
    triggering LLM escalation by the caller.
    """
    from collections import defaultdict
    scores: dict[str, float] = defaultdict(float)
    for signal in SIGNALS:
        if signal.predicate(ct, pt, sa):
            scores[signal.category] += signal.weight

    if not scores:
        return None, 0.0

    # Normalise: divide by sum of all weights for the winning category's signals
    max_possible: dict[str, float] = defaultdict(float)
    for signal in SIGNALS:
        max_possible[signal.category] += signal.weight

    normalised = {
        cat: score / max_possible[cat]
        for cat, score in scores.items()
    }
    winning_cat = max(normalised, key=normalised.__getitem__)
    winning_conf = min(normalised[winning_cat], 1.0)  # cap at 1.0

    if winning_conf < RULE_CONFIDENCE_THRESHOLD:
        return None, winning_conf  # caller invokes LLM
    return winning_cat, winning_conf
```

### Pattern 2: Forced LLM Tool Call for Classification

**What:** When rule confidence < 0.8, call the LLM with `tool_choice={"type":"tool","name":"classify_test"}` and a single tool whose input schema matches the 8-category enum. Claude must respond by calling this tool — it cannot emit free text instead.

**Important constraint:** `tool_choice: {"type": "tool"}` is incompatible with extended thinking. Do not enable extended thinking in this phase.

```python
# Source: https://platform.claude.com/docs/en/agents-and-tools/tool-use/implement-tool-use
import anthropic

_CLASSIFY_TOOL = {
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
        "required": ["category", "probability", "reasoning_chain",
                     "fix_recommendation", "summary_paragraph"],
    },
}


async def classify_with_llm(
    test_title: str,
    log_context: str,  # pre-filtered, truncated to MAX_LOG_TOKENS
    use_sonnet: bool,  # False = haiku (triage), True = sonnet (complex)
) -> dict:
    """Call LLM with forced tool use. Returns tool_use input dict."""
    client = anthropic.AsyncAnthropic()
    model = "claude-sonnet-4-6" if use_sonnet else "claude-haiku-4-5"

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
    # With tool_choice type=tool, response.content[0] is always a tool_use block
    tool_use_block = next(
        b for b in response.content if b.type == "tool_use"
    )
    return tool_use_block.input  # typed dict matching _CLASSIFY_TOOL.input_schema
```

**When to escalate from haiku to sonnet:** If `CorrelatedTest.correlation_confidence == 0.5` (no KG match), use sonnet. If correlation_confidence == 1.0 and rule confidence is merely 0.7-0.8, haiku is sufficient.

### Pattern 3: Token Cost Estimation (Pre-flight)

**What:** `client.messages.count_tokens()` is free, does not consume inference quota, and returns `input_tokens` synchronously. Build the exact messages list you plan to send, call count_tokens with the same model, then compute cost.

```python
# Source: https://platform.claude.com/docs/en/build-with-claude/token-counting
import anthropic

# Current pricing (per million tokens, verified March 2026)
HAIKU_INPUT_COST_PER_M  = 1.00
HAIKU_OUTPUT_COST_PER_M = 5.00
SONNET_INPUT_COST_PER_M = 3.00
SONNET_OUTPUT_COST_PER_M = 15.00

# Estimated output tokens per call (heuristic — LLM output is not counted pre-flight)
ESTIMATED_OUTPUT_TOKENS = 400  # conservative: tool_use response ~300-500 tokens


async def estimate_run_cost(
    tests_needing_llm: list[dict],  # each has {model: str, messages: list}
) -> dict:
    """Count input tokens across all planned LLM calls. Returns cost summary dict."""
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
        + sonnet_calls * (ESTIMATED_OUTPUT_TOKENS / 1_000_000) * SONNET_OUTPUT_COST_PER_M
    )
    return {
        "haiku_calls": haiku_calls,
        "sonnet_calls": sonnet_calls,
        "estimated_input_tokens": total_haiku_input + total_sonnet_input,
        "estimated_cost_usd": round(haiku_cost + sonnet_cost, 4),
    }
```

### Pattern 4: Log Context Truncation (ERROR/WARN extraction)

**What:** Extract only lines containing ERROR or WARN from concatenated error text, then truncate so the total is at most 2000 tokens. Use character heuristic (4 chars per token) to avoid a count_tokens call per test during truncation.

```python
# Source: project convention + token heuristic (4 chars/token is standard approximation)
import re

MAX_LOG_CHARS = 8_000   # 8000 chars / 4 ≈ 2000 tokens (conservative)
_SEVERITY_RE = re.compile(r'\b(ERROR|WARN|FATAL|EXCEPTION|Traceback)\b', re.IGNORECASE)


def extract_log_context(
    error_message: str | None,
    error_stack: str | None,
    retry_errors: list[str],
) -> str:
    """Return filtered, truncated log context string for LLM consumption.

    Concatenates all error text, filters to lines with ERROR/WARN/FATAL/EXCEPTION,
    then truncates to MAX_LOG_CHARS using character-based heuristic.
    """
    all_text = "\n".join(filter(None, [
        error_message, error_stack, *retry_errors
    ]))
    lines = all_text.splitlines()
    filtered = [line for line in lines if _SEVERITY_RE.search(line)]
    # If no severity lines found, fall back to full text (test might have unusual format)
    if not filtered:
        filtered = lines
    context = "\n".join(filtered)
    return context[:MAX_LOG_CHARS]
```

### Pattern 5: SQLite Schema and Upserts

**What:** The Phase 1 spec called for `analysis_runs`, `test_results`, and `flakiness_index` tables. These are not yet created (SQLite DB not found in repo). Phase 4 must create them via `aiosqlite` on first run.

**Important finding:** There is **no existing SQLite database** in the repo. Phase 1 described the tables conceptually in the roadmap but did not implement them. Phase 4 will create the schema.

**Schema design** (inferred from requirements INSGT-01, INSGT-04, OUT-02):

```sql
-- analysis_runs: one row per TeamCity build processed
CREATE TABLE IF NOT EXISTS analysis_runs (
    run_id      TEXT PRIMARY KEY,   -- e.g., "build_12345_2026-03-01"
    build_id    INTEGER NOT NULL,
    created_at  TEXT NOT NULL,      -- ISO-8601 UTC
    total_tests INTEGER DEFAULT 0,
    failed_tests INTEGER DEFAULT 0,
    total_input_tokens  INTEGER DEFAULT 0,
    total_output_tokens INTEGER DEFAULT 0,
    estimated_cost_usd  REAL DEFAULT 0.0,
    report_json TEXT                -- OUT-01 full report as JSON string
);

-- test_results: one row per test per run
CREATE TABLE IF NOT EXISTS test_results (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id      TEXT NOT NULL,
    test_title  TEXT NOT NULL,
    full_title  TEXT NOT NULL,
    status      TEXT NOT NULL,      -- expected/unexpected/flaky/skipped
    category    TEXT,               -- one of 8 labels or 'uncertain'
    probability REAL DEFAULT 0.0,
    retry_count INTEGER DEFAULT 0,
    passed_on_retry INTEGER DEFAULT 0,  -- 1 if flaky (passed on retry)
    FOREIGN KEY (run_id) REFERENCES analysis_runs(run_id)
);

-- flakiness_index: rolling per-test statistics
CREATE TABLE IF NOT EXISTS flakiness_index (
    test_full_title TEXT PRIMARY KEY,
    total_runs      INTEGER DEFAULT 0,
    failure_count   INTEGER DEFAULT 0,
    flaky_count     INTEGER DEFAULT 0,
    failure_rate    REAL GENERATED ALWAYS AS
                    (CASE WHEN total_runs > 0
                          THEN CAST(failure_count AS REAL) / total_runs
                          ELSE 0.0 END) VIRTUAL,
    last_updated    TEXT NOT NULL
);
```

**Upsert pattern with aiosqlite:**

```python
# Source: aiosqlite docs + SQLite INSERT OR REPLACE semantics
import aiosqlite
from pathlib import Path

DB_PATH = Path("analysis.db")


async def init_db() -> None:
    """Create tables if they do not exist. Safe to call on every startup."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS analysis_runs (...);
            CREATE TABLE IF NOT EXISTS test_results (...);
            CREATE TABLE IF NOT EXISTS flakiness_index (...);
        """)
        await db.commit()


async def upsert_flakiness(test_full_title: str, failed: bool, flaky: bool) -> None:
    """Increment counters for a test. Uses INSERT OR REPLACE for upsert."""
    async with aiosqlite.connect(DB_PATH) as db:
        # Read current values first (INSERT OR REPLACE resets AUTOINCREMENT)
        async with db.execute(
            "SELECT total_runs, failure_count, flaky_count FROM flakiness_index WHERE test_full_title = ?",
            (test_full_title,)
        ) as cursor:
            row = await cursor.fetchone()

        if row:
            total, failures, flakies = row
        else:
            total, failures, flakies = 0, 0, 0

        await db.execute(
            """INSERT OR REPLACE INTO flakiness_index
               (test_full_title, total_runs, failure_count, flaky_count, last_updated)
               VALUES (?, ?, ?, ?, datetime('now'))""",
            (
                test_full_title,
                total + 1,
                failures + (1 if failed else 0),
                flakies + (1 if flaky else 0),
            ),
        )
        await db.commit()
```

**CRITICAL NOTE on GENERATED ALWAYS column:** SQLite's `GENERATED ALWAYS AS ... VIRTUAL` syntax for computed columns requires SQLite 3.31.0+. Python 3.9's bundled SQLite may be older. Alternative: compute `failure_rate` in the SELECT query instead of storing it as a generated column.

```sql
-- Safe alternative for older SQLite:
SELECT test_full_title,
       total_runs,
       failure_count,
       CAST(failure_count AS REAL) / total_runs AS failure_rate
FROM flakiness_index
WHERE total_runs > 0
ORDER BY failure_rate DESC;
```

### Pattern 6: Analytics Computations (No Pandas)

**Flakiness index query (INSGT-01):**
```python
async def get_flakiness_index(db_path: Path, min_runs: int = 3) -> list[dict]:
    """Return tests sorted by failure_rate descending. min_runs filters noise."""
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT test_full_title,
                   total_runs,
                   failure_count,
                   flaky_count,
                   CAST(failure_count AS REAL) / total_runs AS failure_rate
            FROM flakiness_index
            WHERE total_runs >= ?
            ORDER BY failure_rate DESC
        """, (min_runs,)) as cursor:
            rows = await cursor.fetchall()
    return [dict(row) for row in rows]
```

**API heatmap (INSGT-02) — pure Python:**
```python
def compute_endpoint_heatmap(correlated_tests: list[CorrelatedTest]) -> list[dict]:
    """Compute endpoint -> failure rate correlation.

    Returns list of dicts: [{endpoint, total_tests, failure_count, failure_rate}]
    JSON-serializable directly — no pandas needed.
    """
    from collections import defaultdict
    endpoint_totals: dict[str, int] = defaultdict(int)
    endpoint_failures: dict[str, int] = defaultdict(int)

    for ct in correlated_tests:
        for ep in ct.endpoint_matches:
            endpoint_totals[ep.kg_id] += 1
            endpoint_failures[ep.kg_id] += 1  # all correlated tests are failures

    return [
        {
            "endpoint": kg_id,
            "total_failing_tests": total,
            "failure_rate": endpoint_failures[kg_id] / total if total > 0 else 0.0,
        }
        for kg_id, total in sorted(
            endpoint_totals.items(),
            key=lambda x: endpoint_failures[x[0]] / x[1],
            reverse=True,
        )
    ]
```

**Infra/app/test-design ratio (INSGT-03):**
```python
INFRA_CATEGORIES = {"infrastructure_instability", "cloud_provisioning_delay"}
TEST_DESIGN_CATEGORIES = {"test_design_issue", "race_condition", "non_deterministic_ai"}
APP_CATEGORIES = {"product_regression", "data_pollution", "auth_session_issue"}

def compute_failure_ratios(classifications: list[dict]) -> dict:
    """Return infra/app/test-design failure ratio for INSGT-03."""
    counts = {"infra": 0, "app": 0, "test_design": 0, "uncertain": 0}
    for c in classifications:
        cat = c.get("category", "uncertain")
        if cat in INFRA_CATEGORIES:
            counts["infra"] += 1
        elif cat in APP_CATEGORIES:
            counts["app"] += 1
        elif cat in TEST_DESIGN_CATEGORIES:
            counts["test_design"] += 1
        else:
            counts["uncertain"] += 1
    total = len(classifications)
    return {
        "counts": counts,
        "ratios": {k: v / total if total > 0 else 0.0 for k, v in counts.items()},
        "total": total,
    }
```

### Anti-Patterns to Avoid

- **Single if/elif classification chain:** Brittle ordering, untestable weights, no confidence score. Use the weighted accumulator instead.
- **LLM call inside the rule engine:** Rule engine must be pure Python with no I/O. LLM escalation is the caller's responsibility.
- **Count tokens inside the log-truncation loop:** count_tokens is an HTTP call. Use the 4-char/token heuristic for truncation; call count_tokens only for the pre-flight cost estimate.
- **SQLAlchemy ORM for simple inserts:** The async ORM session lifecycle adds complexity with minimal benefit for 3-4 table schema. Raw aiosqlite is sufficient.
- **Pandas for ratio/heatmap:** Importing pandas (>30MB) for groupby on <1000 rows is unjustified overhead. Use `collections.defaultdict`.
- **Hardcoded threshold literals (0.8, 0.6):** Must be named constants. The STATE.md flag explicitly states these need calibration.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Guaranteed JSON from LLM | Custom prompt instructing Claude to "return JSON" | `tool_choice={"type":"tool"}` with input_schema | Claude can ignore JSON instructions; tool_use with forced selection is structural guarantee |
| Token counting | `len(text) / 4` heuristic for pre-flight cost | `client.messages.count_tokens()` | Official API is free, returns exact tokenizer count including tool definitions in prompt overhead |
| Async SQLite upsert | Raw `sqlite3` + `asyncio.to_thread` | `aiosqlite` | aiosqlite provides native async context managers; already in requirements.txt |
| Error text filtering | Custom log parser | Simple `re.compile(r'\b(ERROR|WARN|FATAL)\b')` line filter | Error lines are the signal; custom parsers introduce maintenance cost |
| Retry-detection (INSGT-04) | Re-scan ParsedTest retries | Check `test.status == "flaky"` (already set by Phase 2) | Phase 2 parser already sets this status for tests that passed on retry |

**Key insight:** The `CorrelatedTest` convenience flags (`has_infra_signal`, `has_auth_signal`, `has_async_signal`) were deliberately built in Phase 3 for this exact rule engine. Use them directly instead of rescanning `failure_pattern_matches` lists.

---

## Common Pitfalls

### Pitfall 1: SQLite GENERATED ALWAYS column incompatibility
**What goes wrong:** `CREATE TABLE ... failure_rate REAL GENERATED ALWAYS AS ...` raises `OperationalError` on older SQLite bundled with Python 3.9.
**Why it happens:** Python 3.9 ships with SQLite ~3.31-3.35 depending on OS; macOS may be older.
**How to avoid:** Compute `failure_rate` in SELECT query, not as a stored/virtual column.
**Warning signs:** `OperationalError: near "GENERATED": syntax error` at `init_db()`.

### Pitfall 2: tool_choice type="tool" with extended thinking
**What goes wrong:** API returns error `tool_choice type "tool" is not supported with extended thinking`.
**Why it happens:** Extended thinking and forced tool calls are mutually exclusive per Anthropic API constraint (confirmed in official docs).
**How to avoid:** Never enable `thinking={"type":"enabled"}` in the classification LLM calls. If thinking is needed for complex cases, use `tool_choice={"type":"auto"}` with explicit instructions to use the tool.
**Warning signs:** 400 API error at classification call time.

### Pitfall 3: Rule engine confidence not normalised per-category
**What goes wrong:** A category with many weak signals (5 × 0.3 = 1.5 raw) beats a category with one strong signal (1 × 0.9 = 0.9 raw), even though the strong signal is more reliable.
**Why it happens:** Summing weights without normalising by the maximum possible score for that category.
**How to avoid:** Normalise each category's score by the sum of all weights in that category's signal set.
**Warning signs:** infrastructure_instability always wins in tests with many fragile locators.

### Pitfall 4: LLM called for ALL tests (ignoring rule engine)
**What goes wrong:** Every test triggers an LLM call; cost estimation becomes meaningless; token costs explode.
**Why it happens:** Forgetting to check rule engine result before escalating.
**How to avoid:** Always run rule engine first. Call LLM only when `rule_confidence < RULE_CONFIDENCE_THRESHOLD`.
**Warning signs:** `haiku_calls + sonnet_calls == total_failing_tests` in cost estimate.

### Pitfall 5: Flakiness baseline with too few runs
**What goes wrong:** A test that ran 1 time and failed shows failure_rate=1.0, flooding the heatmap.
**Why it happens:** No minimum run count filter on the flakiness query.
**How to avoid:** Use `WHERE total_runs >= MIN_RUNS_FOR_FLAKINESS` (minimum 3, configurable).
**Warning signs:** STATE.md flag: "flakiness baseline need calibration against real log samples".

### Pitfall 6: ParsedSpecAnalysis not always available
**What goes wrong:** Rule predicates crash with `AttributeError` when accessing `sa.fragile_locators`.
**Why it happens:** `ParsedSpecAnalysis` is `Optional` on `ParsedTestSuite` — not every suite has a parsed spec.
**How to avoid:** Rule predicates must check `sa is not None` before accessing spec fields (shown in Signal examples above).
**Warning signs:** `NoneType has no attribute 'fragile_locators'` at rule evaluation time.

### Pitfall 7: aiosqlite.Row needs dict() conversion for JSON serialization
**What goes wrong:** `json.dumps(rows)` fails because `aiosqlite.Row` objects are not JSON-serializable.
**Why it happens:** aiosqlite.Row is a sqlite3.Row proxy, not a dict.
**How to avoid:** Set `db.row_factory = aiosqlite.Row` and call `dict(row)` or `[dict(r) for r in rows]` before returning.
**Warning signs:** `TypeError: Object of type Row is not JSON serializable`.

---

## Code Examples

### Complete single-test classification pipeline
```python
# Source: synthesised from official Anthropic SDK + project existing code patterns
async def classify_test(
    ct: CorrelatedTest,
    pt: ParsedTest,
    sa: "ParsedSpecAnalysis | None",
) -> dict:
    """Full pipeline: rule engine -> optional LLM -> return ClassificationResult dict."""
    # Step 1: Rule engine (deterministic, no I/O)
    rule_category, rule_confidence = run_rule_engine(ct, pt, sa)

    if rule_category is not None:
        # Rule engine confident — return without LLM call
        return {
            "test_title": pt.title,
            "full_title": pt.full_title,
            "category": rule_category,
            "probability": rule_confidence,
            "method": "rule_engine",
            "fix_recommendation": _RULE_FIX_MAP.get(rule_category, "Review test and application logs."),
            "summary_paragraph": f"Rule engine classified as {rule_category} with {rule_confidence:.0%} confidence.",
            "reasoning_chain": [],
            "tokens_used": 0,
        }

    # Step 2: LLM escalation
    log_context = extract_log_context(
        pt.first_error_message,
        pt.first_error_stack,
        [r.error_message or "" for r in pt.retries],
    )
    # Use sonnet when KG had no match (correlation_confidence 0.5 = uncertain infra context)
    use_sonnet = ct.correlation_confidence < 1.0
    llm_result = await classify_with_llm(pt.full_title, log_context, use_sonnet)

    return {
        "test_title": pt.title,
        "full_title": pt.full_title,
        "category": llm_result["category"],
        "probability": llm_result["probability"],
        "method": "llm_haiku" if not use_sonnet else "llm_sonnet",
        "fix_recommendation": llm_result["fix_recommendation"],
        "summary_paragraph": llm_result["summary_paragraph"],
        "reasoning_chain": llm_result["reasoning_chain"],
        "tokens_used": 0,  # populated post-call from response.usage
    }
```

### Retry detection for INSGT-04
```python
# Source: Phase 2 parser sets test.status = "flaky" for tests that passed on retry
def tests_passing_on_retry(parsed_run: ParsedTestRun) -> list[str]:
    """Return full_titles of tests flagged as likely flaky (passed on retry)."""
    return [
        test.full_title
        for suite in parsed_run.suites
        for test in suite.tests
        if test.status == "flaky"
    ]
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Prompt-based JSON extraction ("return JSON") | `tool_use` with `tool_choice={"type":"tool"}` forced call | Anthropic 2024 | Structural guarantee; parser no longer needed |
| Anthropic structured outputs (beta Nov 2025) | `tool_use` forced call (simpler, same effect) | Nov 2025 | Beta structured outputs require beta header and only support Sonnet 4.5/Opus 4.1 as of research date; tool_use works on all models including haiku-4-5 |
| sqlite3 + asyncio.to_thread | aiosqlite | 2020+ | Native async context managers; cleaner FastAPI integration |
| Pre-flight token estimation (chars/4 heuristic) | `client.messages.count_tokens()` free API | Anthropic 2024 | Exact count including tool definition overhead; free; subject only to RPM not TPM |

**Deprecated/outdated:**
- `claude-3-haiku-20240307`: Deprecated April 19, 2026. Use `claude-haiku-4-5` (alias `claude-haiku-4-5-20251001`).
- LangChain Anthropic integration: Not applicable per locked decision.
- Structured outputs beta (`anthropic-beta: structured-outputs-2025-11-13`): Limited model support (Sonnet 4.5, Opus 4.1); tool_use forced call achieves same result on all models.

---

## Open Questions

1. **SQLite database location and lifecycle**
   - What we know: No DB exists yet; Phase 1 spec mentioned tables but did not implement them.
   - What's unclear: Should DB be created at `analysis.db` (project root) or a configurable path via `config/settings.yaml`? Should Phase 4 handle its own schema migration?
   - Recommendation: Add `database.path` to `config/settings.yaml`; default to `analysis.db` at project root. Phase 4 plan creates the schema in `init_db()` on startup.

2. **Rule engine signal weights — calibration**
   - What we know: Weights above are initial estimates. STATE.md flag says they need calibration against real logs.
   - What's unclear: No real log samples are available; initial weights are educated guesses.
   - Recommendation: Define all weights as named constants in a `SIGNAL_WEIGHTS` dict at the top of `rule_engine.py`. Document that calibration against real samples is a post-MVP task. The 0.8 threshold should default to a value that errs toward LLM invocation (i.e., start at 0.7 if unsure).

3. **Token tracking for OUT-02 (actual tokens used)**
   - What we know: `response.usage` from `client.messages.create()` returns `input_tokens` and `output_tokens` on the actual call.
   - What's unclear: The requirement asks to store total tokens per run in SQLite. Need to accumulate across all LLM calls in a run.
   - Recommendation: Maintain a `RunTokenAccumulator` dataclass during classification, sum up `response.usage.input_tokens + response.usage.output_tokens` per call, store total at run completion.

4. **ParsedTest ↔ CorrelatedTest linkage for rule engine**
   - What we know: `CorrelatedTest` has `test_title` and `full_title`; `ParsedTest` is in `ParsedTestSuite.tests`. `ParsedSpecAnalysis` is in `ParsedTestSuite.spec_analysis`.
   - What's unclear: There is no shared ID; matching is by `full_title`. If multiple suites have the same test full_title (unlikely but possible), the match is ambiguous.
   - Recommendation: In `classify_test_run()`, iterate suites and match `ParsedTest` to `CorrelatedTest` by `full_title`. Document that duplicate full_titles are treated as distinct tests (classification is per occurrence, not per unique name).

---

## Sources

### Primary (HIGH confidence)
- `https://platform.claude.com/docs/en/build-with-claude/token-counting` — `client.messages.count_tokens()` API, free, returns `input_tokens`, supports tools parameter
- `https://platform.claude.com/docs/en/agents-and-tools/tool-use/implement-tool-use` — `tool_choice` parameter options (`auto`, `any`, `tool`, `none`), forced tool call constraint with extended thinking
- `https://platform.claude.com/docs/en/about-claude/models/overview` — Model IDs (`claude-haiku-4-5`, `claude-sonnet-4-6`), current pricing ($1/$5 haiku, $3/$15 sonnet per MTok), context windows
- `src/knowledge_graph/models.py` — `CorrelatedTest` fields, convenience flags, correlation_confidence values
- `src/parsers/models.py` — `ParsedTest`, `ParsedSpecAnalysis`, `ParsedRetryResult` field definitions
- `src/knowledge_graph/correlator.py` — `correlate_test_run()` output format, retry error text concatenation
- `https://aiosqlite.omnilib.dev/` — `aiosqlite.connect()` async context manager, `db.row_factory`, `executescript()`

### Secondary (MEDIUM confidence)
- WebSearch "rule engine weighted scoring deterministic classification" + blakecrosley.com signal scoring — weighted composite score pattern for 0.0-1.0 confidence scoring
- WebSearch "aiosqlite raw SQL INSERT OR REPLACE asyncio" — confirms raw SQL pattern without ORM for simple upsert cases
- `.planning/STATE.md` — Phase 4 flag on confidence threshold calibration; prior decisions on sequential processing

### Tertiary (LOW confidence)
- Heuristic "4 chars per token": widely cited but varies by content type; safe for log-text estimation where UTF-8 ASCII is dominant.
- SQLite `GENERATED ALWAYS` version matrix: extrapolated from SQLite release notes; exact Python 3.9 bundled SQLite version on macOS not verified.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — anthropic SDK, aiosqlite, pydantic all officially documented; versions confirmed
- Architecture: HIGH — tool_use forced call pattern verified from official docs; rule engine pattern from existing codebase signals
- Pitfalls: HIGH — SQLite generated column limit and tool_choice/extended-thinking incompatibility verified from official sources; others from code inspection
- Signal weights: LOW — initial estimates only; real calibration requires live log samples

**Research date:** 2026-03-01
**Valid until:** 2026-04-01 (30 days; model pricing and API contracts stable)
