---
phase: 04-classification-engine-and-insights
plan: "01"
subsystem: classifier
tags: [anthropic, pydantic, rule-engine, llm, classification, tool-use, cost-estimation]

requires:
  - phase: 03-knowledge-graph-and-correlation
    provides: CorrelatedTest with has_infra_signal, has_auth_signal, has_async_signal flags
  - phase: 02-parse-and-ingest
    provides: ParsedTest, ParsedSpecAnalysis with fragile_locators, hard_coded_wait_ms

provides:
  - ClassificationResult Pydantic model (8-category taxonomy + uncertain)
  - run_rule_engine() deterministic weighted signal accumulator (no I/O)
  - classify_with_llm() forced tool_use call returning structured classification
  - classify_test() full pipeline (rule engine first, LLM escalation if below threshold)
  - extract_log_context() severity-line filter with MAX_LOG_CHARS truncation
  - estimate_run_cost() pre-flight count_tokens based cost estimation
  - print_cost_summary() human-readable cost output

affects:
  - 04-02 (analytics, SQLite persistence)
  - 04-03 (output formatting, Slack delivery)

tech-stack:
  added:
    - anthropic SDK (AsyncAnthropic, tool_use forced calls, count_tokens pre-flight)
  patterns:
    - Weighted signal accumulator rule engine (normalised per-category, not if/elif chain)
    - Forced tool_use with tool_choice={type:tool,name:classify_test} for structural LLM output
    - Named constants for all tuneable thresholds (RULE_CONFIDENCE_THRESHOLD, LLM_UNCERTAIN_FLOOR)
    - Pre-flight token counting via count_tokens() before inference (free, no quota)
    - Primary/secondary signal weight design (0.9/0.1) so single strong KG signal hits threshold independently

key-files:
  created:
    - src/classifier/__init__.py
    - src/classifier/models.py
    - src/classifier/rule_engine.py
    - src/classifier/llm_client.py
    - src/classifier/cost_estimator.py
  modified: []

key-decisions:
  - "Signal weights use 0.9/0.1 primary/secondary split for KG-backed categories so a single strong signal independently reaches RULE_CONFIDENCE_THRESHOLD=0.8"
  - "product_regression signals use lower weights (0.6/0.65) so catch-all signals alone do NOT hit threshold — requires LLM confirmation for ambiguous regression cases"
  - "LLM_UNCERTAIN_FLOOR applied server-side in classify_with_llm() not in caller — keeps floor enforcement in one place"
  - "classify_test() uses correlation_confidence < 1.0 to decide haiku vs sonnet — no KG match means more context needed"
  - "Tool schema _CLASSIFY_TOOL imported in cost_estimator.py from llm_client.py — single definition, no duplication"

patterns-established:
  - "Rule engine first: always run deterministic rule engine before any LLM call"
  - "Named constants only: 0.8 and 0.6 never appear as literals in logic, only in SIGNAL_WEIGHTS dict values and constant declarations"
  - "sa guard: all predicates accessing ParsedSpecAnalysis fields check sa is not None first"

duration: 6min
completed: 2026-03-02
---

# Phase 4 Plan 01: Classification Engine and Insights Summary

**Deterministic-first classification engine with weighted rule accumulator (16 signals, 8 categories) and Anthropic forced tool_use LLM fallback using claude-haiku-4-5 / claude-sonnet-4-6**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-02T07:53:24Z
- **Completed:** 2026-03-02T07:59:52Z
- **Tasks:** 2
- **Files created:** 5

## Accomplishments

- Built weighted signal accumulator rule engine with 16 named signals across all 8 failure categories; single strong KG-backed signal reaches 0.8 confidence threshold independently
- Implemented forced tool_use LLM classification via `tool_choice={"type":"tool","name":"classify_test"}` with all 5 required fields guaranteed in output
- Added pre-flight cost estimator using `client.messages.count_tokens()` (free, no inference quota) before any LLM calls run

## Task Commits

Each task was committed atomically:

1. **Task 1: ClassificationResult model and weighted rule engine** - `be6025f` (feat)
2. **Task 2: LLM client (forced tool_use) and cost estimator** - `32e4ee7` (feat)

**Plan metadata:** (pending docs commit)

## Files Created/Modified

- `src/classifier/__init__.py` - Package re-exports for all public API symbols
- `src/classifier/models.py` - ClassificationResult Pydantic v2 model with ClassificationCategory type
- `src/classifier/rule_engine.py` - Weighted signal accumulator with SIGNAL_WEIGHTS, RULE_CONFIDENCE_THRESHOLD, LLM_UNCERTAIN_FLOOR; 16 named signals
- `src/classifier/llm_client.py` - classify_with_llm(), classify_test() pipeline, extract_log_context(), _CLASSIFY_TOOL schema, _RULE_FIX_MAP
- `src/classifier/cost_estimator.py` - estimate_run_cost(), print_cost_summary() with HAIKU/SONNET pricing constants

## Decisions Made

- Signal weights use 0.9/0.1 primary/secondary split for KG-backed categories so a single strong signal reaches RULE_CONFIDENCE_THRESHOLD independently. This ensures the rule engine handles clear cases (infra, auth, async) without LLM cost.
- `product_regression` signals use lower weights (0.6/0.65) intentionally. The catch-all "no infra, no design issues" signal alone scores 0.48, below threshold, requiring LLM confirmation. This prevents false product-regression classifications from over-confident rule matching.
- LLM_UNCERTAIN_FLOOR (0.6) is applied inside `classify_with_llm()` — not in the caller. Single enforcement point prevents floor bypass.
- `correlation_confidence < 1.0` (no KG match) triggers sonnet escalation. No KG match means less infrastructure context, so the more capable model is appropriate.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Recalibrated signal weights after normalisation math revealed threshold miss**

- **Found during:** Task 1 (rule_engine verification)
- **Issue:** Initial weights from RESEARCH.md table (infra 0.9, multi_infra_layer 0.6) gave max_possible = 1.5; single infra signal normalised to 0.9/1.5 = 0.6, below RULE_CONFIDENCE_THRESHOLD=0.8. Verification test failed.
- **Fix:** Redesigned weight scheme: primary signals 0.9, secondary signals 0.1 (max_possible = 1.0). Kept product_regression at original 0.6/0.65 weights since it's intentionally a catch-all that should escalate to LLM.
- **Files modified:** `src/classifier/rule_engine.py` (SIGNAL_WEIGHTS dict)
- **Verification:** `run_rule_engine(ct_with_infra, pt, None)` returns `("infrastructure_instability", 0.90)` — passes task 1 done criteria
- **Committed in:** be6025f (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - bug in weight calibration)
**Impact on plan:** Essential fix — the initial weights from RESEARCH.md assumed a different normalisation scheme. The fix aligns weights with the actual per-category normalisation, matching the documented design intent that "one strong signal is sufficient for classification."

## Issues Encountered

None beyond the weight calibration deviation above.

## User Setup Required

External services require manual configuration:
- **ANTHROPIC_API_KEY** must be set before `classify_test()` or `estimate_run_cost()` can make LLM API calls.
- The rule engine (`run_rule_engine`) works without any API key — no LLM is called.
- Get API key: Anthropic Console -> API Keys -> Create new key
- Add to environment: `export ANTHROPIC_API_KEY="sk-ant-..."`

## Next Phase Readiness

- `src/classifier/` package is fully importable and all public API symbols are exported
- Rule engine classifies tests with strong KG signals deterministically (no API cost)
- LLM client ready for API calls once ANTHROPIC_API_KEY is set
- Cost estimator ready for pre-flight estimation
- Phase 4-02 (analytics, SQLite persistence) can import `ClassificationResult` and use `classify_test()` output directly

## Self-Check: PASSED

All created files verified present on disk. Both task commits confirmed in git log.

- FOUND: src/classifier/__init__.py
- FOUND: src/classifier/models.py
- FOUND: src/classifier/rule_engine.py
- FOUND: src/classifier/llm_client.py
- FOUND: src/classifier/cost_estimator.py
- FOUND: .planning/phases/04-classification-engine-and-insights/04-01-SUMMARY.md
- Commit be6025f: feat(04-01): implement ClassificationResult model and weighted rule engine
- Commit 32e4ee7: feat(04-01): implement LLM client with forced tool_use and pre-flight cost estimator

---
*Phase: 04-classification-engine-and-insights*
*Completed: 2026-03-02*
