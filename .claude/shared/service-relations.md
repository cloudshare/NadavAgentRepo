# CloudShare Service Relations

> For deployment, infrastructure, databases, and configuration, see `.claude/shared/azure-deployment.md`.
> For code-level logging (AppEventsConfig, ActivityLog, AppEvent mocks in tests), see `.claude/shared/logging-and-app-events.md`.

## Services & App Insights Instances

The CloudShare production environment spans multiple services, each with its own App Insights resource. Always check **all relevant instances** and correlate by `operation_Id` / `session_Id` across them:

| Service | App Insights Resource | Primary Tables |
|---------|----------------------|----------------|
| CloudShare WebApp / API v3 (`cloudshare` repo) | **`classic-appinsights-prod`** | `requests`, `exceptions`, `dependencies`, `traces` |
| Experiences Backend (BFF, API Gateway, `experiences-backend` repo) | **`prod-appinsights`** | `requests`, `exceptions`, `traces` |
| Experiences Client (frontend, `experiences-client` repo) | `experiences-client-*` | `pageViews`, `exceptions`, `browserTimings`, `traces` |
| Other services | Discovered via Resource Graph | varies |

When the exact App Insights workspace IDs are unknown, use the Azure MCP tools to list all Application Insights resources in the `CloudShare Production Services on Azure` subscription first.

---

## Accelerate AKS Services

All services run in the **`cloudshare`** Kubernetes namespace. Ingress resources run in `nginx-ingress`. TLS is handled by cert-manager with Let's Encrypt.

| Service | Purpose |
|---------|---------|
| `api-gateway` | API routing / gateway layer |
| `bff` | Backend for Frontend |
| `experiences-service` | Core Experiences business logic; owns `Experiences` Azure SQL DB |
| `experiences-client-configuration` | Client configuration; owns `ClientConfiguration` Azure SQL DB |
| `email-sender` | Async email processing via Service Bus |
| `timezones` | Timezone resolution |
| `v-vision` | ML/vision service for guided journey; KEDA-scaled on Service Bus queue |
| `experiences-client` | Angular SPA (Accelerate UI) |
| `accelerate-ui-preview` | CI-only preview build |

Scaling, resource limits, and health check config live in the `kubernetes-deployment` repo.

### Public Hostnames by Environment

| Environment | Classic WebApp (cs-client) | API Gateway | Accelerate Frontend |
|-------------|----------------------------|-------------|---------------------|
| Production | `use.cloudshare.com` | `accelerate-api.cloudshare.com` | `experiences.cloudshare.com` |
| Preprod | — | `accelerate-api.preprod1.mia.cld.sr` | `accelerate-ui.preprod1.mia.cld.sr` |
| CI / webinteg | `webintg.cloudshare.com` | `api.accelerate.ci.cloudshare.com` | `experiences.ci.cloudshare.com` |
| Test1 | — | AKS FQDN (`*.eastus.aksapp.io`) | — |

> **Spelling note:** The CI/webinteg Classic hostname is `webintg.cloudshare.com` — **no second 'e'** (not ~~webinteg~~). Classic pages follow the pattern `https://webintg.cloudshare.com/Ent/CsClient.mvc/#/vendor/{route}`.

---

## Request Routing — How Frontends Reach the Backend

| Origin | Path | Logs appear in |
|--------|------|----------------|
| **Accelerate frontend** (`experiences-client`) | Browser → **BFF** (`experiences-backend`) → WebApp API v3 | `prod-appinsights` (BFF leg) **and** `classic-appinsights-prod` (WebApp leg) |
| **Accelerate API / integrations** | Client → **API Gateway** (`experiences-backend`) → WebApp API v3 | `prod-appinsights` (Gateway leg) **and** `classic-appinsights-prod` (WebApp leg) |
| **Classic frontend** (AngularJS/Angular UI in the `cloudshare` repo) | Browser → **WebApp directly** (API v3) | `classic-appinsights-prod` only |

Key implications when investigating failures:
1. If the failure is reported by an Accelerate user or the Accelerate frontend, **start in `prod-appinsights`** — find the `operation_Id`, then follow it into `classic-appinsights-prod` to see what the WebApp returned.
2. If the failure is reported by a Classic frontend user, **start and stay in `classic-appinsights-prod`**.
3. Use the `HttpRequestException` trace in `prod-appinsights` (`MessageBody` field) to read the WebApp's response without needing to cross-query.
4. The BFF and API Gateway layers are rarely the root cause — if requests pass through them but fail downstream, focus the investigation on `classic-appinsights-prod`.
5. **Retry amplification**: Experiences Service has a retry policy that retries **3 times on HTTP 500**, producing **4 total WebApp calls** per single logical request failure. When counting affected requests in `classic-appinsights-prod`, divide by 4 (or count distinct `OperationId`s in `prod-appinsights` instead). This affects any endpoint that hits the WebApp via Experiences Service (BFF or API Gateway path).
