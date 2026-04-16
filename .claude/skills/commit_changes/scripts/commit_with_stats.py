#!/usr/bin/env python3
"""
Commit With Stats - Create Git commits with AI contribution statistics.

This script analyzes staged changes, reads AI statistics from code_stats.txt,
generates a professional commit message, and resets the stats file.

Usage:
    python commit_with_stats.py
    python commit_with_stats.py --message "Custom commit message"
"""

import argparse
import os
import subprocess
import sys
from datetime import datetime


def run_command(cmd, capture_output=True):
    """Run a command and return the output.

    Args:
        cmd: A list of arguments (e.g., ['git', 'diff', '--cached']).
        capture_output: Whether to capture stdout/stderr.
    """
    try:
        result = subprocess.run(
            cmd,
            shell=False,
            capture_output=capture_output,
            text=True,
            check=True
        )
        return result.stdout.strip() if capture_output else ""
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {' '.join(cmd)}")
        print(f"Error: {e.stderr}")
        sys.exit(1)


def get_git_stats():
    """Get statistics about staged changes."""
    # Check if there are staged changes
    status = run_command(["git", "diff", "--cached", "--stat"])
    if not status:
        print("No staged changes to commit.")
        print("Use 'git add' to stage changes first.")
        sys.exit(0)
    
    # Get numstat for precise line counts
    numstat = run_command(["git", "diff", "--cached", "--numstat"])
    
    total_added = 0
    total_removed = 0
    files_changed = 0
    
    for line in numstat.split('\n'):
        if line.strip():
            parts = line.split('\t')
            if len(parts) >= 2:
                added = parts[0]
                removed = parts[1]
                
                # Handle binary files (shown as '-')
                if added != '-':
                    total_added += int(added)
                if removed != '-':
                    total_removed += int(removed)
                
                files_changed += 1
    
    return total_added, total_removed, files_changed


def read_ai_stats():
    """Read AI statistics from code_stats.txt."""
    if not os.path.exists('code_stats.txt'):
        return 0, 0
    
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
    except Exception as e:
        print(f"Warning: Error reading AI stats: {e}")
        return 0, 0


def reset_stats():
    """Reset code_stats.txt to zero."""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    content = f"""Lines Added: 0
Lines Removed: 0
Last Updated: {timestamp}
"""
    
    try:
        with open('code_stats.txt', 'w') as f:
            f.write(content)
        print("✅ Reset code_stats.txt to zero")
    except Exception as e:
        print(f"Warning: Could not reset code_stats.txt: {e}")


def _count_change_type(diff_summary, prefix):
    """Count occurrences of a change type (e.g., 'M', 'A', 'D') in diff --name-status output."""
    marker = f"{prefix}\t"
    count = diff_summary.count(f"\n{marker}")
    if diff_summary.startswith(marker):
        count += 1
    return count


def _generate_title(files_changed):
    """Generate a commit title from the staged diff."""
    diff_summary = run_command(["git", "diff", "--cached", "--name-status"])

    modifications = _count_change_type(diff_summary, "M")
    additions = _count_change_type(diff_summary, "A")
    deletions = _count_change_type(diff_summary, "D")

    plural = "s" if files_changed > 1 else ""

    if additions and not modifications and not deletions:
        return f"Add {files_changed} new file{plural}"
    if modifications and not additions and not deletions:
        return f"Update {files_changed} file{plural}"
    if deletions and not additions and not modifications:
        return f"Remove {files_changed} file{plural}"
    return f"Update codebase ({files_changed} files changed)"


def _build_stats(total_added, total_removed, ai_added, ai_removed):
    """Build the statistics section of the commit body."""
    stats = f"\nStatistics:\n- Lines added: {total_added}\n- Lines removed: {total_removed}"
    if ai_added > 0 or ai_removed > 0:
        stats += f"\n- AI-contributed lines added: {ai_added}\n- AI-contributed lines removed: {ai_removed}"
    return stats


def generate_commit_message(total_added, total_removed, ai_added, ai_removed, files_changed, custom_message=None):
    """Generate a commit message with statistics."""
    title = custom_message if custom_message else _generate_title(files_changed)
    stats = _build_stats(total_added, total_removed, ai_added, ai_removed)
    return title, stats


def create_commit(title, stats):
    """Create the Git commit."""
    try:
        subprocess.run(
            ["git", "commit", "-m", title, "-m", stats],
            shell=False,
            text=True,
            check=True
        )
        print(f"\n✅ Commit created successfully!")
        print(f"   Title: {title}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error creating commit: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description='Create a Git commit with AI contribution statistics.'
    )
    parser.add_argument(
        '--message', '-m',
        type=str,
        help='Custom commit message (title)'
    )
    parser.add_argument(
        '--no-reset',
        action='store_true',
        help='Do not reset code_stats.txt after commit'
    )
    
    args = parser.parse_args()
    
    # Check if we're in a git repository
    try:
        run_command(["git", "rev-parse", "--git-dir"])
    except Exception:
        print("Error: Not in a git repository")
        sys.exit(1)
    
    # Stage all changes if nothing is staged
    staged = run_command(["git", "diff", "--cached", "--name-only"])
    if not staged:
        print("No changes staged. Staging all changes...")
        run_command(["git", "add", "."], capture_output=False)
    
    # Get statistics
    print("📊 Analyzing changes...")
    total_added, total_removed, files_changed = get_git_stats()
    ai_added, ai_removed = read_ai_stats()
    
    print(f"   Files changed: {files_changed}")
    print(f"   Lines added: {total_added}")
    print(f"   Lines removed: {total_removed}")
    if ai_added > 0 or ai_removed > 0:
        print(f"   AI lines added: {ai_added}")
        print(f"   AI lines removed: {ai_removed}")
    
    # Generate commit message
    title, stats = generate_commit_message(
        total_added, total_removed, ai_added, ai_removed, files_changed, args.message
    )
    
    print(f"\n📝 Commit message:")
    print(f"   {title}")
    print(f"   {stats}")
    
    # Create commit
    if create_commit(title, stats):
        # Reset stats file
        if not args.no_reset:
            reset_stats()


if __name__ == '__main__':
    main()
