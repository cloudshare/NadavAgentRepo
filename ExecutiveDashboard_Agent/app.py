import os
import time
import math
from datetime import datetime, timezone
from collections import defaultdict

import requests
from flask import Flask, jsonify, send_from_directory, request
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__, static_folder="static")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
JIRA_EMAIL = os.getenv("JIRA_EMAIL", "")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN", "")
JIRA_BASE_URL = os.getenv("JIRA_BASE_URL", "").rstrip("/")
INITIATIVE_KEY = os.getenv("INITIATIVE_KEY", "BAC-18816")
CACHE_TTL = int(os.getenv("CACHE_TTL", "300"))  # seconds

# ---------------------------------------------------------------------------
# In-memory cache
# ---------------------------------------------------------------------------
_cache = {"data": None, "ts": 0}

#stam
def _jira_get(path, params=None):
    """Low-level Jira REST call with Basic auth."""
    url = f"{JIRA_BASE_URL}/rest/api/3/{path}"
    resp = requests.get(
        url,
        params=params,
        auth=(JIRA_EMAIL, JIRA_API_TOKEN),
        headers={"Accept": "application/json"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def _jira_search(jql, fields=None, max_results=100):
    """Paginated JQL search using the new /search/jql endpoint."""
    fields = fields or [
        "summary", "status", "assignee", "priority", "updated", "duedate",
    ]
    all_issues = []
    next_token = None
    while True:
        params = {
            "jql": jql,
            "fields": ",".join(fields),
            "maxResults": max_results,
        }
        if next_token:
            params["nextPageToken"] = next_token
        data = _jira_get("search/jql", params)
        all_issues.extend(data.get("issues", []))
        next_token = data.get("nextPageToken")
        if not next_token:
            break
    return all_issues


def _status_category(issue):
    """Return normalised status-category name: done / indeterminate / new."""
    cat = (
        issue.get("fields", {})
        .get("status", {})
        .get("statusCategory", {})
        .get("key", "new")
    )
    return cat  # "done", "indeterminate", "new"


def _normalise_task(issue):
    fields = issue.get("fields", {})
    assignee = fields.get("assignee")
    status = fields.get("status", {})
    priority = fields.get("priority")
    return {
        "key": issue["key"],
        "summary": fields.get("summary", ""),
        "status": status.get("name", ""),
        "statusCategory": _status_category(issue),
        "assignee": assignee.get("displayName", "") if assignee else "Unassigned",
        "priority": priority.get("name", "") if priority else "",
        "updated": fields.get("updated", ""),
        "webUrl": f"{JIRA_BASE_URL}/browse/{issue['key']}",
    }


def _build_dashboard():
    """Fetch initiative, epics and tasks from Jira and build the JSON payload."""
    # 1. Initiative details
    init_raw = _jira_get(f"issue/{INITIATIVE_KEY}", {
        "fields": "summary,status,assignee,project",
    })
    init_fields = init_raw.get("fields", {})
    init_assignee = init_fields.get("assignee")
    initiative = {
        "key": INITIATIVE_KEY,
        "summary": init_fields.get("summary", ""),
        "status": init_fields.get("status", {}).get("name", ""),
        "owner": init_assignee.get("displayName", "") if init_assignee else "Unassigned",
        "project": init_fields.get("project", {}).get("name", ""),
        "webUrl": f"{JIRA_BASE_URL}/browse/{INITIATIVE_KEY}",
    }

    # 2. Child epics (phases)
    epic_issues = _jira_search(
        f"parent = {INITIATIVE_KEY} ORDER BY rank ASC",
        fields=["summary", "status", "assignee", "duedate"],
    )

    # 3. All tasks across all epics (one JQL call)
    epic_keys = [e["key"] for e in epic_issues]
    all_task_issues = []
    if epic_keys:
        keys_csv = ", ".join(epic_keys)
        all_task_issues = _jira_search(
            f"parent in ({keys_csv}) ORDER BY rank ASC",
            fields=["summary", "status", "assignee", "priority", "updated", "duedate", "parent"],
        )

    # Map tasks to their parent epic
    tasks_by_epic = defaultdict(list)
    for t in all_task_issues:
        parent_key = (
            t.get("fields", {}).get("parent", {}).get("key", "")
        )
        tasks_by_epic[parent_key].append(t)

    # Build phase objects
    phases = []
    all_tasks_flat = []
    total_done = total_ip = total_todo = 0

    for idx, epic in enumerate(epic_issues):
        ef = epic.get("fields", {})
        epic_assignee = ef.get("assignee")
        raw_tasks = tasks_by_epic.get(epic["key"], [])
        norm_tasks = [_normalise_task(t) for t in raw_tasks]

        done = sum(1 for t in norm_tasks if t["statusCategory"] == "done")
        ip = sum(1 for t in norm_tasks if t["statusCategory"] == "indeterminate")
        todo = sum(1 for t in norm_tasks if t["statusCategory"] == "new")
        tc = len(norm_tasks)
        pct = round(done / tc * 100) if tc else 0

        total_done += done
        total_ip += ip
        total_todo += todo

        phases.append({
            "key": epic["key"],
            "summary": ef.get("summary", ""),
            "status": ef.get("status", {}).get("name", ""),
            "assignee": epic_assignee.get("displayName", "") if epic_assignee else "Unassigned",
            "dueDate": ef.get("duedate"),
            "taskCount": tc,
            "done": done,
            "inProgress": ip,
            "todo": todo,
            "percentDone": pct,
            "tasks": norm_tasks,
        })
        all_tasks_flat.extend(norm_tasks)

    total_tasks = total_done + total_ip + total_todo
    phases_done = sum(1 for p in phases if p["percentDone"] == 100 and p["taskCount"] > 0)

    # Team aggregation
    team_map = defaultdict(lambda: {"done": 0, "inProgress": 0, "todo": 0, "tasks": []})
    for t in all_tasks_flat:
        name = t["assignee"]
        cat = t["statusCategory"]
        team_map[name]["tasks"].append(t)
        if cat == "done":
            team_map[name]["done"] += 1
        elif cat == "indeterminate":
            team_map[name]["inProgress"] += 1
        else:
            team_map[name]["todo"] += 1

    team = sorted(
        [
            {"name": name, **counts}
            for name, counts in team_map.items()
        ],
        key=lambda m: m["done"] + m["inProgress"] + m["todo"],
        reverse=True,
    )

    pct_done = round(total_done / total_tasks * 100, 1) if total_tasks else 0

    return {
        "fetchedAt": datetime.now(timezone.utc).isoformat(),
        "initiative": initiative,
        "kpi": {
            "totalTasks": total_tasks,
            "done": total_done,
            "inProgress": total_ip,
            "todo": total_todo,
            "phasesTotal": len(phases),
            "phasesDone": phases_done,
            "percentDone": pct_done,
        },
        "phases": phases,
        "team": team,
        "allTasks": all_tasks_flat,
    }


def _get_data(force_refresh=False):
    now = time.time()
    if force_refresh or _cache["data"] is None or (now - _cache["ts"]) > CACHE_TTL:
        _cache["data"] = _build_dashboard()
        _cache["ts"] = now
    return _cache["data"]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return send_from_directory("static", "dashboard.html")


@app.route("/api/dashboard")
def api_dashboard():
    force = request.args.get("refresh") == "1"
    try:
        data = _get_data(force_refresh=force)
        return jsonify(data)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 502


@app.route("/api/health")
def api_health():
    age = round(time.time() - _cache["ts"]) if _cache["ts"] else None
    return jsonify({
        "status": "ok",
        "cached": _cache["data"] is not None,
        "cacheAgeSec": age,
        "cacheTtlSec": CACHE_TTL,
    })


if __name__ == "__main__":
    app.run(debug=True, port=5052)
