# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-17)

**Core value:** Engineers get immediate, actionable system-level intelligence about build failures and test health — not just raw results, but synthesized root-cause hypotheses, risk scores, and prioritized next steps — delivered to Slack the moment a build finishes.
**Current focus:** Phase 4: Classification Engine and Insights

## Current Position

Phase: 4 of 5 (Classification Engine and Insights)
Plan: 1 of 3 in current phase — 04-01 complete
Status: Phase 4 in progress — 04-01 (classifier package: rule engine, LLM client, cost estimator) done. Ready for 04-02.
Last activity: 2026-03-02 — 04-01 complete (src/classifier package: models, rule_engine, llm_client, cost_estimator)

Progress: [███████░░░] 58% (7 of 12 total plans complete — Phases 1, 2, 3, and 04-01 done)

## Performance Metrics

**Velocity:**
- Total plans completed: 5
- Average duration: ~5 minutes
- Total execution time: ~0.4 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01 | 2 | 343s | 172s |
| 02 | 2 | ~11 min | ~5.5 min |
| 03 | 2 | ~33 min | ~16.5 min |
| 04 | 1 (in progress) | 6 min | 6 min |

**Recent Executions:**

| Plan | Duration | Tasks | Files | Date |
|------|----------|-------|-------|------|
| Phase 04-01 | 6 min | 2 tasks | 5 files | 2026-03-02 |
| Phase 03-02 | ~15 min | 2 tasks | 3 files | 2026-03-01 |
| Phase 03-01 | ~18 min | 2 tasks | 3 files | 2026-02-26 |
| Phase 02 P02 | 353s | 2 tasks | 6 files | 2026-02-26 |
| Phase 02-parse-and-ingest P01 | 5min | 2 tasks | 4 files | 2026-02-26 |
| Phase 01 P02 | 190s | 2 tasks | 2 files | 2026-02-18 |
| Phase 01 P01 | 153s | 2 tasks | 7 files | 2026-02-18 |
| Phase 05-dashboard P01 | 5 | 2 tasks | 15 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- External service over TeamCity plugin: Keeps AI credentials off TeamCity agents, easier to iterate
- Query TeamCity for history vs local DB: Simpler architecture, one fewer data store to manage
- Claude API for analysis: Powerful reasoning for system-level synthesis across many signals
- Local filesystem for artifacts: Simplest storage for v1, can add S3/TeamCity upload later
- Create new Slack bot: No existing bot available, need full Slack integration
- [Phase 01-01]: Use Pydantic BaseModel with manual YAML merging for explicit configuration control
- [Phase 01-01]: Return 202 Accepted from webhook endpoint to indicate async processing pattern
- [Phase 01-02]: Sequential processing to prevent resource contention during analysis (later phases)
- [Phase 01-02]: In-memory deduplication with time-based pruning (lost on restart acceptable for v1)
- [Phase 01-02]: HMAC validation optional for development/testing with warning logged
- [Phase 01-02]: Green build lightweight handling - skip full analysis for SUCCESS builds
- [Phase 02-01]: asyncio.to_thread used for file reads instead of aiofiles to avoid extra dependency
- [Phase 02-01]: First-real-error heuristic: network > timeout > assertion priority; confidence flag distinguishes direct vs reordered selection
- [Phase 02-01]: Top-level Playwright suite errors surfaced as ParseWarning on suite, not top-level ParsedTestRun.warnings
- [Phase 02-02]: tree-sitter 0.23.2 Python bindings do NOT auto-apply predicates — Python-side filtering required via Query.matches() with manual node text checks
- [Phase 02-02]: tstype.language_typescript() (not tstype.typescript()) is the correct 0.23.2 grammar function name
- [Phase 02-02]: monitoring_entries stored as list[dict] in ParsedTestSuite for Phase 3 correlation queries
- [Phase 02-02]: Monitoring parser uses best-effort JSON -> CSV -> plain-text fallback; empty/unrecognised files become ParseWarning not exceptions
- [Phase 03-01]: Hand-authored KG JSON — CloudShare V3 docs are HTML-only, no machine-readable OpenAPI/Swagger spec
- [Phase 03-01]: V4/Accelerate endpoints added as low-confidence placeholders — Stoplight SPA blocks programmatic access
- [Phase 03-01]: lru_cache on load_kg() only, not compile_failure_patterns() — list of dataclasses with compiled patterns should not be long-lived cached at module level
- [Phase 03-01]: Schema validation runs inside load_kg() before caching — broken KG always raises ValueError, never silently caches invalid data
- [Phase 03-02]: Unmatched endpoints collected in CorrelatedTestRun.unmatched_endpoints (not silently dropped) to surface KG coverage gaps to Phase 4
- [Phase 03-02]: Only 'unexpected' and 'flaky' tests correlated — 'expected' and 'skipped' excluded since they have no error signals
- [Phase 03-02]: Endpoint matching uses exact match + prefix match for action sub-paths; full path segment comparison prevents false substring matches
- [Phase 03-02]: Error text concatenates message + stack across all retry attempts — error signatures can appear in retry text, not just first_error_message
- [Phase 04-01]: Signal weights use 0.9/0.1 primary/secondary split for KG-backed categories so a single strong signal reaches RULE_CONFIDENCE_THRESHOLD independently
- [Phase 04-01]: product_regression signals use lower weights (0.6/0.65) so catch-all absence-of-other-signals alone does NOT hit threshold — requires LLM confirmation
- [Phase 04-01]: LLM_UNCERTAIN_FLOOR (0.6) applied inside classify_with_llm() for single enforcement point
- [Phase 04-01]: correlation_confidence < 1.0 (no KG match) triggers sonnet escalation — more capable model for less context-rich cases
- [Phase 05-dashboard]: SPAStaticFiles wrapped in try/except so server starts cleanly before npm run build is run
- [Phase 05-dashboard]: Pipeline loads KG internally (lru_cache handles caching); correlate_test_run called with correct 3-arg signature
- [Phase 05-dashboard]: react-router v7 unified package — all imports use 'react-router' not 'react-router-dom'

### Pending Todos

None yet.

### Blockers/Concerns

- [Phase 3 flag RESOLVED]: CloudShare V3 docs confirmed HTML-only, V4 Accelerate confirmed Stoplight SPA — KG hand-authored with V4 placeholders
- [Phase 4 flag PARTIAL]: Rule engine confidence thresholds implemented as named constants (RULE_CONFIDENCE_THRESHOLD=0.8, LLM_UNCERTAIN_FLOOR=0.6). Initial weight calibration done; real-sample calibration still needed post-MVP.
- [Phase 4 flag]: Flakiness baseline (SQLite tracking) not yet implemented — planned for 04-02.

## Session Continuity

Last session: 2026-03-02 (plan execution)
Stopped at: Completed 04-01-PLAN.md — classifier package (models, rule_engine, llm_client, cost_estimator) implemented and committed.
Resume file: None

---
*State initialized: 2026-02-17*
*Last updated: 2026-03-02 after completing plan 04-01 (classifier engine core)*
