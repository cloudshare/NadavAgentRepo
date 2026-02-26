"""Best-effort monitoring log parser for NewRelic, Splunk, and App Insights exports.

Handles three common export formats:
- JSON: array of objects or wrapped under a "value"/"data"/"logs" key
- CSV: header row + data rows with timestamp and message columns
- Plain text: each non-empty line treated as a log message

Unrecognised or empty files produce ParseWarning entries rather than raising
exceptions (FNDTN-04). All parsing is best-effort — partial results are
preferred over failures.
"""

from __future__ import annotations

import asyncio
import csv
import io
import json
import logging
from pathlib import Path
from typing import Optional

from src.parsers.models import ParsedTestRun, ParsedTestSuite, ParseWarning
from src.parsers.runner import parse_folder_with_isolation

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Field name aliases across monitoring tools
# ---------------------------------------------------------------------------

TIMESTAMP_FIELDS: set[str] = {
    "timestamp",
    "time",
    "@timestamp",
    "eventtime",
    "date",
    "datetime",
}

MESSAGE_FIELDS: set[str] = {
    "message",
    "msg",
    "rawmessage",
    "log",
    "logmessage",
    "text",
    "body",
    "description",
}

LEVEL_FIELDS: set[str] = {
    "level",
    "severity",
    "loglevel",
    "logseverity",
    "status",
    "priority",
}

# Keys under which a list of log records may be wrapped in a JSON export
_JSON_LIST_KEYS = {"value", "data", "logs", "records", "results", "items", "entries"}


def _extract_field(record: dict, candidates: set[str]) -> Optional[str]:
    """Case-insensitive field extraction from a record dict."""
    for key in record:
        if key.lower() in candidates:
            val = record[key]
            return str(val) if val is not None else None
    return None


def _normalise_record(raw_record: dict) -> dict:
    """Normalise a raw log record into a consistent dict with known keys."""
    return {
        "timestamp": _extract_field(raw_record, TIMESTAMP_FIELDS),
        "message": _extract_field(raw_record, MESSAGE_FIELDS),
        "level": _extract_field(raw_record, LEVEL_FIELDS),
        "_raw": raw_record,
    }


# ---------------------------------------------------------------------------
# Format-specific parsers
# ---------------------------------------------------------------------------


def _try_json(content: str) -> Optional[list[dict]]:
    """Attempt to parse content as JSON, returning a list of log records.

    Handles:
    - Top-level list: [{...}, {...}]
    - Top-level dict with a list under a well-known key

    Returns:
        List of raw record dicts, or None if content is not valid JSON or
        does not contain a recognisable list of records.
    """
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        return None

    if isinstance(parsed, list):
        # Only treat as log records if items are dicts
        if all(isinstance(item, dict) for item in parsed):
            return parsed
        return None

    if isinstance(parsed, dict):
        # Look for a wrapped list
        for key in parsed:
            if key.lower() in _JSON_LIST_KEYS:
                candidate = parsed[key]
                if isinstance(candidate, list) and all(
                    isinstance(item, dict) for item in candidate
                ):
                    return candidate
        # Single-record dict (some App Insights exports)
        # Return as a single-item list if it looks like a log record
        if _extract_field(parsed, MESSAGE_FIELDS) or _extract_field(
            parsed, TIMESTAMP_FIELDS
        ):
            return [parsed]

    return None


def _try_csv(content: str) -> Optional[list[dict]]:
    """Attempt to parse content as CSV with header row.

    Returns:
        List of raw record dicts (from csv.DictReader), or None if content
        does not look like a valid CSV with at least one header column
        matching known timestamp or message field names.
    """
    try:
        reader = csv.DictReader(io.StringIO(content))
        if reader.fieldnames is None:
            return None

        # Check if any header matches known field names (case-insensitive)
        lower_headers = {h.lower() for h in reader.fieldnames if h}
        has_ts = bool(lower_headers & TIMESTAMP_FIELDS)
        has_msg = bool(lower_headers & MESSAGE_FIELDS)

        if not (has_ts or has_msg):
            return None

        rows = [dict(row) for row in reader]
        if not rows:
            return None
        return rows
    except csv.Error:
        return None


def _parse_plain_text(content: str) -> list[dict]:
    """Treat each non-empty line as a log entry.

    Returns:
        List of raw record dicts with only a "message" key.
    """
    return [{"message": line} for line in content.splitlines() if line.strip()]


# ---------------------------------------------------------------------------
# Single-file parser
# ---------------------------------------------------------------------------


async def parse_single_monitoring_file(
    file_path: Path,
) -> Optional[ParsedTestSuite]:
    """Parse a single monitoring log file (JSON, CSV, or plain text).

    Format detection order: JSON -> CSV -> plain text.

    Args:
        file_path: Path to the monitoring log file.

    Returns:
        ParsedTestSuite with source_type="monitoring_log" and monitoring_entries
        populated, or None if no records could be extracted (which causes the
        caller to emit a ParseWarning).
    """
    raw_bytes: bytes = await asyncio.to_thread(file_path.read_bytes)
    content: str = raw_bytes.decode("utf-8", errors="replace")

    raw_records: Optional[list[dict]] = None

    # 1. Try JSON
    raw_records = _try_json(content)

    # 2. Try CSV
    if raw_records is None:
        raw_records = _try_csv(content)

    # 3. Fall back to plain text
    if raw_records is None:
        raw_records = _parse_plain_text(content)

    if not raw_records:
        # Signal empty result — runner converts this to ParseWarning
        return None

    monitoring_entries = [_normalise_record(r) for r in raw_records]

    return ParsedTestSuite(
        source_file=str(file_path),
        source_type="monitoring_log",
        total_tests=len(monitoring_entries),
        monitoring_entries=monitoring_entries,
    )


# ---------------------------------------------------------------------------
# Folder-level entry point
# ---------------------------------------------------------------------------


async def parse_monitoring_logs(folder: Path) -> ParsedTestRun:
    """Parse all monitoring log files in a folder (non-recursive).

    Globs for .json, .csv, .log, and .txt files. Uses parse_folder_with_isolation
    to ensure one bad file does not abort the run (FNDTN-04).

    Note: .json files that look like Playwright JSON reporter output are
    best handled by json_reporter; monitoring.py does not exclude them since
    it may be called with a dedicated monitoring folder. The caller is
    responsible for routing files to the correct parser.

    Args:
        folder: Directory containing monitoring log files.

    Returns:
        ParsedTestRun with suites and warnings.
    """
    folder = Path(folder)

    # Collect candidate files — deduplicated
    seen: set[Path] = set()
    candidate_files: list[Path] = []

    for pattern in ("*.json", "*.csv", "*.log", "*.txt"):
        for f in folder.glob(pattern):
            if f not in seen:
                candidate_files.append(f)
                seen.add(f)

    if not candidate_files:
        logger.warning("No monitoring log files found in %s", folder)
        return ParsedTestRun(parse_succeeded=False)

    suites, warnings = await parse_folder_with_isolation(
        candidate_files,
        parse_single_monitoring_file,
    )

    total_tests = sum(s.total_tests for s in suites)

    return ParsedTestRun(
        suites=suites,
        warnings=warnings,
        total_tests=total_tests,
        parse_succeeded=len(suites) > 0,
    )
