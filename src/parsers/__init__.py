"""Playwright log parser package.

Auto-detects log format (JSON reporter vs stdout list/line reporter) and
routes to the appropriate parser. Downstream callers use parse_logs() as
the single entry point — no need to know which parser is used.

Detection logic:
  - If folder contains any .json files -> route to parse_playwright_json
  - Otherwise -> route to parse_playwright_stdout (handles .log, .txt, plain text)

Optional extensions:
  - spec_folder: directory of .spec.ts files for AST-level static analysis
  - monitoring_folder: directory of NewRelic/Splunk/App Insights exports
"""

from pathlib import Path
from typing import Optional

from src.parsers.models import ParsedTestRun
from src.parsers.json_reporter import parse_playwright_json
from src.parsers.stdout_reporter import parse_playwright_stdout


async def parse_logs(
    log_folder: Path,
    spec_folder: Optional[Path] = None,
    monitoring_folder: Optional[Path] = None,
) -> ParsedTestRun:
    """Auto-detect format and route to correct parser.

    Merges results from all available input sources into a single
    ParsedTestRun. Each optional source (spec files, monitoring logs)
    appends its suites and warnings to the base result without replacing
    existing data.

    Args:
        log_folder: Directory containing Playwright test output files
            (.json for JSON reporter or .log/.txt for stdout reporter).
        spec_folder: Optional directory containing .spec.ts files for
            tree-sitter AST analysis. When provided, spec_analysis suites
            are appended to the result.
        monitoring_folder: Optional directory containing monitoring log
            exports (NewRelic JSON, Splunk CSV, App Insights JSON, plain
            text). When provided, monitoring_log suites are appended.

    Returns:
        ParsedTestRun with all parsed test suites, normalized regardless
        of whether input was JSON reporter output or stdout logs, combined
        with any spec analysis and monitoring log entries.
    """
    # Lazy imports to avoid circular dependencies and module-level side effects
    from src.parsers.spec_parser import parse_spec_files
    from src.parsers.monitoring import parse_monitoring_logs

    log_folder = Path(log_folder)
    json_files = list(log_folder.glob("*.json")) + list(log_folder.glob("**/*.json"))

    if json_files:
        result = await parse_playwright_json(log_folder)
    else:
        result = await parse_playwright_stdout(log_folder)

    if spec_folder is not None:
        spec_result = await parse_spec_files(Path(spec_folder))
        result.suites.extend(spec_result.suites)
        result.warnings.extend(spec_result.warnings)

    if monitoring_folder is not None:
        mon_result = await parse_monitoring_logs(Path(monitoring_folder))
        result.suites.extend(mon_result.suites)
        result.warnings.extend(mon_result.warnings)

    return result


__all__ = ["parse_logs", "ParsedTestRun"]
