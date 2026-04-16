---
name: cs-jira-raise-bug
description: Creates a Jira bug ticket in the CloudShare BAC project from context already present in the conversation. Use this skill whenever the user says "raise a bug", "file a bug", "create a Jira ticket", "log this as a bug", "open a Jira issue", "report this bug", or any similar phrasing — even if they don't say "Jira" explicitly. Also use this skill when the user finishes an incident investigation or failure analysis and wants to track the findings, even without explicitly asking for a ticket.
---

# Raise a Jira Bug

Creates a bug in the **BAC** project at cloudshare.atlassian.net, pulling all context from the current conversation (incident reports, Azure failure analysis, code review findings, etc.) rather than asking the user to re-describe what they already told you.

## Workflow

### Step 1 — Extract context from conversation

Read the current conversation and extract:
- **What broke** — the feature, endpoint, or component that fails
- **How it fails** — the error message, exception type, or wrong behavior
- **Frequency & scope** — single incident? recurring? specific conditions or environments?
- **Who introduced it** — commit authors from git blame/log, recent PRs, code owners mentioned in the analysis
- **Which repo/service** — `cloudshare`, `experiences-backend`, `experiences-client`, or other
- **Severity** — user impact: blocking? data loss? degraded experience? cosmetic?

If the conversation contains an already-written incident report, use that as the primary source of truth.

---

### Step 2 — Determine assignee

Identify the most likely owner from the conversation (git blame output, commit author, code owner named in analysis). Then:

1. Look them up in Jira using `mcp__atlassian__lookupJiraAccountId` — search by name or email.
2. **Check they're active**: run a JQL query for their recent activity:
   ```
   project = BAC AND assignee = "<accountId>" ORDER BY updated DESC
   ```
   If they have tickets updated within the last 6 months, they're active.
3. If the identified person is inactive, look for the next most recent active committer on the affected file/area (from the conversation's git log context).
4. If no active owner can be determined, leave assignee blank — don't assign to someone who may not be on the team anymore.

---

### Step 3 — Infer "Assigned team"

Query the assignee's recent BAC tickets for the "Assigned team" field:
```
project = BAC AND assignee = "<accountId>" AND "Assigned team" is not EMPTY ORDER BY updated DESC
```
Use the team value that appears most frequently across their recent tickets. If no tickets with a team are found, leave it blank.

---

### Step 4 — Determine Deployment Component

Use the cached values from Step 6. Map the affected repo/service to the best-matching component using the "Repo → Jira Deployment Component Mapping" table in `.claude/shared/cloudshare-repos.md`.

For services not in that table, match by name against the full list in Step 6.

---

### Step 5 — Decide priority

The BAC priority scale is: **Low / Normal / High / Urgent**

Choose based on **severity × scope**:

| | Widespread / many users affected | Isolated / single environment |
|-|----------------------------------|-------------------------------|
| **Blocks users or causes data loss** | Urgent | High |
| **Degrades experience / wrong behavior** | High | Normal |
| **Cosmetic or minor** | Normal | Low |

Use all available signals: error rate from logs, number of affected environments, whether there's a workaround, whether it's a regression in a core feature.

---

### Step 6 — Resolve custom field IDs

The following field IDs and allowed values are cached from the BAC Bug issue type metadata. Use them directly — **do not call `mcp__atlassian__getJiraIssueTypeMetaWithFields` unless the component you need is not in the list below**.

#### Cached field IDs (BAC / Bug)

| Field | Field ID |
|-------|----------|
| Assigned team | `customfield_11413` |
| Investment profile | `customfield_11830` |
| Deployment component | `customfield_11477` |

**Investment profile** is always `Support` (id: `11443`) for internal bugs — no lookup needed.

#### Cached: Deployment component (`customfield_11477`)

| Value | ID |
|-------|----|
| `NA` | `11106` |
| `AI Core` | `11479` |
| `AWS Infra` | `11480` |
| `CloudIIs` | `11016` |
| `PyBE` | `11007` |
| `Angie` | `11008` |
| `Gateway` | `11009` |
| `Workers` | `11010` |
| `Iso file manage` | `11011` |
| `BE actions forwarder` | `11012` |
| `Benv Service` | `11013` |
| `Total Resources Feeder` | `11014` |
| `Predictor` | `11015` |
| `Webhook service` | `11102` |
| `Webhook Azure functions` | `11103` |
| `Integration hub` | `11104` |
| `Accelerate API Gateway` | `11107` |
| `Experience Cluster` | `11108` |
| `EmailSender` | `11109` |
| `Experiences BFF` | `11110` |
| `ExperiencesClient` | `11111` |
| `Experiences Client Configuration` | `11112` |
| `Experiences Client Configuration DB` | `11113` |
| `Experiences Service` | `11114` |
| `Experiences Service DB` | `11115` |
| `Experiences Reporting Service` | `11116` |
| `Experiences Timezone service` | `11117` |
| `WebApp PC BL` | `11118` |
| `PCS` | `11119` |
| `Command Worker` | `11120` |
| `Nuke service` | `11121` |
| `Spark` | `11122` |
| `HIPRA` | `11123` |
| `Webaccess` | `11124` |
| `WebSockets` | `11125` |
| `Billing app` | `11105` |

If the component you need is not in this table, call `mcp__atlassian__getJiraIssueTypeMetaWithFields` (project `BAC`, issue type `Bug`) to get the current list, then use the freshly returned ID.

---

### Step 7 — Compose the ticket

**Summary** (one line, ~80 chars max):
```
[Component/Area] Brief description of the bug
```

**Description** (use Atlassian wiki markup):

```
h3. Summary
One or two sentences: what breaks, who is affected, observable impact.

h3. Details
Technical details relevant to a developer: exception type and message, affected code path (file + method), key stack frames, relevant entity IDs or request IDs from the investigation, environment identifiers.

h3. Reproduction steps
Write as plain prose (not a numbered list) to avoid large font rendering in Jira. Example: "Open the instructor console for a class with active students. Remove a student. Within ~60 seconds observe the UI calling GET .../students/{deletedId} and returning 500."

(If reproduction steps are not known, omit this section and note it. Don't invent steps.)

h3. Investigation context
Pointers to evidence: Azure App Insights OperationIds, Splunk query anchors, specific git commits, related Jira tickets, or App Insights workspace/resource names. Make it easy for the assignee to pick up from where the analysis left off.
```

**Tagging people in the description**: Only @mention individuals when you have high-confidence evidence that they are directly relevant — for example, the commit author who introduced the regression, or a code owner explicitly named in the analysis. Do not tag people who appear tangentially (e.g., mentioned in unrelated commits, nearby code they didn't touch, or tickets they're merely watching). When in doubt, omit the tag.

**Fields:**
| Field | Value |
|-------|-------|
| Project | `BAC` |
| Issue type | `Bug` |
| Priority | From Step 5 |
| Label | `Internal_bug` |
| Assignee | From Step 2 (if resolved) |
| Assigned team | From Step 3 (if resolved) |
| Investment profile | `Support` |
| Deployment component | From Step 4 |

---

### Step 8 — Show preview and confirm

Present a clear preview before creating anything:

```
📋 Jira Bug Preview — BAC project
──────────────────────────────────────────
Summary:          [Area] Brief description
Priority:         High
Assignee:         Jane Smith (jane.smith@cloudshare.com)
Assigned team:    Platform
Component:        CloudIIs
Label:            Internal_bug
Investment profile: Support
──────────────────────────────────────────
Description:
  h2. Summary
  The GET /api/v3/viewer/actions/vmList endpoint returns 500 for env
  EN3jmiu10FYGxA1KP0pnKmOQ2 due to a NullReferenceException in NHibernate's
  TransformTuple during BackendMachinesQuery materialization.
  [... truncated ...]
──────────────────────────────────────────
Create this ticket? (yes / edit / cancel)
```

Wait for explicit confirmation before calling `mcp__atlassian__createJiraIssue`.
- **"yes"** → proceed to Step 9
- **"edit"** → ask what to change, loop back to Step 8
- **"cancel"** → abort cleanly

---

### Step 9 — Create and return

Call `mcp__atlassian__createJiraIssue` with the confirmed field values.

Follow the MCP tool usage guidance in `.claude/shared/jira.md`.

Return:
- The ticket URL: `https://cloudshare.atlassian.net/browse/BAC-XXXXX`
- The ticket key: `BAC-XXXXX`

If any field value is rejected by the API (e.g., invalid component name or team value), try `NA` / blank as fallback and note the substitution to the user.
