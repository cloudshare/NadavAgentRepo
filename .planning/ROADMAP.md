# Roadmap: QA Intelligence Agent

## Overview

This roadmap delivers a webhook-driven QA intelligence service that transforms raw TeamCity build data into actionable engineering insights using Claude AI. The journey progresses from reliable webhook infrastructure through data normalization and AI analysis to multi-format reporting and Slack delivery. Each phase builds on the previous, establishing patterns that prevent critical pitfalls (webhook timeouts, uncontrolled LLM costs, context overflow) while delivering incremental value toward the complete system-level synthesis capability that differentiates this service from per-test analyzers.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Webhook Foundation** - Reliable async webhook ingestion with security and idempotency (completed 2026-02-18)
- [ ] **Phase 2: Data Pipeline** - TeamCity integration, JUnit parsing, and LLM-optimized normalization
- [ ] **Phase 3: AI Intelligence** - Claude integration with token budgets, cost controls, and failure categorization
- [ ] **Phase 4: Classification Engine and Insights** - Deterministic rule engine + LLM classification, flakiness analytics, and structured JSON reporting

## Phase Details

### Phase 1: Webhook Foundation
**Goal**: Service reliably receives and processes TeamCity webhooks without timeouts or duplicates
**Depends on**: Nothing (first phase)
**Requirements**: HOOK-01, HOOK-02
**Success Criteria** (what must be TRUE):
  1. Service accepts TeamCity webhook POST and returns 202 Accepted in under 1 second
  2. Service processes build events asynchronously in background without blocking webhook endpoint
  3. Service prevents duplicate processing when webhooks are retried (idempotency via build IDs)
  4. Service validates webhook signatures via HMAC to reject unauthorized requests
**Plans**: 2 plans

Plans:
- [x] 01-01-PLAN.md — Application foundation: config system, models, FastAPI app with health and webhook endpoints
- [x] 01-02-PLAN.md — Background processing: async queue, HMAC validation, branch filtering, idempotency

### Phase 2: Data Pipeline
**Goal**: Service fetches, parses, and normalizes all TeamCity data into LLM-ready format
**Depends on**: Phase 1
**Requirements**: DATA-01, DATA-02, DATA-03, DATA-04, DATA-05
**Success Criteria** (what must be TRUE):
  1. Service fetches build metadata (status, duration, branch, commit) from TeamCity REST API
  2. Service parses JUnit XML test results into structured test data with pass/fail/skip status
  3. Service extracts AI Quality Analyzer insights from TeamCity build artifacts
  4. Service queries historical builds to provide flaky test and regression context
  5. Service produces normalized packet with flat structure, descriptive keys, and historical context ready for LLM consumption
**Plans**: 3 plans

Plans:
- [ ] 02-01-PLAN.md — TeamCity API client with auth/retry and data pipeline models
- [ ] 02-02-PLAN.md — JUnit XML parser and AI Quality Analyzer insight extraction
- [ ] 02-03-PLAN.md — Historical build context with caching, LLM packet normalization, and queue integration

### Phase 3: AI Intelligence
**Goal**: Service sends normalized data to Claude and receives system-level analysis with cost controls
**Depends on**: Phase 2
**Requirements**: AI-01, AI-02, AI-03, AI-04
**Success Criteria** (what must be TRUE):
  1. Service sends normalized packet to Claude API and receives structured analysis synthesizing all test results
  2. Service categorizes failures into product regression, environment/infra, flaky test, data issue, or dependency failure
  3. Service enforces per-request token budget (50K max) to prevent runaway costs
  4. Service selects appropriate Claude model based on build complexity (Haiku for simple, Opus for complex failures)
**Plans**: TBD

Plans:
- TBD (to be defined during phase planning)

### Phase 4: Classification Engine and Insights
**Goal**: Every failing test is classified into its true root cause category with a probability score, backed by deterministic rules first and LLM reasoning only for uncertain cases, and the full insight suite (flakiness index, heatmaps, ratios, retry analysis) is computed and exportable as structured JSON
**Depends on**: Phases 2 (parsers) and 3 (knowledge graph and correlation)
**Requirements**: CLASS-01, CLASS-02, CLASS-03, CLASS-04, CLASS-05, CLASS-06, INSGT-01, INSGT-02, INSGT-03, INSGT-04, OUT-01, OUT-02
**Success Criteria** (what must be TRUE):
  1. Failing tests are classified into one of 8 categories by a weighted rule engine (no LLM call when confidence >= 0.8)
  2. When rule confidence < 0.8, Claude API is called with forced tool_use; haiku for triage, sonnet for complex
  3. Every classification has a probability score 0–1 and "uncertain" label when score < 0.6
  4. Pre-flight token count and estimated cost are displayed before any inference runs
  5. Every classified test has an actionable CloudShare-domain fix recommendation and NL root cause summary
  6. Flakiness index, endpoint heatmap, and infra/app/test-design ratios are queryable from SQLite
  7. Total tokens and cost per run are stored in SQLite and returnable via API
**Plans**: 3 plans

Plans:
- [ ] 04-01-PLAN.md — Rule engine (8 categories, weighted signals, named constants) and LLM client (haiku/sonnet routing, forced tool_use, cost estimation)
- [ ] 04-02-PLAN.md — Fix recommendation module (DOMAIN_FIX_RECOMMENDATIONS) and NL summary generator wired into classify_test()
- [ ] 04-03-PLAN.md — SQLite schema (init_db), insight generators (flakiness index, heatmap, ratios), and structured JSON report builder

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Webhook Foundation | 2/2 | Complete | 2026-02-18 |
| 2. Data Pipeline | 0/3 | Planning complete | - |
| 3. AI Intelligence | 0/TBD | Not started | - |
| 4. Classification Engine and Insights | 0/3 | Planning complete | - |

---
*Roadmap created: 2026-02-17*
*Last updated: 2026-03-02 after Phase 4 planning*
