#!/usr/bin/env python3
"""
Code Stats Tracker - Update the code_stats.txt file with lines added/removed.

Usage:
    python update_code_stats.py --added 150 --removed 45
"""

import argparse
import os
from datetime import datetime


def read_stats(filepath):
    """Read current stats from file. Returns (added, removed) or (0, 0) if file doesn't exist."""
    if not os.path.exists(filepath):
        return 0, 0
    
    try:
        with open(filepath, 'r') as f:
            lines = f.readlines()
        
        added = 0
        removed = 0
        
        for line in lines:
            if line.startswith('Lines Added:'):
                added = int(line.split(':')[1].strip())
            elif line.startswith('Lines Removed:'):
                removed = int(line.split(':')[1].strip())
        
        return added, removed
    except Exception as e:
        print(f"Warning: Error reading stats file: {e}")
        return 0, 0


def write_stats(filepath, added, removed):
    """Write updated stats to file."""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    content = f"""Lines Added: {added}
Lines Removed: {removed}
Last Updated: {timestamp}
"""
    
    with open(filepath, 'w') as f:
        f.write(content)
    
    print(f" Stats updated successfully!")
    print(f" Total lines added: {added}")
    print(f" Total lines removed: {removed}")
    print(f" Last updated: {timestamp}")


def main():
    parser = argparse.ArgumentParser(
        description='Update code statistics with lines added and removed.'
    )
    parser.add_argument(
        '--added',
        type=int,
        default=0,
        help='Number of lines added in this session'
    )
    parser.add_argument(
        '--removed',
        type=int,
        default=0,
        help='Number of lines removed in this session'
    )
    parser.add_argument(
        '--file',
        type=str,
        default='code_stats.txt',
        help='Path to stats file (default: code_stats.txt in current directory)'
    )
    
    args = parser.parse_args()
    
    # Read current stats
    current_added, current_removed = read_stats(args.file)
    
    # Add new counts
    total_added = current_added + args.added
    total_removed = current_removed + args.removed
    
    # Write updated stats
    write_stats(args.file, total_added, total_removed)


if __name__ == '__main__':
    main()
