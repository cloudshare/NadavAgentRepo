# CloudShare Skill Naming Guidelines

All custom Claude Code skills in this repo follow a consistent naming scheme so that skills are discoverable, self-describing, and unambiguous alongside third-party skills.

---

## Pattern

```
cs-<area>-<action>   ← preferred: skill clearly belongs to one domain
cs-<action>          ← when the skill spans multiple tools or areas
```

| Segment | Description |
|---------|-------------|
| `cs` | Mandatory prefix — marks the skill as CloudShare-specific |
| `<area>` | The domain or toolchain the skill operates in (see table below). Omit when the skill spans multiple areas and no single one fits without being misleading. |
| `<action>` | Imperative verb-noun phrase describing what the skill does (kebab-case, e.g. `raise-bug`, `plan-epic`, `analyze-failures`) |

---

## Registered area prefixes

| Area | Use for |
|------|---------|
| `jira` | Creating, updating, querying, or planning Jira issues / epics / sprints |
| `azure` | Azure logs, App Insights, KQL queries, failure analysis, infrastructure |
| `angular` | Angular / AngularJS migration, component upgrades, frontend architecture |
| `confluence` | Confluence page creation, publishing, or search |
| `git` | Git workflows, branch management, PR automation |

Add a new area when a skill doesn't fit any existing one. Keep area names lowercase, one word, no hyphens.

---

## Naming examples

| Old / ad-hoc name | Correct cs- name | Rationale |
|-------------------|------------------|-----------|
| `raise-jira-bug` | `cs-jira-raise-bug` | Jira area, action = raise-bug |
| `plan-upgrade-epic` | `cs-jira-plan-epic` | Jira area, action = plan-epic |
| `azure-failure-analysis` | `cs-analyze-failures` | No area — spans Azure logs, GitHub code, and Splunk |
| `upgrade-angularjs-to-angular` | `cs-angular-upgrade` | Angular area, action = upgrade |

---

## File layout

Each skill lives in its own directory under `.claude/skills/`. The directory name **must** match the `name` field in the skill's YAML frontmatter exactly — this is the identifier Claude uses as the slash command.

```
.claude/skills/
  cs-jira-plan-epic/
    SKILL.md          ← frontmatter: name: cs-jira-plan-epic
  cs-jira-raise-bug/
    SKILL.md          ← frontmatter: name: cs-jira-raise-bug
  cs-analyze-failures/
    SKILL.md          ← frontmatter: name: cs-analyze-failures
  cs-angular-upgrade/
    SKILL.md          ← frontmatter: name: cs-angular-upgrade
```

---

## Writing the `description` field

The description is used by Claude to decide when to invoke the skill automatically. Make it:

1. **Action-first** — start with what the skill does, not its name.
2. **Include a WHEN clause** — list specific trigger phrases a user might say.
3. **Generic over specific** — describe the general capability, not a single use case.

Example:
```yaml
description: "Plan a Jira epic into sprints by building a dependency graph from Blocks
  links, balancing effort across sprints, and applying assignments. WHEN: plan epic
  into sprints, schedule tasks, assign sprints, sprint planning for an epic."
```
