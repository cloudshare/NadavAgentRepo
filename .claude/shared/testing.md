# Testing in the `cloudshare` Repo

## C# / .NET Backend Tests (`Itst.Tests.BL`)

### Framework
- **NUnit 2.6** with **NUnitTestAdapter 2.3.0**
- Mocking via **Moq** + `DITestHelper.InjectMock<T>()` / `DITestHelper.InjectConcrete<TInterface, TConcrete>()`
- Common attributes: `[TestFixture]`, `[Test]`, `[TestCase(...)]`, `[SetUp]`, `[TestFixtureTearDown]`

### CRITICAL: `dotnet test` does NOT work
Projects target **.NET Framework 4.7.2**. `dotnet test` fails due to missing VS Web Application MSBuild targets. Use **MSBuild + vstest.console.exe** instead.

To find the tools on the current machine:
```powershell
Get-ChildItem 'C:\Program Files\Microsoft Visual Studio\' -Recurse -Filter 'MSBuild.exe' -ErrorAction SilentlyContinue | Select-Object FullName
Get-ChildItem 'C:\Program Files\Microsoft Visual Studio\' -Recurse -Filter 'vstest.console.exe' -ErrorAction SilentlyContinue | Select-Object FullName
```

### Build commands (run in order)
```powershell
# Step 1 — build the library under test
& '<msbuild-path>' 'src\Itst.BL\Itst.BL.csproj' `
    /p:Configuration=Debug /p:UseSharedCompilation=false /nologo /verbosity:minimal

# Step 2 — build the test project (skip rebuilding already-built refs)
& '<msbuild-path>' 'src\Itst.Tests.BL\Itst.Tests.BL.csproj' `
    /p:Configuration=Debug /p:UseSharedCompilation=false /p:BuildProjectReferences=false `
    /nologo /verbosity:minimal
```

Pre-existing assembly version conflict warnings are harmless — look only for `error` lines.

### Run commands
```powershell
# All tests
& '<vstest-path>' 'src\Itst.Tests.BL\bin\Debug\Itst.Tests.BL.dll' /logger:Console

# Filter to a specific test class
& '<vstest-path>' 'src\Itst.Tests.BL\bin\Debug\Itst.Tests.BL.dll' `
    /TestCaseFilter:'FullyQualifiedName~MenuItemManagerTests' /logger:Console
```

### Test structure conventions
- `DITestHelper.InjectMock<T>()` registers a Moq mock into the StructureMap container
- `DITestHelper.InjectConcrete<TInterface, TConcrete>()` resolves the real service under test with mocked dependencies injected
- `SetUserLevel(Mock<User>, UserLevel)` sets up `IUserHelpersWrapper` to return correct booleans for all `UserLevelIsAtLeast` / `UserLevelIsHigherThan` calls — always call this in tests that depend on authorization level
- `ObjectFactory.ResetDefaults()` in `[TestFixtureTearDown]` clears the container; required to avoid cross-fixture contamination

### When to rebuild vs re-run
- If only test code changed: rebuild `Itst.Tests.BL` only (step 2), then re-run vstest
- If production `Itst.BL` code changed: rebuild both (step 1 then step 2), then re-run vstest

---

## Frontend Tests (`cs-client` — Karma / Jasmine)

- **Karma** + **Jasmine**, run from `src/javascript/cs-client/`

### CRITICAL: always set `COV=false`
The istanbul-instrumenter-loader is not installed; `COV=true` (the npm default via `npm run test`) causes an ENOENT error that kills the run before any tests execute.

### Run commands
```bash
# Single run
COV=false node_modules/.bin/karma start --single-run

# Watch mode (two terminals)
npm run watchSpec        # terminal 1
COV=false node_modules/.bin/karma start   # terminal 2
```

Never use `npm run test` — it sets `COV=true` and always fails.

---

## E2E & API Tests — `TestAutomation` repo

Accelerate E2E (Selenium) and API tests. Repo: `cloudshare/TestAutomation`. **C# / .NET 9.0**, **NUnit 4**, Selenium WebDriver 4.x, Kiota-generated API client.

```bash
dotnet build TestAutomation.sln
dotnet test TestAutomation.sln                                    # all tests
dotnet test TestAutomation/TestAutomation.csproj                  # E2E only
dotnet test TestAutomation.AccelerateApiClient.Tests/TestAutomation.AccelerateApi.Tests.csproj  # API only
dotnet test TestAutomation.sln --filter "FullyQualifiedName~SalesTests"  # filter by class
```

Set `ASPNETCORE_ENVIRONMENT` to `Development`, `CI`, or `Production` — controls which `appsettings.*.json` is loaded.

---

## E2E & API Tests — `AutomaticTesting` repo

Full E2E and API suite for Classic + Accelerate. Repo: `cloudshare/AutomaticTesting`. **TypeScript / Playwright**, Allure reporting, Claude AI failure analysis.

```bash
npm install && npx playwright install && npx playwright install-deps
npx playwright test                        # all tests
npx playwright test sanity-part-one        # specific spec
npx playwright test --grep "pattern"       # filter by name
```

Set `TEST_ENVIRONMENT` in `.env`: `WEBINTG` (default), `PREPROD`, or `PROD`. Credentials in `.env.secret`. Do not use `npm run test` — it fails silently if credentials are missing.

---

## Quick reference

| Scenario | Command |
|---|---|
| Changed C# BL or test code | MSBuild step 1+2 → vstest all |
| Changed only C# tests | MSBuild step 2 only → vstest all |
| One test class (cloudshare repo) | vstest with `/TestCaseFilter:FullyQualifiedName~ClassName` |
| Changed cs-client Angular | Karma single-run |
| Developing cs-client tests | Karma watch mode (watchSpec + karma separately) |
| Accelerate E2E / API (TestAutomation) | `dotnet test TestAutomation.sln` |
| One TestAutomation class | `dotnet test --filter "FullyQualifiedName~ClassName"` |
| CloudShare E2E (AutomaticTesting) | `npx playwright test` from repo root |
| One Playwright spec | `npx playwright test <filename>` |
| Filter Playwright by name | `npx playwright test --grep "pattern"` |
