---
name: commit-staged
description: Create professional Git commits with AI-tracked statistics for currently staged changes only. Use this skill when the user has already staged specific changes and wants to commit only those staged changes without auto-staging everything.
---

# Commit Staged Changes

This skill helps Claude Code create professional Git commits with detailed statistics about code changes, including AI-generated vs manually-written code, for currently staged changes only.

## How It Works

When the user asks to commit staged changes, Claude should:

1. Verify there are staged changes (do NOT auto-stage anything)
2. Analyze the staged changes using `git diff --cached --stat`
3. Generate a professional, concise commit message describing the changes
4. Read `code_stats.txt` to get AI-contributed lines (if file exists)
5. Create the commit with an extended message containing statistics
6. Reset `code_stats.txt` to zero after successful commit

## Key Difference from commit-changes

Unlike the `commit-changes` skill which automatically stages all changes if nothing is staged, this skill:
- **Only commits what's already staged**
- **Will NOT auto-stage files**
- **Will exit with a message if nothing is staged**

This gives users precise control over what goes into each commit.

## Commit Message Format

The commit message should follow this structure:

```
<Short descriptive title (50 chars max)>

<Optional detailed description if needed>

Statistics:
- Lines added: <total>
- Lines removed: <total>
- AI-contributed lines added: <from code_stats.txt>
- AI-contributed lines removed: <from code_stats.txt>
```

## Workflow

### 1. Check for Staged Changes

```bash
git diff --cached --name-only
```

If nothing is staged, inform the user and exit.

### 2. Analyze Staged Changes

Get statistics using:
```bash
git diff --cached --stat
git diff --cached --numstat
```

Count total lines added and removed from the git diff output.

### 3. Read AI Statistics

Read `code_stats.txt` from the project root to get AI-contributed lines:

```python
def read_ai_stats():
    try:
        with open('code_stats.txt', 'r') as f:
            lines = f.readlines()

        ai_added = 0
        ai_removed = 0

        for line in lines:
            if line.startswith('Lines Added:'):
                ai_added = int(line.split(':')[1].strip())
            elif line.startswith('Lines Removed:'):
                ai_removed = int(line.split(':')[1].strip())

        return ai_added, ai_removed
    except FileNotFoundError:
        return 0, 0
```

### 4. Generate Commit Message

Create a clear, professional commit message:

- Start with a short title (imperative mood: "Add", "Fix", "Update", "Refactor")
- Add details if the change is complex
- Include statistics section

Example:
```
Add user authentication system

Implement JWT-based authentication with login/logout endpoints
and session management.

Statistics:
- Lines added: 450
- Lines removed: 23
- AI-contributed lines added: 380
- AI-contributed lines removed: 15
```

### 5. Create Commit

Use `git commit` with the generated message:
```bash
git commit -m "Title" -m "Description" -m "Statistics: ..."
```

Or use the helper script (see `scripts/commit_staged.py`).

### 6. Reset AI Stats

After successful commit, reset `code_stats.txt`:

```python
from datetime import datetime

def reset_stats():
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    content = f"""Lines Added: 0
Lines Removed: 0
Last Updated: {timestamp}
"""
    with open('code_stats.txt', 'w') as f:
        f.write(content)
```

## Platform Notes

- **Do not use `cd`** in bash commands — the Bash tool already runs in the project working directory.
- **Do not use `cd /d`** — this is Windows cmd.exe syntax and is invalid in bash.
- **Use forward slashes** in all file paths passed to bash commands (e.g., `python .claude/skills/commit_staged/scripts/commit_staged.py`). Backslashes are interpreted as escape characters in bash.
- **Prefer relative paths** when calling scripts from the project root (e.g., `python scripts/commit_staged.py` instead of an absolute path).

## Guidelines

### Commit Message Best Practices

- **Be concise**: Title should be 50 characters or less
- **Use imperative mood**: "Add feature" not "Added feature"
- **Focus on what changed**: Not why it changed (unless important)
- **Group related changes**: Don't commit unrelated changes together

### When to Skip AI Stats

If `code_stats.txt` doesn't exist or contains zero values, simply omit the AI-contributed lines from the statistics section.

## Resources

### scripts/commit_staged.py

A helper script that automates the entire commit workflow for staged changes only. Can be called directly or used as a reference implementation.

Usage:
```bash
python .claude/skills/commit_staged/scripts/commit_staged.py
```

The script will:
1. Check for staged changes (exit if none)
2. Analyze staged changes
3. Read AI statistics
4. Generate commit message
5. Create the commit
6. Reset code_stats.txt