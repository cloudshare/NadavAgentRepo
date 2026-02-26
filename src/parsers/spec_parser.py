"""Tree-sitter TypeScript spec file parser.

Extracts static analysis information from .spec.ts files using tree-sitter:
- Test names (test() / it() calls)
- Describe hierarchy (describe() blocks)
- page.goto() URLs
- API endpoint calls (request.get/post/put/delete/patch)
- Fragile locator patterns (:nth-child, text=, XPath, deep chaining)
- Hard-coded wait values (waitForTimeout, setTimeout, sleep)

Uses the tree-sitter 0.23.x API:
  Language(tstype.language_typescript())
  Parser(TS_LANGUAGE)
  Query.captures(node) -> dict[str, list[Node]]

NOTE: In tree-sitter Python bindings 0.23.2, query predicates (#eq?, #any-of?,
etc.) are NOT applied automatically by the Python layer. Filtering is done in
Python after captures() returns all structural matches.
"""

from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING

import tree_sitter_typescript as tstype
from tree_sitter import Language, Parser, Query

from src.parsers.models import (
    ParsedSpecAnalysis,
    ParsedTestRun,
    ParsedTestSuite,
    ParseWarning,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level language / parser (expensive — instantiate once)
# ---------------------------------------------------------------------------

TS_LANGUAGE = Language(tstype.language_typescript())
_parser = Parser(TS_LANGUAGE)

# ---------------------------------------------------------------------------
# Module-level queries (expensive to construct — define once)
# NOTE: predicates (#eq?, #any-of?) are structural hints only; Python
# post-filtering is required because the 0.23.2 bindings do not auto-apply
# predicates.  Queries are intentionally broad to capture all structural
# matches, then narrowed in Python.
# ---------------------------------------------------------------------------

# Matches: test("name", fn) / it("name", fn)
#   and: test.only("name", fn) / test.skip(...) / test.fixme(...)
TEST_CALL_QUERY = Query(
    TS_LANGUAGE,
    """
    (call_expression
      function: (identifier) @_func
      arguments: (arguments (string) @test-title))

    (call_expression
      function: (member_expression
        object: (identifier) @_obj
        property: (property_identifier) @_prop)
      arguments: (arguments (string) @test-title-member))
    """,
)

# Matches: describe("name", fn) / test.describe("name", fn)
DESCRIBE_QUERY = Query(
    TS_LANGUAGE,
    """
    (call_expression
      function: (identifier) @_id
      arguments: (arguments (string) @suite-name))

    (call_expression
      function: (member_expression
        property: (property_identifier) @_dprop)
      arguments: (arguments (string) @suite-name-member))
    """,
)

# Matches: *.goto("url")
GOTO_QUERY = Query(
    TS_LANGUAGE,
    """
    (call_expression
      function: (member_expression
        property: (property_identifier) @_method)
      arguments: (arguments (string) @url))
    """,
)

# Matches: *.get("/endpoint") / .post(...) / .put(...) / .delete(...) / .patch(...)
API_CALL_QUERY = Query(
    TS_LANGUAGE,
    """
    (call_expression
      function: (member_expression
        property: (property_identifier) @http-method)
      arguments: (arguments (string) @endpoint))
    """,
)

# Matches: *.locator("selector") / *.getBySelector("selector")
LOCATOR_QUERY = Query(
    TS_LANGUAGE,
    """
    (call_expression
      function: (member_expression
        property: (property_identifier) @_lmethod)
      arguments: (arguments (string) @selector))
    """,
)

# Matches: *.waitForTimeout(ms) / setTimeout(fn, ms) / *.sleep(ms)
WAIT_QUERY = Query(
    TS_LANGUAGE,
    """
    (call_expression
      function: (member_expression
        property: (property_identifier) @_wmethod)
      arguments: (arguments (number) @wait-ms))

    (call_expression
      function: (identifier) @_wfunc
      arguments: (arguments _ (number) @wait-ms-second))
    """,
)

# ---------------------------------------------------------------------------
# Fragile locator detection
# ---------------------------------------------------------------------------

_FRAGILE_PATTERNS = [
    re.compile(r":nth-child\("),  # positional — breaks on DOM change
    re.compile(r"(?i)text="),  # brittle with i18n/whitespace
    re.compile(r"^\s*//"),  # absolute XPath
    re.compile(r">>.*>>.*>>"),  # 3+ level deep chaining
]

_TEST_FUNC_NAMES = {"test", "it"}
_TEST_MODIFIER_PROPS = {"only", "skip", "fixme"}
_TEST_MODIFIER_OBJS = {"test", "it"}
_DESCRIBE_FUNC_NAMES = {"describe"}
_DESCRIBE_PROP_NAMES = {"describe"}
_GOTO_METHOD = "goto"
_HTTP_METHODS = {"get", "post", "put", "delete", "patch"}
_LOCATOR_METHODS = {"locator", "getBySelector"}
_WAIT_MEMBER_METHODS = {"waitForTimeout", "sleep"}
_WAIT_FREE_FUNCS = {"setTimeout"}


def is_fragile(selector: str) -> bool:
    """Return True if the selector matches a known fragile pattern."""
    return any(p.search(selector) for p in _FRAGILE_PATTERNS)


# ---------------------------------------------------------------------------
# String node helper
# ---------------------------------------------------------------------------


def node_text(node) -> str:
    """Decode and strip surrounding quotes from a tree-sitter string node."""
    raw = node.text.decode("utf-8")
    if (raw.startswith('"') and raw.endswith('"')) or (
        raw.startswith("'") and raw.endswith("'")
    ):
        return raw[1:-1]
    if raw.startswith("`") and raw.endswith("`"):
        return raw[1:-1]
    return raw


# ---------------------------------------------------------------------------
# Core single-file parser
# ---------------------------------------------------------------------------


async def parse_single_spec_file(file_path: Path) -> "ParsedTestSuite | None":
    """Parse a single .spec.ts file into a ParsedTestSuite.

    Uses tree-sitter AST queries with Python-side predicate filtering (because
    the 0.23.2 Python bindings do not apply predicates automatically).

    Args:
        file_path: Path to the .spec.ts file to parse.

    Returns:
        ParsedTestSuite with source_type="spec_analysis" and spec_analysis
        populated, or None if the file could not be read.
    """
    source: bytes = await asyncio.to_thread(file_path.read_bytes)
    tree = _parser.parse(source)
    root = tree.root_node

    # ------------------------------------------------------------------
    # Test names — test("name") / it("name")
    # ------------------------------------------------------------------
    test_names: list[str] = []

    captures = TEST_CALL_QUERY.captures(root)

    # Direct calls: test("name") / it("name")
    func_nodes = captures.get("_func", [])
    title_nodes = captures.get("test-title", [])
    # Pair them up by position order — each capture set corresponds to
    # one match. Use matches() to get paired results safely.
    for _match_idx, match_dict in TEST_CALL_QUERY.matches(root):
        if "test-title" in match_dict and "_func" in match_dict:
            func_node = match_dict["_func"][0]
            func_name = func_node.text.decode("utf-8")
            if func_name in _TEST_FUNC_NAMES:
                test_names.append(node_text(match_dict["test-title"][0]))
        elif "test-title-member" in match_dict and "_obj" in match_dict and "_prop" in match_dict:
            obj_name = match_dict["_obj"][0].text.decode("utf-8")
            prop_name = match_dict["_prop"][0].text.decode("utf-8")
            if obj_name in _TEST_MODIFIER_OBJS and prop_name in _TEST_MODIFIER_PROPS:
                test_names.append(node_text(match_dict["test-title-member"][0]))

    # ------------------------------------------------------------------
    # Describe hierarchy — describe("name") / test.describe("name")
    # ------------------------------------------------------------------
    describe_names: list[str] = []

    for _match_idx, match_dict in DESCRIBE_QUERY.matches(root):
        if "suite-name" in match_dict and "_id" in match_dict:
            func_name = match_dict["_id"][0].text.decode("utf-8")
            if func_name in _DESCRIBE_FUNC_NAMES:
                describe_names.append(node_text(match_dict["suite-name"][0]))
        elif "suite-name-member" in match_dict and "_dprop" in match_dict:
            prop_name = match_dict["_dprop"][0].text.decode("utf-8")
            if prop_name in _DESCRIBE_PROP_NAMES:
                describe_names.append(node_text(match_dict["suite-name-member"][0]))

    # ------------------------------------------------------------------
    # page.goto() URLs
    # ------------------------------------------------------------------
    goto_urls: list[str] = []

    for _match_idx, match_dict in GOTO_QUERY.matches(root):
        if "url" in match_dict and "_method" in match_dict:
            method = match_dict["_method"][0].text.decode("utf-8")
            if method == _GOTO_METHOD:
                goto_urls.append(node_text(match_dict["url"][0]))

    # ------------------------------------------------------------------
    # API endpoint calls — request.get/post/put/delete/patch("/endpoint")
    # ------------------------------------------------------------------
    api_endpoints: list[str] = []

    for _match_idx, match_dict in API_CALL_QUERY.matches(root):
        if "endpoint" in match_dict and "http-method" in match_dict:
            method = match_dict["http-method"][0].text.decode("utf-8")
            if method in _HTTP_METHODS:
                api_endpoints.append(node_text(match_dict["endpoint"][0]))

    # ------------------------------------------------------------------
    # Fragile locators — page.locator("selector")
    # ------------------------------------------------------------------
    fragile_locators: list[str] = []

    for _match_idx, match_dict in LOCATOR_QUERY.matches(root):
        if "selector" in match_dict and "_lmethod" in match_dict:
            method = match_dict["_lmethod"][0].text.decode("utf-8")
            if method in _LOCATOR_METHODS:
                selector = node_text(match_dict["selector"][0])
                if is_fragile(selector):
                    fragile_locators.append(selector)

    # ------------------------------------------------------------------
    # Hard-coded wait values — waitForTimeout(ms) / setTimeout(fn, ms)
    # ------------------------------------------------------------------
    hard_coded_wait_ms: list[int] = []

    for _match_idx, match_dict in WAIT_QUERY.matches(root):
        if "wait-ms" in match_dict and "_wmethod" in match_dict:
            method = match_dict["_wmethod"][0].text.decode("utf-8")
            if method in _WAIT_MEMBER_METHODS:
                try:
                    hard_coded_wait_ms.append(
                        int(match_dict["wait-ms"][0].text.decode("utf-8"))
                    )
                except ValueError:
                    pass
        elif "wait-ms-second" in match_dict and "_wfunc" in match_dict:
            func = match_dict["_wfunc"][0].text.decode("utf-8")
            if func in _WAIT_FREE_FUNCS:
                try:
                    hard_coded_wait_ms.append(
                        int(match_dict["wait-ms-second"][0].text.decode("utf-8"))
                    )
                except ValueError:
                    pass

    spec_analysis = ParsedSpecAnalysis(
        file_path=str(file_path),
        test_names=test_names,
        describe_hierarchy=[describe_names],  # flat list; hierarchy rebuild is Phase 3
        api_endpoints=api_endpoints,
        goto_urls=goto_urls,
        fragile_locators=fragile_locators,
        hard_coded_wait_ms=hard_coded_wait_ms,
    )

    return ParsedTestSuite(
        source_file=str(file_path),
        source_type="spec_analysis",
        spec_analysis=spec_analysis,
        total_tests=len(test_names),
    )


# ---------------------------------------------------------------------------
# Folder-level entry point
# ---------------------------------------------------------------------------


async def parse_spec_files(folder: Path) -> ParsedTestRun:
    """Parse all .spec.ts files in a folder (recursive).

    Each file is parsed concurrently. Exceptions from individual files
    produce ParseWarning entries and do not abort the run (FNDTN-04).

    Args:
        folder: Directory to search for .spec.ts files.

    Returns:
        ParsedTestRun with suites (one per file) and warnings (one per
        failed file).
    """
    folder = Path(folder)
    spec_files = list(folder.rglob("*.spec.ts"))

    if not spec_files:
        logger.warning("No .spec.ts files found in %s", folder)
        return ParsedTestRun(parse_succeeded=False)

    tasks = [parse_single_spec_file(f) for f in spec_files]
    raw_results = await asyncio.gather(*tasks, return_exceptions=True)

    suites: list[ParsedTestSuite] = []
    warnings: list[ParseWarning] = []
    any_success = False

    for file_path, result in zip(spec_files, raw_results):
        if isinstance(result, Exception):
            logger.warning("Failed to parse spec file %s: %s", file_path, result)
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
            any_success = True

    total_tests = sum(s.total_tests for s in suites)

    return ParsedTestRun(
        suites=suites,
        warnings=warnings,
        total_tests=total_tests,
        parse_succeeded=any_success or len(suites) > 0,
    )
