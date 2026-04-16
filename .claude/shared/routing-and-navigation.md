# Frontend Routing & Navigation

> For overall frontend architecture, bootstrap, and shared packages, see `.claude/shared/frontend-architecture.md`.

---

## Route Naming Conventions

These conventions apply to all new Angular routes in `cs-client` and `experiences-client`. When migrating an AngularJS route, apply the convention to the new path.

| Page type | Convention | Examples |
|-----------|-----------|---------|
| **List / grid** | Plural noun, no suffix | `classes`, `projects`, `blueprints` — **not** `classesList`, `classes/list` |
| **Detail** | Plural noun + `/:id` | `classes/:id`, `projects/:projectId` — **not** `classes/details/:id` |
| **Create / wizard** | Singular noun + `/create` | `class/create`, `project/create` — **not** `createClass` |
| **Sub-page of a detail** | `things/:id/sub-page` | `projects/:id/members` |

**Casing:** kebab-case for multi-word segments (`end-users`, `creation-scripts`).

**Do not** embed the entity type in the ID segment: `/classes/:id` is correct; `/classes/entity/:id` is wrong.

**When renaming a route, grep the entire `src/` tree** for the old path string and update every match — URLs are hardcoded in many layers: `*.cs` URL managers (`EntAppUrlManager.cs`, `LegacyUrlManager.cs`, `StaticUrlHelpers.cs`), `*.aspx`/`*.ascx`, TypeScript/JS (`EntityUrlResolver`, `LocationMapperService`, routing modules, mock data files), and test files.

---

## Angular Routes — Classic Frontend (`cs-client`)

All routes are lazy-loaded. Full list in `src/javascript/cs-client/src/app/Layouts/layoutsRouting.module.ts`.

- `app/vendor/*` — feature pages (environments, projects, users, admin, blueprintsList, training, hub, etc.)
- `app/legacy/**` — legacy ASPX / AngularJS pages embedded in iframe
- `app/accelerate/**` — Accelerate SPA (`experiences-client`) embedded in iframe
- `app/viewer` — environment viewer (full-screen, no chrome)
- `app/clean/*` — standalone pages with no chrome (remote-access, http-access, page-not-found, lti-error, etc.)

Legacy AngularJS UI-Router states are reachable via `/Ent/CsClient.mvc/#/...` hash URLs. Full state list in `src/javascript/cs-client/src/app.uiRouter.config.js`.

---

## iframe Embedding

### Legacy ASPX / AngularJS → `app/legacy`

Component: `EmbeddedIframeComponent` (`Layouts/Common/EmbeddedIframe/`). Route `/app/legacy{path}` → iframe loads `{path}`. Syncs navigation back via `_handleIframeNavigation()`. PostMessage events: `mouseclick`, `RedirectingCsClientInIframe`, `LoginInIframe`, `DOMContentLoaded`. CORS guard: falls back to `entityUrlResolver.getHomePage()` on cross-origin navigation.

### Accelerate SPA → `app/accelerate`

Component: `EmbeddedAccelerateIframeComponent` (`Layouts/Common/EmbeddedAccelerateIframe/`). Base URL from `DynamicConfig` `AccelerateApp.BaseUrl`. Route `/app/accelerate{path}` → iframe loads `{accelerateBaseUrl}{path}`. PostMessage events: `RedirectingCsClientInIframe`/`CsClientInIframe` (navigate Angular router), `AccelerateTitleChanged` (update title), `AccelerateNavigationEnded` (sync URL).

---

## Accelerate Frontend Routes (`experiences-client`)

Full list in `src/app/app-routing.module.ts`. Key areas: `instructor-console`, `analytics`, `admin`, `projects`, `environments`, `blueprints`, `snapshots`, `policies`, `user-details`, `root-users`, `landing`, `cloud-folders`, `editor`, `invitation-details/:invitationToken`, `old-project-details`. Default route loads `ExperiencesShellModule`.

---

## URL Managers (backend → frontend link generation)

### Key classes

| Class / Interface | Location | Purpose |
|---|---|---|
| `IUrlManager` | `src/Itst.Core/Web/IUrlManager.cs` | Base: login, env details, landing page per user |
| `IEntAppUrlManager` / `EntAppUrlManager` | `src/Itst.Web.App/Code/EntAppUrlManager.cs` | 100+ methods for all entity/page URLs; uses `InternalExternalMapper` and `EntityIdMapper` |
| `StaticUrlHelpers` | `src/Itst.Web.Utils/StaticUrlHelpers.cs` | `ToCsClientLegacyPageUrl()`, `ToAcceleratePageUrl()`, absolute/relative conversions |
| `EntityUrlResolver` (TS) | `src/javascript/cs-client/src/app/Common/Libraries/common.libraries.entityUrlResolver.ts` | Frontend mirror of backend URL logic; user-type-aware routing |
| `LocationMapperService` (TS) | `src/javascript/cs-client/src/app/Common/Libraries/common.libraries.locationMapper.service.ts` | Maps current URL to sidebar category |

### User-type routing logic

Both `EntAppUrlManager` (backend) and `EntityUrlResolver` (frontend) check `isExperiencesAppUser`:
- `true` → Accelerate App URL (`{AccelerateApp.BaseUrl}/...`)
- `false` → Classic cs-client URL (`/Ent/CsClient.mvc/#/...`)

### Entity ID format

Internal DB IDs are never exposed in URLs. Encoded via `EntityIdMapper.InternalToExternal(id, EntityType.XX)` — 2-char prefix + encoded token (e.g. `US` = User, `PR` = Project, `BP` = Blueprint, `EN` = Environment, `CO` = Course/Experience). Full prefix list in `EntityInfoToTypeMapper.cs`.

---

## Internal Navigation: `[csHref]`

For any `<a>` linking to an internal page in Angular templates, **use `[csHref]` instead of `[href]`**. The app uses hash-based routing (`#/app/...`). `CsHrefDirective` routes internal Angular URLs via `router.navigateByUrl()`, other hash URLs via `window.location.assign()`, and external URLs via native `<a href>`. Using plain `[href]` bypasses the Angular router and can re-run the hybrid bootstrap.

```typescript
import { CsHrefDirective } from 'app/Common/Directives/CsHref/common.directives.cshref.directive';
@Component({ standalone: true, imports: [CsHrefDirective] })
// template: <a [csHref]="url">Link</a>
```

In AngularJS templates: `<a cs-href="ctrl.url">`.

---

## Breadcrumbs (`BreadCrumbsViewService`)

Angular components that set breadcrumbs call two methods in `ngOnInit`:

```typescript
this._breadCrumbsViewService.setPageId('contractFolder');
this._breadCrumbsViewService.setPath([
  { name: 'Resources Repository', href: this._entityUrlResolver.getResourcesRepositoryUrl() }
]);
```

**`setPageId`** — must match the `Id` property of the menu item in [MenuItemManager.cs](<../../../src/Itst.BL/BLServices/UI Services/Service/MenuItemManager.cs>). Find the right id via [NavigationMenuCreatorService.cs](<../../../src/Itst.BL/BLServices/UI Services/Service/NavigationMenuCreatorService.cs>).

**`setPath`** — entries must use `href` (from `EntityUrlResolver`), not `state`. The breadcrumbs template renders `state` with `ui-sref` (AngularJS), which silently produces broken links in the Angular shell.

**Which `EntityUrlResolver` method:** grid list pages → `getGridUrl(entityType, [])` (add a `case` if missing); wizard/create → `getWizardUrl(entityType, params)`; entity detail → `getEntityUrl(type, id)`; other standalone pages → existing getter or add one.

**Nested breadcrumbs** — include parent as first entry. Admin pages always prepend `{ name: 'Admin', href: this._entityUrlResolver.getAdminUrl() }`.

**Embedded grid guard** — grids must not set breadcrumbs when embedded. `GridPageWrapper` sets `embeddedData.isEmbedded` after the parent's `ngOnInit`, so subscribe to the view model, filter for `isEmbedded === null` (confirmed not-embedded), then `take(1)`. The component must extend `ComponentBase`.

---

## Cross-frontend URL Linking

The two frontends cross-link heavily. `experiences-client` contains hardcoded `cloudshare` URLs in nav links, `window.location`/`href` assignments, and iframe message handlers. When a route in `cloudshare` changes, search `experiences-client` for the old path and file a separate PR if needed.
