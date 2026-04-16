# CloudShare Logging & App Events

> For App Insights instances, cross-service correlation, and Splunk/log4net query guidance, see `.claude/shared/service-relations.md`.

## Overview

There are two parallel logging mechanisms in the WebApp:

| Mechanism | Purpose | Interface |
|-----------|---------|-----------|
| `ILog` / `ILogicalActivityLog` | Structured activity/telemetry logging | `_logger.AppEvent(...)` |
| log4net `ILog` | Free-text diagnostic logging | `_logger.Warn(...)`, `_logger.Error(...)`, etc. |

Prefer `AppEvent` over generic `Warn`/`Error` for domain failures that have a defined event in `dynamic_events_config.xml`. Use generic `Warn`/`Error` only for truly unexpected exceptions or infrastructure-level issues.

---

## AppEventsConfig — Dynamic Event Mapping

Domain events are declared in **`AppEventsConfig`** (`src/Itst.Core/EventsAuditors/AppEventsConfig.cs`) and mapped to runtime values via **`local_config/dynamic_events_config.xml`**.

### How it works

- `AppEventsConfig` is an XML-serializable class with one `AppEvent` property per event type.
- At runtime it is loaded via `DynamicXmlLoader<AppEventsConfig>`, registered as `ServiceLocator<IDynamicXmlLoader<AppEventsConfig>>.Service`.
- `ActivityLog.AppEvent(e => e.SomeEvent)` calls `ServiceLocator<IDynamicXmlLoader<AppEventsConfig>>.Service.Config` to resolve the event at call time.

### AppEvent fields (set in XML)

| Field | XML attribute/element | Notes |
|-------|-----------------------|-------|
| `EventId` | derived from element name | e.g. `"Lti1_3LaunchFailed"` |
| `Severity` | `severity` attribute | `Debug`, `Info`, `Warn`, `Error` |
| `Feature` | `feature` attribute | Used for grouping in dashboards |
| `AlertNOC` | `alertNOC` attribute | `Yes`/`No` — whether to page on-call |
| `Subject` | `<Subject>` child | Message template, supports `{Placeholder}` tokens |

### Severity guidance

- Use `Warn` for expected-but-notable failures (e.g. invalid LTI token, missing config) — things that can happen in normal operation and don't require immediate action.
- Use `Error` + `alertNOC="Yes"` only for unexpected failures that should wake someone up.

### LTI-specific events (Lti1_3BlService)

| Event property | Severity | alertNOC | When fired |
|---------------|----------|----------|-----------|
| `Lti1_3LoginFailed` | Warn | No | LTI config not found during login initiation |
| `Lti1_3LaunchFailed` | Warn | No | Token/tool/state/nonce/sub validation failure during launch |
| `InstructorDetailsNotProvided` | Error | Yes | Instructor user details missing in launch message |
| `StudentDetailsNotProvided` | Error | Yes | Student user details missing in launch message |

---

## ILogicalActivityLog interface

Only two `AppEvent` overloads are exposed on the `ILogicalActivityLog` interface (the others are commented out):

```csharp
void AppEvent(Func<AppEventsConfig, AppEvent> eventSelector);
void AppEvent(Func<AppEventsConfig, AppEvent> eventSelector, Func<AppEventAuditor.TempEvent, AppEventAuditor.TempEvent> dataSpecifier);
```

To attach extra data use the `dataSpecifier` lambda:
```csharp
_logger.AppEvent(e => e.Lti1_3LaunchFailed, ev => ev.AddEventData("ToolUrl", toolUri));
```

---

## Testing with AppEventsConfig mocks

`ActivityLog.AppEvent` and `ActivityLog.UnknownWarningEventId` both call `ServiceLocator<IDynamicXmlLoader<AppEventsConfig>>.Service` — a **static** registry separate from StructureMap/`ObjectFactory`. `DITestHelper.InjectMock<T>()` only registers into ObjectFactory; you must **also** register into `ServiceLocator`.

### Required test setup pattern

```csharp
[SetUp]
public void Setup()
{
    var mockAppEventsConfig = DITestHelper.InjectMock<IDynamicXmlLoader<AppEventsConfig>>();
    mockAppEventsConfig.Setup(d => d.Config).Returns(new AppEventsConfig
    {
        Lti1_3LoginFailed  = new AppEvent { EventId = "Lti1_3LoginFailed",  Severity = AppEvent.EventSeverity.Warn },
        Lti1_3LaunchFailed = new AppEvent { EventId = "Lti1_3LaunchFailed", Severity = AppEvent.EventSeverity.Warn },
        // add only the events exercised by the test
    });
    ServiceLocator<IDynamicXmlLoader<AppEventsConfig>>.Replace(mockAppEventsConfig.Object);
    // ...
}

[TearDown]
public void TearDown()
{
    ServiceLocator<IDynamicXmlLoader<AppEventsConfig>>.UnregisterCurrent();
    DITestHelper.ResetDefaults();
}
```

Key points:
- **Always populate `EventId` and `Severity`** on each `AppEvent` — `ActivityLog.GetAppEventId` will NPE if `EventId` is null.
- Only populate events that the code under test will actually fire; leave others null (they'll be skipped by the `if (eventConfig != null)` guard in `ActivityLog.AppEvent`).
- `UnregisterCurrent()` in teardown prevents state leaking between tests.

### Convenience helper

`DITestHelper.InjectMockAppEventsConfig()` exists but sets up an empty `AppEventsConfig` (no event properties). It's useful only if the code under test never fires a specific named event (i.e. only hits the `if (eventConfig != null)` null path).

---

## File locations

| File | Purpose |
|------|---------|
| `src/Itst.Core/EventsAuditors/AppEventsConfig.cs` | C# class with all event property declarations |
| `src/Itst.Core/Activities/Impl/ActivityLog.cs` | `AppEvent()` / `Warn()` implementation; uses `ServiceLocator` |
| `src/Itst.Core/Activities/ILogicalActivityLog.cs` | Interface — only 2 `AppEvent` overloads exposed |
| `local_config/dynamic_events_config.xml` | Runtime mapping (severity, subject, alertNOC) |
