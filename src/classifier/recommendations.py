"""CloudShare-domain fix recommendations and NL summary generator.

Contains DOMAIN_FIX_RECOMMENDATIONS (9 entries: 8 categories + uncertain)
and generate_rule_summary() for the deterministic rule_engine path.

CLASS-05: actionable fix recommendation per failing test.
CLASS-06: natural language root cause summary paragraph per failing test.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Domain-specific fix recommendations
# ---------------------------------------------------------------------------

DOMAIN_FIX_RECOMMENDATIONS: dict[str, str] = {
    "infrastructure_instability": (
        "Check CSC/PCS infrastructure logs for VMware ESX host errors, storage latency spikes, or "
        "hypervisor reboots. If errors are transient, add retry logic with exponential backoff "
        "(3 retries, 2s base delay) around the failing API call. Escalate to CloudShare Ops if the "
        "ESX host shows repeated failures within the same build window."
    ),
    "cloud_provisioning_delay": (
        "The async provisioning operation took longer than the test timeout. Two options: (1) increase "
        "the per-environment timeout in test configuration to match the KG typical_duration_seconds range "
        "for this endpoint, or (2) replace fixed waits with polling (page.waitForFunction / retry until "
        "environment status == 'active'). For CloudShare V3 envs, typical provisioning is 120-300s."
    ),
    "auth_session_issue": (
        "Auth token expired or was invalidated mid-test. Add a beforeAll hook that calls the login "
        "endpoint and stores the session token; verify the token is passed in Authorization headers "
        "for every API call. Check if the CloudShare session idle timeout (default 30 min) is shorter "
        "than the test suite runtime. Consider extending the token TTL for test accounts."
    ),
    "test_design_issue": (
        "Replace fragile locators (CSS selectors tied to DOM structure, index-based selectors) with "
        "stable data-testid attributes. Replace hard-coded wait times (page.waitForTimeout) with "
        "explicit condition polling (page.waitForSelector, page.waitForResponse). Review the spec "
        "file for any hardcoded environment IDs or user credentials that should come from config."
    ),
    "race_condition": (
        "Two or more tests share mutable state (environment, user, dataset) and the access ordering "
        "is non-deterministic. Assign each test its own isolated environment or user account. If "
        "sharing is required, add a mutex/semaphore around the critical section. Also check for "
        "async callbacks that fire after test teardown."
    ),
    "data_pollution": (
        "A prior test left behind data (environment, snapshot, user) that conflicts with this test's "
        "preconditions. Add an afterEach teardown step that deletes test-created resources. Use a "
        "unique prefix per test run (e.g., test-run-{uuid}) to namespace all created entities and "
        "prevent cross-run collisions."
    ),
    "product_regression": (
        "This failure does not match infrastructure, auth, or test-design patterns — likely a product "
        "regression. Review commits merged since the last green build, focusing on changes to the "
        "endpoint or feature this test exercises. Create a bug report with the full error message and "
        "add this test to the regression gate."
    ),
    "non_deterministic_ai": (
        "The AI Quality Analyzer or another ML component produced output outside the expected range. "
        "Do not assert exact AI output values; instead define acceptance criteria as a range or "
        "semantic check. Add a retry (up to 3) with different seeds before marking the test failed. "
        "If the AI model was updated, re-baseline the expected output distribution."
    ),
    "uncertain": (
        "Insufficient signals for automated classification. Review the full test log manually, paying "
        "attention to the initial error and any upstream failures in the same build. Check whether "
        "the test was recently added or modified (could be a test-design issue) and whether the "
        "endpoint it tests has recent production incidents."
    ),
}


# ---------------------------------------------------------------------------
# NL summary generator for rule_engine path
# ---------------------------------------------------------------------------


def generate_rule_summary(
    category: str,
    probability: float,
    signal_names: list[str],
) -> str:
    """Return a natural language root cause summary for a rule_engine classification.

    Args:
        category: The winning category string from run_rule_engine().
        probability: Normalised confidence score (0.0–1.0).
        signal_names: List of signal names that fired (from _matched_signal_names()).

    Returns:
        One-paragraph NL summary mentioning category, confidence, and signals matched.
    """
    confidence_pct = f"{probability:.0%}"
    if signal_names:
        signal_list = ", ".join(signal_names)
        signal_clause = (
            f" The following signals were matched: {signal_list}."
        )
    else:
        signal_clause = ""

    return (
        f"The rule engine classified this test as {category} with "
        f"{confidence_pct} confidence.{signal_clause} No LLM call was required."
    )
