from __future__ import annotations

import json
import unittest
from pathlib import Path

from llm_red_team.evaluation import build_reconstruction
from llm_red_team.evaluation_report import (
    build_combined_report,
    build_defense_section,
    render_combined_markdown,
)


ROOT = Path(__file__).resolve().parents[1]


class CombinedEvaluationReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        execution = json.loads(
            (ROOT / "evaluation/historical-execution-manifest.json").read_text(encoding="utf-8")
        )
        cls.reconstruction = build_reconstruction(execution, repo_root=ROOT)
        evidence_dir = ROOT / "replays/memory-defense-selective-repair-v1/evidence"
        cls.defense = build_defense_section(
            summary_path=evidence_dir / "latest.summary.json",
            evidence_path=evidence_dir / "latest.jsonl",
            manifest_path=evidence_dir / "latest.manifest.json",
        )

    def test_frozen_defense_is_verified_and_remains_separate(self) -> None:
        self.assertEqual(self.defense["classification"], "repair-ready")
        self.assertFalse(self.defense["modes"]["none"]["F1"])
        self.assertTrue(self.defense["modes"]["write+read"]["F1"])
        self.assertTrue(self.defense["modes"]["write+read"]["F2"])

    def test_combined_report_marks_uncollected_review_and_is_hashed(self) -> None:
        report = build_combined_report(self.reconstruction, self.defense)
        self.assertEqual(report["manual_review"]["status"], "not-collected")
        self.assertIn("separate evaluation tracks", report["separation_invariant"])
        self.assertEqual(len(report["report_sha256"]), 64)
        markdown = render_combined_markdown(report)
        self.assertIn("Offline memory defense", markdown)
        self.assertIn("not live IAM ASR", markdown)


if __name__ == "__main__":
    unittest.main()
