# LTI 1.3 Integration

## Spec References

Fetch these when investigating LTI issues:

| Spec | URL |
|------|-----|
| LTI 1.3 Core | https://www.imsglobal.org/spec/lti/v1p3/ |
| IMS Security Framework (OIDC login flow, required params) | https://www.imsglobal.org/spec/security/v1p0/ |
| Assignment & Grades Services (score reporting) | https://www.imsglobal.org/spec/lti-ags/v2p0/ |
| Names & Roles Provisioning | https://www.imsglobal.org/spec/lti-nrps/v2p0/ |

Key things to check in the spec when debugging:
- **Login initiation required params**: only `iss`, `login_hint`, `target_link_uri` are required; `client_id` and `lti_deployment_id` are optional
- **`target_link_uri`**: "the actual endpoint executed at the end of the OIDC flow" — customers may use either the tool base URL or the launch URL
- **Deployment IDs**: one `client_id` can have many `deployment_id`s (e.g. per Canvas sub-account); each needs its own `LtiConfiguration` row

## Overview

CloudShare supports LTI 1.3 (Learning Tools Interoperability), allowing external LMS platforms (Canvas, Docebo) to launch CloudShare experiences. The integration lives in the `cloudshare` repo under the WebApp.

## Key Files

| File | Purpose |
|------|---------|
| `src/Itst.Web.App/Api/Controllers/v3/Unauthenticated/Lti1_3Controller.cs` | HTTP entry points: `/login`, `/launch`, `/keySet`, `/toolConfiguration` |
| `src/Itst.BL/BLServices/Integrations/Lti/Service/Lti1_3BlService.cs` | All business logic: login validation, token validation, student/instructor routing |
| `src/Itst.BL/BLServices/Integrations/Lti/Service/LmsIntegrationService.cs` | Subscription-level LMS config (Docebo push, Canvas setup) |
| `src/Itst.DataAccess/DataAccess/BLServices/Lti/LtiDataAccess.cs` | DB access for `LtiConfigurations` table |
| `src/Itst.BL/BLServices/Integrations/Lti/Helpers/LtiIdToken.cs` | JWT claim extraction |
| `src/Itst.Config/DynamicConfig.cs` | `Lti` config section (keys, tool URLs, Docebo settings) |
| `local_config/dynamic_web_config.xml` | Local LTI config under `<Lti>` — `baseUrl`, `toolUrl`, `redirectUrl`, etc. |

## Flow

### Login (OIDC third-party initiation)
1. Canvas POSTs to `/api/v3/unauthenticated/lti/v1.3/login` with: `iss`, `login_hint`, `target_link_uri`, `client_id`, `lti_deployment_id`, `lti_message_hint`
2. CloudShare looks up `LtiConfiguration` by `(iss=PlatformId, client_id=ClientId, lti_deployment_id=DeploymentId)`
3. If found: generates `state` + `nonce` in Redis, redirects to Canvas's OIDC auth endpoint → returns 302
4. If not found: logs Warn + throws `InvalidRequestException` → 401

### Launch
1. Canvas POSTs `id_token` + `state` to `/api/v3/unauthenticated/lti/v1.3/launch`
2. Looks up config again by `(PlatformId, ClientId, DeploymentId)` from JWT claims
3. Validates state (Redis), JWT signature (JWKS from Canvas), nonce (Redis), userId, ToolUrl
4. Creates/finds the course and redirects student or instructor

## LtiConfiguration — Per-Class Setup

- Each CloudShare **class (course)** has its own `LtiConfiguration` row
- The 3-way key `(PlatformId, ClientId, DeploymentId)` must match exactly what Canvas sends
- Saved by the class owner via `POST /Api/v3/class/{classId}/LtiConfiguration`
- For Docebo: auto-saved during `PushToDocebo` flow

## Non-Obvious Behaviours

### Canvas issuer is always `https://canvas.instructure.com`
Canvas cloud always sends `iss=https://canvas.instructure.com` regardless of the customer's actual domain. A customer at `learn.statistics.com` still has `PlatformId=https://canvas.instructure.com`. The actual domain appears only in the `lti_message_hint` JWT (`canvas_domain` field), which is opaque to CloudShare.

**Common new-customer mistake**: entering their Canvas domain (e.g. `https://learn.myschool.com`) as `PlatformId` instead of `https://canvas.instructure.com` → config lookup fails → 401.

### `target_link_uri` — base URL or launch URL are both valid
Canvas sends the `target_link_uri` from the login initiation back as a JWT claim in the launch. CloudShare validates this against the configured `ToolUrl`. Per LTI spec, `target_link_uri` is "the endpoint executed at the end of the OIDC flow", so customers may correctly set it to either:
- `https://use.cloudshare.com` (base URL — what `ToolUrl` resolves to when `toolUrl=""` in config)
- `https://use.cloudshare.com/api/v3/unauthenticated/lti/v1.3/launch` (the launch endpoint — also correct per spec)

Both are accepted. If the check fails, a Warn is logged with the actual vs expected values.

### State and nonce use Redis, not cookies
No SameSite cookie issues. TTL is 600 seconds (set in `LtiRedisExpirationS`).

### Deployment ID format
Canvas deployment IDs look like `334:b38a3c62d62e0ba8c261c118e3aa3631c6d9c63c` (numeric prefix + hash). Customers must enter the full value exactly.

### One deployment ID per Canvas deployment
A single Canvas developer key (`client_id`) can have multiple deployments (e.g. per sub-account), each with its own `deployment_id`. Each deployment requires a separate `LtiConfiguration` row in CloudShare pointing to a different class.

## Diagnosing 401 Errors

All validation failures fire `AppEvent` at **Warn** level (see `.claude/shared/logging-and-app-events.md`). Query `classic-appinsights-prod` `customEvents` table, filter on `name` = `Lti1_3LoginFailed` or `Lti1_3LaunchFailed`:

| Event | Cause |
|-------|-------|
| `Lti1_3LoginFailed` | LTI config not found — 3-way key mismatch (`issuer` / `clientId` / `deploymentId`); check what Canvas sent vs what's in DB |
| `Lti1_3LaunchFailed` | One of: `target_link_uri` not matching configured tool URL; Redis state expired/tampered; JWT signature/issuer/audience/expiry invalid; missing `sub`; nonce expired or reused |

The perf log (`Itst.Perf.UI`) captures `post_data_iss`, `post_data_client_id`, `post_data_lti_deployment_id` on every login request — useful for cross-referencing with DB values.

## DynamicConfig LTI Section

```xml
<Lti>
  <Keys> ... </Keys>
  <Info
    baseUrl="https://use.cloudshare.com"
    toolUrl=""
    redirectUrl="/api/v3/unauthenticated/lti/v1.3/launch"
    publicKeysetUrl="/api/v3/unauthenticated/lti/v1.3/keyset"
    initiateLoginUrl="/api/v3/unauthenticated/lti/v1.3/login" />
  <DoceboIntegration ... />
</Lti>
```

`toolUrl=""` means `ToolUrl = baseUrl`. Changing `toolUrl` affects JWT validation — existing customers' Canvas setups must match.
