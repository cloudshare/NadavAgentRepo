"""Playwright stdout (list/line reporter) parser with ANSI stripping.

Parses a folder of Playwright list/line reporter stdout log files into
normalized ParsedTestRun structures.

The Playwright list reporter emits lines like:
  '  ✓  [chromium] › path/to/file.spec.ts:5:3 › describe > test name  (1.2s)'
  '  ✗  [chromium] › path/to/file.spec.ts:12:3 › describe > other test  (438ms)'
  '  -  skipped test  (0ms)'

When piped from CI, ANSI color codes may wrap the status symbols.
This parser strips ANSI codes before applying regex matching.
"""

from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path
from typing import Optional

from src.parsers.models import (
    ParseWarning,
    ParsedRetryResult,
    ParsedTest,
    ParsedTestRun,
    ParsedTestSuite,
)

logger = logging.getLogger(__name__)

# Strip ANSI escape codes (colors, cursor movement, etc.) before regex matching.
# This covers: ESC [ ... m (SGR), ESC [ ... G/K/H/F (cursor/erase)
ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*[mGKHF]")

# Matches Playwright list reporter lines in multiple formats:
#   "  ✓  [chromium] › path/to/file.spec.ts:5:3 › describe > test name  (1.2s)"
#   "  ✗  describe > test name  (438ms)"
#   "  -  skipped test  (0ms)"
#   "  PASS  [chromium] › test name  (1s)"   (ASCII fallback)
LIST_LINE_RE = re.compile(
    r"^\s*"
    r"(?P<status>[✓✗×\-]|(?:PASS|FAIL|SKIP))"  # Unicode symbols or ASCII fallback
    r"\s+"
    r"(?:\[(?P<project>[^\]]+)\]\s+›\s+)?"  # optional [browser] › prefix
    r"(?:(?P<location>\S+:\d+:\d+)\s+›\s+)?"  # optional file:line:col ›
    r"(?P<title>.+?)"
    r"\s+\((?P<duration>\d+(?:\.\d+)?(?:ms|s|m))\)"
    r"\s*$"
)

STATUS_MAP: dict[str, str] = {
    "✓": "passed",
    "✗": "failed",
    "×": "failed",
    "-": "skipped",
    "PASS": "passed",
    "FAIL": "failed",
    "SKIP": "skipped",
}

# Map stdout status strings to ParsedTest.status Literal values
_TEST_STATUS_MAP: dict[str, str] = {
    "passed": "expected",
    "failed": "unexpected",
    "skipped": "skipped",
}


def strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from text.

    Args:
        text: Raw log line potentially containing ANSI codes.

    Returns:
        Clean text with ANSI codes removed.
    """
    return ANSI_ESCAPE.sub("", text)


def parse_duration_ms(duration_str: str) -> int:
    """Convert Playwright duration string to integer milliseconds.

    Supported formats:
      - "438ms"  -> 438
      - "1.2s"   -> 1200
      - "2m"     -> 120000

    Args:
        duration_str: Duration string from list reporter output.

    Returns:
        Duration in milliseconds as an integer.
    """
    if duration_str.endswith("ms"):
        return int(float(duration_str[:-2]))
    elif duration_str.endswith("s"):
        return int(float(duration_str[:-1]) * 1000)
    elif duration_str.endswith("m"):
        return int(float(duration_str[:-1]) * 60000)
    return 0


async def parse_single_stdout_file(file_path: Path) -> Optional[ParsedTestSuite]:
    """Parse a single Playwright stdout log file into a ParsedTestSuite.

    Reads the file asynchronously using asyncio.to_thread, decodes with
    errors='replace' to handle non-UTF-8 CI logs, strips ANSI per line,
    and applies LIST_LINE_RE to match test result lines.

    Args:
        file_path: Path to a .log/.txt/.out or similar stdout log file.

    Returns:
        ParsedTestSuite if at least one Playwright list reporter line was
        matched, or None if no lines matched (caller adds ParseWarning).
    """
    raw_bytes: bytes = await asyncio.to_thread(file_path.read_bytes)
    content: str = raw_bytes.decode("utf-8", errors="replace")

    tests: list[ParsedTest] = []

    for line in content.splitlines():
        clean_line = strip_ansi(line)
        match = LIST_LINE_RE.match(clean_line)
        if not match:
            continue

        raw_status = match.group("status")
        stdout_status = STATUS_MAP.get(raw_status, "failed")
        test_status = _TEST_STATUS_MAP.get(stdout_status, "unexpected")

        title: str = match.group("title").strip()
        duration_str: str = match.group("duration")
        duration_ms: int = parse_duration_ms(duration_str)
        project: Optional[str] = match.group("project")

        retry_result = ParsedRetryResult(
            retry=0,
            status=stdout_status,  # type: ignore[arg-type]
            duration_ms=duration_ms,
        )

        tests.append(
            ParsedTest(
                title=title,
                full_title=title,  # No describe hierarchy available from stdout format
                status=test_status,  # type: ignore[arg-type]
                duration_ms=duration_ms,
                retries=[retry_result],
                retry_count=0,
                first_error_message=None,  # Stdout format doesn't include stack traces
                first_error_stack=None,
                project=project,
            )
        )

    if not tests:
        # Signal to caller that no Playwright lines were found
        return None

    passed = sum(1 for t in tests if t.status == "expected")
    failed = sum(1 for t in tests if t.status == "unexpected")
    skipped = sum(1 for t in tests if t.status == "skipped")

    return ParsedTestSuite(
        source_file=str(file_path),
        source_type="stdout_reporter",
        tests=tests,
        total_tests=len(tests),
        passed=passed,
        failed=failed,
        skipped=skipped,
    )


async def parse_playwright_stdout(folder: Path) -> ParsedTestRun:
    """Parse a folder of Playwright stdout log files.

    Concurrently reads .log, .txt, .out, and other non-.json files,
    wrapping each file parse in try/except so one bad file does not abort
    the entire run. Files that contain no Playwright list reporter lines
    are recorded as ParseWarning entries.

    Args:
        folder: Directory containing Playwright stdout log files.

    Returns:
        ParsedTestRun aggregating all successfully parsed suites.
        parse_succeeded is False only if ALL files failed to parse.
    """
    folder = Path(folder)

    # Collect candidate files: .log, .txt, .out, and any other non-.json files
    candidate_files: list[Path] = []
    seen: set[Path] = set()

    for pattern in ("*.log", "*.txt", "*.out"):
        for f in folder.glob(pattern):
            if f not in seen:
                candidate_files.append(f)
                seen.add(f)

    # Also pick up bare files (no extension) that are not .json
    for f in folder.glob("*"):
        if f.is_file() and f.suffix not in (".json",) and f not in seen:
            candidate_files.append(f)
            seen.add(f)

    if not candidate_files:
        logger.warning(f"No stdout log files found in {folder}")
        return ParsedTestRun(parse_succeeded=False)

    tasks = [parse_single_stdout_file(f) for f in candidate_files]
    raw_results = await asyncio.gather(*tasks, return_exceptions=True)

    suites: list[ParsedTestSuite] = []
    top_warnings: list[ParseWarning] = []
    any_success = False

    for file_path, result in zip(candidate_files, raw_results):
        if isinstance(result, Exception):
            logger.warning(f"Failed to parse stdout file {file_path}: {result}")
            top_warnings.append(
                ParseWarning(
                    file=str(file_path),
                    error=str(result),
                    error_type="parse_error",
                )
            )
        elif result is None:
            # No Playwright list reporter lines found
            top_warnings.append(
                ParseWarning(
                    file=str(file_path),
                    error="No Playwright list reporter lines found in file",
                    error_type="no_playwright_lines",
                )
            )
        else:
            suites.append(result)
            any_success = True

    total_tests = sum(s.total_tests for s in suites)

    return ParsedTestRun(
        suites=suites,
        warnings=top_warnings,
        total_tests=total_tests,
        parse_succeeded=any_success,
    )
