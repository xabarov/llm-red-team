import json
from pathlib import Path
import unittest

from llm_red_team.mutator import load_seed_family
from llm_red_team.planner import (
    build_seed_family_prompt,
    normalize_openrouter_model,
    parse_planner_seed_family,
    read_dotenv_value,
)
from llm_red_team.scenario import load_scenario


BASE_SCENARIO_PATH = Path("replays/cross-user-policy-poisoning-v1/scenario.json")
SEED_FAMILY_PATH = Path("seeds/cross-user-policy-poisoning.yaml")


class PlannerTests(unittest.TestCase):
    def test_build_seed_family_prompt_mentions_contract(self) -> None:
        prompt = build_seed_family_prompt(
            base_scenario=load_scenario(BASE_SCENARIO_PATH),
            reference_family=load_seed_family(SEED_FAMILY_PATH),
            categories=["C1", "C2"],
            variants_per_category=1,
        )

        self.assertIn("seed-family/v1", prompt)
        self.assertIn("Return exactly one JSON object", prompt)
        self.assertIn("C1, C2", prompt)

    def test_parse_planner_seed_family_adds_openrouter_provenance(self) -> None:
        content = json.dumps(
            {
                "schema_version": "seed-family/v1",
                "id": "planned-family",
                "base_scenario": "replays/cross-user-policy-poisoning-v1/scenario.json",
                "variants": [
                    {
                        "id": "c1-doc",
                        "patches": [
                            {"path": ["steps", "inject.policy", "content"], "value": "payload"},
                        ],
                    }
                ],
            }
        )

        family = parse_planner_seed_family(content, model="openai:openai/gpt-4.1-mini")

        self.assertEqual(family["provenance"]["kind"], "llm_mutator")
        self.assertEqual(family["provenance"]["model"], "openai/gpt-4.1-mini")
        self.assertEqual(len(family["provenance"]["source_hash"]), 64)

    def test_normalize_openrouter_model_strips_langchain_prefix(self) -> None:
        self.assertEqual(normalize_openrouter_model("openai:openai/gpt-4.1-mini"), "openai/gpt-4.1-mini")

    def test_read_dotenv_value_without_leaking_other_values(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".env"
            path.write_text("OPENROUTER_API_KEY='secret-value'\nOTHER=value\n", encoding="utf-8")

            self.assertEqual(read_dotenv_value(path, "OPENROUTER_API_KEY"), "secret-value")


if __name__ == "__main__":
    unittest.main()
