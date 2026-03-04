"""Full analysis pipeline: parse -> correlate -> classify -> report -> store."""
import asyncio
import json
import logging
import uuid
from pathlib import Path

from src.parsers import parse_logs
from src.knowledge_graph import (
    correlate_test_run,
    load_kg,
    compile_failure_patterns,
)
from src.classifier import (
    classify_test,
    generate_report,
    store_run_cost,
    RunTokenAccumulator,
    compute_endpoint_heatmap,
    compute_failure_ratios,
    get_flakiness_index,
    upsert_flakiness,
    store_result,
)

logger = logging.getLogger(__name__)


async def run_analysis_pipeline(
    run_id: str,
    test_folder: str,
    log_folder: str,
    run_status: dict,  # shared in-memory dict: run_id -> status
) -> None:
    """Execute full pipeline; update run_status on completion/failure.

    Pipeline steps:
    1. parse_logs() — detect format (JSON/stdout), parse all test files
    2. correlate_test_run() — match endpoints and error patterns against KG
    3. classify_test() per failing/flaky test — rule engine first, LLM escalation if needed
    4. generate_report() — structured JSON report
    5. store_run_cost() — persist run metadata to SQLite

    Args:
        run_id: Unique identifier for this analysis run (UUID).
        test_folder: Path to directory containing .spec.ts test files.
        log_folder: Path to directory containing Playwright log output.
        run_status: Shared in-memory dict updated on completion/failure.
    """
    try:
        # Step 1: Parse logs (auto-detects JSON vs stdout format)
        parsed = await parse_logs(
            log_folder=Path(log_folder),
            spec_folder=Path(test_folder),
        )

        # Step 2: Correlate against knowledge graph
        # Load KG and compile patterns (cached after first call)
        kg = load_kg()
        compiled_patterns = compile_failure_patterns(kg)
        correlated = correlate_test_run(parsed, kg, compiled_patterns)

        # Build a map from full_title -> (ParsedTest, ParsedSpecAnalysis|None)
        # for lookup during classification, since correlator only produces CorrelatedTests
        parsed_test_map: dict[str, object] = {}
        spec_analysis_map: dict[str, object] = {}
        for suite in parsed.suites:
            sa = suite.spec_analysis
            for pt in suite.tests:
                parsed_test_map[pt.full_title] = pt
                if sa is not None:
                    spec_analysis_map[pt.full_title] = sa

        # Step 3: Classify each correlated test
        accumulator = RunTokenAccumulator()
        classifications = []
        for ct in correlated.correlated_tests:
            pt = parsed_test_map.get(ct.full_title)
            if pt is None:
                # Correlated test has no matching ParsedTest — skip
                logger.warning(
                    f"No ParsedTest found for correlated test '{ct.full_title}' in run {run_id}"
                )
                continue
            sa = spec_analysis_map.get(ct.full_title)
            result = await classify_test(ct, pt, sa)
            accumulator.add(result)
            classifications.append(result)
            await store_result(run_id=run_id, result=result)
            if getattr(result, "total_runs", None) is not None:
                await upsert_flakiness(
                    test_full_title=result.full_title,
                    failed=result.category != "passed",
                    flaky=result.method in ("llm_haiku", "llm_sonnet"),
                )

        # Step 4: Generate structured JSON report
        report = generate_report(
            classifications=classifications,
            run_id=run_id,
            accumulator=accumulator,
        )

        # Augment report with insight data (endpoint heatmap, failure ratios, flakiness)
        report["endpoint_heatmap"] = compute_endpoint_heatmap(correlated.correlated_tests)
        report["failure_ratios"] = compute_failure_ratios(
            [{"category": r.category} for r in classifications]
        )
        report["flakiness_index"] = await get_flakiness_index()

        # Count totals from parsed data (all tests across all suites)
        all_parsed_tests = [t for suite in parsed.suites for t in suite.tests]
        total_tests = len(all_parsed_tests)
        failed_tests = sum(1 for t in all_parsed_tests if t.status == "unexpected")

        # Step 5: Persist run-level cost and metadata to SQLite
        await store_run_cost(
            run_id=run_id,
            build_id=0,  # not a TeamCity build — dashboard-submitted run
            total_input_tokens=accumulator.total_input_tokens,
            total_output_tokens=0,
            estimated_cost_usd=accumulator.estimated_cost_usd(),
            total_tests=total_tests,
            failed_tests=failed_tests,
            report_json=json.dumps(report),
        )

        run_status[run_id] = "completed"
        logger.info(f"Pipeline completed for run {run_id}: {total_tests} tests, {failed_tests} failed")

    except Exception as e:
        run_status[run_id] = "failed"
        logger.error(f"Pipeline failed for run {run_id}: {e}", exc_info=True)
