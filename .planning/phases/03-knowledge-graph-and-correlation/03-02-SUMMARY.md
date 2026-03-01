---
phase: 03-knowledge-graph-and-correlation
plan: "02"
subsystem: api
tags: [pydantic, correlation, knowledge-graph, regex, url-normalization, cloudshare]

# Dependency graph
requires:
  - phase: 03-01
    provides: load_kg(), compile_failure_patterns(), CompiledFailurePattern, cloudshare_kg.json with 87 endpoints and 11 failure patterns
  - phase: 02-01
    provides: ParsedTestRun, ParsedTestSuite, ParsedTest, ParsedSpecAnalysis Pydantic models
provides:
  - EndpointMatch, FailurePatternMatch, CorrelatedTest, CorrelatedTestRun Pydantic v2 output models (Phase 3->4 interface)
  - normalize_endpoint_path(): URL normalization handling absolute URLs, root-relative, template literals, Express params, UUIDs, numeric IDs
  - match_endpoint_to_kg(): exact + prefix KG matching with false-match prevention
  - match_error_against_patterns(): pre-compiled regex matching with 50KB truncation guard
  - correlate_test_run(): full CORR-01 + CORR-02 pipeline against failing/flaky tests only
  - Updated src/knowledge_graph/__init__.py re-exporting all models and correlator symbols
affects: [04-classification-engine, phase-4]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "CORR-01: normalize endpoint path then exact/prefix match against KG path_pattern for infra layer attribution"
    - "CORR-02: pre-compiled regex search across concatenated error text (message + stack + retries) for failure pattern identification"
    - "lru_cache(maxsize=512) on normalize_endpoint_path() — safe because raw endpoint strings repeat across tests in a suite"
    - "50KB truncation guard on error text prevents catastrophic regex backtracking on large stack traces"
    - "Confidence 1.0 if any KG match found, 0.5 if no match — enables Phase 4 to weight uncertain correlations"

key-files:
  created:
    - src/knowledge_graph/models.py
    - src/knowledge_graph/correlator.py
  modified:
    - src/knowledge_graph/__init__.py

key-decisions:
  - "Collect unmatched endpoints in CorrelatedTestRun.unmatched_endpoints (not silently dropped) to surface KG coverage gaps to Phase 4"
  - "Only 'unexpected' and 'flaky' tests are correlated — 'expected' and 'skipped' excluded since they have no error signals"
  - "Endpoint matching uses both exact match and prefix match for action sub-paths (e.g., /api/v3/envs matches /api/v3/envs/actions/resume)"
  - "Error text concatenates first_error_message, first_error_stack, and all retry attempts — research showed error signatures sometimes appear in retry error text, not just the first attempt"

patterns-established:
  - "CORR-01 endpoint matching pattern: normalize -> generalize IDs -> exact match -> prefix match"
  - "CORR-02 error matching pattern: compile at startup, search concatenated error text, return (pattern, matched_substr) tuples for explainability"

# Metrics
duration: ~15min (implementation session; elapsed calendar time larger due to session gap)
completed: 2026-03-01
---

# Phase 3 Plan 02: Correlation Engine Summary

**Deterministic CORR-01/CORR-02 correlation engine wiring Phase 2 ParsedTestRun to Phase 3 KG via URL normalization, endpoint-to-infra matching, and pre-compiled error pattern regex matching**

## Performance

- **Duration:** ~15 min (implementation)
- **Started:** 2026-02-26T16:20:52Z
- **Completed:** 2026-03-01T16:34:11Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Built four Pydantic v2 output models (EndpointMatch, FailurePatternMatch, CorrelatedTest, CorrelatedTestRun) forming the Phase 3 to Phase 4 interface
- Implemented normalize_endpoint_path() handling all 5 URL formats (absolute URL, root-relative, relative, template literal ${envId}, Express-style :param) plus UUID and numeric ID generalization
- Implemented correlate_test_run() wiring ParsedTestRun through CORR-01 (endpoint -> infra layer) and CORR-02 (error text -> failure pattern) with proper test status filtering and unmatched endpoint tracking

## Task Commits

Each task was committed atomically:

1. **Task 1: CorrelatedTest Pydantic v2 output models** - `8d1d8c7` (feat)
2. **Task 2: Correlation engine — normalization, matching, and correlate_test_run()** - `f9e0d26` (feat)

**Plan metadata:** (pending docs commit)

## Files Created/Modified

- `src/knowledge_graph/models.py` - Four Pydantic v2 models: EndpointMatch, FailurePatternMatch, CorrelatedTest, CorrelatedTestRun
- `src/knowledge_graph/correlator.py` - normalize_endpoint_path(), match_endpoint_to_kg(), match_error_against_patterns(), correlate_test_run()
- `src/knowledge_graph/__init__.py` - Updated to re-export all models and correlator symbols (14 total exports)

## Decisions Made

- Collect unmatched endpoints in CorrelatedTestRun.unmatched_endpoints rather than silently dropping them — lets Phase 4 surface KG coverage gaps to users
- Only 'unexpected' and 'flaky' tests are processed; 'expected' (passing) and 'skipped' tests excluded since they have no error signals to correlate
- Endpoint matching uses exact match plus prefix match to handle action sub-paths without false substring matches
- Error text search concatenates message + stack across all retry attempts since research showed error signatures sometimes appear in retry text, not just first_error_message

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None. The plan's `match_endpoint_to_kg()` with `/api/v3/envs` correctly matches multiple KG entries (envs_list, envs_create, envs_update, envs_patch) since the KG has separate entries per HTTP method for the same path — this is correct behavior per the plan's success criteria.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 4 classification engine can now import `correlate_test_run` from `src.knowledge_graph` and receive `CorrelatedTestRun` output
- `has_infra_signal`, `has_auth_signal`, `has_async_signal` convenience flags on CorrelatedTest eliminate need for Phase 4 to rescan lists for common patterns
- `correlation_confidence` (1.0 = KG matched, 0.5 = no match) enables Phase 4 rule engine to weight uncertain correlations differently
- `unmatched_endpoints` on CorrelatedTestRun enables Phase 4 to surface KG coverage gaps

## Self-Check: PASSED

- FOUND: src/knowledge_graph/models.py
- FOUND: src/knowledge_graph/correlator.py
- FOUND: .planning/phases/03-knowledge-graph-and-correlation/03-02-SUMMARY.md
- FOUND: commit 8d1d8c7 (feat(03-02): add CorrelatedTest Pydantic v2 output models)
- FOUND: commit f9e0d26 (feat(03-02): implement correlation engine and update package exports)

---
*Phase: 03-knowledge-graph-and-correlation*
*Completed: 2026-03-01*
