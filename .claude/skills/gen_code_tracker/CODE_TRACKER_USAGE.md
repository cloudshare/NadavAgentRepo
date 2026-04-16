# Code Tracker Skill - Usage Guide

This skill enables Claude Code to automatically track lines of code added and removed across all your coding sessions.

## What It Does

- Maintains a `code_stats.txt` file in your project root
- Tracks cumulative lines added and removed
- Updates automatically after each coding session
- Provides a simple way to monitor your coding productivity

## How to Install

1. Download the `code-tracker.skill` file
2. In Claude Code, go to Settings → Skills
3. Click "Import Skill" and select the `code-tracker.skill` file
4. The skill is now active!

## How It Works

Once installed, Claude Code will:

1. **After each coding session**, automatically count the lines you've added and removed
2. **Update `code_stats.txt`** in your project root with cumulative totals
3. **Track the timestamp** of the last update

## The Stats File

The `code_stats.txt` file will look like this:

```
Lines Added: 1250
Lines Removed: 340
Last Updated: 2026-02-02 14:30:15
```

## Manual Usage

You can also manually update stats using the included helper script:

```bash
python scripts/update_code_stats.py --added 150 --removed 45
```

Or specify a custom stats file location:

```bash
python scripts/update_code_stats.py --added 150 --removed 45 --file /path/to/stats.txt
```

## What Gets Counted

- **Lines Added**: All new lines written to files
- **Lines Removed**: All lines deleted from files
- **File Creation**: All lines in new files count as "added"
- **File Deletion**: All lines in deleted files count as "removed"
- **Modifications**: New lines count as "added", replaced lines count as both "removed" and "added"

## Tips

- The stats file persists across sessions, giving you a running total
- Check `code_stats.txt` anytime to see your cumulative coding activity
- Perfect for tracking productivity on long-term projects
- Great for understanding the scope of refactoring work

Enjoy tracking your code changes! 🚀
