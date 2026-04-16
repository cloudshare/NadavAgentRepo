---
name: cs-jira-plan-epic
description: "Plan a Jira epic into sprints by building a dependency graph from Blocks links, balancing effort across sprints, applying sprint/date assignments, and creating missing Blocks links. Optionally creates new tasks before scheduling. WHEN: plan epic into sprints, schedule tasks across sprints, assign tasks to sprints, set sprint dates for an epic, distribute work across sprints, sprint planning for an epic."
---

# Plan Epic into Sprints

Reads all tasks under a Jira epic, builds the dependency graph from existing Blocks relations, assigns tasks to sprints respecting dependencies and balancing load, then applies the schedule (sprint, start date, due date) and creates any missing Blocks links.

---

## Step 1 — Read the epic and its tasks

1. Call `mcp__atlassian__getJiraIssue` on the epic to understand scope and current state.
2. Call `mcp__atlassian__searchJiraIssuesUsingJql`:
   ```
   parent = <EPIC-KEY> ORDER BY key ASC
   ```
   Fields to request: `summary`, `customfield_11962` (effort size), `customfield_10007` (sprint), `customfield_11402` (start date), `duedate`, `issuelinks`, `status`.

3. For each task record:
   - **Effort size** from `customfield_11962` (XS / Small / Medium / Large / XL)
   - **Current sprint** if already assigned
   - **Status** — Done or In Progress tasks are frozen; do not reschedule them
   - **Blocks / is-blocked-by** links from `issuelinks`

---

## Step 2 — Build the dependency graph

From `issuelinks`, extract all directed edges:
- `"blocks"` outward link on A → A must finish before B starts
- `"is blocked by"` inward link on B → same edge from the other side

Identify:
- **Roots**: tasks with no unresolved incoming edges → can start in sprint N
- **Leaves**: tasks with no outgoing edges → typically the last things to ship
- **Critical path**: longest dependency chain → sets the minimum number of sprints needed

If the epic has tasks with no Blocks links at all, ask the user whether to create them or treat all tasks as independent (schedulable in parallel).

---

## Step 3 — Determine the starting sprint and available sprints

Ask the user which sprint to start from, or infer it from tasks that already have sprint assignments.

For sprint IDs, dates, and discovery JQL — see **`.claude/shared/jira.md` → "FrEM sprint history"** and **"FrEM sprint discovery"**.

---

## Step 4 — Assign tasks to sprints

### Scheduling rules

1. Tasks with no unfinished predecessors are "ready" for the current sprint.
2. A task can only be assigned to a sprint if **all its blockers are in an earlier sprint** — never the same sprint.
3. Advance to the next sprint when the current one is full. Then the tasks that were blocked by this sprint's tasks become ready.
4. Repeat until all tasks are assigned.

### Sprint capacity target

Aim for **3–4 tasks per sprint**. Use effort size as a weight to avoid overloading:

| Effort | Weight |
|--------|--------|
| XS | 0.5 |
| Small | 1 |
| Medium | 2 |
| Large | 3 |
| XL | 4 |

Target weight per sprint: **4–6**. When a sprint would exceed this, defer overflow tasks to the next sprint (provided their dependencies allow it).

### Hard rules

- A task and its blocker must **never be in the same sprint**.
- Do not move tasks that are already **In Progress** or **Done**.
- The final integration / wiring task always lands in the last sprint.

---

## Step 5 — Present the plan and confirm

Show the full proposed schedule before applying anything:

```
Epic: BAC-XXXXX — <title>

Sprint FrEM Q2_2  (Apr 13 – Apr 27)
  BAC-AAAAA  <summary>   [Small]
  BAC-BBBBB  <summary>   [Medium]

Sprint FrEM Q2_3  (Apr 27 – May 11)
  BAC-CCCCC  <summary>   [Medium]   blocked by: BAC-AAAAA
  BAC-DDDDD  <summary>   [Small]    blocked by: BAC-AAAAA
  BAC-EEEEE  <summary>   [Small]    blocked by: BAC-BBBBB

Sprint FrEM Q2_4  (May 11 – May 25)
  BAC-GGGGG  <summary>   [Medium]   blocked by: BAC-CCCCC, BAC-DDDDD, BAC-EEEEE

Blocks links to create:
  BAC-AAAAA → BAC-CCCCC, BAC-DDDDD
  BAC-BBBBB → BAC-EEEEE
  BAC-CCCCC, BAC-DDDDD, BAC-EEEEE → BAC-GGGGG

Apply this plan? (yes / adjust / cancel)
```

Wait for explicit confirmation. If the user says **adjust**, ask what to change and re-present before proceeding.

---

## Step 6 — Apply sprint + date assignments

For each task that needs updating, call `mcp__atlassian__editJiraIssue`:

```json
{
  "fields": {
    "customfield_10007": <sprint-id-integer>,
    "customfield_11402": "YYYY-MM-DD",
    "duedate": "YYYY-MM-DD"
  }
}
```

Batch all tasks for the same sprint into one parallel call group.

---

## Step 7 — Create missing Blocks links

For each dependency edge not already present in the tasks' `issuelinks`, call `mcp__atlassian__createIssueLink`. For field usage and link direction — see **`.claude/shared/jira.md` → "Blocks links"**.

Create all new links in parallel.

---

## Step 8 — Creating new tasks (if needed)

If the epic is missing tasks, create them first (before scheduling) using `mcp__atlassian__createJiraIssue`.

For all required fields, field IDs, effort size values, and the epic parent field — see **`.claude/shared/jira.md` → "Creating tasks via API"** and **"Jira field IDs"**.

### Include a description for every task

When creating tasks, always include a `description` field in the same `createJiraIssue` call. Do **not** add it as a separate `editJiraIssue` step afterwards.

**Format:** pass a plain markdown string — do NOT use an ADF object (it causes a "Failed to convert markdown to adf" error). Use this structure:

```
## Overview

One-paragraph summary of what this task delivers and why it matters in the context of the epic.

## Scope

- Bullet list of concrete deliverables: endpoints, components, infra resources, integrations
- Be specific: name routes, table names, component names, AWS service + boto3 client
- Cover both backend and frontend work where applicable

## Acceptance Criteria

- Testable, binary pass/fail conditions
- Reference related tasks by key where the output of this task is consumed by another (e.g. "integrated with BAC-XXXXX")

## Tech Notes

- Implementation hints: library choices, terraform module layout, key config flags
- Known gotchas or constraints the implementer should know upfront
```

Derive the content from the epic description, the task summary, its effort size, and its position in the dependency graph (what it depends on, what depends on it).

Create all tasks (with descriptions) before running the scheduling steps above.

---

## Step 9 — Return final summary

```
Applied plan for BAC-XXXXX:

Sprint FrEM Q2_2  (Apr 13 – Apr 27)
  BAC-AAAAA  <summary>   [Small]
  BAC-BBBBB  <summary>   [Medium]

Sprint FrEM Q2_3  (Apr 27 – May 11)
  BAC-CCCCC  <summary>   [Medium]   blocked by: BAC-AAAAA
  ...

Sprint assignments updated: N tasks
Blocks links created: M links
```
