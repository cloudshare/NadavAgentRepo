"""Playwright JSON reporter parser.

Parses a folder of Playwright built-in JSON reporter output files into
normalized ParsedTestRun structures.

The Playwright JSON reporter produces a tree:
  JSONReport
    .stats       -> expected, unexpected, skipped, flaky counts
    .suites[]    -> JSONReportSuite (file-level and describe-level)
    .errors[]    -> top-level errors (suite setup failures)

Each JSONReportSuite may contain nested suites (describe blocks) and
specs (individual test cases). Tests inside describe() blocks live at
suites[0].suites[1].specs — never assume flat structure.
"""

from __future__ import annotations

import asyncio
import json
import logging
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

# Error heuristic priority categories (higher index = higher priority)
_PRIORITY_NETWORK = 3
_PRIORITY_TIMEOUT = 2
_PRIORITY_ASSERTION = 1
_PRIORITY_UNKNOWN = 0

# Keyword sets for each priority tier
_NETWORK_KEYWORDS = [
    "net::ERR",
    "ERR_CONNECTION",
    "navigation timeout",
    "ERR_ABORTED",
    "Failed to navigate",
]
_TIMEOUT_KEYWORDS = [
    "Timeout",
    "waiting for",
    "exceeded",
]
_ASSERTION_KEYWORDS = [
    "Expected",
    "toBe",
    "toEqual",
    "expect(",
    "received",
]


def _error_priority(message: str) -> int:
    """Return priority rank for an error message (higher = more root-cause-like)."""
    if not message:
        return _PRIORITY_UNKNOWN
    for keyword in _NETWORK_KEYWORDS:
        if keyword in message:
            return _PRIORITY_NETWORK
    for keyword in _TIMEOUT_KEYWORDS:
        if keyword in message:
            return _PRIORITY_TIMEOUT
    for keyword in _ASSERTION_KEYWORDS:
        if keyword in message:
            return _PRIORITY_ASSERTION
    return _PRIORITY_UNKNOWN


def extract_first_error(
    errors: list[dict],
) -> tuple[Optional[str], Optional[str], str]:
    """Apply heuristic priority ranking to identify root cause from errors[].

    Priority order (highest first):
      1. Navigation/network errors (net::ERR, ERR_CONNECTION, navigation timeout, …)
      2. Timeout errors (Timeout, waiting for, exceeded)
      3. Assertion errors (Expected, toBe, toEqual, expect(, received)
      4. Fallback: chronological first (errors[0])

    Args:
        errors: List of JSONReportError dicts with optional "message", "stack",
                "value" keys.

    Returns:
        Tuple of (message, stack, confidence) where confidence is "direct" when
        errors[0] is chosen naturally and "heuristic" when reordering was applied.
    """
    if not errors:
        return None, None, "direct"

    if len(errors) == 1:
        err = errors[0]
        return (
            err.get("message"),
            err.get("stack"),
            "direct",
        )

    # Find the highest-priority error
    best_idx = 0
    best_priority = _error_priority(errors[0].get("message", ""))

    for idx, err in enumerate(errors[1:], start=1):
        p = _error_priority(err.get("message", ""))
        if p > best_priority:
            best_priority = p
            best_idx = idx

    chosen = errors[best_idx]
    confidence = "direct" if best_idx == 0 else "heuristic"
    return chosen.get("message"), chosen.get("stack"), confidence


def flatten_specs(suite: dict, path: list[str] | None = None) -> list[dict]:
    """Recursively flatten all specs from nested suites.

    Args:
        suite: A JSONReportSuite dict with optional "title", "suites", "specs".
        path: Accumulated list of parent suite titles.

    Returns:
        List of dicts with keys "spec" (JSONReportSpec) and "path" (list of titles).
    """
    if path is None:
        path = []

    current_title = suite.get("title", "")
    current_path = path + [current_title] if current_title else list(path)

    results: list[dict] = []

    for spec in suite.get("specs", []):
        results.append({"spec": spec, "path": current_path})

    for child_suite in suite.get("suites", []):
        results.extend(flatten_specs(child_suite, current_path))

    return results


async def parse_single_json_file(file_path: Path) -> Optional[ParsedTestSuite]:
    """Parse a single Playwright JSON reporter file into a ParsedTestSuite.

    Reads the file asynchronously (via asyncio.to_thread), handles nested
    describe hierarchies, extracts per-retry results, and applies the
    first-real-error heuristic.

    Args:
        file_path: Path to a .json Playwright reporter output file.

    Returns:
        ParsedTestSuite on success, or None if the file is not a valid report.
        Top-level suite errors (config load failures) appear as parse_warnings.
    """
    raw_bytes: bytes = await asyncio.to_thread(file_path.read_bytes)
    report: dict = json.loads(raw_bytes)

    suite_warnings: list[ParseWarning] = []

    # Surface top-level errors (e.g. playwright.config.ts failed to load)
    top_errors = report.get("errors", [])
    if top_errors:
        for err in top_errors:
            msg = err.get("message", str(err))
            suite_warnings.append(
                ParseWarning(
                    file=str(file_path),
                    error=f"Top-level Playwright error: {msg}",
                    error_type="playwright_suite_error",
                )
            )
        # If there are no suites, return a suite with only warnings
        if not report.get("suites"):
            return ParsedTestSuite(
                source_file=str(file_path),
                source_type="json_reporter",
                parse_warnings=suite_warnings,
            )

    # Flatten all specs from nested suite tree
    all_specs: list[dict] = []
    for top_suite in report.get("suites", []):
        all_specs.extend(flatten_specs(top_suite))

    tests: list[ParsedTest] = []

    for item in all_specs:
        spec: dict = item["spec"]
        path: list[str] = item["path"]

        title: str = spec.get("title", "")
        # Build full_title from path + title, filtering empty strings
        path_parts = [p for p in path if p]
        if title:
            full_title = " > ".join(path_parts + [title]) if path_parts else title
        else:
            full_title = " > ".join(path_parts)

        spec_tests: list[dict] = spec.get("tests", [])
        if not spec_tests:
            continue

        # Use first project (index 0) as the primary test result
        primary_test: dict = spec_tests[0]

        status = primary_test.get("status", "unexpected")
        project_name: Optional[str] = primary_test.get("projectName") or primary_test.get(
            "projectId"
        )

        # Build per-retry results
        retries: list[ParsedRetryResult] = []
        total_duration = 0

        for result in primary_test.get("results", []):
            retry_idx: int = result.get("retry", 0)
            retry_status: str = result.get("status", "failed")
            duration: int = result.get("duration", 0)

            total_duration += duration

            # Extract error for this attempt using the full errors[] list
            attempt_errors: list[dict] = result.get("errors", [])
            # Fall back to single "error" field if errors[] is empty
            if not attempt_errors and result.get("error"):
                attempt_errors = [result["error"]]

            err_msg, err_stack, _ = extract_first_error(attempt_errors)

            # Also grab error_value from the top-level error if available
            err_value: Optional[str] = None
            if attempt_errors:
                err_value = attempt_errors[0].get("value")

            retries.append(
                ParsedRetryResult(
                    retry=retry_idx,
                    status=retry_status,  # type: ignore[arg-type]
                    duration_ms=duration,
                    error_message=err_msg,
                    error_stack=err_stack,
                    error_value=err_value,
                )
            )

        # Determine first_error_message/stack using the heuristic across ALL
        # failed attempt errors (use first failed attempt's errors list)
        first_error_message: Optional[str] = None
        first_error_stack: Optional[str] = None
        first_error_confidence = "direct"

        for result in primary_test.get("results", []):
            attempt_errors = result.get("errors", [])
            if not attempt_errors and result.get("error"):
                attempt_errors = [result["error"]]
            if attempt_errors:
                first_error_message, first_error_stack, first_error_confidence = (
                    extract_first_error(attempt_errors)
                )
                break

        tests.append(
            ParsedTest(
                title=title,
                full_title=full_title,
                status=status,  # type: ignore[arg-type]
                duration_ms=total_duration,
                retries=retries,
                retry_count=max(0, len(retries) - 1),
                first_error_message=first_error_message,
                first_error_stack=first_error_stack,
                first_error_confidence=first_error_confidence,  # type: ignore[arg-type]
                project=project_name,
            )
        )

    # Count by status
    passed = sum(1 for t in tests if t.status == "expected")
    failed = sum(1 for t in tests if t.status == "unexpected")
    skipped = sum(1 for t in tests if t.status == "skipped")
    flaky = sum(1 for t in tests if t.status == "flaky")

    return ParsedTestSuite(
        source_file=str(file_path),
        source_type="json_reporter",
        tests=tests,
        parse_warnings=suite_warnings,
        total_tests=len(tests),
        passed=passed,
        failed=failed,
        skipped=skipped,
        flaky=flaky,
    )


async def parse_playwright_json(folder: Path) -> ParsedTestRun:
    """Parse a folder of Playwright JSON reporter output files.

    Concurrently reads all .json files in the folder (and subdirectories),
    wrapping each file parse in try/except so one bad file does not abort
    the entire run.

    Args:
        folder: Directory containing .json Playwright reporter files.

    Returns:
        ParsedTestRun aggregating all successfully parsed suites.
        parse_succeeded is False only if ALL files failed to parse.
    """
    folder = Path(folder)

    # Glob all .json files (top-level + subdirectories, deduplicated)
    json_files: list[Path] = list(folder.glob("*.json"))
    sub_files = [f for f in folder.glob("**/*.json") if f not in set(json_files)]
    all_files = json_files + sub_files

    if not all_files:
        logger.warning(f"No .json files found in {folder}")
        return ParsedTestRun(parse_succeeded=False)

    # Parse files concurrently; capture exceptions per-file
    tasks = [parse_single_json_file(f) for f in all_files]
    raw_results = await asyncio.gather(*tasks, return_exceptions=True)

    suites: list[ParsedTestSuite] = []
    top_warnings: list[ParseWarning] = []
    any_success = False

    for file_path, result in zip(all_files, raw_results):
        if isinstance(result, Exception):
            logger.warning(f"Failed to parse {file_path}: {result}")
            top_warnings.append(
                ParseWarning(
                    file=str(file_path),
                    error=str(result),
                    error_type="parse_error",
                )
            )
        elif result is not None:
            suites.append(result)
            any_success = True

    total_tests = sum(s.total_tests for s in suites)

    return ParsedTestRun(
        suites=suites,
        warnings=top_warnings,
        total_tests=total_tests,
        parse_succeeded=any_success,
    )
