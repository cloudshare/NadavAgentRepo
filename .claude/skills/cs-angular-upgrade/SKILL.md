---
name: cs-angular-upgrade
description: "Upgrade AngularJS components, directives, controllers, and services to Angular following CloudShare's specific architecture: DataServiceBase/ViewServiceBase/ComponentBase pattern, MasterModelService state management, standalone components, and the hybrid AngularJS↔Angular bridge. WHEN: migrate AngularJS component, upgrade directive to Angular, convert controller to service, migrate AngularJS service, port AngularJS template, upgrade to standalone component, convert to Angular, remove AngularJS dependency, migrate from AngularJS, upgrade component to ng2."
---

# Upgrade AngularJS to Angular

> Systematic workflow for migrating AngularJS components, directives, services, and controllers to Angular following CloudShare's architecture. Always starts with a pre-migration analysis report before writing any code.

---

## Core Principles

1. **Always produce a pre-migration analysis report first.** Before writing a single line of Angular code, read the source files, understand what's there, and report on complexity, risks, and incompatible patterns. The user reviews and approves the plan before migration starts.

2. **Migrate one layer per PR.** Each PR covers exactly one service class (ViewService, DataService) or one directive/component — not the whole feature at once.

3. **Delete AngularJS and add Angular in the same PR.** Never split "add Angular" and "remove AngularJS" into separate PRs.

4. **Make no unnecessary changes.** Do not reformat, rename variables, refactor logic, or add comments/types to code not being migrated. The diff should contain only the migration. Preserve data model property names exactly as they were in AngularJS — do not rename `page` to `samplesPage` or `totalItems` to `totalSamples`. Do not wrap flat properties in `{ loading: boolean; value: T }` objects — use a private `_workingCount` counter (matching the AngularJS `_setWorking` pattern) instead. New model properties with no AngularJS equivalent may use whatever shape is appropriate.

5. **Use the `$injector` bridge as a valid intermediate state.** When the code you're migrating depends on services not yet migrated, bridge them via `$injector` in the feature module providers. Remove the bridge in the PR that migrates the dependency.

6. **Always inject by class type, never by `InjectionToken`.** Both Angular and AngularJS services can be injected via their class type in the constructor. Angular services are injected directly; AngularJS services are injected via a `$injector` factory provider typed to the class (see principle 5 and the [Angular upgrade guide](https://v15.angular.io/guide/upgrade#making-angularjs-dependencies-injectable-to-angular)). There is no case where an `InjectionToken` is needed for service injection during migration.

7. **Use `DataServiceBaseCompat` / `ViewServiceBaseCompat` while AngularJS callers remain.** If the service being migrated is still registered via `downgradeInjectable` or consumed by AngularJS code not yet migrated, extend the Compat variant instead of the plain base class. Switch to the plain variant in a follow-up PR once all AngularJS callers are gone.

8. **Preserve method order and column definitions.** Keep methods in the same order as the AngularJS source. If a column had `directive: 'cs-foo-column'`, preserve that `directive:` field exactly — column directives are migrated in their own separate PR. When a `directive:` column is used for sorting, map the directive name to the actual model property inside `_loadPage()` rather than overriding `_getSort()`.

   **When the directive itself is migrated (its own PR):** replace `directive:` with `component: FooColumnComponent` and add `property: 'backendFieldName'` for sortable columns — both `GridViewService._getSort()` and `GridViewServiceNg1._getSort()` read `c.directive || c.property`, so removing `directive:` without adding `property:` causes sort to resolve as `null`. Delete any manual remapping that referenced the old directive name from both `_getSort()` overrides and `_loadPage()`.

9. **Never cache service data models as ViewService fields.** Use `combineLatest` to unify all reactive streams and pass data directly as parameters to `_update()` — no `this._dataModel` class-level fields. See [SamplesGrid ViewService](../../../src/javascript/cs-client/src/app/ExternalResources/SamplesGrid/externalResources.samplesGrid.viewservice.ts) for the canonical example. `combineLatest` waits for all streams to emit before firing, ensuring the view only renders when all data is available.

10. **File naming — no duplicate feature noun + "grid".** Use `<feature-noun>.grid.<role>.ts` — never `<featurenoun>grid.grid.<role>.ts`. Example: `snapshots.grid.viewservice.ts`, not `snapshotsgrid.grid.viewservice.ts`.

11. **Modal dialogs — use `ModalBoxComponent` in cs-client.** When migrating `$modal.open()`, use `ModalBoxComponent` (`app/Common/Controls/ModalBox/controls.modalBox.component.ts`) as the interim pattern. Do not use Angular CDK Dialog or `MatDialog` directly. Switch to `cs-dialog` once cs-client aligns with experiences-client's Angular version.

12. **Remove blockers before migrating.** If a directive has patterns that block upgrading (`$broadcast`/`$on`/`$emit`, shared `$scope` reads, `$compile`), remove them in separate preparatory PRs first while the code is still AngularJS. Search the existing Angular codebase for services/subjects already used for the same purpose and reuse them.

---

## Architecture Overview

> See `.claude/shared/frontend-architecture.md` — "AngularJS → Angular migration structure" for the directory split, bridge files, and version numbers.
> Angular v15 upgrade guide (hybrid app, DI bridging, UpgradeComponent): https://v15.angular.io/guide/upgrade

Key files referenced throughout this skill:
- [ng2Module.ts](../../../src/javascript/cs-client/src/ng2Module.ts) — `downgradeComponent()` / `downgradeInjectable()`
- [app.compat.module.ts](../../../src/javascript/cs-client/src/app/Compat/app.compat.module.ts) — `$injector` factory providers

---

## Step 0 — Pre-Migration Analysis Report

**Do this before writing any Angular code.** Read all source files for the feature and produce a structured report.

### What to read

1. The AngularJS service files in `src/<Feature>/` — all `.service.ts`, `.directive.js`, `.controller.js`, `.viewservice.ts`, `.dataservice.ts`
2. The AngularJS templates (`.html`) used by the directives/components
3. The AngularJS module barrel (`ngModule.ts`, `index.ts`) to understand dependency declarations
4. Entries in `src/app/Compat/app.compat.module.ts` — is this feature already bridged?
5. Entries in `src/ng2Module.ts` — is anything already downgraded?
6. The existing Angular feature module `src/app/<Feature>/<feature>.module.ts` (if it exists)
7. Any callers of this service/directive — AngularJS templates or Angular components that inject/use it
8. **Styles**: If no dedicated stylesheet exists, search for where the CSS/LESS classes are defined. If in a shared stylesheet and not used elsewhere, extract into a new `.less` file next to the Angular component.

### Report structure

#### 1. Inventory
List every file to **delete** (AngularJS source), **add** (new Angular source), and **modify** (bridge registrations, routing, parent modules, callers).

#### 2. Dependency map
For each service being migrated, list its injected dependencies and whether each is: already Angular (inject directly), still AngularJS (needs `$injector` bridge), or a framework service (`$http`, `$state`, `Restangular`, `gettextCatalog`) — see substitution table below.

#### 3. AngularJS patterns present

| Pattern found | Migration approach |
|---|---|
| `Restangular` calls | Replace with `HttpClient` + `firstValueFrom` for promise-based; `Observable` for reactive |
| `ng.copy(obj)` | `cloneFromNg1Model(obj)` from `app/Common/Helpers/parsing-data.ts` |
| `ng.equals(a, b)` | `deepEqual(a, b)` from `app/Common/Helpers/parsing-data.ts` |
| `_fireEvent()` / event bus | Remove — `MasterModelService` BehaviorSubject handles reactivity automatically |
| `$scope.$broadcast` / `$on` / `$emit` | Replace with RxJS `Subject` or `MasterModelService` state — flag as **blocker**, remove in preparatory PR |
| `$scope.$watch(() => expr, fn)` | `ngOnChanges` for `@Input()`; `distinctUntilChanged()` for service state; `ngOnInit` + manual diff for one-time setup |
| `$scope.$watchCollection` | `ngOnChanges` for `@Input()` arrays; RxJS stream with `distinctUntilChanged` + deep equality for service state |
| `$compile` usage | **Blocker** — requires ComponentPortal or custom strategy |
| `ng-grid` | Replace with `<cs-table>` (Angular `CsTableComponent` downgraded) |
| `&` bindings (expression callbacks) | `@Output() EventEmitter<{paramName: Type}>` — callers need `(event)="handler($event.paramName)"` |
| `=` two-way bindings | `@Input()` + `@Output()` pair, or `[(ngModel)]` for form controls |
| `$state.go(...)` / `$stateParams` | `Router.navigate(...)` / `ActivatedRoute` |
| `GridStateHrefService` | Remove — inject `EntityUrlResolver` instead (`getEntityUrl()`, `getGridUrl()`, `getWizardUrl()`) |
| `$window.location.href` (Angular route) | `this.router.navigate(['/app/vendor/...'])` |
| `$window.location.href` (AngularJS route) | Keep `window.location.assign(url)` — prefer `[csHref]` in templates |
| `JSON.parse(JSON.stringify(obj))` | `structuredClone(obj)` |
| `$filter('date')(val, fmt)` | Inject `DatePipe`, call `this.datePipe.transform(val, fmt)` |
| Direct `_model.*` mutation | `applyChange((m) => ({ ...m, field: value }))` |
| `<a ng-href="url">` / `<a cs-href="url">` | `<a [csHref]="url">` — import `CsHrefDirective` for internal CloudShare navigation; plain `[href]` is for external links only |
| `getNg1DataModel$(dep)` in existing Angular code | Will become `getDataModel$(dep)` after this dep is migrated |
| `getNg1ViewModel$(dep)` in existing Angular code | Will become `getViewModel$(dep)` after this dep is migrated |
| `.enum.js` file (plain JS object as enum) | Convert to TypeScript `enum` in a separate `.enum.ts` file — numeric values must match exactly |

#### 4. Callers that need updating
List every AngularJS template or Angular component that injects this service, uses the directive, or calls `getNg1DataModel$`/`getNg1ViewModel$` (must be updated to `getDataModel$`/`getViewModel$` in the same PR).

#### 4b. Directive upgrade viability (directives only)

Check each criterion and state the upgrade path:

```
restrict: 'E'?              YES / NO
scope: {} (isolate)?        YES / NO
bindToController: {}?       YES / NO
own controller?             YES / NO
own template?               YES / NO

compile function?           YES (BLOCKER) / NO
replace: true?              YES (BLOCKER) / NO
priority / terminal?        YES (HIGH RISK) / NO
multi-element?              YES (BLOCKER) / NO
$scope inheritance?         YES (BLOCKER) / NO
$broadcast/$on/$emit?       YES (BLOCKER, must remove first) / NO

→ Upgrade path: UpgradeComponent wrap / Full rewrite (reason: ___)
```

**UpgradeComponent requires ALL of:** `restrict: 'E'`, isolate `scope: {}`, `bindToController`, own controller, own template, and **none of:** `compile`, `replace: true`, `priority`/`terminal`, `multi-element`, shared `$scope`, `$broadcast`/`$on`/`$emit`. If any blocker is present, do a full rewrite as a standalone Angular component instead.

#### 5. Complexity and risk assessment

| Item | Level | Notes |
|------|-------|-------|
| Overall complexity | Low / Medium / High | |
| `$compile` usage | Blocker if present | |
| `$broadcast`/`$emit` across features | High risk | May require coordinating with other services |
| Restangular calls | Medium | Mechanical replacement |
| Remaining AngularJS consumers | Medium | Need `downgradeInjectable`/`downgradeComponent` |
| Size (lines of logic) | Informational | |

#### 6. PR plan
Propose the sequence of PRs — see [Reference: Real Migration Examples](#reference-real-migration-examples) for the canonical PR structure.

#### 7. Test file inventory
Search `spec/` for `<feature>*.spec.js` or `<feature>*.spec.ts`. If found, the spec must be upgraded in the same PR. Document which spec file to **delete** (old `.spec.js`) and which to **add** (new `.spec.ts` at `spec/app/<Feature>/`).

#### 8. Testing suggestions
Propose specific manual test steps based on the feature's functionality (see Testing section at the end).

---

## Migration Patterns

### Service migration (ViewService or DataService)

| File | Action |
|------|--------|
| `src/<Feature>/<feature>.viewservice.ts` | **Delete** |
| `src/app/<Feature>/<feature>.viewservice.ts` | **Add** |
| `src/app/<Feature>/<feature>.module.ts` | Modify — update providers |
| `src/app/Compat/app.compat.module.ts` | Modify — remove bridge for this service |
| `src/ng2Module.ts` | Modify — add `downgradeInjectable` if AngularJS consumers remain |

> **Compat variants:** If the service still has AngularJS callers, extend `ViewServiceBaseCompat` / `DataServiceBaseCompat` instead of the plain base classes. Both are exported from `common.libraries.serviceBase`.

**For the code shape of ViewService, DataService, $injector bridge, and module teardown**, follow the real examples listed in [Reference: Real Migration Examples](#reference-real-migration-examples). Key patterns:
- ViewService: constructor takes `MasterModelService` + dependencies, calls `_activate()` which subscribes via `getDataModel$`/`getNg1DataModel$`
- DataService: constructor takes `MasterModelService` + `HttpClient`, uses `applyChange()` for all state updates
- `$injector` bridge in feature module: `{ provide: Dep, useFactory: ($injector: any) => $injector.get('Dep'), deps: ['$injector'] }` — temporary, removed when dep is migrated
- `downgradeInjectable` in `ng2Module.ts`: `.factory('ServiceName', downgradeInjectable(ServiceClass))` — removed once all AngularJS callers are migrated
- `getNg1DataModel$` → `getDataModel$` / `getNg1ViewModel$` → `getViewModel$`: update in the same PR that migrates the dependency

### Full module teardown (final PR)

Delete `src/<Feature>/ngModule.ts`, `index.ts`, and remaining files. Update parent AngularJS module declarations to remove the dependency. Remove `downgradeInjectable` from `ng2Module.ts` if nothing needs it.

---

### Directive-to-Component migration

| File | Action |
|------|--------|
| `src/Controls/<Name>/<name>.directive.js` + template + ngModule + index | **Delete** |
| `src/Controls/ngModule.js` | Modify — remove this directive's module name |
| `src/app/Controls/<Name>/controls.<name>.component.ts` + `.html` + `.less` | **Add** |
| `src/ng2Module.ts` | Modify — add `downgradeComponent` |
| AngularJS templates using this directive | Modify — update binding syntax |

New component must be `standalone: true` with explicit `imports`. See [csFormContentTitle](../../../src/javascript/cs-client/src/app/Controls/FormContentTitle/controls.formContentTitle.component.ts) and [csWizardContinueButton](../../../src/javascript/cs-client/src/app/Controls/WizardContinueButton/controls.wizardContinueButton.component.ts) for real examples.

**Binding syntax in AngularJS templates after downgrade:**
```html
<!-- Before (AngularJS) → After (downgraded Angular component in AngularJS template) -->
title="'My Title'"          → [title]="'My Title'"
is-disabled="ctrl.disabled" → [is-disabled]="ctrl.disabled"
on-action="ctrl.fn(item)"   → (on-action)="ctrl.fn($event.item)"
```

**`&` binding → `@Output`:** AngularJS `this.onAction({ item })` becomes Angular `this.onAction.emit({ item })`. Callers access params via `$event.paramName`.

**Template syntax after downgrade:** When a downgraded Angular component appears in AngularJS templates, binding syntax switches to Angular: `[input]="expr"` for inputs, `(output)="handler($event.param)"` for outputs. For `[csHref]` usage, see `.claude/shared/routing-and-navigation.md` — "Internal Navigation: `[csHref]`".

### Making an `UpgradeComponent`-based directive standalone

When a standalone Angular component needs an `UpgradeComponent`-based directive, make the directive standalone before importing it directly (precedent: `GridPageTableColumnComponent`):

1. Add `standalone: true` to its `@Directive` decorator
2. In any `NgModule` that declared it, move it from `declarations` to `imports` (exports stay)
3. The consuming standalone component can now import it directly

### Removing UpgradeComponent after migration

`UpgradeComponent` is transitional only. In the PR that completes the directive migration: delete the wrapper class, remove its module declaration, replace usages with the new Angular component selector.

---

## Routing Changes

When a migration changes a route path, a route change is **never local to one file**. Apply the naming convention from `.claude/shared/routing-and-navigation.md` (plural for lists, `/:id` for details, `/create` for creation, kebab-case).

### Files to check and update

**cs-client (TypeScript/HTML/JS):**

| File | What to update |
|------|----------------|
| [adminRouting.module.ts](../../../src/javascript/cs-client/src/app/Admin/adminRouting.module.ts) | Add new Angular route |
| [app.uiRouter.config.js](../../../src/javascript/cs-client/src/app.uiRouter.config.js) | Remove old UI-Router state |
| [layoutsRouting.module.ts](../../../src/javascript/cs-client/src/app/Layouts/layoutsRouting.module.ts) | Add `loadChildren` if new top-level group |
| [locationMapper.service.ts](../../../src/javascript/cs-client/src/app/Common/Libraries/common.libraries.locationMapper.service.ts) | Add new Angular URL **and** remove old AngularJS URL |
| [entityUrlResolver.ts](../../../src/javascript/cs-client/src/app/Common/Libraries/common.libraries.entityUrlResolver.ts) | Update if the page is linked from entity cards, grids, or wizards |

**C# backend:**

| File | What to update |
|------|----------------|
| `src/Itst.BL/BLServices/UI Services/Service/LegacyUrlManager.cs` | Update `Get<Page>Url()` method |
| `src/Itst.Web.App/Code/EntAppUrlManager.cs` | Update URL builder; check `TimersEntAppUrlManager.cs` too |
| `src/Itst.Web.App/Admin/Admin.aspx` | Internal admin nav links |
| `src/Itst.Web.App/Mvc/Views/Cloudshare/EnvironmentMainTitleView.ascx` | Env-scoped deep links (preserve `?env=` query param) |

**Cross-repo:** Search `experiences-client` repo for references to the old path — file a separate PR if changes are needed.

### Search patterns before closing the PR

Grep for the old route path and AngularJS state name across: `src/javascript/cs-client/src/` (`.html`, `.ts`, `.js`), `src/Itst.Web.App/` (`.aspx`, `.ascx`, `.cs`), and `src/` (`.cs`). Also check `app.uiRouter.config.js` for remaining `state: 'VendorBase.TheOldStateName'` references in other states' breadcrumbs — convert to `href:` pointing to the new Angular URL.

### Breadcrumb rules

Follow `.claude/shared/routing-and-navigation.md` ("Breadcrumbs" section). Key points:
- `setPageId` id must come from the `Id` field in [MenuItemManager.cs](<../../../src/Itst.BL/BLServices/UI Services/Service/MenuItemManager.cs>)
- `setPath` entries must use `href` (from `EntityUrlResolver`), not `state` — `state` renders via `ui-sref` and silently produces broken links in the Angular shell
- Both calls belong in `ngOnInit`, not the constructor
- **Grids must not update breadcrumbs when embedded.** Subscribe to the view model, filter for `embeddedData.isEmbedded === null` (the value `GridPageWrapper` sets when it determines the grid is **not** embedded), then `take(1)`. This skips both the uninitialized default (`false`) and the embedded case (`true`). The outer component must extend `ComponentBase` to access `getViewModel$`.

---

## Spec File Upgrade

When the service being migrated has an existing AngularJS spec, upgrade it to Angular TestBed spec in the same PR. New specs go under `spec/app/`, mirroring `src/app/`.

### Test module setup

- Use `createFakeServiceProvider` for Angular services (extend `DataServiceBase`/`ViewServiceBase`)
- Use `createFakeNg1ServiceProvider` for AngularJS services (extend legacy `ServiceBase`) — custom methods require `(service as any).methodName` cast with `// eslint-disable-next-line @typescript-eslint/no-explicit-any`
- Import helpers from `../../testing`
- Use `FakeMasterModelService` as `MasterModelService` provider

### Asserting model state

- Read current model: `fakeMasterModelService.getModelOnce(viewService).subscribe(model => expect(...))`
- Inject Angular data service state: `fakeMasterModelService.applyChange(dataService.sectionName, (model: any) => ({ ...model, ... }))`
- Inject AngularJS data service state: mutate `dataService.model` directly, then call `dataService._fireEvent()`
- Filters: AngularJS specs use array index (`model.filters[0].id`); Angular specs use `Object.keys(model.filters)` / access by key
- `changeFilters` triggers `_loadPage` via 300ms debounce — use `fakeAsync` + `tick(300)`

### Running specs

See [`.claude/shared/testing.md`](../../../.claude/shared/testing.md) (Frontend Tests / Karma section). Run tests immediately after writing — fix all new failures before closing the PR.

---

## Testing Suggestions

After writing the report, tailor these to the specific feature:

- **Smoke test:** page loads, no console errors, expected API calls in Network tab, hard-refresh works
- **Service migrations:** data visible, loading states correct, error states handled, cross-service reactivity works, `downgradeInjectable` consumers still work
- **ViewService specifically:** `loadViewModel()` called on init, `getNg1DataModel$` vs `getDataModel$` correctly chosen (wrong choice = silent empty subscription)
- **DataService (Restangular → HttpClient):** compare API request URLs (trailing slashes, query params), auth headers present, test POST/PUT/DELETE not just GETs
- **Directive migrations:** renders in all parent templates, `@Input()` values received, `@Output()` events fire, styles apply correctly
- **Routing changes:** direct URL navigation works, in-app links/breadcrumbs work, browser back/forward works, old state name not referenced anywhere
- **Module teardown:** all features that depended on the AngularJS module still work, no `Unknown provider` errors

---

## Reference: Real Migration Examples

These are human-authored migrations. **Read them before writing code.**

### Service migrations (non-grid)

**ContractFolder — service-by-service over 3 PRs (BAC-21739, BAC-21877, BAC-21878):**
- ViewService PR (#9898): [contractFolder.viewservice.ts](../../../src/javascript/cs-client/src/app/ContractFolder/contractFolder.viewservice.ts) — bridged DataService via `$injector`, used `getNg1DataModel$`
- DataService PR (#9885): [contractFolder.dataservice.ts](../../../src/javascript/cs-client/src/app/ContractFolder/contractFolder.dataservice.ts) — replaced Restangular with `HttpClient`, added `downgradeInjectable` in `ng2Module.ts`
- Teardown PR (#9888): deleted entire `src/ContractFolder/`, removed from VendorLayout + SelfService module declarations, switched ViewService to `getDataModel$`

**ContractBranding — ViewService introduced `deepEqual`/`cloneFromNg1Model` (BAC-21740, BAC-21880):**
- ViewService PR (#9879): [contractBranding.viewservice.ts](../../../src/javascript/cs-client/src/app/ContractBranding/Services/contractBranding.viewservice.ts)
- DataService PR (#9910): [contractBranding.dataservice.ts](../../../src/javascript/cs-client/src/app/ContractBranding/Services/contractBranding.dataservice.ts)

### Directive migrations

**csFormContentTitle (BAC-21973, PR #9939):**
- [controls.formContentTitle.component.ts](../../../src/javascript/cs-client/src/app/Controls/FormContentTitle/controls.formContentTitle.component.ts) — simple `@Input()`-only directive

**csWizardContinueButton (BAC-21974, PR #9940):**
- [controls.wizardContinueButton.component.ts](../../../src/javascript/cs-client/src/app/Controls/WizardContinueButton/controls.wizardContinueButton.component.ts) — `@Input()` + `@Output()` with `EventEmitter`

### Grid page migration

**AWS Accounts Grid (BAC-22163, PR #9953)** and **Worker Commands Grid (BAC-22164, PR #9954):**
- Full replacement in single PR: `src/ExternalResources/<Grid>/` deleted, `src/app/ExternalResources/<Grid>/` added
- [SamplesGrid](../../../src/javascript/cs-client/src/app/ExternalResources/SamplesGrid/) — useful for grid structure reference

---

## PR Checklist

Before opening any migration PR:

- [ ] Pre-migration analysis report was produced and reviewed
- [ ] Only the target service/component changed — no unrelated modifications
- [ ] AngularJS version deleted in the same PR as Angular version added
- [ ] `$injector` bridges added for unmigrated dependencies (or removed if now Angular)
- [ ] `downgradeInjectable` added to `ng2Module.ts` if AngularJS code still needs this service
- [ ] `getNg1DataModel$` / `getNg1ViewModel$` updated to `getDataModel$` / `getViewModel$` for any newly-Angular dependencies
- [ ] State model interface typed (no avoidable `any`)
- [ ] All state updates use `applyChange()` with immutable spreads
- [ ] `loadViewModel()` called from `ngOnInit`, not a constructor
- [ ] No `$scope`, `$http`, `Restangular`, or `$inject` arrays in new Angular code
- [ ] All internal `<a>` links use `[csHref]` — no plain `[href]` for in-app navigation
- [ ] For component PRs: routing updated in `adminRouting.module.ts`, old UI-Router state removed
- [ ] For directive PRs: confirmed upgrade path (UpgradeComponent or full rewrite); `downgradeComponent` added; AngularJS templates updated to Angular binding syntax
- [ ] For column directive PRs: sortable columns have `property:` added alongside `component:`; old directive name remapping removed
- [ ] For directive PRs: if an `UpgradeComponent` wrapper existed, it is deleted in this PR
- [ ] For routing PRs: old state removed from `app.uiRouter.config.js`, `locationMapper.service.ts` updated, old path grepped across repo (including `.aspx`, `.ascx`, `.cs`), `LegacyUrlManager.cs` and `EntAppUrlManager.cs` updated, `experiences-client` checked
- [ ] Checked for existing spec files; if found: old `.spec.js` deleted, new `.spec.ts` added, all tests pass
- [ ] No TypeScript errors
- [ ] App loads without console errors in the affected area
