# Jira

**Project**: BAC (CloudShare Product / Dev) — `https://cloudshare.atlassian.net`

## Sprint rules
- Duration: 2 weeks
- Naming pattern: `{Team} {YYYY} Q{quarter}.{N}` or `{Team} {YYYY} Q{quarter}_{N}`
  - Quarter and sprint-within-quarter separated by `.` or `_` — both are valid
  - Older/legacy sprints may omit the year (e.g., "FrEM Q2_6")
  - **FrEM** uses short names without year: `FrEM Q{quarter}_{N}` (e.g., `FrEM Q2_2`) — may change

## Team fields on issues
- **"Assigned team"**: mandatory
- **"Team"**: optional, can provide additional context

## Teams

| Abbreviation | Full name | Jira board |
|---|---|---|
| **Ex. Management** | Experiences Management | BAC Board 54 |
| **BE** | Backend / Environments Team | BAC Board 47 |
| **Innovation** | Innovation Team | BAC Board 267 |
| **Automation** | Automation | BAC Board 300 |
| **FrEM** | Frontend Modernization | BAC Board 131 (`https://cloudshare.atlassian.net/jira/software/c/projects/BAC/boards/131`) |
| **PC** | Public Clouds | BAC Board 53 |

## Team members (as of 2026-Q1)

**Ex. Management**: Evyatar Kanety, Andrey Alonzov, Alla Bliahrov, Alexander Karyazhkin
**BE**: Alexander Motov, Amos Elgali, Eitan Roth, Ilan Elmakyes, Ofir Ben Shahar
**Innovation**: Amit Weiss, Jonathan Sadan, Shmuel Kuflik
**Automation**: Yarden Ben-Aharon, Shir Levi
**FrEM**: Nini Chirgadze, Valeri Gogichashvili, Giga Gelashvili, Ruben Mikayelyan

## Sprint dashboards
Auto-generated in Confluence after each sprint closes — Confluence DASH space → "Sprint Dashboards" folder. FrEM has no sprint dashboards in DASH (as of 2026-03-28).

## Creating tasks via API

### Linking a Task to its Epic

Use `parent: { "key": "BAC-XXXXX" }` in `additional_fields`. Do **not** use `customfield_10014` (Epic Link) — it is not on the BAC Task edit screen and the API will reject it.

### Issue types (BAC project)

| Name | ID | `subtask` | Hierarchy level |
|------|----|-----------|-----------------|
| Initiative | `10154` | false | 2 |
| Epic | `10000` | false | 1 |
| Bug | `1` | false | 0 |
| Story | `10001` | false | 0 |
| Task | `3` | false | 0 |
| Sub-task | `5` | **true** | -1 |

When creating a sub-task, set `issuetype: {"id": "5"}` and `parent: {"key": "BAC-XXXXX"}`.

### Required fields when creating a Task

| Field | additional_fields key | Example value |
|-------|-----------------------|---------------|
| Assigned Team | `customfield_11413` | `{"id": "11305"}` (FrEM) |
| Investment profile | `customfield_11830` | `{"id": "11444"}` (Tech) |
| Deployment component | `customfield_11477` | `{"id": "11016"}` (CloudIIs) |

### Known Assigned Team IDs (`customfield_11413`)

| Team | ID |
|------|----|
| FrEM | `11305` |
| Ex. Management | `10986` |

Look up unknown team IDs by querying a recent ticket for that team and reading `customfield_11413.id`.

### MCP tool usage — critical parameter requirements

- Use **`issueTypeName`** (string, e.g. `"Bug"`, `"Task"`) — `issueType` does not exist and will fail.
- Use **`assignee_account_id`** (not `assignee`) for the account ID string.
- Pass **`additional_fields`** as a **native JSON object** — not a JSON-encoded string.
- Do **not** set `contentFormat` — Jira wiki markup is the native format.
- Use **`searchString`** (not `query`) when calling `lookupJiraAccountId`.

```json
"additional_fields": {
  "priority": {"name": "Normal"},
  "labels": ["Internal_bug"],
  "customfield_11413": {"id": "10986"},
  "customfield_11830": {"id": "11443"},
  "customfield_11477": {"id": "11016"}
}
```

### Blocks links

`createIssueLink` with `inwardIssue` = blocker (A), `outwardIssue` = blocked (B), `type` = `"Blocks"`.

## Jira field IDs (BAC project, Task issue type)

| Field (UI label) | Field ID | Format / Values |
|---|---|---|
| Assigned Team | `customfield_11413` | `{"id": "..."}` |
| Investment profile | `customfield_11830` | `{"id": "..."}` — Tech = `11444`, Support = `11443` |
| Deployment component | `customfield_11477` | `{"id": "..."}` — CloudIIs = `11016` |
| Effort Size | `customfield_11962` | `{"id": "..."}` — XS=`11586`, Small=`11550`, Medium=`11551`, Large=`11552`, X Large=`11553` |
| Sprint | `customfield_10007` | Plain integer sprint ID — find by querying JQL with `fields: ["customfield_10007"]` and `responseContentFormat: adf` |
| Start date | `customfield_11402` | `"YYYY-MM-DD"` — JQL name: `"Start date[Date]"`. (`customfield_10015` is a different field — not writable.) |
| Due date | `duedate` | `"YYYY-MM-DD"` |
| Target start | `customfield_11407` | `"YYYY-MM-DD"` — Advanced Roadmaps field, distinct from Start date |
| Target end | `customfield_11408` | `"YYYY-MM-DD"` — Advanced Roadmaps field, distinct from Due date |

## FrEM team members (as of 2026-Q1)
Nini Chirgadze, Valeri Gogichashvili, Giga Gelashvili, Ruben Mikayelyan

## FrEM sprint discovery

To discover FrEM sprints (including future ones), run this JQL and read `customfield_10007` from any returned issue — it contains `id`, `name`, `startDate`, `endDate`, `state`:

```
project = BAC AND "Assigned team" = 11305 AND sprint in (openSprints(), futureSprints()) ORDER BY sprint ASC
```

**Requirement:** each sprint must contain at least one FrEM issue (guaranteed now that we assign tasks to every sprint).

## FrEM sprint history (known)

| Sprint | ID | Start | End | State |
|---|---|---|---|---|
| FrEM Q1_6 | 2129 | 2026-03-17 | 2026-03-30 | active |
| FrEM Q2_1 | 2195 | 2026-03-30 | 2026-04-13 | future |
| FrEM Q2_2 | 2196 | 2026-04-13 | 2026-04-27 | future |
| FrEM Q2_3 | 2197 | 2026-04-27 | 2026-05-11 | future |
| FrEM Q2_4 | 2198 | 2026-05-11 | 2026-05-25 | future |
