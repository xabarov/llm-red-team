import json
import tempfile
import unittest
from pathlib import Path

from llm_red_team.campaign import batch_summary
from llm_red_team.metrics import (
    aggregate_cases,
    analyze_case,
    analyze_run,
    build_report,
    recompute_batch_summary,
    select_candidates,
)


CORE_CODES = ("W1", "W2", "E1", "E2", "E3")


def mode_summary(
    passed_codes: set[str],
    *,
    outcome: str = "failed",
    attempts_used: int = 1,
    metrics: dict | None = None,
    attempts: list[dict] | None = None,
) -> dict:
    value = {
        "outcome": outcome,
        "passed": outcome == "passed",
        "attempts_used": attempts_used,
        "selected_attempt": attempts_used,
        "checkpoints": [
            {"code": code, "passed": code in passed_codes, "evidence_ids": [f"EVT-{code}"]}
            for code in CORE_CODES
        ],
        "attempts": attempts
        if attempts is not None
        else [{"attempt": index} for index in range(1, attempts_used + 1)],
    }
    if metrics is not None:
        value["metrics"] = metrics
    return value


def case_summary(
    scenario_id: str,
    *,
    vulnerable: dict | None = None,
    protected: dict | None = None,
    run_id: str = "campaign-test",
) -> dict:
    modes = {}
    if vulnerable is not None:
        modes["vulnerable"] = vulnerable
    if protected is not None:
        modes["protected"] = protected
    return {"scenario_id": scenario_id, "run_id": run_id, "modes": modes}


class CaseMetricsTests(unittest.TestCase):
    def test_case_funnel_and_replay_ready_classification(self) -> None:
        passed = set(CORE_CODES)
        case = analyze_case(
            case_summary(
                "ready",
                vulnerable=mode_summary(passed, outcome="passed", attempts_used=2),
                protected=mode_summary(passed, outcome="passed"),
            )
        )

        self.assertTrue(case["modes"]["vulnerable"]["funnel"]["e2e"])
        self.assertEqual(case["candidate"]["classification"], "replay-ready")
        self.assertEqual(case["candidate"]["attempts_total"], 3)

    def test_partial_write_and_recall_is_near_miss(self) -> None:
        recall_only = {"W1", "W2", "E1"}
        case = analyze_case(
            case_summary(
                "near",
                vulnerable=mode_summary(recall_only),
                protected=mode_summary(recall_only),
            )
        )

        self.assertTrue(case["modes"]["vulnerable"]["funnel"]["recall"])
        self.assertFalse(case["modes"]["vulnerable"]["funnel"]["effect"])
        self.assertEqual(case["candidate"]["classification"], "near-miss")

    def test_error_or_missing_required_mode_is_not_candidate(self) -> None:
        error_case = analyze_case(
            case_summary(
                "error",
                vulnerable=mode_summary(set(), outcome="error"),
                protected=mode_summary(set(CORE_CODES), outcome="passed"),
            )
        )
        missing_case = analyze_case(
            case_summary("missing", vulnerable=mode_summary(set(CORE_CODES), outcome="passed"))
        )

        self.assertEqual(error_case["candidate"]["classification"], "invalid")
        self.assertFalse(error_case["candidate"]["eligible"])
        self.assertEqual(missing_case["candidate"]["classification"], "invalid")

    def test_structurally_inconsistent_attempt_selection_is_invalid(self) -> None:
        passed = set(CORE_CODES)
        broken = mode_summary(passed, outcome="passed")
        broken["selected_attempt"] = 2
        case = analyze_case(
            case_summary(
                "broken",
                vulnerable=broken,
                protected=mode_summary(passed, outcome="passed"),
            )
        )

        self.assertEqual(case["candidate"]["classification"], "invalid")
        self.assertTrue(
            any("selected_attempt is absent" in reason for reason in case["candidate"]["reasons"])
        )

    def test_impossible_selected_attempt_is_invalid_without_attempt_details(self) -> None:
        passed = set(CORE_CODES)
        broken = mode_summary(passed, outcome="passed", attempts_used=3, attempts=[])
        broken["selected_attempt"] = 5
        case = analyze_case(
            case_summary(
                "broken-legacy",
                vulnerable=broken,
                protected=mode_summary(passed, outcome="passed"),
            )
        )

        self.assertEqual(case["candidate"]["classification"], "invalid")
        self.assertTrue(
            any("selected_attempt exceeds attempts_used" in reason for reason in case["candidate"]["reasons"])
        )

    def test_protected_e3_is_reported_as_protected_gate_not_asr(self) -> None:
        passed = set(CORE_CODES)
        case = analyze_case(
            case_summary(
                "protected-label",
                vulnerable=mode_summary(passed, outcome="passed"),
                protected=mode_summary(passed, outcome="passed"),
            )
        )
        aggregate = aggregate_cases([case])

        self.assertIsNone(aggregate["modes"]["protected"]["e2e_asr"])
        self.assertEqual(aggregate["modes"]["protected"]["protected_gate_rate"]["rate"], 1.0)

    def test_unknown_outcome_cannot_be_replay_candidate(self) -> None:
        passed = set(CORE_CODES)
        case = analyze_case(
            case_summary(
                "unknown-outcome",
                vulnerable=mode_summary(passed, outcome="cancelled"),
                protected=mode_summary(passed, outcome="passed"),
            )
        )

        self.assertEqual(case["candidate"]["classification"], "invalid")


class AggregateMetricsTests(unittest.TestCase):
    def test_conjunction_funnel_is_not_inferred_from_checkpoint_totals(self) -> None:
        first = analyze_case(
            case_summary(
                "first",
                vulnerable=mode_summary({"W1"}),
                protected=mode_summary({"W1"}),
            )
        )
        second = analyze_case(
            case_summary(
                "second",
                vulnerable=mode_summary({"W2"}),
                protected=mode_summary({"W2"}),
            )
        )

        aggregate = aggregate_cases([first, second])

        self.assertEqual(aggregate["modes"]["vulnerable"]["checkpoints"]["W2"]["passed"], 1)
        self.assertEqual(aggregate["modes"]["vulnerable"]["mpsr"]["passed"], 0)

    def test_telemetry_uses_mode_hook_and_attempt_fallback_with_coverage(self) -> None:
        passed = set(CORE_CODES)
        direct = analyze_case(
            case_summary(
                "direct",
                vulnerable=mode_summary(
                    passed,
                    outcome="passed",
                    metrics={"cost_usd": 0.12, "latency_ms": 800},
                ),
                protected=mode_summary(passed, outcome="passed"),
            )
        )
        fallback = analyze_case(
            case_summary(
                "fallback",
                vulnerable=mode_summary(
                    passed,
                    outcome="passed",
                    attempts_used=2,
                    attempts=[
                        {"attempt": 1, "metrics": {"cost_usd": 0.03, "latency_ms": 200}},
                        {"attempt": 2, "metrics": {"cost_usd": 0.05, "latency_ms": 300}},
                    ],
                ),
                protected=mode_summary(passed, outcome="passed"),
            )
        )

        aggregate = aggregate_cases([direct, fallback])["modes"]["vulnerable"]["telemetry"]

        self.assertAlmostEqual(aggregate["cost_usd"]["sum"], 0.20)
        self.assertEqual(aggregate["cost_usd"]["observations"], 2)
        self.assertEqual(aggregate["latency_ms"]["coverage"], 1.0)

    def test_candidate_selection_prefers_fewer_attempts(self) -> None:
        passed = set(CORE_CODES)
        slow = analyze_case(
            case_summary(
                "same",
                run_id="campaign-slow",
                vulnerable=mode_summary(passed, outcome="passed", attempts_used=3),
                protected=mode_summary(passed, outcome="passed", attempts_used=2),
            )
        )
        stable = analyze_case(
            case_summary(
                "same",
                run_id="campaign-stable",
                vulnerable=mode_summary(passed, outcome="passed"),
                protected=mode_summary(passed, outcome="passed"),
            )
        )

        selected = select_candidates([slow, stable])

        self.assertEqual(selected[0]["run_id"], "campaign-stable")
        self.assertEqual(selected[0]["eligible_occurrences"], 2)

    def test_srsr_uses_all_poisoned_cases_once_repair_is_observed(self) -> None:
        passed = set(CORE_CODES)
        with_repair = mode_summary(passed, outcome="passed")
        with_repair["checkpoints"].extend(
            [
                {"code": "F1", "passed": True, "evidence_ids": []},
                {"code": "F2", "passed": True, "evidence_ids": []},
            ]
        )
        observed = analyze_case(
            case_summary(
                "observed",
                vulnerable=with_repair,
                protected=mode_summary(passed, outcome="passed"),
            )
        )
        missing = analyze_case(
            case_summary(
                "missing",
                vulnerable=mode_summary(passed, outcome="passed"),
                protected=mode_summary(passed, outcome="passed"),
            )
        )

        srsr = aggregate_cases([observed, missing])["modes"]["vulnerable"]["srsr"]

        self.assertEqual(srsr, {"passed": 1, "total": 2, "rate": 0.5})

    def test_unmeasured_later_funnel_stages_are_na_not_failures(self) -> None:
        partial = mode_summary({"W1", "W2", "E1"})
        partial["checkpoints"] = partial["checkpoints"][:3]
        case = analyze_case(
            case_summary(
                "repair-only",
                vulnerable=partial,
                protected=mode_summary(set(CORE_CODES), outcome="passed"),
            )
        )

        mode = aggregate_cases([case])["modes"]["vulnerable"]

        self.assertIsNone(mode["funnel"]["E2"]["rate"])
        self.assertIsNone(mode["e2e_gate_rate"]["rate"])
        self.assertIsNone(mode["mesr"]["rate"])


class RunInputTests(unittest.TestCase):
    def test_analyze_run_reads_case_and_matching_batch_summaries(self) -> None:
        passed = set(CORE_CODES)
        raw = case_summary(
            "fixture",
            vulnerable=mode_summary(passed, outcome="passed"),
            protected=mode_summary(passed, outcome="passed"),
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir) / "campaign-test"
            case_dir = run_dir / "fixture"
            case_dir.mkdir(parents=True)
            (case_dir / "summary.json").write_text(json.dumps(raw), encoding="utf-8")
            (run_dir / "batch-summary.json").write_text(
                json.dumps(batch_summary([raw])), encoding="utf-8"
            )

            run, cases = analyze_run(run_dir)

        self.assertEqual(run["batch_consistency"], "matched")
        self.assertEqual(len(cases), 1)

    def test_analyze_run_detects_batch_mismatch(self) -> None:
        raw = case_summary(
            "fixture",
            vulnerable=mode_summary({"W1"}),
            protected=mode_summary({"W1"}),
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir) / "campaign-test"
            case_dir = run_dir / "fixture"
            case_dir.mkdir(parents=True)
            (case_dir / "summary.json").write_text(json.dumps(raw), encoding="utf-8")
            (run_dir / "batch-summary.json").write_text(json.dumps({"cases": 999, "modes": {}}), encoding="utf-8")

            report = build_report([run_dir])

        self.assertEqual(report["runs"][0]["batch_consistency"], "mismatch")
        self.assertTrue(report["runs"][0]["batch_differences"])

    def test_batch_only_run_is_reported_as_unverifiable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir) / "campaign-batch-only"
            run_dir.mkdir()
            (run_dir / "batch-summary.json").write_text(
                json.dumps({"cases": 1, "modes": {}}), encoding="utf-8"
            )

            report = build_report([run_dir])

        run = report["runs"][0]
        self.assertEqual(run["batch_consistency"], "unverifiable")
        self.assertIn("conjunction funnel", run["batch_differences"][0])

    def test_tolerant_batch_recompute_keeps_unknown_outcome_visible(self) -> None:
        raw = case_summary(
            "old-error",
            vulnerable=mode_summary(set(), outcome="cancelled"),
            protected=None,
        )

        result = recompute_batch_summary([raw])

        self.assertEqual(result["modes"]["vulnerable"]["cancelled"], 1)


if __name__ == "__main__":
    unittest.main()
