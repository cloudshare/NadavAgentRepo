---
name: code-tracker
description: Track lines of code added and removed across coding sessions in Claude Code. Use this skill when working in Claude Code to automatically maintain a running count of code changes in a stats file. Triggers on any coding task where code is being written, modified, or deleted.
---

# Code Tracker

This skill helps Claude Code maintain a persistent record of code changes across sessions by tracking lines added and removed.

## How It Works

After any session where code is created, modified, or deleted, Claude should:

1. Count the lines of code added and removed in the current session
2. Update or create a `code_stats.txt` file in the project root
3. Add the current session's changes to the cumulative totals

## Stats File Format

The `code_stats.txt` file should be stored in the project root directory and contain:

```
Lines Added: [total_number]
Lines Removed: [total_number]
Last Updated: [timestamp]
```

## Tracking Process

### When to Update

Update the stats file after completing any coding work that involves:

- Creating new files
- Modifying existing files
- Deleting files or code sections

### How to Count

1. **Lines added**: New lines written in all files during the session
2. **Lines removed**: Lines deleted from all files during the session

For modifications:

- New lines count as "added"
- Replaced/deleted lines count as "removed"

### Updating the File

Use the helper script `scripts/update_code_stats.py` to update stats:

```bash
python scripts/update_code_stats.py --added <num> --removed <num>
```

Or manually:

1. If `code_stats.txt` doesn't exist, create it with current session counts
2. If it exists, read current totals, add session counts, and write updated totals
3. Update the timestamp to current date/time

## Platform Notes

- **Do not use `cd`** in bash commands — the Bash tool already runs in the project working directory.
- **Do not use `cd /d`** — this is Windows cmd.exe syntax and is invalid in bash.
- **Use forward slashes** in all file paths passed to bash commands. Backslashes are interpreted as escape characters in bash.
- **Prefer relative paths** when calling scripts (e.g., `python scripts/update_code_stats.py` instead of an absolute path).

## Resources

### scripts/update_code_stats.py

A Python utility script to easily update the code stats file. Can be called with `--added` and `--removed` flags to add counts to the running total.
