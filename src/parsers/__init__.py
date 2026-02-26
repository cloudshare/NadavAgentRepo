"""Playwright log parser package.

Auto-detects log format (JSON reporter vs stdout list/line reporter) and
routes to the appropriate parser. Downstream callers use parse_logs() as
the single entry point — no need to know which parser is used.

Detection logic:
  - If folder contains any .json files -> route to parse_playwright_json
  - Otherwise -> route to parse_playwright_stdout (handles .log, .txt, plain text)
"""

from pathlib import Path

from src.parsers.models import ParsedTestRun
from src.parsers.json_reporter import parse_playwright_json
from src.parsers.stdout_reporter import parse_playwright_stdout


async def parse_logs(folder: Path) -> ParsedTestRun:
    """Auto-detect format and route to correct parser.

    Args:
        folder: Directory containing Playwright test output files.

    Returns:
        ParsedTestRun with all parsed test suites, normalized regardless
        of whether input was JSON reporter output or stdout logs.
    """
    folder = Path(folder)
    json_files = list(folder.glob("*.json")) + list(folder.glob("**/*.json"))
    if json_files:
        return await parse_playwright_json(folder)
    return await parse_playwright_stdout(folder)


__all__ = ["parse_logs", "ParsedTestRun"]
