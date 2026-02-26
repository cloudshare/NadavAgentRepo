"""Pydantic v2 data models for parsed Playwright test output.

Provides normalized structures that downstream correlation and classification
(Phases 3-4) consume regardless of whether input came from JSON reporter output
or stdout list/line reporter logs.
"""

from __future__ import annotations

from typing import Optional, Literal

from pydantic import BaseModel, Field


class ParseWarning(BaseModel):
    """A per-file parse failure that did not abort the run."""

    file: str
    error: str
    error_type: str = "parse_error"


class ParsedRetryResult(BaseModel):
    """Single attempt (retry) for one test."""

    retry: int  # 0 = first attempt
    status: Literal["passed", "failed", "timedOut", "skipped", "interrupted"]
    duration_ms: int
    error_message: Optional[str] = None
    error_stack: Optional[str] = None
    error_value: Optional[str] = None  # non-Error thrown values


class ParsedTest(BaseModel):
    """One test case across all its retry attempts."""

    title: str
    full_title: str  # describe hierarchy joined with " > "
    status: Literal["expected", "unexpected", "skipped", "flaky"]
    duration_ms: int  # sum of all attempt durations
    retries: list[ParsedRetryResult]
    retry_count: int  # len(retries) - 1
    first_error_message: Optional[str] = None
    first_error_stack: Optional[str] = None
    first_error_confidence: Literal["direct", "heuristic"] = "direct"
    project: Optional[str] = None


class ParsedSpecAnalysis(BaseModel):
    """Static analysis of a .spec.ts file via tree-sitter."""

    file_path: str
    test_names: list[str] = Field(default_factory=list)
    describe_hierarchy: list[list[str]] = Field(default_factory=list)
    api_endpoints: list[str] = Field(default_factory=list)
    goto_urls: list[str] = Field(default_factory=list)
    fragile_locators: list[str] = Field(default_factory=list)
    hard_coded_wait_ms: list[int] = Field(default_factory=list)


class ParsedTestSuite(BaseModel):
    """Normalized output from parsing one report file or spec file."""

    source_file: str
    source_type: Literal["json_reporter", "stdout_reporter", "spec_analysis"]
    tests: list[ParsedTest] = Field(default_factory=list)
    spec_analysis: Optional[ParsedSpecAnalysis] = None
    parse_warnings: list[ParseWarning] = Field(default_factory=list)
    total_tests: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    flaky: int = 0


class ParsedTestRun(BaseModel):
    """Aggregated result from parsing a folder of files."""

    suites: list[ParsedTestSuite] = Field(default_factory=list)
    warnings: list[ParseWarning] = Field(default_factory=list)
    total_tests: int = 0
    parse_succeeded: bool = True
