from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field


class EndpointMatch(BaseModel):
    """One KG endpoint entry that matched a raw endpoint string from test code.

    Produced by CORR-01: normalize_endpoint_path() + match_endpoint_to_kg().
    """
    kg_id: str
    """KG entry id, e.g. 'envs_create'"""
    raw_endpoint: str
    """Original endpoint string extracted from test code by Phase 2 tree-sitter"""
    normalized_path: str
    """After normalize_endpoint_path() — lowercase, {id} placeholders, no trailing slash"""
    infra_layers: list[str]
    """Infrastructure layers this endpoint touches, e.g. ['WebApp', 'CSC', 'PCS']"""
    is_async: bool
    """True if this endpoint triggers an async operation (provisioning, snapshot, etc.)"""
    typical_duration_seconds: Optional[list[int]] = None
    """[min_seconds, max_seconds] from KG, or None if not specified"""
    related_failure_pattern_ids: list[str] = Field(default_factory=list)
    """Failure pattern IDs from KG that are associated with this endpoint"""


class FailurePatternMatch(BaseModel):
    """One failure pattern whose regex matched error text from this test.

    Produced by CORR-02: match_error_against_patterns().
    """
    pattern_id: str
    """KG failure pattern id, e.g. 'vmware_esx_timeout'"""
    pattern_name: str
    """Human-readable name, e.g. 'VMware ESX Timeout'"""
    infra_layer: str
    """Infrastructure layer associated with this pattern, e.g. 'CSC'"""
    category: str
    """Failure category: infrastructure_instability | cloud_provisioning_delay | auth_session_issue | data_pollution | race_condition"""
    matched_text: str
    """The specific substring of error text that triggered the regex match (for explainability)"""
    description: str
    """Human-readable description of what this pattern detects"""


class CorrelatedTest(BaseModel):
    """Correlation result for a single failing or flaky test.

    Consumed by Phase 4 classification engine (CLASS-01 through CLASS-06).
    Contains both CORR-01 (endpoint -> infra) and CORR-02 (error -> pattern) outputs.
    """
    test_title: str
    full_title: str

    # CORR-01: which infra layers this test exercises
    endpoint_matches: list[EndpointMatch] = Field(default_factory=list)
    primary_infra_layers: list[str] = Field(default_factory=list)
    """Deduplicated union of all infra_layers from endpoint_matches"""
    exercises_async_flow: bool = False
    """True if any matched endpoint is async"""

    # CORR-02: which failure patterns are present in error text
    failure_pattern_matches: list[FailurePatternMatch] = Field(default_factory=list)

    # Convenience flags for Phase 4 rule engine (avoid re-scanning lists)
    has_infra_signal: bool = False
    """True if any failure pattern matched error text"""
    has_auth_signal: bool = False
    """True if an auth_session_issue category pattern matched"""
    has_async_signal: bool = False
    """True if test exercises async endpoint AND has infra signal"""
    correlation_confidence: float = 1.0
    """1.0 if KG matched endpoint or pattern; 0.5 if no KG match found"""


class CorrelatedTestRun(BaseModel):
    """Correlation results for an entire analysis run.

    Top-level output of correlate_test_run().
    """
    correlated_tests: list[CorrelatedTest] = Field(default_factory=list)
    unmatched_endpoints: list[str] = Field(default_factory=list)
    """Raw endpoint strings from test code that had no matching KG entry.
    Used by Phase 4 to surface gaps in KG coverage."""
    total_tests: int = 0
    tests_with_infra_signal: int = 0
    tests_with_auth_signal: int = 0
