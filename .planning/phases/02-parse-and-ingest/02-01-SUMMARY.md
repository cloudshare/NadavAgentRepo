---
phase: 02-parse-and-ingest
plan: "01"
subsystem: parsing
tags: [pydantic, playwright, json-reporter, stdout-reporter, ansi, asyncio, log-parsing]

requires:
  - phase: 01-foundation
    provides: FastAPI app skeleton, BackgroundTasks async pattern, build queue worker

provides:
  - src/parsers/models.py with ParsedTestRun, ParsedTestSuite, ParsedTest, ParsedRetryResult, ParsedSpecAnalysis, ParseWarning Pydantic v2 models
  - src/parsers/json_reporter.py with parse_playwright_json(folder) async parser
  - src/parsers/stdout_reporter.py with parse_playwright_stdout(folder) async parser
  - src/parsers/__init__.py with parse_logs(folder) format-auto-detecting entry point

affects:
  - 02-02 (spec file parser — consumes same ParsedTestSuite/ParsedTestRun models)
  - 03-correlate (consumes ParsedTestRun from parse_logs())
  - 04-classify (consumes ParsedTest.first_error_message, first_error_confidence)

tech-stack:
  added:
    - pydantic v2 (already in stack — first use of BaseModel in parsers module)
    - asyncio.to_thread for non-blocking file reads
    - asyncio.gather with return_exceptions for concurrent per-file parsing
  patterns:
    - Per-file error isolation: each file wrapped in try/except, failures add ParseWarning not abort
    - format-auto-detection: .json presence routes to json_reporter, else stdout_reporter
    - First-real-error heuristic: network > timeout > assertion priority ranking

key-files:
  created:
    - src/parsers/models.py
    - src/parsers/json_reporter.py
    - src/parsers/stdout_reporter.py
    - src/parsers/__init__.py

key-decisions:
  - "asyncio.to_thread used for file reads instead of aiofiles — avoids extra dependency, equivalent for O(100) files"
  - "First-real-error heuristic: network > timeout > assertion priority; first_error_confidence='heuristic' when reordering applied"
  - "stdout_reporter committed in same PR as __init__.py since __init__ imports stdout_reporter"
  - "Top-level Playwright suite errors (e.g., config load failure) surfaced as ParseWarning on the suite, not as top-level run warnings"

patterns-established:
  - "Parser isolation: each parser returns Optional[ParsedTestSuite], callers add ParseWarning on None"
  - "Async parser signature: async def parse_playwright_*(folder: Path) -> ParsedTestRun"
  - "ANSI stripping: always strip before regex matching in stdout parsers"

duration: 5min
completed: 2026-02-26
---

# Phase 2 Plan 01: Parse and Ingest (Playwright Parsers) Summary

**Pydantic v2 normalized models plus async Playwright JSON reporter and stdout list-reporter parsers with first-real-error heuristic, ANSI stripping, and format-auto-detecting parse_logs() entry point**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-02-26T06:23:56Z
- **Completed:** 2026-02-26T06:28:20Z
- **Tasks:** 2 of 2
- **Files created:** 4

## Accomplishments

- Pydantic v2 normalized model hierarchy (ParsedTestRun -> ParsedTestSuite -> ParsedTest -> ParsedRetryResult) covering all fields needed by Phases 3-4
- parse_playwright_json() with recursive flatten_specs() handling arbitrarily nested describe() blocks, concurrent file parsing via asyncio.gather, and per-file error isolation
- First-real-error heuristic (network > timeout > assertion) with first_error_confidence flag distinguishing direct vs. reordered selection
- parse_playwright_stdout() with ANSI stripping, LIST_LINE_RE matching Unicode and ASCII status symbols, duration normalization (ms/s/m), and graceful handling of non-Playwright files
- parse_logs() auto-detection: .json files present -> json_reporter, otherwise -> stdout_reporter

## Task Commits

1. **Task 1: Pydantic v2 models and Playwright JSON reporter parser** - `6490f57` (feat)
2. **Task 2: Playwright stdout parser with ANSI stripping and format router** - `339e18b` (feat)

**Plan metadata:** (docs commit — see below)

## Files Created/Modified

- `src/parsers/models.py` — ParsedTestRun, ParsedTestSuite, ParsedTest, ParsedRetryResult, ParsedSpecAnalysis, ParseWarning Pydantic v2 models
- `src/parsers/json_reporter.py` — parse_playwright_json(folder), flatten_specs(), extract_first_error() with heuristic priority
- `src/parsers/stdout_reporter.py` — parse_playwright_stdout(folder), strip_ansi(), parse_duration_ms(), LIST_LINE_RE regex
- `src/parsers/__init__.py` — parse_logs(folder) format-auto-detecting router

## Decisions Made

- **asyncio.to_thread vs aiofiles:** Used asyncio.to_thread(file_path.read_bytes) for non-blocking file reads. Avoids the aiofiles dependency while achieving the same result for O(100) file sets.
- **stdout_reporter committed alongside __init__.py:** Since __init__.py imports from stdout_reporter, they were committed together in Task 2 to keep the package importable at every commit boundary.
- **Top-level Playwright errors -> suite parse_warnings:** When report.errors[] is non-empty but suites[] is empty (e.g., playwright.config.ts load failure), the errors are surfaced as ParseWarning items on the ParsedTestSuite, not on the top-level ParsedTestRun.warnings. This keeps suite-level concerns at the suite level.
- **First-error heuristic scope:** Heuristic applied to the first failed attempt's errors[] list. If first attempt passed (retry scenario), the second attempt's errors are used. Direct confidence when errors[0] is chosen without reordering.

## Deviations from Plan

None — plan executed exactly as written. All four files created per specification. stdout_reporter.py was implemented fully during Task 1 execution (to satisfy __init__.py import), and committed in the Task 2 commit as planned.

## Issues Encountered

None — all imports, round-trip tests, heuristic tests, and format-detection tests passed on first run.

## User Setup Required

None — no external service configuration required. parsers module is pure Python (stdlib + pydantic).

## Next Phase Readiness

- All four parser files ready: `src/parsers/__init__.py`, `models.py`, `json_reporter.py`, `stdout_reporter.py`
- parse_logs(folder) is the single entry point for downstream consumers (queue worker, Phase 3 correlator)
- ParsedTestRun model is stable for Phase 3 consumption
- Phase 02-02 can proceed immediately: spec_parser.py (tree-sitter TypeScript) will add a third ParsedTestSuite source_type="spec_analysis" reusing the same model hierarchy

---
*Phase: 02-parse-and-ingest*
*Completed: 2026-02-26*
