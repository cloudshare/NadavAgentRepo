---
phase: 02-parse-and-ingest
plan: "02"
subsystem: parsing
tags: [tree-sitter, typescript, ast, monitoring, newrelic, splunk, app-insights, aiofiles]

# Dependency graph
requires:
  - phase: 02-01
    provides: "ParsedTestSuite, ParsedTestRun, ParseWarning models; json_reporter; stdout_reporter; parse_logs() entry point"
provides:
  - "src/parsers/spec_parser.py — parse_spec_files(folder) via tree-sitter TypeScript AST"
  - "src/parsers/monitoring.py — parse_monitoring_logs(folder) best-effort JSON/CSV/text"
  - "src/parsers/runner.py — parse_folder_with_isolation() shared isolation utility"
  - "parse_logs() extended with spec_folder and monitoring_folder optional params"
  - "ParsedTestSuite.monitoring_entries field and 'monitoring_log' source_type"
affects:
  - phase-03-correlate
  - phase-04-classify

# Tech tracking
tech-stack:
  added:
    - tree-sitter==0.23.2 (TypeScript AST parsing)
    - tree-sitter-typescript==0.23.2 (TypeScript grammar)
    - aiofiles>=24.0.0 (added to requirements.txt; asyncio.to_thread used for I/O)
  patterns:
    - "Module-level Language + Parser instantiation (expensive, done once at import time)"
    - "Module-level Query objects (expensive to construct, reused across calls)"
    - "Python-side predicate filtering: tree-sitter 0.23.2 Python bindings do NOT auto-apply predicates; Query.matches() used with manual Python filtering"
    - "parse_folder_with_isolation() as single shared FNDTN-04 isolation pattern"
    - "Best-effort parsing: JSON -> CSV -> plain text fallback chain"

key-files:
  created:
    - src/parsers/spec_parser.py
    - src/parsers/monitoring.py
    - src/parsers/runner.py
  modified:
    - src/parsers/__init__.py
    - src/parsers/models.py
    - requirements.txt

key-decisions:
  - "Use Query.matches() with manual Python filtering instead of trusting predicate auto-application — tree-sitter 0.23.2 Python bindings do not filter on #eq?/#any-of? automatically"
  - "tstype.language_typescript() not tstype.typescript() — correct function name for 0.23.2 grammar module"
  - "No QueryCursor in tree-sitter 0.23.2 Python bindings — use Query.captures(node) directly returning dict[str, list[Node]]"
  - "monitoring_entries stored as list[dict] in ParsedTestSuite — Phase 3 correlation queries them separately from test results"
  - "Monitoring parser uses best-effort JSON -> CSV -> plain-text fallback; unrecognised/empty files become ParseWarning not exceptions"

patterns-established:
  - "parse_folder_with_isolation: single shared implementation for FNDTN-04 — all parsers route through this"
  - "source_type Literal extended progressively: json_reporter | stdout_reporter | spec_analysis | monitoring_log"
  - "Tree-sitter queries are module-level constants; QueryCursor instances are NOT (create per-call)"

# Metrics
duration: 6min
completed: 2026-02-26
---

# Phase 2 Plan 02: Spec Parser and Monitoring Log Parser Summary

**tree-sitter TypeScript AST spec parser extracting test names, describe hierarchy, API endpoints, page.goto() URLs, fragile locators, and hard-coded waits — plus best-effort monitoring log parser (NewRelic/Splunk/App Insights) and centralized per-file isolation runner**

## Performance

- **Duration:** ~6 min
- **Started:** 2026-02-26T06:31:09Z
- **Completed:** 2026-02-26T06:37:02Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- Implemented tree-sitter 0.23.x TypeScript spec parser that correctly extracts all 6 target fields from .spec.ts files using proper 0.23.2 API (Language, Parser, Query)
- Implemented best-effort monitoring log parser handling JSON (NewRelic/App Insights), CSV (Splunk), and plain-text formats with graceful degradation to ParseWarning
- Centralized per-file error isolation into parse_folder_with_isolation() so all parsers share identical FNDTN-04 semantics
- Extended parse_logs() entry point with optional spec_folder and monitoring_folder params, merging all sources into a single ParsedTestRun

## Task Commits

Each task was committed atomically:

1. **Task 1: tree-sitter TypeScript spec parser** - `6af4f9d` (feat)
2. **Task 2: Monitoring parser, isolation runner, and parse_logs() extension** - `97239bd` (feat)

**Plan metadata:** (docs commit — see below)

## Files Created/Modified

- `src/parsers/spec_parser.py` — tree-sitter AST parser; parse_spec_files(folder) returns ParsedTestRun with spec_analysis populated on each suite
- `src/parsers/monitoring.py` — best-effort monitoring log parser; parse_monitoring_logs(folder) handles JSON/CSV/text with ParseWarning on unrecognised files
- `src/parsers/runner.py` — parse_folder_with_isolation() shared FNDTN-04 isolation utility using asyncio.gather + return_exceptions=True
- `src/parsers/__init__.py` — parse_logs() extended with spec_folder and monitoring_folder optional params
- `src/parsers/models.py` — ParsedTestSuite.source_type Literal includes "monitoring_log"; monitoring_entries: list[dict] field added
- `requirements.txt` — added tree-sitter==0.23.2, tree-sitter-typescript==0.23.2, aiofiles>=24.0.0

## Decisions Made

- **tree-sitter predicate filtering is manual**: The 0.23.2 Python bindings do not auto-apply `#eq?` and `#any-of?` predicates. Query.matches() returns all structural matches; Python code filters by checking captured node text values. This was discovered during implementation and corrected without user intervention (Rule 1 auto-fix).
- **tstype.language_typescript() not tstype.typescript()**: The plan specified `Language(tstype.typescript())` but the correct 0.23.2 API is `Language(tstype.language_typescript())`. Fixed automatically.
- **No QueryCursor in 0.23.2**: The plan referenced QueryCursor (from a different version), which does not exist in this release. Used `Query.captures(node)` and `Query.matches(node)` directly.
- **monitoring_entries as list[dict]**: Phase 3 correlation needs raw log entries queryable separately from test results; stored in dedicated field rather than reusing parse_warnings.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Corrected tree-sitter 0.23.2 API — tstype.language_typescript() not tstype.typescript()**
- **Found during:** Task 1 (spec parser implementation)
- **Issue:** Plan specified `Language(tstype.typescript())` but module exposes `language_typescript()` (and `language_tsx()`)
- **Fix:** Used `Language(tstype.language_typescript())` throughout spec_parser.py
- **Files modified:** src/parsers/spec_parser.py
- **Verification:** `Language(tstype.language_typescript())` instantiates cleanly; import passes
- **Committed in:** 6af4f9d (Task 1 commit)

**2. [Rule 1 - Bug] QueryCursor does not exist in tree-sitter 0.23.2 Python bindings**
- **Found during:** Task 1 (spec parser implementation)
- **Issue:** Plan's code pattern used `from tree_sitter import QueryCursor` + `QueryCursor(query).captures(node)` — this class does not exist in 0.23.2
- **Fix:** Used `Query.captures(node)` (returns dict[str, list[Node]]) and `Query.matches(node)` (returns list of (pattern_idx, dict) tuples) directly
- **Files modified:** src/parsers/spec_parser.py
- **Verification:** All 6 extraction fields correctly populated in test run
- **Committed in:** 6af4f9d (Task 1 commit)

**3. [Rule 1 - Bug] tree-sitter 0.23.2 predicates are not auto-applied by Python bindings**
- **Found during:** Task 1 (spec parser implementation)
- **Issue:** Plan assumed `(#eq? @method "goto")` and `(#any-of? @fn "test" "it")` would filter matches automatically. Testing revealed all structural matches are returned regardless of predicates — `foo("a")` and `bar("a")` both match `(call_expression function: (identifier) @fn arguments: (arguments (string) @arg)) (#eq? @fn "foo")`
- **Fix:** Applied Python-side filtering in all extraction functions: checked `.text.decode("utf-8")` values of captured nodes against expected sets before adding to results
- **Files modified:** src/parsers/spec_parser.py
- **Verification:** Comprehensive test with test/it/describe/goto/locator/waitForTimeout in one spec file returns correctly separated results
- **Committed in:** 6af4f9d (Task 1 commit)

---

**Total deviations:** 3 auto-fixed (all Rule 1 — incorrect API assumptions in plan)
**Impact on plan:** All fixes necessary for correct operation. The plan was written for a version of tree-sitter that differs from what pip installs. No scope creep; all functional requirements met exactly as specified.

## Issues Encountered

None beyond the API deviations documented above.

## User Setup Required

None — tree-sitter packages installed automatically via pip. No external service configuration required.

## Next Phase Readiness

- Phase 3 (correlate): parse_logs() now returns merged ParsedTestRun from all three sources (Playwright logs, spec AST analysis, monitoring logs). Correlation logic has all inputs available.
- ParsedTestSuite.spec_analysis provides test_names, describe_hierarchy, api_endpoints, goto_urls, fragile_locators, hard_coded_wait_ms for each .spec.ts file.
- ParsedTestSuite.monitoring_entries provides raw normalised log records (timestamp/message/level) for each monitoring file.
- parse_folder_with_isolation() is available for any future parsers added in Phase 3+.

## Self-Check: PASSED

All created files verified present:
- src/parsers/spec_parser.py — FOUND
- src/parsers/monitoring.py — FOUND
- src/parsers/runner.py — FOUND
- src/parsers/__init__.py — FOUND
- src/parsers/models.py — FOUND
- requirements.txt — FOUND
- .planning/phases/02-parse-and-ingest/02-02-SUMMARY.md — FOUND

All task commits verified:
- 6af4f9d (Task 1: tree-sitter spec parser) — FOUND
- 97239bd (Task 2: monitoring parser + runner + parse_logs extension) — FOUND

---
*Phase: 02-parse-and-ingest*
*Completed: 2026-02-26*
