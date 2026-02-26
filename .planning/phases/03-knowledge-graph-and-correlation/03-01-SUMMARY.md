---
phase: 03-knowledge-graph-and-correlation
plan: "01"
subsystem: knowledge-graph
tags: [json, knowledge-graph, cloudshare, regex, lru_cache, dataclass, pattern-matching]

# Dependency graph
requires:
  - phase: 02-parse-and-ingest
    provides: ParsedSpecAnalysis.api_endpoints used by Phase 4 correlation engine
provides:
  - src/knowledge_graph/cloudshare_kg.json — 87 CloudShare V3/V4 endpoints and 11 failure patterns
  - src/knowledge_graph/loader.py — load_kg() singleton, _validate_kg(), compile_failure_patterns()
  - src/knowledge_graph/__init__.py — package re-exporting public API
affects:
  - 03-02 (correlation engine — uses load_kg() and compile_failure_patterns())
  - 04-rule-engine (uses CompiledFailurePattern for log-to-pattern matching)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Static JSON knowledge graph committed to repo — no runtime API calls needed"
    - "@lru_cache(maxsize=1) singleton loader — JSON file read exactly once per process"
    - "dataclass CompiledFailurePattern — pre-compiled re.Pattern objects at startup"
    - "Schema validation at load time — ValueError raised before invalid KG can be cached"

key-files:
  created:
    - src/knowledge_graph/cloudshare_kg.json
    - src/knowledge_graph/loader.py
    - src/knowledge_graph/__init__.py
  modified: []

key-decisions:
  - "Hand-authored KG JSON — CloudShare V3 docs are HTML-only, no machine-readable OpenAPI/Swagger spec"
  - "V4/Accelerate endpoints added as low-confidence placeholders — Stoplight SPA blocks programmatic access"
  - "lru_cache on load_kg() not compile_failure_patterns() — list of dataclasses with compiled patterns should not be long-lived cached at module level; caller controls lifetime"
  - "Validation runs inside load_kg() before caching — broken KG always raises, never silently caches invalid data"

patterns-established:
  - "KG JSON must maintain: lowercase path_patterns, infra_layer as array, failure_patterns as id string references"
  - "Failure pattern IDs in endpoints array are string references to failure_patterns[].id — validated at load time"

# Metrics
duration: 181min
completed: 2026-02-26
---

# Phase 3 Plan 01: CloudShare Knowledge Graph Summary

**Static CloudShare KG JSON with 87 V3/V4 endpoints and 11 failure patterns, plus singleton Python loader with schema validation and pre-compiled regex pattern compiler**

## Performance

- **Duration:** ~18 min (181 min wall clock includes research and setup)
- **Started:** 2026-02-26T13:14:26Z
- **Completed:** 2026-02-26T16:16:13Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Authored cloudshare_kg.json with 87 endpoints (82 V3 + 5 V4 placeholders) mapped to infra layers (CSC, PCS, WebApp, ExperienceService, Predictor), async flags, duration thresholds, and failure pattern references
- All 8 required failure patterns present: vmware_esx_timeout, netapp_nfs_contention, azure_service_bus_delay, aws_sqs_delay, redis_cache_staleness, vlan_ip_exhaustion, predictor_ml_failure, rbac_jwt_expiry — plus 3 additional: aws_ami_sharing, terraform_failure, eventual_consistency
- load_kg() singleton with @lru_cache(maxsize=1) guarantees single JSON read per process; _validate_kg() enforces schema correctness before caching
- compile_failure_patterns() pre-compiles all 11 regex patterns into CompiledFailurePattern dataclasses ready for Phase 4

## Task Commits

Each task was committed atomically:

1. **Task 1: cloudshare_kg.json — full endpoint registry and failure pattern library** - `a0ac673` (feat)
2. **Task 2: KG loader module with singleton, validation, and pattern compiler** - `d141d54` (feat)

## Files Created/Modified

- `src/knowledge_graph/cloudshare_kg.json` — 87 endpoint entries and 11 failure pattern entries; hand-authored from CloudShare V3 HTML docs and architecture brief
- `src/knowledge_graph/loader.py` — load_kg() with lru_cache, _validate_kg() schema enforcer, compile_failure_patterns() returning list[CompiledFailurePattern]
- `src/knowledge_graph/__init__.py` — package init re-exporting load_kg, compile_failure_patterns, CompiledFailurePattern, KG_PATH

## Decisions Made

- **Hand-authored KG:** CloudShare V3 REST API docs are traditional HTML pages with no machine-readable OpenAPI/Swagger spec. Hand-documentation is the only viable approach; the research phase confirmed this.
- **V4 as low-confidence placeholders:** Accelerate API is hosted on Stoplight as a JavaScript-rendered SPA — cannot be fetched programmatically. Five V4 experience endpoints included with `"confidence": "low"`.
- **lru_cache on load_kg() only:** compile_failure_patterns() returns a list of dataclasses containing compiled re.Pattern objects. Caching at module level would prevent garbage collection and the caller controls lifetime — left uncached by design.
- **Validation inside load_kg() before caching:** A broken KG always raises ValueError rather than silently caching invalid data that would cause all correlations to return empty results.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None — JSON parsed correctly on first attempt, all path_patterns were authored lowercase, all infra_layer fields were JSON arrays. Python import resolution worked without modification since the project uses src/ package layout already established in Phase 1.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- load_kg() and compile_failure_patterns() are ready for import in Phase 3 Plan 02 (correlation engine)
- CompiledFailurePattern dataclass provides the interface for Phase 4 rule engine log-pattern matching
- KG_PATH constant exposed for test fixtures that need to mock or validate the JSON file
- No blockers — all 5 success criteria met: JSON valid, 70+ endpoints, 11 failure patterns, all paths lowercase, singleton caching verified

---
*Phase: 03-knowledge-graph-and-correlation*
*Completed: 2026-02-26*

## Self-Check: PASSED

- src/knowledge_graph/cloudshare_kg.json: FOUND
- src/knowledge_graph/loader.py: FOUND
- src/knowledge_graph/__init__.py: FOUND
- 03-01-SUMMARY.md: FOUND
- Commit a0ac673: FOUND
- Commit d141d54: FOUND
