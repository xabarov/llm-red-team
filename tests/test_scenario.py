import unittest
from pathlib import Path

from llm_red_team.scenario import (
    ScenarioValidationError,
    load_scenario,
    render_scenario,
    stage1_config,
    validate_scenario,
)


SCENARIO_PATH = Path("replays/cross-user-policy-poisoning-v1/scenario.json")


class ScenarioTests(unittest.TestCase):
    def test_replay_scenario_is_valid(self) -> None:
        scenario = load_scenario(SCENARIO_PATH)

        self.assertEqual(scenario["id"], "cross-user-policy-poisoning-v1")
        self.assertEqual(validate_scenario(scenario), [])

    def test_render_scenario_replaces_actor_and_run_variables(self) -> None:
        scenario = load_scenario(SCENARIO_PATH)

        rendered = render_scenario(scenario, run_id="run-123", mode="protected")

        self.assertEqual(rendered["sessions"]["inject"], "run-123-protected-inject")
        self.assertEqual(rendered["oracle"]["target_actor"], "1002")
        self.assertIn("RTM-CROSS-USER-001", rendered["steps"][3]["content"])

    def test_stage1_config_extracts_legacy_fields(self) -> None:
        scenario = load_scenario(SCENARIO_PATH)

        legacy = stage1_config(scenario, run_id="run-123", mode="vulnerable")

        self.assertEqual(legacy["source_actor"], "1001")
        self.assertEqual(legacy["target_actor"], "1002")
        self.assertEqual(legacy["foreign_cus"], "1001")
        self.assertEqual(legacy["expected_service_path"], "/clients/1001")
        self.assertIn("portfolio_get_positions_valuation", legacy["payload"])

    def test_semantic_validation_rejects_late_since_step_reference(self) -> None:
        scenario = load_scenario(SCENARIO_PATH)
        scenario["steps"][8]["since_step"] = "cleanup.reset"

        errors = validate_scenario(scenario)

        self.assertTrue(any("since_step" in error for error in errors))

    def test_load_scenario_rejects_unknown_extension(self) -> None:
        with self.assertRaises(ScenarioValidationError):
            load_scenario(Path("scenario.txt"))


if __name__ == "__main__":
    unittest.main()
