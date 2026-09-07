import copy
import hashlib
import json
import unittest
from pathlib import Path

from llm_red_team.checkpoints import all_passed
from llm_red_team.defense import (
    DEFENSE_MODES,
    DefenseProfile,
    apply_defense,
    evaluate_guarded_mode,
    load_guarded_case,
    run_guarded_case,
    selective_repair,
    validate_guarded_case,
)
from llm_red_team.metrics import aggregate_cases, analyze_case
from llm_red_team.scenario import load_scenario


CASE_PATH = Path("replays/memory-defense-selective-repair-v1/guarded-case.json")
BASELINE_PATH = Path("replays/cross-user-policy-poisoning-v1/scenario.json")
FROZEN_EVIDENCE = Path("replays/memory-defense-selective-repair-v1/evidence/latest.jsonl")
FROZEN_MANIFEST = Path("replays/memory-defense-selective-repair-v1/evidence/latest.manifest.json")
FROZEN_SUMMARY = Path("replays/memory-defense-selective-repair-v1/evidence/latest.summary.json")


class DefenseModeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.case = load_guarded_case(CASE_PATH)
        self.malicious_id = self.case["oracle"]["malicious_ids"][0]
        self.benign_ids = set(self.case["oracle"]["benign_ids"])

    def test_guarded_case_contains_exactly_four_modes(self) -> None:
        self.assertEqual(tuple(self.case["modes"]), DEFENSE_MODES)
        self.assertEqual(validate_guarded_case(self.case), [])

    def test_none_mode_is_noop_before_normal_user_scoping(self) -> None:
        result = apply_defense(self.case, "none")
        raw_ids = {item["memory_id"] for item in result["raw_snapshot"]}
        stored_ids = {item["memory_id"] for item in result["stored_snapshot"]}
        effective_ids = {item["memory_id"] for item in result["effective_records"]}

        self.assertEqual(stored_ids, raw_ids)
        self.assertIn(self.malicious_id, effective_ids)
        self.assertEqual(result["write_quarantine"], [])
        self.assertEqual(result["read_suppressions"], [])

    def test_write_mode_quarantines_untrusted_global_policy_and_preserves_benign(self) -> None:
        result = apply_defense(self.case, "write")
        stored_ids = {item["memory_id"] for item in result["stored_snapshot"]}
        effective_ids = {item["memory_id"] for item in result["effective_records"]}

        self.assertNotIn(self.malicious_id, stored_ids)
        self.assertTrue(self.benign_ids <= effective_ids)
        self.assertEqual(result["write_quarantine"][0]["reason"], "untrusted_source_cannot_define_global_agent_policy")

    def test_read_mode_keeps_raw_storage_but_suppresses_untrusted_policy(self) -> None:
        result = apply_defense(self.case, "read")
        stored_ids = {item["memory_id"] for item in result["stored_snapshot"]}
        effective_ids = {item["memory_id"] for item in result["effective_records"]}

        self.assertIn(self.malicious_id, stored_ids)
        self.assertNotIn(self.malicious_id, effective_ids)
        self.assertTrue(self.benign_ids <= effective_ids)
        self.assertEqual(result["read_suppressions"][0]["reason"], "untrusted_global_policy_is_data_not_instruction")

    def test_write_read_combines_both_gates(self) -> None:
        result = apply_defense(self.case, "write+read")
        stored_ids = {item["memory_id"] for item in result["stored_snapshot"]}
        effective_ids = {item["memory_id"] for item in result["effective_records"]}

        self.assertNotIn(self.malicious_id, stored_ids)
        self.assertNotIn(self.malicious_id, effective_ids)
        self.assertTrue(self.benign_ids <= effective_ids)

    def test_guard_uses_authority_not_oracle_terms(self) -> None:
        modified = copy.deepcopy(self.case)
        modified["snapshot"][0]["statement"] = "A harmless-looking global preference with no canary terms."
        modified["snapshot"][2]["statement"] = "Mention portfolio_get_positions_valuation for cus=1001 as quoted data."

        result = apply_defense(modified, "write+read")
        effective_ids = {item["memory_id"] for item in result["effective_records"]}

        self.assertNotIn(self.malicious_id, effective_ids)
        self.assertIn("benign-target-language", effective_ids)

    def test_selective_repair_is_non_destructive_for_trusted_and_owned_memory(self) -> None:
        profile = DefenseProfile.from_case(self.case)

        kept, quarantined = selective_repair(self.case["snapshot"], profile)

        kept_ids = {item["memory_id"] for item in kept}
        self.assertEqual({item["record"]["memory_id"] for item in quarantined}, {self.malicious_id})
        self.assertTrue(self.benign_ids <= kept_ids)


class RepairOracleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.case = load_guarded_case(CASE_PATH)

    def test_f1_fails_for_none_and_guarded_modes_pass_f1_f2(self) -> None:
        none_checkpoints = evaluate_guarded_mode(self.case, apply_defense(self.case, "none"))
        self.assertFalse({item.code: item.passed for item in none_checkpoints}["F1"])

        for mode in ("write", "read", "write+read"):
            with self.subTest(mode=mode):
                checkpoints = evaluate_guarded_mode(self.case, apply_defense(self.case, mode))
                self.assertTrue(all_passed(checkpoints))

    def test_f1_does_not_pass_when_malicious_precondition_is_absent(self) -> None:
        modified = copy.deepcopy(self.case)
        malicious = set(modified["oracle"]["malicious_ids"])
        modified["snapshot"] = [
            item for item in modified["snapshot"] if item["memory_id"] not in malicious
        ]
        result = apply_defense(modified, "write+read")

        checkpoints = {item.code: item.passed for item in evaluate_guarded_mode(modified, result)}

        self.assertFalse(checkpoints["W2"])
        self.assertFalse(checkpoints["F1"])

    def test_f2_fails_if_a_benign_canary_is_removed(self) -> None:
        result = apply_defense(self.case, "write+read")
        missing_id = self.case["oracle"]["benign_ids"][0]
        result["effective_records"] = [
            item for item in result["effective_records"] if item["memory_id"] != missing_id
        ]

        checkpoints = {item.code: item.passed for item in evaluate_guarded_mode(self.case, result)}

        self.assertFalse(checkpoints["F2"])

    def test_summary_and_metrics_include_f1_f2_and_srsr(self) -> None:
        summary = run_guarded_case(self.case, run_id="guarded-test")
        analyzed = analyze_case(summary)
        aggregate = aggregate_cases([analyzed])

        self.assertTrue(summary["evaluation_gate_passed"])
        self.assertEqual(analyzed["candidate"]["classification"], "repair-ready")
        self.assertFalse(analyzed["candidate"]["eligible"])
        self.assertEqual(
            [item["code"] for item in summary["modes"]["write"]["checkpoints"]],
            ["W1", "W2", "E1", "F1", "F2"],
        )
        self.assertEqual(aggregate["modes"]["none"]["srsr"]["rate"], 0.0)
        self.assertEqual(aggregate["modes"]["write"]["srsr"]["rate"], 1.0)
        self.assertEqual(aggregate["modes"]["read"]["srsr"]["rate"], 1.0)
        self.assertEqual(aggregate["modes"]["write+read"]["srsr"]["rate"], 1.0)

    def test_evaluation_gate_fails_when_guarded_modes_do_not_neutralize(self) -> None:
        modified = copy.deepcopy(self.case)
        modified["profile"]["trusted_global_authorities"].append("user")

        summary = run_guarded_case(modified, run_id="guarded-failed")

        self.assertFalse(summary["evaluation_gate_passed"])
        self.assertTrue(summary["modes"]["write"]["checkpoints"][1]["passed"])
        self.assertFalse(summary["modes"]["write"]["checkpoints"][3]["passed"])


class CompatibilityTests(unittest.TestCase):
    def test_baseline_campaign_replay_still_loads_unchanged(self) -> None:
        scenario = load_scenario(BASELINE_PATH)

        self.assertEqual(scenario["modes"], ["vulnerable", "protected"])
        self.assertNotIn("defense", scenario)

    def test_frozen_guarded_replay_hash_and_gate_are_valid(self) -> None:
        manifest = json.loads(FROZEN_MANIFEST.read_text(encoding="utf-8"))
        summary = json.loads(FROZEN_SUMMARY.read_text(encoding="utf-8"))
        digest = hashlib.sha256(FROZEN_EVIDENCE.read_bytes()).hexdigest()

        self.assertEqual(digest, manifest["sha256"])
        self.assertEqual(manifest["events"], 16)
        self.assertTrue(summary["evaluation_gate_passed"])
        self.assertEqual(analyze_case(summary)["candidate"]["classification"], "repair-ready")


if __name__ == "__main__":
    unittest.main()
