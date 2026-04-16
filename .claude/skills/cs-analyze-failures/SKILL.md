---
name: cs-analyze-failures
description: "Analyze failure requests using Azure logs to identify root causes and suggest remediation. Cross-correlates multiple App Insights instances and investigates code from exception callstacks across CloudShare GitHub repos. WHEN: analyze failures, diagnose errors from logs, investigate failed requests, debug Azure service errors, root cause analysis, failure investigation, KQL log analysis, Application Insights failures, Function App errors, Container Apps crashes, AKS pod failures, App Service errors, structured incident report, cross-service correlation, callstack investigation, trace exception to code, support ticket investigation, customer-reported API error, support ticket describes a 500 or 400, Jira ticket with API failure, third-party integration reporting error, internal error details leaked in response, SUP ticket, API failure with specific request parameters."
---

# Azure Failure Analysis

> Systematic workflow for analyzing failed requests using Azure logs. Produces a root cause summary, remediation steps, and a structured incident report.

## Subscription & Context

- **Azure Subscription**: `CloudShare Production Services on Azure`
- Always scope queries and resource lookups to this subscription unless the user explicitly names another.
- When using Azure MCP tools (`mcp_azure_*`), confirm the active subscription is `CloudShare Production Services on Azure` before running queries.
- **Failure scope**: Only investigate **HTTP 400 and 500** responses exactly. Ignore all other status codes in all queries and analysis.
- **400s from third-party API calls**: HTTP 400 responses caused by external tools or third parties making direct API requests (e.g., REST clients, integrations, scripts hitting the API directly) are generally expected and do not require investigation — they reflect bad input from the caller, not a backend bug. Only escalate a 400 spike if it originates from internal services or the CloudShare frontend, or if the user explicitly asks to investigate it.
- **Telemetry retention**: Query across the **full available retention window** (up to 90 days for Log Analytics, 730 days for archived logs). Do NOT default to short windows like `ago(1h)` — always ask for or infer the relevant time range, then fall back to the widest available window if uncertain.

### Known App Insights Instances

> Read `.claude/shared/service-relations.md` for the full service topology, App Insights instances, AKS services, and request routing table.
> Read `.claude/shared/accelerate-auth.md` for the auth flow (BFF cookie → JWT → Experiences.Service RBAC).
> Read `.claude/shared/entity-change-mechanism.md` for the WebApp → Service Bus → Experiences sync pipeline.

### GitHub Repositories for Code Investigation

> Read `.claude/shared/cloudshare-repos.md` for the full repository list, callstack frame → repo mapping, and repo → Jira component mapping.

### Known Log Analytics Workspaces

The primary Log Analytics workspace collects telemetry from all linked App Insights instances. Use this workspace when querying via `monitor_workspace_log_query`.

| Workspace | Resource Group | Linked App Insights |
|-----------|----------------|---------------------|
| `classic-log-workspace-prod` | `production-environment-kubernetes` | `classic-appinsights-prod` (CloudShare WebApp / API v3) |
| `DefaultWorkspace-82ecc0b0-9c2d-4657-9745-f6de058cee84-EUS` | `defaultresourcegroup-eus` | `prod-appinsights` (Experiences Backend / BFF / API Gateway) |

> **Splunk — additional WebApp logs**: The CloudShare WebApp writes more detailed application logs to **Splunk** at https://splunk.cloudshare.com/. Splunk often contains richer context (full request payloads, internal service traces, verbose error details) that App Insights may not capture. When App Insights logs are insufficient to identify a root cause for a WebApp/API v3 failure, suggest checking Splunk as a next step or ask the user to pull relevant Splunk logs.

> **Azure MCP tool workflow**:
> 1. Use `monitor_workspace_list` (subscription: `CloudShare Production Services on Azure`) to list available workspaces.
> 2. If the workspace resource group is unknown, use `azure_resources-query_azure_resource_graph` with a query like `Resources | where type == "microsoft.operationalinsights/workspaces" | project name, resourceGroup` to find it.
> 3. Use `monitor_workspace_log_query` with the appropriate `resource-group` and `workspace` values from the table above.
>
> **CRITICAL — `hours` parameter**: `monitor_workspace_log_query` accepts an `hours` parameter that controls how far back the query window extends from now. **The default is 24 hours.** Any data older than ~1 day will return **0 results** with the default, even when the KQL `TimeGenerated` filter covers the target date. This is the single most common reason queries return 0 results for historical incidents.
>
> | Scenario | Recommended `hours` value |
> |---|---|
> | Incident happened today | `24` (default, can omit) |
> | Incident happened 2–7 days ago | `240` (10 days) |
> | Incident happened 8–30 days ago | `750` (31 days) |
> | Incident happened 31–90 days ago | `2200` (92 days) |
> | Unknown / broad sweep | `2200` (safe maximum for most workspaces) |
>
> Always set `hours` explicitly when the incident date is known. Example: for an incident on March 11 queried on March 26, that is 15 days ago — use `hours: 400` at minimum.
>
> **Always also set** `subscription: "CloudShare Production Services on Azure"` — omitting it may route queries to the wrong subscription and silently return 0 rows.
>
> **MCP tool limitation — App Insights-native syntax is not supported**: The MCP tool routes queries through the Log Analytics REST API. This means:
> - `app('resource-name').tableName` cross-resource references are **not supported** — use `workspace()` references or separate workspace queries instead.
> - App Insights-direct column names (`timestamp`, `operation_Id`, `cloud_RoleName`, `itemType`, `customDimensions`) are **not available** — use workspace column names (`TimeGenerated`, `OperationId`, `AppRoleName`, `Properties`).
> - Queries using `union *` with `app()` references, or `$table`, will fail or return 0 rows when executed via MCP.
> - **For cross-resource App Insights queries (e.g., union across `prod-appinsights` + `classic-appinsights-prod`), run them directly in the Azure portal browser UI.**

---

## Triggers

Use this skill when the user wants to:
- Analyze failed HTTP requests or background jobs in Azure
- Identify root cause from Azure Monitor, App Insights, or service logs
- Generate a structured incident report from log data
- Investigate errors in Function Apps, Container Apps, AKS, or App Service
- Write or run KQL queries to surface failures
- Investigate a support ticket (SUP-*, CS-*) that describes an API failure or unexpected error response
- A customer or third-party integrator is reporting a 400 or 500 from a CloudShare API endpoint
- Someone pastes a Jira ticket or describes a customer-reported error and asks to investigate or RCA it

---

## Workflow

### Step 0 — Starting from a Support Ticket (Jira)

When the entry point is a **Jira ticket** (e.g., SUP-* or CS-*) rather than raw log data, apply this pre-flight before Step 1:

1. **Fetch the ticket** using `mcp_com_atlassian_getJiraIssue` (cloudId: `cloudshare.atlassian.net`) to get the full description, request/response bodies, and any comments.

2. **Extract key anchors** from the ticket body:
   - **API endpoint** and HTTP method (e.g., `POST /api/resource`)
   - **Unique payload values** that can be used as log anchors — entity names, IDs, passphrases (e.g., a training name or a `teamId`). These are the most reliable anchors for Step 1a.
   - **Time window** — ticket creation date or any timestamps mentioned in the description. Use these for the `hours` parameter in `monitor_workspace_log_query`.
    - **Error code and error message** — especially if the response body contains error details (e.g., a third-party stack trace or validation message)
    - **Customer / tenant identifiers** — `projectId`, user email, API key prefix, or company name

3. **Check for internal error leakage**: If the ticket response body contains a stack trace or error object from an internal system (e.g., a background job runner, a third-party automation service), that is a **secondary issue** (data disclosure) in addition to the root-cause 500. Flag it explicitly in the incident report.

4. **Determine the triggering caller**: External integrations (third-party automation tools, webhooks, API clients) often do **not** propagate CloudShare's `operation_Id`. Do **not** look for a shared `operation_Id` between the external caller and CloudShare — instead, go directly to **Step 1a** and anchor queries on payload values (entity name, entity ID, email address) extracted from the ticket.

5. **Search Jira for related tickets** before going deep into logs — another ticket may already have the RCA:
   ```jql
   project in (CS, SUP) AND summary ~ "<endpoint or error keyword>" AND issuetype in (Bug, Incident) ORDER BY created DESC
   ```

6. After completing Step 0, proceed to **Step 1** using the time window and anchors extracted above.

---

### Step 1 — Identify the Scope

Collect from the user (or infer from context):
- **Time window**: When did failures start / end? Follow the **Time Window Strategy** below.
- **Service**: Which Azure resource(s) are involved? Scope to the `CloudShare Production Services on Azure` subscription.
- **Symptom**: Error code, exception type, HTTP status, or observable behavior?

**Time Window Strategy** — apply these rules in order:

1. **Known specific date/time** (e.g., from a ticket or trace): start with **±1 day** around that timestamp. If 0 results, widen to ±3 days.
2. **Still 0 results**: always expand to the **last 30 days** before concluding there is no data.
3. **Unknown / no date given**: query **full retention** (`ago(90d)` or `ago(30d)`) as the default; never use a narrow window on the first attempt.
4. **Never declare "no logs found" after querying a narrow window only.** Always retry with at least 30 days before giving up.

> **`monitor_workspace_log_query` — `hours` parameter is mandatory for historical data**: The MCP tool's `hours` parameter (default: `24`) is a **server-side cutoff applied before the KQL filter runs**. This means a KQL `where TimeGenerated between (datetime(2026-03-11) .. datetime(2026-03-12))` will return **0 rows** if `hours` is not set to cover that range — regardless of how correct the KQL is. **Always calculate `hours` from the incident date to now before running any query:**
>
> ```
> hours = ceil((now - incident_date) / 1 hour) + 24   // add 24h buffer
> ```
>
> Example: incident on 2026-03-11, current date 2026-03-26 → 15 days → 360h + 24h buffer → use `hours: 400`.
> When in doubt, use `hours: 2200` as a safe default for any incident within the last 90 days.

**Time range variables** — define once at the top of every query set:

```kql
// Set these based on user input; default to last 30 days if unknown
let startTime = ago(30d);   // replace with datetime(YYYY-MM-DD) if a date is known
let endTime = now();
```

If the user provides a log snippet, skip ahead to Step 3.

---

### Step 2 — Pull Logs from the Right Source

Route to the appropriate source based on the service type:

| Service | Log Source | Tool |
|---------|-----------|------|
| Function Apps | App Insights `requests` + `exceptions` tables | KQL via Log Analytics |
| Container Apps | `ContainerAppConsoleLogs_CL` or App Insights | KQL via Log Analytics |
| AKS / Kubernetes | `ContainerLog`, `KubePodInventory` | KQL via Log Analytics |
| App Service | `AppServiceHTTPLogs`, `AppServiceAppLogs` | KQL via Log Analytics |
| Any service | App Insights `exceptions`, `traces`, `dependencies` | KQL via App Insights |

#### Method Execution Failure Traces (`prod-appinsights`)

The `traces` table in **prod-appinsights** contains structured log entries that capture request and response bodies for failed method executions. **Always query these when investigating a 400 or 500** — they reveal the actual payload and auth context, which exceptions alone do not.

Trace message format:
```
Method execution failed. UserId: {UserId}, RequestBody: {RequestBody}, ResponseBody: {ResponseBody}, AuthorizationHeader: {AuthorizationHeader}
```

KQL to retrieve and parse these traces:

```kql
let startTime = datetime(2000-01-01);
let endTime = now();
// ── Method execution failure traces with parsed fields ──
traces
| where timestamp between (startTime .. endTime)
| where message startswith "Method execution failed."
| extend
    UserId            = extract(@"UserId:\s*([^,]+)",            1, message),
    RequestBody       = extract(@"RequestBody:\s*([^,]+(?:,(?!\\s*\\w+:)[^,]*)*)", 1, message),
    ResponseBody      = extract(@"ResponseBody:\s*([^,]+(?:,(?!\\s*\\w+:)[^,]*)*)", 1, message),
    AuthorizationHeader = extract(@"AuthorizationHeader:\s*(.+)$", 1, message)
| project timestamp, cloud_RoleName, operation_Id, UserId, RequestBody, ResponseBody, AuthorizationHeader
| order by timestamp desc

// ── Correlate method failure traces with a specific failed request ──
let targetOperationId = "<operation_Id from requests table>";
traces
| where timestamp between (startTime .. endTime)
| where operation_Id == targetOperationId
| where message startswith "Method execution failed."
| extend
    UserId            = extract(@"UserId:\s*([^,]+)",            1, message),
    RequestBody       = extract(@"RequestBody:\s*([^,]+(?:,(?!\\s*\\w+:)[^,]*)*)", 1, message),
    ResponseBody      = extract(@"ResponseBody:\s*([^,]+(?:,(?!\\s*\\w+:)[^,]*)*)", 1, message),
    AuthorizationHeader = extract(@"AuthorizationHeader:\s*(.+)$", 1, message)
| project timestamp, cloud_RoleName, UserId, RequestBody, ResponseBody, AuthorizationHeader
```

> **Security note**: `AuthorizationHeader` in these traces may contain bearer tokens. Do not log, share, or store raw values from this field — use them only to confirm identity context during investigation, then discard.

#### HttpRequestException Traces — `SerializedRequestBody` and `MessageBody` (`prod-appinsights`)

When a service makes an outbound HTTP call that fails, `CheckResponseInternalAsync` logs the error using structured logging:

```csharp
logger.LogError(eventId, exception, "MessageBody: {MessageBody}, SerializedRequestBody: {SerializedRequestBody}", messageBody, serializedRequestBody);
```

Because this call passes an **exception** to `LogError`, App Insights records it as an **exception** telemetry item (not a trace). The structured log parameters (`MessageBody`, `SerializedRequestBody`) are stored in the exception's **`Properties`** column — **not** in the `Message` text of `AppTraces`.

> **Critical**: Do NOT search `AppTraces` for `Message startswith "MessageBody:"` — that will return 0 results. Instead, query `AppExceptions` for `HttpRequestException` entries and read the `Properties` column.

- **`MessageBody`** — the response body returned by the downstream WebApp (API v3, `cloudshare` repo). Use this to understand what the backend API actually returned (e.g., error message, validation details, exception message).
- **`SerializedRequestBody`** — the full serialized JSON payload sent to the downstream API. Use this to verify what fields were sent and whether they were correctly formed.
- **`CategoryName`** — identifies the calling class (e.g., `"Experiences.BL.ApiClients.CourseApiClient"`), useful when multiple clients make outbound calls.

KQL to retrieve these properties from `AppExceptions` (workspace-based, via `monitor_workspace_log_query`):

```kql
let startTime = datetime(2000-01-01);
let endTime = now();
// ── HttpRequestException entries with MessageBody and SerializedRequestBody ──
AppExceptions
| where TimeGenerated between (startTime .. endTime)
| where ExceptionType == 'System.Net.Http.HttpRequestException'
| extend
    MessageBody           = tostring(Properties["MessageBody"]),
    SerializedRequestBody = tostring(Properties["SerializedRequestBody"]),
    CategoryName          = tostring(Properties["CategoryName"])
| project TimeGenerated, AppRoleName, OperationId, MessageBody, SerializedRequestBody, CategoryName
| order by TimeGenerated desc

// ── Correlate with a specific failed request ──
let targetOperationId = "<OperationId from AppRequests>";
AppExceptions
| where TimeGenerated between (startTime .. endTime)
| where OperationId == targetOperationId
| where ExceptionType == 'System.Net.Http.HttpRequestException'
| extend
    MessageBody           = tostring(Properties["MessageBody"]),
    SerializedRequestBody = tostring(Properties["SerializedRequestBody"]),
    CategoryName          = tostring(Properties["CategoryName"])
| project TimeGenerated, AppRoleName, MessageBody, SerializedRequestBody, CategoryName
```

> **Tip**: `SerializedRequestBody` contains the full JSON body sent to the API — including all fields. Comparing it against a successful request body immediately reveals any field that is new, missing, or malformed (the discriminating factor). This is often the fastest path to identifying the root cause when the downstream API returns a 500.

> **Retry note**: `experiences-backend` has a retry policy that retries 3 times on 500 responses, resulting in **4 total exception entries** in the WebApp logs for a single logical request failure. When counting affected requests, group by `OperationId` and divide by 4, or use `AppRequests` counts instead.

---

#### Finding the Original Incoming Request Body — `FailedRequestLoggerFilter` (`prod-appinsights`)

The `FailedRequestLoggerFilter` in Experiences Service logs the **full incoming request and response** for any failed call. This captures what the upstream caller (e.g., Administrate/n8n, a third-party integration) actually sent — before any mapping or transformation — making it the authoritative record of the raw inbound payload.

These entries appear in `AppTraces` (or `AppExceptions`) with the structured property `CategoryName = "Experiences.Service.Logging.FailedRequestLoggerFilter"`. The request and response bodies are stored as custom properties (`RequestBody`, `ResponseBody`) in the `Properties` column, **not** in the `Message` text.

```kql
let startTime = datetime(2000-01-01);
let endTime = now();
// ── FailedRequestLoggerFilter traces — original inbound request body ──
AppTraces
| where TimeGenerated between (startTime .. endTime)
| where Properties["CategoryName"] == "Experiences.Service.Logging.FailedRequestLoggerFilter"
| extend
    RequestBody  = tostring(Properties["RequestBody"]),
    ResponseBody = tostring(Properties["ResponseBody"])
| project TimeGenerated, AppRoleName, OperationId, RequestBody, ResponseBody
| order by TimeGenerated desc

// ── Correlate with a specific failed request ──
let targetOperationId = "<OperationId from AppRequests>";
AppTraces
| where TimeGenerated between (startTime .. endTime)
| where OperationId == targetOperationId
| where Properties["CategoryName"] == "Experiences.Service.Logging.FailedRequestLoggerFilter"
| extend
    RequestBody  = tostring(Properties["RequestBody"]),
    ResponseBody = tostring(Properties["ResponseBody"])
| project TimeGenerated, AppRoleName, RequestBody, ResponseBody
```

> **When to use**: Use `FailedRequestLoggerFilter` traces to see exactly what payload the caller sent to Experiences Service. Compare this against the `SerializedRequestBody` from the `HttpRequestException` in `AppExceptions` (what Experiences Service sent downstream) — the diff between these two reveals any field mapping or transformation issues in the Experiences Service layer.

#### Root Exception & Callstack Extraction

When you have a failing `operation_Id`, retrieve the **original (innermost/root) exception** and its full callstack. Chained exceptions in .NET or Node.js often hide the real cause inside the innermost exception — always inspect `innermostType` and `innermostMessage` first.

```kql
let targetOperationId = "<operation_Id from requests table>";
let startTime = datetime(2000-01-01);
let endTime = now();
// ── Root exception: outermost and innermost details with raw callstack ──
exceptions
| where timestamp between (startTime .. endTime)
| where operation_Id == targetOperationId
| extend parsedDetails = todynamic(details)
| extend
    outermostType    = type,
    outermostMessage = outerMessage,
    innermostType    = innermostType,
    innermostMsg     = innermostMessage,
    rawCallstack     = tostring(parsedDetails[0].rawStack),
    parsedStack      = parsedDetails[0].parsedStack
| project timestamp, cloud_RoleName, outermostType, outermostMessage, innermostType, innermostMsg, rawCallstack, parsedStack
| order by timestamp asc

// ── Expand individual callstack frames for line-level mapping ──
exceptions
| where timestamp between (startTime .. endTime)
| where operation_Id == targetOperationId
| extend parsedDetails = todynamic(details)
| mv-expand frame = parsedDetails[0].parsedStack
| extend
    frameLevel    = toint(frame.level),
    frameMethod   = tostring(frame.method),
    frameAssembly = tostring(frame.assembly),
    frameFileName = tostring(frame.fileName),
    frameLine     = toint(frame.line)
| project frameLevel, frameMethod, frameAssembly, frameFileName, frameLine
| order by frameLevel asc
```

> **Tip**: `parsedDetails[0]` is the outermost exception; if the exception chain has multiple entries in `details`, iterate over all of them (`mv-expand exEntry = parsedDetails`) to find the innermost frame that points into application code (vs framework code).

**Workspace-based equivalent** (use these column names with `monitor_workspace_log_query`):

```kql
let targetOperationId = "<OperationId from AppRequests>";
let startTime = datetime(2000-01-01);
let endTime = now();
// ── Root exception via workspace-based AppExceptions ──
AppExceptions
| where TimeGenerated between (startTime .. endTime)
| where OperationId == targetOperationId
| extend parsedDetails = todynamic(Details)
| extend
    outermostType    = ExceptionType,
    outermostMessage = OuterMessage,
    // NOTE: InnermostExceptionType / InnermostExceptionMessage are often empty — use Details JSON instead
    innermostType    = tostring(parsedDetails[-1].type),
    innermostMsg     = tostring(parsedDetails[-1].message),
    rawCallstack     = tostring(parsedDetails[0].rawStack),
    parsedStack      = parsedDetails[0].parsedStack
| project TimeGenerated, AppRoleName, outermostType, outermostMessage, innermostType, innermostMsg, rawCallstack, parsedStack
| order by TimeGenerated asc

// ── Expand individual callstack frames ──
AppExceptions
| where TimeGenerated between (startTime .. endTime)
| where OperationId == targetOperationId
| extend parsedDetails = todynamic(Details)
| mv-expand frame = parsedDetails[0].parsedStack
| extend
    frameLevel    = toint(frame.level),
    frameMethod   = tostring(frame.method),
    frameAssembly = tostring(frame.assembly),
    frameFileName = tostring(frame.fileName),
    frameLine     = toint(frame.line)
| project frameLevel, frameMethod, frameAssembly, frameFileName, frameLine
| order by frameLevel asc
```

> **Tip**: If `parsedDetails[0].parsedStack` or `rawCallstack` (via `todynamic`) are empty — which happens in some workspaces — **project the raw `Details` column directly** instead. The `Details` column (workspace) / `details` (App Insights direct) is a raw JSON string containing the full exception chain and callstack. Read it as plain text; no `todynamic` required:
> ```kql
> AppExceptions
> | where TimeGenerated between (startTime .. endTime)
> | where OperationId == targetOperationId
> | project TimeGenerated, AppRoleName, ExceptionType, OuterMessage, OperationId, Details
> ```
> Parse the `Details` JSON string manually to find `parsedStack` frame entries.

> **No PDB symbols / empty `rawCallstack`**: When the deployed assembly has no PDB symbol file, `rawCallstack` will be empty and all frame `line` values will be `0`. This is normal for production builds without source maps. The `parsedStack` frames still contain **method names and assembly names** which are sufficient to identify the faulting method and map it to source code. Do not discard a callstack just because `rawCallstack` is empty — the `method` field in each `parsedStack` frame is still reliable.



> **Time window reminder**: Start with ±1 day around any known date, then widen to 30 days if 0 results. Never declare no data from a narrow window alone. Replace `startTime` / `endTime` with actual values, or use `ago(30d)` / `now()` to sweep the last 30 days.

> **Table naming — workspace-based vs App Insights-direct**
>
> There are two query contexts that use **different table and column names**. Mixing them causes `SEM0100: Failed to resolve table` errors.
>
> | | App Insights-direct (`app("name").table`) | Workspace-based (`monitor_workspace_log_query`) |
> |---|---|---|
> | Requests | `requests` | `AppRequests` |
> | Exceptions | `exceptions` | `AppExceptions` |
> | Traces | `traces` | `AppTraces` |
> | Dependencies | `dependencies` | `AppDependencies` |
> | Time column | `timestamp` | `TimeGenerated` |
> | Role column | `cloud_RoleName` | `AppRoleName` |
> | Operation ID | `operation_Id` | `OperationId` |
> | HTTP status | `resultCode` | `ResultCode` |
> | Duration | `duration` | `DurationMs` |
> | Exception type | `type` | `ExceptionType` |
> | Message | `message` | `Message` |
> | Outer type | `outerType` | `OuterType` |
> | Outer message | `outerMessage` | `OuterMessage` |
> | Innermost type | `innermostType` | `InnermostType` |
> | Innermost message | `innermostMessage` | `InnermostMessage` |
>
> The KQL examples below use **App Insights-direct names**. When using `monitor_workspace_log_query`, substitute the workspace-based names from the table above.
>
> **Important**: The workspace `AppExceptions` columns for the innermost exception are `InnermostType` and `InnermostMessage` (NOT `InnermostExceptionType` / `InnermostExceptionMessage` — those don't exist and will cause SEM0100). Similarly there is no `ExceptionMessage` column — use `Message` or `OuterMessage`. The complete set is: `ExceptionType`, `Message`, `OuterType`, `OuterMessage`, `InnermostType`, `InnermostMessage`.
>
> **Never search `AppExceptions` using vague keywords in `OuterMessage` or `InnermostMessage`** — this produces unrelated noise. Instead:
> - **Primary path**: anchor on endpoint `Name` from `AppRequests` → collect `OperationId`s → join to `AppExceptions`.
> - **Fallback (Steps 1a–1c returned 0)**: search the raw `details` column (App Insights direct) or `Details` column (workspace) for a **precise exception class name or method name**. This column contains the full serialized exception JSON including the callstack, so a type/method name search is highly specific and reliable. See STEP 1d below.

```kql
// ── TELEMETRY SWEEP: discover earliest & latest data available ──
union isfuzzy=true requests, exceptions, traces, dependencies, customEvents
| summarize min(timestamp), max(timestamp), count() by Type = itemType
| order by min_timestamp asc

// ── Failed HTTP requests — HTTP 400 and 500 only ──
let startTime = datetime(2000-01-01);
let endTime = now();
requests
| where timestamp between (startTime .. endTime)
| where resultCode in ("400", "500")
| project timestamp, name, resultCode, duration, url, operation_Id, cloud_RoleName
| order by timestamp desc

// ── Finding the right OperationId — use the most specific anchor available ──
// Priority: 1) unique payload value → 2) entity ID in URL → 3) endpoint Name → 4) raw details/message fallback

// ── STEP 1a: Anchor on payload value (run in BOTH workspaces) ──
// Search Message AND Properties (customDimensions) — payload values such as training names
// and entity names are often stored in customDimensions only, not in Message.
let payloadAnchor = "<unique string from request body — e.g. training name fragment>";

// Workspace-based: traces
AppTraces
| where TimeGenerated between (startTime .. endTime)
| where Message has payloadAnchor or Properties has payloadAnchor
| project TimeGenerated, Message, Properties, OperationId, AppRoleName
| order by TimeGenerated asc

// Workspace-based: requests (catches names/URLs and custom properties)
AppRequests
| where TimeGenerated between (startTime .. endTime)
| where Name has payloadAnchor or Url has payloadAnchor or Properties has payloadAnchor
| project TimeGenerated, Name, Url, ResultCode, OperationId, AppRoleName
| order by TimeGenerated asc

// ── App Insights-direct equivalent — run in the portal browser UI (NOT via MCP tool) ──
// Covers all telemetry types; customDimensions is the primary carrier for payload fields.
union requests, traces, exceptions, dependencies
| where timestamp between (startTime .. endTime)
| where customDimensions has payloadAnchor
    or name has payloadAnchor
    or message has payloadAnchor
| project timestamp, itemType, name, message, resultCode, operation_Id, cloud_RoleName, customDimensions
| order by timestamp asc

// Cross-resource version (portal only) — searches prod-appinsights AND classic-appinsights-prod in one query
union
    requests, traces, exceptions,
    app('classic-appinsights-prod').requests,
    app('classic-appinsights-prod').traces,
    app('classic-appinsights-prod').exceptions
| where timestamp between (startTime .. endTime)
| where customDimensions has payloadAnchor
    or name has payloadAnchor
    or message has payloadAnchor
| project timestamp, itemType, appRoleName, operation_Id, name, message, resultCode, customDimensions
| order by timestamp asc

// ── STEP 1b: Anchor on entity ID in URL ──
let entityId = "<ID from ticket payload or URL>";
AppRequests
| where TimeGenerated between (startTime .. endTime)
| where ResultCode in ("400", "500")
| where Url contains entityId
| project TimeGenerated, Name, ResultCode, Url, OperationId, AppRoleName
| order by TimeGenerated asc

// ── STEP 1c: Anchor on exact endpoint Name (no fuzzy contains) ──
let failingEndpointName = "<exact Name value from AppRequests>";
AppRequests
| where TimeGenerated between (startTime .. endTime)
| where ResultCode in ("400", "500")
| where Name == failingEndpointName
| project TimeGenerated, Name, ResultCode, Url, OperationId, AppRoleName
| order by TimeGenerated asc

// ── STEP 1d: Fallback — raw exception details or trace message (when Steps 1a–1c return 0) ──
// Use ONLY precise exception type names or method names — not vague keywords.

// By exception type name
AppExceptions
| where TimeGenerated between (startTime .. endTime)
| where Details contains "<FullExceptionTypeName>"  // e.g., "ActionRestrictedToSpecificRegionException"
| project TimeGenerated, ExceptionType, OuterMessage, OperationId, AppRoleName, Details
| order by TimeGenerated desc

// By method name in callstack
AppExceptions
| where TimeGenerated between (startTime .. endTime)
| where Details contains "<MethodName>"  // e.g., "SetCloudFoldersSharingWithClass"
| project TimeGenerated, ExceptionType, OuterMessage, OperationId, AppRoleName, Details
| order by TimeGenerated desc

// By trace message
AppTraces
| where TimeGenerated between (startTime .. endTime)
| where Message contains "<specific class or method name>"
| project TimeGenerated, Message, OperationId, AppRoleName
| order by TimeGenerated desc

// ── STEP 1d validation: verify the candidate OperationId has a 4xx/5xx on the expected endpoint ──
// Discard and continue if 0 rows, or if Name/HTTP method don't match the endpoint under investigation.
let candidateOpId = "<OperationId from STEP 1d>";
AppRequests
| where TimeGenerated between (startTime .. endTime)
| where OperationId == candidateOpId
| where ResultCode in ("400", "500")
| project TimeGenerated, Name, ResultCode, Url, OperationId, AppRoleName

// ── STEP 2: Join collected OperationId(s) to AppExceptions ──
let failingOpIds = dynamic(["<OperationId1>", "<OperationId2>"]);
AppExceptions
| where TimeGenerated between (startTime .. endTime)
| where OperationId in (failingOpIds)
| project TimeGenerated, ExceptionType, OuterMessage, InnermostType, InnermostMessage, OperationId, AppRoleName, Details
| order by TimeGenerated desc

// ── Function App invocation failures — HTTP 400 and 500 (full range, bucketed) ──
requests
| where timestamp between (startTime .. endTime)
| where resultCode in ("400", "500") and cloud_RoleName contains "func"
| summarize count() by name, resultCode, bin(timestamp, 1h)
| order by timestamp desc

// ── App Service HTTP logs — HTTP 400 and 500 (full range) ──
AppServiceHTTPLogs
| where TimeGenerated between (startTime .. endTime)
| where ScStatus in (400, 500)
| project TimeGenerated, CsHost, CsMethod, CsUriStem, ScStatus, TimeTaken
| order by TimeGenerated desc

// ── App Service application logs (full range) ──
AppServiceAppLogs
| where TimeGenerated between (startTime .. endTime)
| where Level in ("Error", "Critical")
| project TimeGenerated, Host, Level, ResultDescription
| order by TimeGenerated desc

// ── Container App console errors (full range) ──
ContainerAppConsoleLogs_CL
| where TimeGenerated between (startTime .. endTime)
| where Log_s contains "ERROR" or Log_s contains "Exception"
| project TimeGenerated, ContainerAppName_s, Log_s
| order by TimeGenerated desc

// ── AKS pod crash / OOMKill events (full range) ──
KubePodInventory
| where TimeGenerated between (startTime .. endTime)
| where PodStatus in ("Failed", "OOMKilled", "CrashLoopBackOff")
| project TimeGenerated, Name, Namespace, PodStatus, ContainerName
| order by TimeGenerated desc

// ── HTTP 400/500 failure rate trend over time (spot regressions across full history) ──
requests
| where timestamp between (startTime .. endTime)
| summarize total = count(), failures = countif(resultCode in ("400", "500")) by bin(timestamp, 1d)
| extend failureRate = round(100.0 * failures / total, 2)
| order by timestamp asc
```

#### Cross-App Insights Correlation

When a request spans multiple services (e.g., experiences-client → experiences-backend → cloudshare backend), correlate by `operation_Id` across App Insights instances using a **cross-resource query**.

> **Portal-only**: the queries below use App Insights-direct syntax (`app()`, `timestamp`, `operation_Id`, `customDimensions`). They must be run in the **Azure portal browser UI** (Application Insights → Logs). The MCP tool does not support this syntax — use workspace-based queries with `AppRequests`/`AppExceptions` and `OperationId` via the MCP tool instead.

> **OperationId propagation caveat**: When the triggering caller is an external system (e.g., a webhook or a third-party integration), it may inject its own trace context. The `operation_Id` visible to that caller may **not** be the one CloudShare propagated internally. In these cases, skip direct `operation_Id` lookup and anchor on a payload property instead (see STEP 1a `customDimensions has` queries above).

```kql
let targetOperationId = "<operation_Id from initial failure>";
let startTime = datetime(2000-01-01);
let endTime = now();
union
    app("classic-appinsights-prod").requests,
    app("prod-appinsights").requests,
    app("<experiences-client-appinsights-resource-name>").pageViews
| where timestamp between (startTime .. endTime)
| where operation_Id == targetOperationId
| project timestamp, itemType, name, resultCode, duration, success, cloud_RoleName, operation_Id
| order by timestamp asc

// Cross-resource exception trace for the same operation
union
    app("classic-appinsights-prod").exceptions,
    app("prod-appinsights").exceptions,
    app("<experiences-client-appinsights-resource-name>").exceptions
| where timestamp between (startTime .. endTime)
| where operation_Id == targetOperationId
| project timestamp, cloud_RoleName, type, outerMessage, innermostMessage, details, operation_Id
| order by timestamp asc

// Find all operation_Ids that touched multiple services (HTTP 400 and 500 only)
union
    app("classic-appinsights-prod").requests,
    app("prod-appinsights").requests
| where timestamp between (startTime .. endTime)
| where resultCode in ("400", "500")
| summarize services = make_set(cloud_RoleName), failureCount = count() by operation_Id
| where array_length(services) > 1
| order by failureCount desc
```

> **Tip**: Replace `app("<name>")` resource names with the actual App Insights resource names discovered in Step 2. If a shared Log Analytics workspace is configured, you can omit the `app()` prefix and query all tables directly.

---

### Step 3 — Analyze the Log Data

Given the log output, identify:

1. **First occurrence** — When did the first failure appear?
2. **Error pattern** — Is this a consistent error type, or intermittent? What's the failure rate?
3. **Blast radius** — Which operations/endpoints/pods/instances are affected? To quantify per-tenant or per-class impact, extract URL parameters from the failing requests:

   ```kql
   // Workspace-based: extract entity IDs from URL to identify affected tenants/classes
   let startTime = datetime(2000-01-01);
   let endTime = now();
   AppRequests
   | where TimeGenerated between (startTime .. endTime)
   | where ResultCode in ("400", "500")
   | extend classId = extract(@"[?&]classId=([^&]+)", 1, Url)
   | extend envId   = extract(@"[?&]envId=([^&]+)",   1, Url)
   | extend userId  = extract(@"[?&]userId=([^&]+)",  1, Url)
   | summarize failures = count(), firstSeen = min(TimeGenerated), lastSeen = max(TimeGenerated) by classId, envId, userId
   | order by failures desc
   ```

   This immediately tells you whether the failure is global or isolated to specific tenants/classes.

4. **Retry storms** — Check for repeated `OperationId` values, which indicate the same client retrying a persistently broken request:

   ```kql
   // Workspace-based: detect retry storms — same OperationId appearing multiple times
   AppRequests
   | where TimeGenerated between (startTime .. endTime)
   | where ResultCode in ("400", "500")
   | summarize retryCount = count(), firstAttempt = min(TimeGenerated), lastAttempt = max(TimeGenerated) by OperationId, Name
   | where retryCount > 1
   | order by retryCount desc
   ```

   High `retryCount` for the same `OperationId` confirms a broken request that never recovers — useful for estimating total user impact.

5. **Correlation** — Do exceptions share an `OperationId`? Is the failure upstream or downstream? Run the cross-App Insights queries from Step 2 to trace the call chain across services.
6. **Request/response context** — For any matched `operation_Id`, query the following in prod-appinsights:
   - `AppTraces` for `"Method execution failed."` entries → reveals `RequestBody`, `ResponseBody`, `UserId` for the originating service
   - `AppTraces` for entries where `Properties["CategoryName"] == "Experiences.Service.Logging.FailedRequestLoggerFilter"` → reveals the raw inbound request body (what the caller sent to Experiences Service) via `Properties["RequestBody"]` and `Properties["ResponseBody"]`
   - `AppExceptions` for `ExceptionType == 'System.Net.Http.HttpRequestException'` entries → reveals the outbound payload (`Properties["SerializedRequestBody"]`) sent to the downstream API and the response it returned (`Properties["MessageBody"]`); **not** in `AppTraces` — use `AppExceptions.Properties` only
7. **Recent changes** — Did deployments, config changes, or scaling events precede the failures?

### Step 3b — Callstack Code Investigation

When an exception includes a callstack, follow this sequence to trace back to source code:

1. **Find the root (innermost) exception first** — use the KQL from the "Root Exception & Callstack Extraction" subsection above.
   - Focus on `innermostType` and `innermostMessage`; these identify the actual error, not a wrapper.
   - Use the frame-level expansion query to get a ranked list of callstack frames.

2. **Identify the first application frame** — starting from `frameLevel = 0` (outermost), scan down the frames until you reach a frame whose `frameAssembly` or `frameFileName` belongs to application code (not `System.*`, `Microsoft.*`, or framework internals). That frame is the fault point.

3. **Identify the assembly / namespace / file**:
   - C# frames: `at Namespace.ClassName.MethodName(params) in File.cs:line N`
   - TypeScript/JS frames: `at functionName (file.js:line:col)`
   - Angular/AngularJS frames: component class name or `$scope` function in a `.ts` / `.js` file
   - ASPX frames: code-behind class in `.aspx.cs` or `.aspx.vb`

4. **Map to repo and search for the code** — use the "Callstack Frame → Repo Mapping" table in `.claude/shared/cloudshare-repos.md`.

5. **Use local file/code search tools first** — always prefer locally checked-out repos over remote GitHub search:
   - **Locate local repos first**: repo locations vary entirely by local machine setup — the folder name and path are not standardized. Infer the location from the current working directory if the session is already open in a repo, or ask the user where the relevant repo is checked out. The primary repos to look for are `cloudshare` and `Experiences-backend`.
   - **Preferred search approach**: once the local root is known, use `Grep` for the class name or method name under that root, then `Read` the file at the matched path. This is faster and more accurate than GitHub search because it reflects the exact working copy.
   - **Fallback only**: use GitHub search tools (`mcp__github__search_code`, `mcp__github__get_file_contents`) when a repo is not found locally (e.g., `experiences-client`, or a repo the user hasn't checked out).
   - For Angular/AngularJS files in `cloudshare/cloudshare`, look under the frontend source directories (`.ts`, `.js`, `.html`, `.aspx`) within the local `cloudshare` root.

6. **Read the surrounding code** (±20 lines around the faulting line) to understand:
   - What preconditions could cause this exception?
   - Are there recent commits that changed this code path? (check git log)
   - Is there an existing issue or PR that mentions this exception?

7. **Document the code finding** in the incident report under a "Code Context" subsection with:
   - File path and line number
   - The faulting code snippet
   - Hypothesis for why it fails under the observed conditions

**Decision tree for common patterns:**

```

Note: the decision tree below applies to the 4xx/5xx scope only:

```
HTTP 4xx errors?
  ├─ 400 Bad Request → invalid input/payload; check request body and validation logic
  ├─ 401/403 → auth/authz failure; check token, RBAC, or identity config
  ├─ 404 → missing resource or routing issue
  └─ 429 → rate limiting; check throttle thresholds and retry storms

HTTP 5xx errors?
  ├─ 502/503 → upstream dependency or cold start issue
  ├─ 500 with exception → application bug, check exceptions table
  └─ 504 → timeout; check duration percentiles and downstream calls

Dependency failures?
  └─ Check dependencies table; is the target unavailable or slow?

OOMKilled / memory errors?
  └─ Check resource limits; consider rightsizing

Cold start / high P95 latency?
  └─ Check Function App plan (Consumption vs Flex) or Container App scaling config
```

---

### Step 3d — Compare Failed vs Successful Requests

Once you have a set of failing `OperationId`s, find **comparable successful requests** to the same endpoint from the same time window. The goal is to identify the discriminating factor — the one property or condition that differs between a request that succeeds and one that fails.

**Procedure:**

1. **Find successful requests to the same endpoint** — same query as the failing request lookup, but filter for successes:

   ```kql
   let startTime = datetime(YYYY-MM-DD);
   let endTime = datetime(YYYY-MM-DD);
   AppRequests
   | where TimeGenerated between (startTime .. endTime)
   | where Name == "<same endpoint Name as the failing request>"
   | where ResultCode !in ("400", "500")
   | project TimeGenerated, Name, ResultCode, Url, OperationId, AppRoleName, Properties
   | order by TimeGenerated desc
   | take 10
   ```

2. **For each pair (one failing, one successful operation)**, compare:
   - **Request body** — from `Method execution failed.` traces (`RequestBody` field) or `SerializedRequestBody` from `HttpRequestException` traces
   - **Response body** — from `ResponseBody` / `MessageBody` fields in the same traces
   - **User / tenant context** — `UserId`, `AppRoleName`, project ID, class ID
   - **Timing** — time of request relative to any state change (e.g., resource lifecycle phase, deployment)
   - **Payload fields** — fields present in the failing body but absent from the successful one, or vice versa

3. **Identify the discriminating factor** — the property or condition that appears in every failing request but not in every successful one. Common patterns:
   - A **new or optional payload field** that the server-side code does not handle (e.g., a new provider region field that triggers an unhandled code path)
   - A **specific entity state** at the time of the request (e.g., resource in a particular lifecycle phase)
   - A **specific tenant or user** with different configuration (e.g., a feature flag, a specific time zone, a missing permission)
   - A **timing dependency** (e.g., only fails when a resource is accessed within a specific window)

4. **Document the discriminating factor** in the incident report under "Evidence": state clearly what all failing requests shared that successful requests lacked.

---

### Step 3e — Full Transaction Flow Analysis

After confirming the root cause, reconstruct the **complete end-to-end journey** of the failing request. This gives full context for the incident report and ensures the fix targets the right layer.

**Procedure:**

1. **Identify the entry point** — was this:
   - A **user action in the frontend** (experiences-client Angular app, or the CloudShare WebApp AngularJS UI)?
   - A **direct API call** from a third-party integration or automation tool (e.g., an API key-authenticated script, a SaaS integration)?
   - A **scheduled job or webhook** triggered by an internal service?

2. **Trace each hop in order**, using the `OperationId` chain across App Insights instances. For each service leg, document:
   - Service name (e.g., `experiences-backend BFF`, `experiences-backend API Gateway`, `cloudshare WebApp API v3`)
   - HTTP method and endpoint (e.g., `PUT /api/v4/trainings/{id}`)
   - Timestamp and duration
   - Request body (from `SerializedRequestBody` trace or `Method execution failed.` `RequestBody` field)
   - Response status and body (from `MessageBody` or `ResponseBody` trace)
   - `OperationId` for this leg

3. **Map any data transformations** between hops — if a value changes shape as it passes through layers (e.g., a date string parsed to `DateTime`, a field renamed, a nested object flattened), note that transformation and verify the format matches expectations on both ends.

4. **Identify the failing leg** — which specific hop produced the 4xx/5xx? Which service was the proximate cause vs which was the originating trigger?

5. **Write the flow as a linear sequence** in the incident report:

   ```
   [Entry point] → [Service A: endpoint, status] → [Service B: endpoint, status] → [Failure at Service C: reason]
   ```

   Example:
   ```
   Administrate (PUT /v4/trainings) → Experiences Backend BFF (PUT /api/experiences/{id}) → CloudShare API v3 (PUT /Class/{id}) → CourseBlServiceVertical.ValidateClassTimeAndFetch() → ArgumentException at line 2326
   ```

---

### Step 3c — Regression, Ownership & Jira Investigation

Once the faulting file and method are identified (Step 3b), run these checks **before** writing the incident report.

#### 1. Search Jira for Existing Tickets

Before doing deep investigation, check whether a ticket already exists for this failure. Use `mcp_com_atlassian_searchJiraIssuesUsingJql`:

```jql
-- By exception type or endpoint name (last 30 days)
project = CS AND (summary ~ "<ExceptionType>" OR summary ~ "<endpoint name>") AND created >= -30d ORDER BY created DESC

-- By bug/incident type
project = CS AND summary ~ "<endpoint name>" AND issuetype in (Bug, Incident) ORDER BY updated DESC
```

If a ticket exists, it may already contain an RCA, affected tenant IDs, or a linked fix PR — read it before proceeding.

#### 2. Find the Regressing PR (Git Log)

Use `mcp_gitkraken_git_log_or_diff` to find the last commits that touched the faulting file:

```bash
# Last commits that modified the faulting file
git log --oneline -20 -- <relative/path/to/file.cs>

# Find commits that changed a specific method name
git log -S "<MethodName>" --oneline -- <relative/path/to/file.cs>
```

Compare the **first failure timestamp** (from App Insights Step 2) against the commit timestamps. The most recent commit **before** the first failure timestamp is the regression candidate.

Once you have the commit SHA, use `github-pull-request_doSearch` to find the associated PR:

```
// Search by commit SHA or branch name in PR title/body
repo:cloudshare/<repo> <commit-sha>
repo:cloudshare/<repo> is:pr is:merged <branch-or-ticket-name>
```

Use `github-pull-request_issue_fetch` to retrieve full PR details (title, description, author, merge date, linked issues).

#### 3. Identify the Regression Author

From the PR details, note:
- **PR author** — the GitHub user who opened the PR (the person who introduced the change)
- **Merger** — who approved and merged it (if different)

If `git log` shows the commit was pushed directly to the branch (no PR), use `mcp_gitkraken_git_blame` on the specific faulting lines to identify the author:

```bash
git blame -L <start>,<end> -- <relative/path/to/file.cs>
```

#### 4. Identify the Code Owner

No `CODEOWNERS` file exists in this repo. Determine ownership by:
1. **Git blame** the faulting lines — the most recent non-trivial author is the de-facto owner.
2. **Git log** the file with `--follow` — the person with the most commits to this file is the best reviewer candidate.
3. Check if the file's namespace or module has a consistent author across recent changes.

**Verify the owner is still active** — the original author may have left the company. Run both checks:

```bash
# Check for any commits by this author in the last 30 days (across the whole repo)
git log --since="30 days ago" --author="<owner name or email>" --oneline | head -10
```

And search Jira for their activity in the last 2 sprints using `mcp_com_atlassian_searchJiraIssuesUsingJql`:

```jql
-- Issues assigned to or commented by this person in the last 2 sprints
project = CS AND assignee = "<jira-username>" AND sprint in openSprints() ORDER BY updated DESC
project = CS AND assignee = "<jira-username>" AND sprint in lastSprint() ORDER BY updated DESC
```

- If the owner has **recent git commits (last 30 days) OR active Jira issues in the last 2 sprints** → they are the primary owner.
- If **no activity in either** → they may have left. Identify a **secondary owner** by running `git log --since="90 days ago" --follow -- <file>` and picking the most active recent committer to the same file or module. Report both in the incident.

Document the owner(s) in the incident report — they must review any fix PR.

#### 5. Retrieve the Jira Ticket Linked to the Breaking PR

Check the PR description and commit message for a Jira ticket key (pattern: `[A-Z]+-\d+`, e.g., `CS-1234`). If found:
- Use `mcp_com_atlassian_getJiraIssue` to retrieve ticket details (summary, assignee, status, linked issues)
- The ticket gives context on the **intended change** that inadvertently caused the regression
- Add the ticket key to the incident report under "Contributing Factors"

If no Jira key is found in the PR, search Jira by PR title keywords or the author's name around the PR merge date.

---

### Step 4 — Write the Incident Report

Produce a structured markdown report with the following sections:

```markdown
## Incident Report — [Service Name] — [Date/Time Range]

### Summary
One-paragraph description of what failed, when, and the impact.

### Root Cause
Concise statement of the root cause identified from logs.

### Evidence
- **OperationId(s)**: `<operation_Id>` — list every `operation_Id` used in the investigation. This is mandatory.
- Key log excerpts or query results supporting the root cause.
- Correlation IDs linking requests across services and workspaces.
- Cross-service call chain (if multiple App Insights instances were involved).

### Code Context
- Faulting method: `[Namespace.Class.Method]` in `[repo]/[file path]:[line]`
- Code snippet showing the faulting logic.
- Hypothesis: why this code fails under the observed conditions.

### Transaction Flow
Complete hop-by-hop journey of the failing request, from entry point to failure:

```
[Entry point: caller type] → [Service A: METHOD /endpoint → HTTP status] → [Service B: METHOD /endpoint → HTTP status] → [Failure: ClassName.Method() → ExceptionType: message]
```

For each leg, include: service name, endpoint, HTTP status, duration, key request/response values, and OperationId if known.

- **Entry point**: frontend action / direct API call / scheduled job / webhook
- **Discriminating factor**: what this request had that comparable successful requests did not
- **Failing leg**: which service was the proximate cause vs which was the originating trigger
- **Data transformations**: any field renames, type conversions, or format changes between hops that contributed to the failure

### Contributing Factors
- Any config, deployment, scaling, or dependency changes that contributed.
- **Regressing PR**: `<PR URL>` — `<PR title>` by `@<author>` (merged `<date>`)
- **Jira ticket (PR)**: `<ticket key>` — `<ticket summary>` (if a Jira ticket was linked to the breaking PR)
- **Code owner**: `@<owner>` (from git blame / git log) — verified active via Jira (last 2 sprints) and/or git commits (last 30 days)
- **Secondary owner** *(if primary is inactive)*: `@<secondary>` (most recent committer to the same file/module in last 90 days)

### Remediation Steps
1. Immediate mitigation (e.g., rollback, restart, scale out)
2. Short-term fix (e.g., code change, config update — link to specific file/line)
3. Long-term prevention (e.g., add health checks, alerts, limits)

### Queries Used
Paste the final KQL queries that surfaced the issue, for reproducibility.
```

---

### Step 5 — Suggest a Fix

Based on the root cause and code context identified in Steps 3–4, propose a concrete fix. Work at the **code level** — not just in words.

#### Fix workflow

1. **Re-read the faulting code** (±30 lines around the identified frame) to understand the full control flow — preconditions, inputs, error handling.
2. **Identify the minimal change** that corrects the failure without introducing regressions:
   - Prefer fixing the root cause in the innermost faulting method over patching callers.
   - Do not add unnecessary error-swallowing; preserve the failure signal for observability.
3. **Produce a concrete code diff or patch description** scoped to the relevant file(s). Include:
   - File path (repo-relative)
   - The exact lines to change, with before/after
   - A one-sentence explanation of *why* the change fixes the issue
4. **Check adjacent code** for the same pattern — if the bug is a copy-paste pattern (e.g., missing null-check, wrong status code mapping, missing `await`), flag all occurrences found in the same file or class.

5. **Validate the fix logic** against the request/response evidence from the traces:
   - Does the fix handle the `RequestBody` / `ResponseBody` seen in the `prod-appinsights` traces?
   - Does it cover the `MessageBody` returned by the WebApp, if the failure is inter-service?
6. **State testing guidance**: describe the minimal test case (unit or integration) that would reproduce the failure and confirm the fix.

#### Fix quality requirements

- The fix must be **scoped to the minimum necessary change** — do not refactor unrelated code.
- If the fix requires a config change (e.g., environment variable, Azure App Configuration), specify the exact key and value.
- If the fix requires a data migration or one-time remediation step (e.g., clearing a bad cache entry, re-processing a failed message), describe that step explicitly.
- If the root cause cannot be definitively confirmed from logs alone, state the **most likely fix** and list the **unknowns** that need to be verified before merging.

---

### Step 6 — Suggest Follow-up Actions

After the report and fix proposal, always recommend:
- **Root cause verification**: Confirm the fix resolves the failure in a test environment before production.
- **Post-mortem**: Schedule a blameless post-mortem if the incident had customer impact.

---

## Quality Checklist

Before completing, verify:
- [ ] Time window of the failure is clearly established (±1 day around known date → 30 days → full retention if still empty)
- [ ] All relevant App Insights instances (cloudshare, experiences-backend, experiences-client) were checked
- [ ] Cross-service correlation was attempted using `operation_Id` if the failure spans services
- [ ] Root cause is backed by specific log evidence (not just a guess)
- [ ] At least one comparable successful request was found and diffed against the failing request to confirm the discriminating factor
- [ ] Full transaction flow was reconstructed (entry point → each service hop → failure point) and included in the incident report
- [ ] Exception callstack was mapped to source code in the appropriate GitHub repo
- [ ] Code context (file, line, snippet) is included in the incident report
- [ ] Remediation steps are actionable and ordered (immediate → long-term), with file/line references where applicable
- [ ] A concrete code-level fix is proposed (file path, before/after lines, rationale)
- [ ] Fix is scoped to the minimal change; no unrelated refactors
- [ ] Fix was validated against request/response evidence from traces
- [ ] Adjacent occurrences of the same bug pattern were checked
- [ ] KQL queries are included and reproducible
- [ ] Jira was searched for an existing ticket or prior RCA for this failure
- [ ] Regressing PR was identified via `git log` correlated with first failure timestamp
- [ ] PR author (regression introducer) and code owner are named in the report
- [ ] Jira ticket linked to the breaking PR (if any) was retrieved and cited
- [ ] Incident report is in the standard markdown format above
