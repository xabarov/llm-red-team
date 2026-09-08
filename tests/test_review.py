from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from llm_red_team.evaluation import EvaluationError, file_hash
from llm_red_team.review import aggregate_reviews, build_review_bundle, load_rubric


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "evaluation/historical-execution-manifest.json"
RUBRIC = ROOT / "evaluation/judge-rubric.yaml"


def _filled(template: dict, reviewer: str, *, suspiciousness: int = 1) -> dict:
    value = copy.deepcopy(template)
    value["reviewer_id"] = reviewer
    for verdict in value["verdicts"]:
        verdict["task_coherence"] = 2
        verdict["suspiciousness"] = suspiciousness
        verdict["evidence_sufficient"] = True
    return value


class ReviewBundleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        cls.rubric = load_rubric(RUBRIC)
        cls.packet, cls.key, cls.template = build_review_bundle(
            cls.manifest,
            cls.rubric,
            rubric_sha256=file_hash(RUBRIC),
            repo_root=ROOT,
        )

    def test_packet_contains_all_mode_cells_without_blind_metadata(self) -> None:
        self.assertEqual(len(self.packet["items"]), 6)
        self.assertEqual(len(self.key["items"]), 6)
        for item in self.packet["items"]:
            self.assertEqual(
                set(item),
                {"review_id", "injection_prompt", "trigger_prompt", "response_content"},
            )
            self.assertTrue(item["review_id"].startswith("REV-"))
        self.assertEqual(
            {item["review_id"] for item in self.packet["items"]},
            {item["review_id"] for item in self.key["items"]},
        )

    def test_two_agreeing_reviews_produce_hashed_breakdowns(self) -> None:
        report = aggregate_reviews(
            self.packet,
            self.key,
            [_filled(self.template, "reviewer-a"), _filled(self.template, "reviewer-b")],
        )
        self.assertEqual(len(report["adjudicated"]), 6)
        self.assertEqual(report["by_model_and_auth_mode"][0]["stealth_proxy"]["rate"], 1.0)
        self.assertEqual(len(report["report_sha256"]), 64)

    def test_disagreement_requires_third_reviewer(self) -> None:
        first = _filled(self.template, "reviewer-a", suspiciousness=0)
        second = _filled(self.template, "reviewer-b", suspiciousness=2)
        with self.assertRaisesRegex(EvaluationError, "third review required"):
            aggregate_reviews(self.packet, self.key, [first, second])

        third = _filled(self.template, "reviewer-c", suspiciousness=2)
        report = aggregate_reviews(self.packet, self.key, [first, second, third])
        self.assertEqual(report["adjudicated"][0]["suspiciousness"], 2)

    def test_unfilled_template_is_rejected(self) -> None:
        with self.assertRaisesRegex(EvaluationError, "reviewer_id must be filled"):
            aggregate_reviews(
                self.packet,
                self.key,
                [self.template, _filled(self.template, "reviewer-b")],
            )

    def test_private_key_is_bound_before_review(self) -> None:
        key = copy.deepcopy(self.key)
        key["items"][0]["auth_mode"] = "tampered"
        with self.assertRaisesRegex(EvaluationError, "blind commitment"):
            aggregate_reviews(
                self.packet,
                key,
                [_filled(self.template, "reviewer-a"), _filled(self.template, "reviewer-b")],
            )

    def test_boolean_is_not_an_ordinal_score(self) -> None:
        first = _filled(self.template, "reviewer-a")
        first["verdicts"][0]["task_coherence"] = True
        with self.assertRaisesRegex(EvaluationError, "task_coherence"):
            aggregate_reviews(
                self.packet,
                self.key,
                [first, _filled(self.template, "reviewer-b")],
            )


if __name__ == "__main__":
    unittest.main()
