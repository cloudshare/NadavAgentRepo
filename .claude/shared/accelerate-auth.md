# Accelerate Auth Architecture

Authentication flow for users accessing **Accelerate** (Experiences) — from WebApp login through to Experiences.Service authorization.

---

## Flow summary

```
User login (WebApp)
  → BFF.SharedCookie set (AES-encrypted, 6h TTL)

Browser request → Experiences.BFF (reverse proxy)
  → AuthMiddleware: decrypt cookie → extract userId → mint 5-min JWT (audience "BFF")
  → inject Authorization: Bearer header
  → proxy to Experiences.Service

Experiences.Service
  → validate JWT (HS256 + AES-256-CBC-HMAC-SHA512)
  → claim "Id" → userId
  → CS.Auth.Library: RBAC checks against Experiences DB
```

---

## WebApp — cookie creation (`cloudshare` repo)

`LoginManager.DoLogin()` → `IFormsAuthenticationService.CreateBffAuthCookies()`.

**File:** `src/Itst.Core/Web/FormsAuthenticationService.cs`

Two cookies written on login:
- **`BFF.SharedCookie`** (360 min): AES-encrypted JSON `{ UserId, UserEmail, ExpirationTime }`. Key = `BffAuthentication.CookieEncryptionSymmetricKey`, IV = 16 zero bytes.
- **`BFF.SharedCookieHalf`** (180 min): renewal marker — when absent, WebApp re-issues both cookies on the next authenticated request (`PostAuthenticateRequest` hook, feature flag `EnableExtendingBffAuthenticationCookie`).

Both cookies: `HttpOnly`, `Secure`, `SameSite=Strict`.

Cookies cleared on logout (`LogoutManager`) and replaced on impersonation (`ImpersonationManager`).

Config lives in `DynamicConfig.BffAuthentication` (keys: `CookieName`, `HalftimeMarkerCookieName`, `CookieExpireMinutes`, `CookieEncryptionSymmetricKey`, `CookieDomainName`).

---

## Experiences.BFF — token exchange (`experiences-backend` repo)

`AuthMiddleware` → `CookieAuthenticationDataRetriever` → `AuthCookieDecryptor` → `JwtGenerator`.

- Decrypts `BFF.SharedCookie` with the same AES key/IV as WebApp.
- Validates `ExpirationTime`.
- Mints a 5-min JWT: claim `"Id"` = userId, audience `"BFF"`, signed HS256, encrypted AES-256-CBC-HMAC-SHA512.
- Injects `Authorization: Bearer <token>` on the proxied request.

Config sections: `CookieDecryption.CookieName` / `CookieDecryptingKey`, `Authentication.SigningKey` / `EncryptingKey` / `ValidIssuer` / `Audience`.

---

## Experiences.Service — JWT validation (`experiences-backend` repo)

`Startup.ConfigureAuth()` registers `AddJwtBearer` with `ValidAudiences = ["BFF", "APIGW"]`.
`UseFakeAuthentication = true` (dev) skips this and returns a hardcoded user (`FakeAuthHandler`).

userId extracted from claim `"Id"` via `CurrentUserProvider.GetCurrentUserId()` (with external→internal ID mapping).

---

## CS.Auth.Library — RBAC (`experiences-backend` repo)

Shared library providing authorization for Experiences.Service. The Experiences.Service EF DB context inherits from `AuthDBContext`, so auth tables live in the **same Experiences DB**.

Auth tables are populated via a dedicated Service Bus subscription (`AuthEntityChangedServiceBusOptions`, `ServiceName = "AuthService_ExperiencesService"`). `AuthBackgroundService` consumes auth-related entity change messages and upserts/deletes auth table rows.

The Auth channel is a **parallel subscription** to the same Service Bus topics as the main Experiences sync — not a separate publishing path. See `entity-change-mechanism.md` for the message format.

Key services registered by `CsAuthServiceCollectionExtensions.ConfigureCSAuth()`:
- `IAuthorizationValidator` — top-level check: can user perform action on resource?
- Per-entity validators: `IProjectPermissionsValidator`, `ICoursePermissionsValidator`, `ITeamPermissionsValidator`
- `IVisibilityFilters` / `IVisibilityFiltersApplier` — filter entity lists to what calling user can see
