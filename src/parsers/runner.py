"""Centralized per-file error isolation for all parsers.

Implements the FNDTN-04 requirement: individual file parse failures must not
abort the entire run. All parsers (json_reporter, stdout_reporter, spec_parser,
monitoring) share this single isolation implementation to ensure consistent
error-handling semantics.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Awaitable, Callable, TypeVar

from src.parsers.models import ParseWarning, ParsedTestSuite

logger = logging.getLogger(__name__)

T = TypeVar("T")


async def parse_folder_with_isolation(
    files: list[Path],
    parse_fn: Callable[[Path], Awaitable[ParsedTestSuite | None]],
) -> tuple[list[ParsedTestSuite], list[ParseWarning]]:
    """Run parse_fn on each file concurrently with per-file error isolation.

    Implements FNDTN-04: one file failing to parse must not abort the run.
    All parse exceptions are caught and converted to ParseWarning entries.
    Files for which parse_fn returns None (e.g., no recognised lines found)
    also become ParseWarning entries.

    Args:
        files: List of file paths to parse.
        parse_fn: Async callable that takes a Path and returns a
            ParsedTestSuite or None.

    Returns:
        Tuple of (suites, warnings) where:
        - suites: all successful non-None ParsedTestSuite results
        - warnings: one ParseWarning per file that raised an exception or
          returned None
    """
    if not files:
        return [], []

    tasks = [parse_fn(f) for f in files]
    raw_results = await asyncio.gather(*tasks, return_exceptions=True)

    suites: list[ParsedTestSuite] = []
    warnings: list[ParseWarning] = []

    for file_path, result in zip(files, raw_results):
        if isinstance(result, Exception):
            logger.warning("Failed to parse %s: %s", file_path, result)
            warnings.append(
                ParseWarning(
                    file=str(file_path),
                    error=str(result),
                    error_type=type(result).__name__,
                )
            )
        elif result is None:
            warnings.append(
                ParseWarning(
                    file=str(file_path),
                    error="Parser returned no data for this file",
                    error_type="empty_parse",
                )
            )
        else:
            suites.append(result)

    return suites, warnings
