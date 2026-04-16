# Commit Staged Changes Skill - Usage Guide

This skill enables Claude Code to create professional Git commits with detailed statistics about AI contributions, but only for changes you've already staged.

## What It Does

- **Only commits staged changes** - will NOT auto-stage anything
- **Analyzes git diff** to count lines added/removed in staged changes
- **Reads AI statistics** from `code_stats.txt`
- **Generates professional commit messages** with detailed statistics
- **Resets the stats file** after each commit to start fresh

## Key Difference from commit-changes

The `commit-changes` skill automatically stages all changes if nothing is staged. This skill (`commit-staged`) gives you precise control:

- ✅ **You stage exactly what you want** with `git add`
- ✅ **Claude commits only those staged files**
- ❌ **No auto-staging** - if nothing is staged, you'll get a message to stage changes first

This is perfect when you want to create focused, incremental commits with only specific files or changes.

## How to Install

1. The skill files should be in `.claude/skills/commit_staged/`
2. Claude Code automatically loads skills from this directory
3. The skill is now active!

## How It Works

### Integration with Code Tracker

This skill works perfectly with the **gen-code-tracker** skill:

1. **Code Tracker** maintains `code_stats.txt` as you code, tracking AI-written lines
2. **Commit Staged** reads that file when you commit, includes the stats in the commit message
3. After committing, it resets `code_stats.txt` to zero for the next coding session

### The Commit Workflow

When you say "commit these staged changes" or "commit what's staged", Claude will:

1. ✅ Check for staged changes (exits if none found)
2. 📊 Analyze the staged changes only
3. 📖 Read AI contribution stats from `code_stats.txt`
4. 💬 Generate a professional commit message
5. 🎯 Create the commit with full statistics
6. 🔄 Reset `code_stats.txt` to zero

## Commit Message Format

Your commits will look like this:

```
Add user authentication system

Statistics:
- Lines added: 450
- Lines removed: 23
- AI-contributed lines added: 380
- AI-contributed lines removed: 15
```

Or for simple changes:

```
Update 3 files

Statistics:
- Lines added: 75
- Lines removed: 12
- AI-contributed lines added: 60
- AI-contributed lines removed: 8
```

## Features

### Automatic Message Generation

Claude will generate appropriate commit messages based on what's staged:

- "Add 5 new files" - when only adding files
- "Update 3 files" - when only modifying files
- "Remove old configuration" - when deleting files
- "Update codebase (10 files changed)" - for mixed changes

### Custom Messages

You can provide your own commit message:
```bash
python .claude/skills/commit_staged/scripts/commit_staged.py --message "Fix login bug"
```

### Smart Statistics

The skill tracks four key metrics:

- **Total lines added** - All new lines in the staged changes
- **Total lines removed** - All deleted lines in the staged changes
- **AI lines added** - Lines written by Claude (from code_stats.txt)
- **AI lines removed** - Lines deleted by Claude (from code_stats.txt)

This lets you see at a glance how much of your commit was AI-assisted vs manual work.

## Manual Usage

You can also run the commit script directly:

```bash
# Auto-generate message for staged changes
python .claude/skills/commit_staged/scripts/commit_staged.py

# Custom message
python .claude/skills/commit_staged/scripts/commit_staged.py --message "Your commit message"

# Keep stats file (don't reset to zero)
python .claude/skills/commit_staged/scripts/commit_staged.py --no-reset
```

## Example Workflow

Here's a typical workflow with selective staging:

```bash
# You've modified 5 files but only want to commit 2 of them
$ git add src/auth.js src/login.js

# Ask Claude to commit
$ # You: "commit the staged changes"
$ # Claude creates commit with only those 2 files:
#   Update 2 files
#
#   Statistics:
#   - Lines added: 120
#   - Lines removed: 30
#   - AI-contributed lines added: 100
#   - AI-contributed lines removed: 20

# Later, stage and commit the remaining files
$ git add src/api.js src/utils.js src/config.js
$ # You: "commit staged"
$ # Claude creates another focused commit with just those 3 files
```

## When to Use Each Skill

**Use `commit-changes`** when:
- You want to commit everything you've worked on
- You want Claude to handle staging automatically
- You're making one big commit with all changes

**Use `commit-staged`** when:
- You want precise control over what goes in each commit
- You're making focused, incremental commits
- You've already staged specific files with `git add`
- You're following a disciplined commit workflow

## Best Practices

1. **Stage related changes together** - Group logically related changes
2. **Make focused commits** - Each commit should represent one logical change
3. **Review what's staged** - Use `git status` or `git diff --cached` before committing
4. **Let Claude generate messages** - Usually produces good descriptions
5. **Use with code-tracker** - For accurate AI contribution tracking

## Tips

- If you try to use this skill with nothing staged, Claude will inform you and ask you to stage changes first
- If `code_stats.txt` doesn't exist or is zero, AI stats are simply omitted
- Statistics are added to commit body, not the title, keeping git logs clean
- Works with any Git workflow (branches, PRs, etc.)
- Perfect for atomic commits and keeping a clean git history

## Requirements

- Git repository initialized
- Git user configured (`git config user.name` and `git config user.email`)
- Changes must be staged with `git add` before using this skill
- Optional: `code_stats.txt` file for AI contribution tracking

Enjoy your precise, stat-tracked commits! 📊✨