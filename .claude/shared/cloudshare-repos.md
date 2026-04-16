# CloudShare Repository Reference

## Repositories Overview

| Repo | Primary Language | Purpose | App Insights |
|------|-----------------|---------|--------------|
| `cloudshare/cloudshare` | C# / Python / Angular / AngularJS | Full-stack: C# API v3 backend, Python services; Angular + AngularJS frontend (`src/javascript/cs-client/`); shared vanilla JS for ASPX pages (`src/javascript/cs/`) | `classic-appinsights-prod` |
| `cloudshare/experiences-backend` | C# / Node.js | BFF, API Gateway, Experiences API layer | `prod-appinsights` |
| `cloudshare/experiences-client` | TypeScript / Angular | Frontend SPA (Accelerate UI) | `experiences-client-*` |
| `cloudshare/angular-libs` | TypeScript / Angular | Shared Angular component libraries (e.g. audio/video conference) used by both cs-client and experiences-client | — |
| `cloudshare/TestAutomation` | C# / .NET 9.0 | E2E browser tests (Selenium) and API tests for the Accelerate product; NUnit 4; Kiota-generated API clients | — |
| `cloudshare/AutomaticTesting` | TypeScript / Node.js | Full E2E and API test suite for Classic and Accelerate; Playwright; Allure reporting with Claude AI failure analysis | — |

**Megatron** (`src/Megatron/` inside the `cloudshare` repo) is a separate ASP.NET Core service that accepts the same JWT Bearer tokens as Experiences.Service (`ValidAudiences = ["BFF", "APIGW"]`). It is **not deployed to production** and **not actively developed** — treat it as dead code when investigating active flows.

Additional repos may exist — if a callstack references an assembly or module not found above, search GitHub for it under the `cloudshare` organization.

---

## Callstack Frame → Repo Mapping

Use this table when a callstack points to application code, to identify which repo to search.

| Frame pattern | Local path (preferred) | GitHub repo (fallback) |
|--------------|------------------------|------------------------|
| `CloudShare.*`, `CS.*`, `Backend.*`, C# namespaces from web app | local `cloudshare` repo (path varies) | `cloudshare/cloudshare` |
| `*.aspx`, `*.aspx.cs`, ASPX code-behind classes | local `cloudshare` repo (path varies) | `cloudshare/cloudshare` |
| Angular / AngularJS component/service/controller from WebApp UI | local `cloudshare` repo (path varies) | `cloudshare/cloudshare` |
| `Experiences.*`, `ExperiencesBackend.*`, BFF/Gateway namespaces | local `Experiences-backend` repo (path varies) | `cloudshare/experiences-backend` |
| Angular component/service path references `experiences-client` | not typically checked out locally | `cloudshare/experiences-client` |
| Unknown assembly | Search local repos first; then GitHub `cloudshare` org | — |

Always prefer locally checked-out repos over remote GitHub search. Repo locations vary by machine — infer from the current working directory or ask the user. The primary repos to look for are `cloudshare` and `Experiences-backend`.

---

## Repo → Jira Deployment Component Mapping

| Repo / Service | Jira Deployment Component |
|----------------|--------------------------|
| `cloudshare` (WebApp / API v3) | `CloudIIs` |
| `experiences-client` (Accelerate frontend) | `ExperiencesClient` |
| `experiences-backend` BFF | `Experiences BFF` |
| `experiences-backend` API Gateway | `Accelerate API Gateway` |
| `experiences-backend` Experiences.Service (API layer) | `Experiences Service` |
| `TestAutomation` / `AutomaticTesting` (test repos) | `NA` |
| Unknown / doesn't fit | `NA` |
