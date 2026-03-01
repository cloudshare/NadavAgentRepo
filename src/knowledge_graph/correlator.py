from __future__ import annotations
import re
from urllib.parse import urlparse
from functools import lru_cache

from src.knowledge_graph.loader import CompiledFailurePattern

# Compiled at module level — applied during normalize_endpoint_path()
_TEMPLATE_VAR = re.compile(r'\$\{[^}]+\}|:[A-Za-z_][A-Za-z0-9_]*(?=/|$)')
_UUID_SEGMENT = re.compile(
    r'/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}(?=/|$)',
    re.IGNORECASE,
)
_NUMERIC_SEGMENT = re.compile(r'/[0-9]+(?=/|$)')
_ID_SEGMENT_FOR_MATCH = re.compile(
    r'/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|[0-9]+)(?=/|$)',
    re.IGNORECASE,
)


@lru_cache(maxsize=512)
def normalize_endpoint_path(raw: str) -> str:
    """Normalize raw endpoint string to canonical KG path form.

    Handles all formats that Phase 2 tree-sitter may produce:
    - Absolute URLs: https://use.cloudshare.com/api/v3/envs -> /api/v3/envs
    - Root-relative: /api/v3/envs -> /api/v3/envs
    - Relative: api/v3/envs -> /api/v3/envs
    - Template literals: /api/v3/envs/${envId} -> /api/v3/envs/{id}
    - Express-style params: /api/v3/envs/:envId -> /api/v3/envs/{id}
    - Numeric IDs: /api/v3/class/12345/students -> /api/v3/class/{id}/students
    - UUIDs: /api/v3/envs/abc-123-... -> /api/v3/envs/{id}

    Always lowercase output (CloudShare docs show mixed casing; server is case-insensitive).
    """
    raw = raw.strip().lower()
    parsed = urlparse(raw)
    # Use parsed.path if a scheme (http/https) was detected
    path = parsed.path if parsed.scheme else raw
    if not path.startswith('/'):
        path = '/' + path
    path = path.rstrip('/')
    # Normalize template vars: ${envId} -> {id}, :param -> {id}
    path = _TEMPLATE_VAR.sub('/{id}', path)
    # Normalize UUID segments
    path = _UUID_SEGMENT.sub('/{id}', path)
    # Normalize numeric segments
    path = _NUMERIC_SEGMENT.sub('/{id}', path)
    # Collapse any double-slashes introduced by substitutions
    path = re.sub(r'/+', '/', path)
    return path


def match_endpoint_to_kg(
    normalized_path: str,
    kg_endpoints: list[dict],
) -> list[dict]:
    """Find all KG endpoint entries matching a normalized path.

    Matching strategy (in order):
    1. Exact match after generalizing numeric/UUID segments to {id}
    2. Prefix match for action sub-paths (e.g., /api/v3/envs matches /api/v3/envs/actions/foo)

    Returns list of matching KG entries (usually 0 or 1).

    Critical: Do NOT use substring 'in' check — '/api/v3/env' would falsely match
    '/api/v3/environments'. Always compare full path segments.
    """
    # Generalize any remaining numeric/UUID segments in the caller's path
    generalized = _ID_SEGMENT_FOR_MATCH.sub('/{id}', normalized_path)
    # Collapse double slashes after substitution
    generalized = re.sub(r'/+', '/', generalized)

    matches = []
    for entry in kg_endpoints:
        pattern = entry['path_pattern']  # Already lowercase from KG
        # Strategy 1: exact match on generalized path
        if generalized == pattern:
            matches.append(entry)
            continue
        # Strategy 2: prefix match — /api/v3/envs matches /api/v3/envs/actions/resume
        # But only on full path segment boundaries (not substring)
        if normalized_path.startswith(pattern + '/') or normalized_path.startswith(pattern + '?'):
            matches.append(entry)
    return matches


def match_error_against_patterns(
    error_text: str,
    compiled_patterns: list[CompiledFailurePattern],
) -> list[tuple[CompiledFailurePattern, str]]:
    """Return all failure patterns that match error_text, with matched substring.

    Search all patterns against the concatenated error text. Returns list of
    (pattern, matched_text) tuples — matched_text is the specific substring
    that triggered the match, used for explainability in FailurePatternMatch.

    Performance note: patterns are pre-compiled at startup. Do NOT compile
    inside this function — 10-50x overhead per call.

    Catastrophic backtracking guard: patterns avoid multi-wildcard combinations
    on long strings. If error_text is very large (>50KB), truncate to first 50KB
    before matching — stack traces beyond that are noise.
    """
    MAX_ERROR_TEXT = 50_000
    if len(error_text) > MAX_ERROR_TEXT:
        error_text = error_text[:MAX_ERROR_TEXT]

    results = []
    for pattern in compiled_patterns:
        for compiled_re in pattern.compiled_patterns:
            m = compiled_re.search(error_text)
            if m:
                results.append((pattern, m.group(0)))
                break  # One matching regex per pattern is enough
    return results


from src.parsers.models import ParsedTestRun
from src.knowledge_graph.models import (
    CorrelatedTest, CorrelatedTestRun, EndpointMatch, FailurePatternMatch
)


def correlate_test_run(
    parsed_run: ParsedTestRun,
    kg: dict,
    compiled_patterns: list[CompiledFailurePattern],
) -> CorrelatedTestRun:
    """Run CORR-01 and CORR-02 against all failing/flaky tests in the parsed run.

    Only processes tests with status 'unexpected' (failed) or 'flaky'.
    Passing ('expected') and 'skipped' tests are excluded — they have no
    error signals to correlate.

    Args:
        parsed_run: Output of Phase 2 parse_logs()
        kg: KG dict from load_kg()
        compiled_patterns: Pre-compiled patterns from compile_failure_patterns()

    Returns:
        CorrelatedTestRun with one CorrelatedTest per failing/flaky test,
        plus unmatched_endpoints listing raw endpoint strings not found in KG.
    """
    correlated = []
    unmatched_endpoints: set[str] = set()

    for suite in parsed_run.suites:
        # Get spec analysis (populated by Phase 2 tree-sitter parser)
        spec = suite.spec_analysis
        raw_endpoints: list[str] = spec.api_endpoints if spec else []

        for test in suite.tests:
            # Only correlate tests that actually failed or are flaky
            if test.status not in ('unexpected', 'flaky'):
                continue

            # --- CORR-01: endpoint -> infra layer matching ---
            ep_matches: list[EndpointMatch] = []
            for raw_ep in raw_endpoints:
                normalized = normalize_endpoint_path(raw_ep)
                kg_hits = match_endpoint_to_kg(normalized, kg['endpoints'])
                if kg_hits:
                    for hit in kg_hits:
                        ep_matches.append(EndpointMatch(
                            kg_id=hit['id'],
                            raw_endpoint=raw_ep,
                            normalized_path=normalized,
                            infra_layers=hit['infra_layer'],
                            is_async=hit['async'],
                            typical_duration_seconds=hit.get('typical_duration_seconds'),
                            related_failure_pattern_ids=hit.get('failure_patterns', []),
                        ))
                else:
                    unmatched_endpoints.add(raw_ep)

            # --- CORR-02: error text -> failure pattern matching ---
            # Concatenate all available error text for this test
            # (pattern may span message + stack; search all retries, not just first)
            error_parts = [
                test.first_error_message or '',
                test.first_error_stack or '',
            ]
            for retry in test.retries:
                error_parts.append(retry.error_message or '')
                error_parts.append(retry.error_stack or '')
            error_text = ' '.join(filter(None, error_parts))

            fp_tuples = match_error_against_patterns(error_text, compiled_patterns)
            fp_match_models = [
                FailurePatternMatch(
                    pattern_id=fp.id,
                    pattern_name=fp.name,
                    infra_layer=fp.infra_layer,
                    category=fp.category,
                    matched_text=matched_substr,
                    description=fp.description,
                )
                for fp, matched_substr in fp_tuples
            ]

            # Derive convenience flags for Phase 4 rule engine
            all_layers = list({layer for ep in ep_matches for layer in ep.infra_layers})
            has_infra = len(fp_match_models) > 0
            has_auth = any(m.category == 'auth_session_issue' for m in fp_match_models)
            has_async = any(ep.is_async for ep in ep_matches)

            # Confidence: 1.0 if we matched something; 0.5 if KG had no entry
            matched_something = bool(ep_matches or fp_match_models)
            confidence = 1.0 if matched_something else 0.5

            correlated.append(CorrelatedTest(
                test_title=test.title,
                full_title=test.full_title,
                endpoint_matches=ep_matches,
                primary_infra_layers=all_layers,
                exercises_async_flow=has_async,
                failure_pattern_matches=fp_match_models,
                has_infra_signal=has_infra,
                has_auth_signal=has_auth,
                has_async_signal=has_async and has_infra,
                correlation_confidence=confidence,
            ))

    return CorrelatedTestRun(
        correlated_tests=correlated,
        unmatched_endpoints=sorted(unmatched_endpoints),
        total_tests=len(correlated),
        tests_with_infra_signal=sum(1 for c in correlated if c.has_infra_signal),
        tests_with_auth_signal=sum(1 for c in correlated if c.has_auth_signal),
    )


__all__ = [
    "normalize_endpoint_path",
    "match_endpoint_to_kg",
    "match_error_against_patterns",
    "correlate_test_run",
]
