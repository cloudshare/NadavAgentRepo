# Commit Changes Skill - Usage Guide

This skill enables Claude Code to create professional Git commits with detailed statistics about AI contributions to your codebase.

## What It Does

- **Automatically stages changes** if nothing is already staged (respects manual staging)
- **Analyzes git diff** to count lines added/removed
- **Reads AI statistics** from `code_stats.txt`
- **Generates professional commit messages** with detailed statistics
- **Resets the stats file** after each commit to start fresh

## How to Install

1. Download the `commit-changes.skill` file
2. In Claude Code, go to Settings → Skills
3. Click "Import Skill" and select the `commit-changes.skill` file
4. The skill is now active!

## How It Works

### Integration with Code Tracker

This skill works perfectly with the **code-tracker** skill:

1. **Code Tracker** maintains `code_stats.txt` as you code, tracking AI-written lines
2. **Commit Changes** reads that file when you commit, includes the stats in the commit message
3. After committing, it resets `code_stats.txt` to zero for the next coding session

### The Commit Workflow

When you say "commit these changes" or "create a commit", Claude will:

1. ✅ Stage all changes (`git add .`) if nothing is already staged, otherwise use the current staging
2. 📊 Analyze the staged changes
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

Claude will generate appropriate commit messages based on what changed:

- "Add 5 new files" - when only adding files
- "Update 3 files" - when only modifying files
- "Remove old configuration" - when deleting files
- "Update codebase (10 files changed)" - for mixed changes

### Custom Messages

You can provide your own commit message:
```bash
python scripts/commit_with_stats.py --message "Fix login bug"
```

### Smart Statistics

The skill tracks four key metrics:

- **Total lines added** - All new lines in the commit
- **Total lines removed** - All deleted lines in the commit
- **AI lines added** - Lines written by Claude (from code_stats.txt)
- **AI lines removed** - Lines deleted by Claude (from code_stats.txt)

This lets you see at a glance how much of your commit was AI-assisted vs manual work.

## Manual Usage

You can also run the commit script directly:

```bash
# Auto-generate message
python scripts/commit_with_stats.py

# Custom message
python scripts/commit_with_stats.py --message "Your commit message"

# Keep stats file (don't reset to zero)
python scripts/commit_with_stats.py --no-reset
```

## Example Workflow

Here's a typical workflow combining both skills:

```bash
# Day 1: Code with Claude
$ # Claude writes 300 lines of code
$ # code_stats.txt now shows: Lines Added: 300, Lines Removed: 0

# Commit the changes
$ # You: "commit these changes"
$ # Claude creates commit with message including:
#   Statistics:
#   - Lines added: 350
#   - Lines removed: 10
#   - AI-contributed lines added: 300
#   - AI-contributed lines removed: 0
$ # code_stats.txt is reset to zero

# Day 2: More coding
$ # Claude adds 150 more lines, removes 50
$ # code_stats.txt shows: Lines Added: 150, Lines Removed: 50

# Commit again
$ # Next commit will have fresh statistics starting from zero
```

## Best Practices

1. **Commit frequently** - Don't let changes pile up
2. **Let Claude generate messages** - Usually produces good descriptions
3. **Review before pushing** - Check `git log` to see the commit details
4. **Use with code-tracker** - For accurate AI contribution tracking

## Tips

- If no files are staged, the skill automatically stages all changes (`git add .`). If you've already staged specific files, it commits only those
- If `code_stats.txt` doesn't exist or is zero, AI stats are simply omitted
- Statistics are added to commit body, not the title, keeping git logs clean
- Works with any Git workflow (branches, PRs, etc.)

## Requirements

- Git repository initialized
- Git user configured (`git config user.name` and `git config user.email`)
- Optional: `code_stats.txt` file for AI contribution tracking

Enjoy your professional, stat-tracked commits! 📊✨
