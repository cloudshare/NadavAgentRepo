# Frontend Architecture

> For routes, iframe embedding, URL managers, and navigation — see `.claude/shared/routing-and-navigation.md`.

CloudShare has two distinct frontends served to different user populations, plus a component library demo app.

---

## 1. Classic Frontend (`cloudshare` repo — `cs-client`)

Hybrid Angular/AngularJS SPA. Serves **Classic users** directly. Also embeds the Accelerate frontend in an iframe for Accelerate users navigating from the classic shell.

- Source: `src/javascript/cs-client/src/`
- Served at: `use.cloudshare.com/Ent/CsClient.mvc/`
- App Insights: `classic-appinsights-prod`

### Versions

Angular **15.2.10** | AngularJS **1.5.11** | RxJS **7.8.1** | No NgRx

> `experiences-client` is on Angular 17. The version gap means components cannot be shared directly yet.

### Bootstrap

Entry point: `src/index.ts`. Only bootstraps when **not inside an iframe** — unless the URL includes `/remote-access`, `/app/clean`, or `/app/viewer`. AngularJS module `csClient`, bootstrapped via `angular.bootstrap(csClientContainer, ['csClient'], {strictDi: true})`. Hybrid integration via `@angular/upgrade/static`.

### AngularJS → Angular migration structure

Two parallel directory trees during migration:
- **Angular:** `src/javascript/cs-client/src/app/<Feature>/`
- **AngularJS (being emptied):** `src/javascript/cs-client/src/<Feature>/`

Bridge files:

| File | Purpose |
|---|---|
| `src/javascript/cs-client/src/ng2Module.ts` | `downgradeComponent()` and `downgradeInjectable()` — Angular → AngularJS interop |
| `src/javascript/cs-client/src/app/Compat/app.compat.module.ts` | `$injector` factory providers — AngularJS → Angular interop |

> For full migration rules, see the `cs-angular-upgrade` skill (`SKILL.md` Core Principles).

### Layout system

`AppLayoutComponent` (`Layouts/layouts.app.component.ts`) drives layout based on route:

| URL prefix | Layout | TopBar | SideBar |
|---|---|---|---|
| `/app/vendor/*`, `/app/legacy/*`, `/app/accelerate/*` | Vendor | yes | yes |
| `/app/viewer/*` | Vendor | no | no (full-screen) |
| `/app/clean/*` | Clean | no | no |

`legacyPage` mode activates when the URL path does **not** start with `/Ent/CsClient.mvc` — i.e., the SPA is embedded in a plain ASPX page.

### Standalone ASPX pages (not embedded in iframe)

`Login.aspx`, `Logout.aspx`, `FederatedLogin.aspx`, `SamlLogin.aspx`, `RecoverPassword.aspx`, `ChangePassword.aspx` — all under `src/Itst.Web.App/Mvc/Views/Cloudshare/`.

---

## 2. Accelerate Frontend (`experiences-client` repo)

Pure Angular SPA, no AngularJS. Serves **Accelerate users** directly, also embedded in Classic frontend via `EmbeddedAccelerateIframeComponent`.

- Served at: `experiences.cloudshare.com` (prod), `accelerate-ui.preprod1.mia.cld.sr` (preprod), `experiences.ci.cloudshare.com` (CI)
- App Insights: `experiences-client-*`
- Uses hash-free routing

### ASPX rewrites and backend status

Most areas call real backend APIs. Exceptions — areas still using mock-only data (no real HTTP calls):
- `old-project-details` — rewrite of `CampaignDetails.aspx`; all service methods return static mocks
- `policies` → root policy section — no backend yet; the environment policy section is real

---

## 3. Component Library Demo App

Small standalone Angular app for demoing the component library. Not user-facing.

---

## Shared Code Between Frontends

### `@cs/` scoped npm packages

Published to CloudShare private Artifactory (`https://cloudshare.jfrog.io/artifactory/api/npm/npm`). Both repos use `.npmrc`: `@cs:registry=https://cloudshare.jfrog.io/artifactory/api/npm/npm`.

**From `cloudshare` repo (cs-client source tree):**

| Package | Source path | Purpose |
|---|---|---|
| `@cs/websockets` | `src/Common/Libraries/Websockets/` | WebSocket communication; factory pattern, mock support |
| `@cs/cors-communication` | `src/app/RemoteAccess/CorsCommunication/` | Remote Access cross-origin postMessage API |
| `@cs/remote-access-external-menu` | `src/app/RemoteAccess/ExternalMenu/` | Remote Access external menu management |

Each package has its own `package.json`/`tsconfig.json` inside cs-client and is published independently. Not a monorepo/workspaces setup.

**From `cloudshare/angular-libs`:**

| Package | Purpose |
|---|---|
| `@cs/video-call` | Audio/video conference components (depends on `@cs/websockets`) |
| `@cs/chat-component` | Chat UI component |

> When bumping `@cs/websockets`, also check `@cs/video-call` in `angular-libs` since it depends on it — then bump both consumer repos.

### WebSockets for legacy ASPX pages (`javascript/cs`)

The same `@cs/websockets` TypeScript source has a webpack build (`CloudShareWebSockets/webpack.deploy.config.js`) that compiles to `javascript/cs/src/csws.js`. The `javascript/cs` project re-bundles it with heartbeat-over-WebSocket and an HTML sanitizer into `dist/bundle.js`, loaded by ASPX pages as a `<script>` tag (`window.cs.csws` / `window.cs.heartbeatsoverws` / `window.cs.htmlSanitizer`).

> Modifying WebSockets TS source requires rebuilding both the cs-client Angular bundle and the `javascript/cs` standalone bundle.
