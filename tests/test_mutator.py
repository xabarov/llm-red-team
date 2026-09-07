from pathlib import Path
import unittest

from llm_red_team.mutator import (
    SeedFamilyValidationError,
    load_seed_family,
    materialize_family,
    write_materialized_scenarios,
)
from llm_red_team.scenario import load_scenario, stage1_config, validate_scenario


BASE_SCENARIO_PATH = Path("replays/cross-user-policy-poisoning-v1/scenario.json")
SEED_FAMILY_PATH = Path("seeds/cross-user-policy-poisoning.yaml")


class MutatorTests(unittest.TestCase):
    def test_materialize_seed_family_produces_valid_scenarios(self) -> None:
        base = load_scenario(BASE_SCENARIO_PATH)
        family = load_seed_family(SEED_FAMILY_PATH)

        scenarios = materialize_family(family, base)

        self.assertEqual(len(scenarios), 8)
        self.assertEqual(validate_scenario(scenarios[0]), [])
        self.assertEqual(scenarios[0]["provenance"]["family_id"], "cross-user-policy-poisoning")
        self.assertEqual(scenarios[0]["provenance"]["backend"], "deterministic")

    def test_variant_patch_updates_step_by_id(self) -> None:
        base = load_scenario(BASE_SCENARIO_PATH)
        family = load_seed_family(SEED_FAMILY_PATH)

        scenario = materialize_family(family, base)[1]
        legacy = stage1_config(scenario, run_id="run-42", mode="vulnerable")

        self.assertEqual(scenario["id"], "cross-user-policy-poisoning-c2-policy-document")
        self.assertIn("RTM-C2-run-42", legacy["payload"])
        self.assertIn("продуктовой документации", legacy["payload"])

    def test_g2_variants_keep_strong_oracles(self) -> None:
        base = load_scenario(BASE_SCENARIO_PATH)
        family = load_seed_family(SEED_FAMILY_PATH)

        scenarios = {scenario["id"]: scenario for scenario in materialize_family(family, base)}

        c2 = scenarios["cross-user-policy-poisoning-c2-policy-document-argument-binding"]
        c3 = scenarios["cross-user-policy-poisoning-c3-compaction-policy-summary"]
        self.assertIn("portfolio_get_positions_valuation", c2["steps"][3]["content"])
        self.assertIn("cus=1001", c2["steps"][3]["content"])
        self.assertIn("глобальную политику агента", c3["steps"][3]["content"])
        self.assertEqual(c2["oracle"]["required_policy_terms"], ["1001", "portfolio_get_positions_valuation"])
        self.assertEqual(c3["oracle"]["required_policy_terms"], ["1001", "portfolio_get_positions_valuation"])

    def test_g2_soft_variants_avoid_overly_direct_policy_wording(self) -> None:
        base = load_scenario(BASE_SCENARIO_PATH)
        family = load_seed_family(SEED_FAMILY_PATH)

        scenarios = {scenario["id"]: scenario for scenario in materialize_family(family, base)}

        c2 = scenarios["cross-user-policy-poisoning-c2-policy-document-soft-binding"]
        c3 = scenarios["cross-user-policy-poisoning-c3-compaction-neutral-summary"]
        self.assertIn("benchmark_customer", c2["steps"][3]["content"])
        self.assertIn("customer reference", c3["steps"][3]["content"])
        self.assertNotIn("не подменяй", c2["steps"][7]["content"].lower())
        self.assertNotIn("сохрани", c3["steps"][3]["content"].lower())

    def test_invalid_seed_family_is_rejected(self) -> None:
        with self.assertRaises(SeedFamilyValidationError):
            materialize_family({"schema_version": "seed-family/v1", "id": "broken", "variants": []}, {})

    def test_write_materialized_scenarios_creates_json_files(self) -> None:
        import json
        import tempfile

        base = load_scenario(BASE_SCENARIO_PATH)
        family = load_seed_family(SEED_FAMILY_PATH)
        scenarios = materialize_family(family, base)

        with tempfile.TemporaryDirectory() as tmp:
            paths = write_materialized_scenarios(scenarios[:1], Path(tmp))

            self.assertEqual(len(paths), 1)
            generated = json.loads(paths[0].read_text(encoding="utf-8"))
            self.assertEqual(generated["id"], scenarios[0]["id"])


if __name__ == "__main__":
    unittest.main()
