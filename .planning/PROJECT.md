# QA Intelligence Agent

## What This Is

A Python service that acts as an autonomous QA intelligence layer between TeamCity, an existing AI Quality Analyzer, and Slack. It receives TeamCity webhooks on build completion, fetches and normalizes build/test data, sends it to Claude for system-level analysis, and outputs structured engineering reports plus Slack alerts. It synthesizes per-test AI analyzer insights into higher-level build health, failure intelligence, and release risk assessments.

## Core Value

Engineers get immediate, actionable system-level intelligence about build failures and test health — not just raw results, but synthesized root-cause hypotheses, risk scores, and prioritized next steps — delivered to Slack the moment a build finishes.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Receive TeamCity webhooks on build finished/failed events
- [ ] Fetch build metadata, test occurrences, and artifacts via TeamCity REST API
- [ ] Parse JUnit XML test results into normalized structure
- [ ] Parse AI Quality Analyzer insights from TeamCity build artifacts
- [ ] Query TeamCity for historical builds to detect flaky patterns and regressions
- [ ] Normalize all data into a structured packet for Claude analysis
- [ ] Send normalized packet to Claude API for system-level intelligence
- [ ] Generate engineering-report.md (full technical report)
- [ ] Generate executive-summary.md (non-technical impact summary)
- [ ] Generate structured-insights.json (machine-readable analysis)
- [ ] Store generated artifacts on local filesystem
- [ ] Create Slack bot that posts formatted build alert summaries
- [ ] Produce build health assessment with severity and regression detection
- [ ] Group failures by category (product regression, infra, flaky, data issue, dependency)
- [ ] Detect performance regressions and slowest tests
- [ ] Score build stability, release readiness, and test infrastructure reliability (1-10)
- [ ] Correlate failures to recent commits and changed modules

### Out of Scope

- Cloud deployment — local-first for v1, deployment infra deferred
- Persistent local database — historical data comes from TeamCity API queries
- Dashboard / web UI — artifacts are files and Slack messages
- Mobile app notifications — Slack only
- Custom TeamCity plugin — runs as an external service
- Real-time log streaming — analyzes post-build, not during build

## Context

- TeamCity is the existing CI/CD system with build and test data
- An AI Quality Analyzer already runs per-test and produces insights (suspected failure reason, anomaly detection, performance commentary, stability signals, code-risk annotations) embedded as a separate tab in TeamCity per test run
- The quality analyzer outputs are available as build artifacts (quality-analyzer.json or similar)
- The agent's job is system-level synthesis, not re-doing per-test analysis
- Engineering team consumes results via Slack alerts and can drill into full reports on disk

## Constraints

- **Stack**: Python (FastAPI for webhook receiver, Anthropic SDK for Claude API, Slack SDK for bot)
- **AI Provider**: Claude API (Anthropic) for analysis — prompt-based, not fine-tuned
- **Data Source**: TeamCity REST API is the single source of truth for builds, tests, and artifacts
- **History**: No local persistence — flaky detection and trend analysis query TeamCity's build history each time
- **Deployment**: Local-first, no containerization or cloud infra in v1

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| External service over TeamCity plugin | Keeps AI credentials off TeamCity agents, easier to iterate | — Pending |
| Query TeamCity for history vs local DB | Simpler architecture, one fewer data store to manage | — Pending |
| Claude API for analysis | Powerful reasoning for system-level synthesis across many signals | — Pending |
| Local filesystem for artifacts | Simplest storage for v1, can add S3/TeamCity upload later | — Pending |
| Create new Slack bot | No existing bot available, need full Slack integration | — Pending |

---
*Last updated: 2026-02-17 after initialization*
