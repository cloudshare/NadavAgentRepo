# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-17)

**Core value:** Engineers get immediate, actionable system-level intelligence about build failures and test health — not just raw results, but synthesized root-cause hypotheses, risk scores, and prioritized next steps — delivered to Slack the moment a build finishes.
**Current focus:** Phase 3: Correlate and Classify

## Current Position

Phase: 2 of 5 (Parse and Ingest)
Plan: 2 of 2 in current phase — PHASE COMPLETE
Status: Phase 2 complete — ready for Phase 3 (Correlate and Classify)
Last activity: 2026-02-26 — 02-02 complete (tree-sitter spec parser, monitoring parser, isolation runner)

Progress: [████░░░░░░] 33.3% (4 of 12 total plans complete — Phases 1 and 2 done)

## Performance Metrics

**Velocity:**
- Total plans completed: 4
- Average duration: ~4 minutes
- Total execution time: ~0.3 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01 | 2 | 343s | 172s |
| 02 | 2 | ~11 min | ~5.5 min |

**Recent Executions:**

| Plan | Duration | Tasks | Files | Date |
|------|----------|-------|-------|------|
| Phase 02 P02 | 353s | 2 tasks | 6 files | 2026-02-26 |
| Phase 02-parse-and-ingest P01 | 5min | 2 tasks | 4 files | 2026-02-26 |
| Phase 01 P02 | 190s | 2 tasks | 2 files | 2026-02-18 |
| Phase 01 P01 | 153s | 2 tasks | 7 files | 2026-02-18 |

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

### Pending Todos

None yet.

### Blockers/Concerns

- [Phase 3 flag]: CloudShare API doc format needs validation before writing the crawler — Stoplight vs raw HTML vs Swagger YAML structure unknown until tested against actual docs
- [Phase 4 flag]: Rule engine confidence thresholds (0.8 cutoff) and flakiness baseline need calibration against real log samples

## Session Continuity

Last session: 2026-02-26 (plan execution)
Stopped at: Completed 02-02-PLAN.md — tree-sitter spec parser, monitoring parser, isolation runner, and extended parse_logs() all implemented and committed
Resume file: None

---
*State initialized: 2026-02-17*
*Last updated: 2026-02-26 after completing plan 02-02 (Phase 2 complete)*
