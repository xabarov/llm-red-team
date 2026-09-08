from __future__ import annotations

import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from llm_red_team.evaluation import (
    EvaluationError,
    assert_execution_approved,
    build_plan,
    build_reconstruction,
    file_hash,
    load_matrix,
    verify_inputs,
)


ROOT = Path(__file__).resolve().parents[1]
INPUT_PATH_MAP = json.loads((ROOT / "evaluation/input-path-map.json").read_text(encoding="utf-8"))


class EvaluationPlanTests(unittest.TestCase):
    def test_core_plan_is_deterministic_and_budget_is_estimated(self) -> None:
        matrix = load_matrix(ROOT / "evaluation/matrix.yaml", schema_path=ROOT / "schemas/evaluation-matrix.schema.json")
        verify_inputs(matrix, repo_root=ROOT, path_map=INPUT_PATH_MAP)
        first = build_plan(matrix, repo_root=ROOT, path_map=INPUT_PATH_MAP)
        second = build_plan(matrix, repo_root=ROOT, path_map=INPUT_PATH_MAP)

        self.assertEqual(first["plan_sha256"], second["plan_sha256"])
        self.assertEqual(first["live"]["scenario_runs"], 18)
        self.assertEqual(first["live"]["mode_cells"], 36)
        self.assertEqual(first["live"]["totals"]["expected_attempts"], 84)
        self.assertEqual(first["live"]["totals"]["maximum_attempts"], 108)
        self.assertEqual(first["live"]["totals"]["expected_llm_calls"], 504)
        self.assertEqual(first["live"]["totals"]["maximum_llm_calls"], 1836)
        self.assertEqual(first["live"]["totals"]["expected_duration_seconds"], 1472.19)
        self.assertEqual(first["offline"]["mode_cells"], 4)
        self.assertEqual(
            {cell["defense_mode"] for cell in first["offline"]["cells"]},
            {"none", "write", "read", "write+read"},
        )
        self.assertEqual(first["live"]["telemetry_status"]["cost"], "estimated from pricing snapshot; not measured")

    def test_proposed_matrix_cannot_execute(self) -> None:
        matrix = load_matrix(ROOT / "evaluation/matrix.yaml", schema_path=ROOT / "schemas/evaluation-matrix.schema.json")
        matrix = copy.deepcopy(matrix)
        matrix["status"] = "proposed"
        matrix["live"]["budget"]["approved"] = False
        matrix["live"]["budget"]["hard_cap_usd"] = None
        plan = build_plan(matrix, repo_root=ROOT, path_map=INPUT_PATH_MAP)
        with self.assertRaisesRegex(EvaluationError, "not approved"):
            assert_execution_approved(matrix, plan, plan["plan_sha256"])

    def test_approved_matrix_still_respects_conservative_cap(self) -> None:
        matrix = load_matrix(ROOT / "evaluation/matrix.yaml", schema_path=ROOT / "schemas/evaluation-matrix.schema.json")
        matrix = copy.deepcopy(matrix)
        matrix["status"] = "approved"
        matrix["live"]["budget"]["approved"] = True
        matrix["live"]["budget"]["hard_cap_usd"] = 1.0
        plan = build_plan(matrix, repo_root=ROOT, path_map=INPUT_PATH_MAP)
        with self.assertRaisesRegex(EvaluationError, "exceeds hard cap"):
            assert_execution_approved(matrix, plan, plan["plan_sha256"])

    def test_changed_input_is_rejected(self) -> None:
        matrix = load_matrix(ROOT / "evaluation/matrix.yaml", schema_path=ROOT / "schemas/evaluation-matrix.schema.json")
        matrix["live"]["scenarios"][0]["sha256"] = "0" * 64
        with self.assertRaisesRegex(EvaluationError, "hash mismatch"):
            verify_inputs(matrix, repo_root=ROOT, path_map=INPUT_PATH_MAP)


class ReconstructionTests(unittest.TestCase):
    def _fixture(self, root: Path) -> tuple[dict, Path]:
        case_dir = root / "run" / "case"
        case_dir.mkdir(parents=True)
        events = [
            {"id": "EVT-0000", "run_id": "run", "scenario_id": "case", "kind": "target.ready", "data": {"runtime": {"stand_revision": "b" * 40, "stand_env": {"research_model": "runtime:model-a", "summarization_model": "runtime:model-a"}}}},
            {"id": "EVT-0001", "run_id": "run", "scenario_id": "case", "kind": "oracle.checkpoints"},
            {"id": "EVT-0002", "run_id": "run", "scenario_id": "case", "kind": "oracle.checkpoints"},
        ]
        evidence = case_dir / "evidence.jsonl"
        evidence.write_text("".join(json.dumps(item) + "\n" for item in events), encoding="utf-8")
        evidence_digest = file_hash(evidence)
        evidence_manifest = case_dir / "manifest.json"
        evidence_manifest.write_text(
            json.dumps({"run_id": "run", "scenario_id": "case", "sha256": evidence_digest, "events": len(events)}),
            encoding="utf-8",
        )

        def mode(event_id: str) -> dict:
            checkpoints = [
                {"code": code, "passed": True, "detail": "ok", "evidence_ids": [event_id]}
                for code in ("W1", "W2", "E1", "E2", "E3")
            ]
            return {
                "outcome": "passed",
                "passed": True,
                "attempts_used": 1,
                "selected_attempt": 1,
                "checkpoints": checkpoints,
                "attempts": [{"attempt": 1, "outcome": "passed", "passed": True, "checkpoints": checkpoints}],
            }

        summary = case_dir / "summary.json"
        summary.write_text(
            json.dumps({"scenario_id": "case", "run_id": "run", "modes": {"vulnerable": mode("EVT-0001"), "protected": mode("EVT-0002")}}),
            encoding="utf-8",
        )
        artifact = {
            "run_id": "run",
            "model": "model-a",
            "research_model": "runtime:model-a",
            "summarization_model": "runtime:model-a",
            "repeat_index": 1,
            "scenario_id": "case",
            "attack_class": "C1",
            "carrier": "direct",
            "maturity": "replay-ready",
            "scenario_path": "scenario.json",
            "scenario_sha256": "",
            "summary_path": str(summary.relative_to(root)),
            "summary_sha256": file_hash(summary),
            "evidence_path": str(evidence.relative_to(root)),
            "evidence_sha256": evidence_digest,
            "evidence_manifest_path": str(evidence_manifest.relative_to(root)),
            "evidence_manifest_sha256": file_hash(evidence_manifest),
        }
        scenario_path = root / "scenario.json"
        scenario_path.write_text("{}", encoding="utf-8")
        artifact["scenario_sha256"] = file_hash(scenario_path)
        manifest = {
            "schema_version": "evaluation-execution/v1",
            "manifest_kind": "historical-calibration",
            "matrix_id": "matrix",
            "plan_sha256": "a" * 64,
            "stand_revision": "b" * 40,
            "session_id": "fixture",
            "expected_modes": ["vulnerable", "protected"],
            "expected_artifacts": [{"model": "model-a", "scenario_id": "case", "repeat_index": 1}],
            "artifacts": [artifact],
        }
        return manifest, evidence

    def test_aggregate_is_reconstructed_from_bound_sources(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manifest, _ = self._fixture(Path(directory))
            report = build_reconstruction(manifest, repo_root=Path(directory))
            self.assertEqual(report["aggregate"]["cases"], 1)
            self.assertEqual(report["aggregate"]["modes"]["vulnerable"]["e2e_asr"]["rate"], 1.0)
            by_model = report["matrix_aggregate"]["by_model_and_auth_mode"]
            self.assertEqual(len(by_model), 2)
            self.assertEqual(by_model[0]["e2e_gate_rate"]["ci95"][1], 1.0)
            self.assertEqual(len(report["aggregate_sha256"]), 64)

    def test_tampered_evidence_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest, evidence = self._fixture(root)
            evidence.write_text(evidence.read_text(encoding="utf-8") + "{}\n", encoding="utf-8")
            with self.assertRaisesRegex(EvaluationError, "evidence hash mismatch"):
                build_reconstruction(manifest, repo_root=root)

    def test_missing_expected_artifact_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest, _ = self._fixture(root)
            manifest["expected_artifacts"].append({"model": "model-b", "scenario_id": "case", "repeat_index": 1})
            with self.assertRaisesRegex(EvaluationError, "incomplete"):
                build_reconstruction(manifest, repo_root=root)

    def test_artifact_path_cannot_escape_repository(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest, _ = self._fixture(root)
            manifest["artifacts"][0]["summary_path"] = "../summary.json"
            with self.assertRaisesRegex(EvaluationError, "escapes repository"):
                build_reconstruction(manifest, repo_root=root)

    def test_frozen_path_map_reconstructs_after_sources_move(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest, _ = self._fixture(root)
            frozen = root / "frozen"
            shutil.copytree(root / "run", frozen / "run")
            shutil.copy2(root / "scenario.json", frozen / "scenario.json")
            path_map = {"scenario.json": "frozen/scenario.json"}
            for name in ("summary_path", "evidence_path", "evidence_manifest_path"):
                logical = manifest["artifacts"][0][name]
                path_map[logical] = str(Path("frozen") / logical)
            manifest["path_map"] = path_map
            shutil.rmtree(root / "run")
            (root / "scenario.json").unlink()

            report = build_reconstruction(manifest, repo_root=root)

            self.assertEqual(report["aggregate"]["cases"], 1)

    def test_frozen_source_manifest_hash_is_verified(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest, _ = self._fixture(root)
            source = root / "source-manifest.json"
            source.write_text("{}\n", encoding="utf-8")
            manifest.update(
                {
                    "frozen_at": "2026-09-08T00:00:00+00:00",
                    "source_manifest_path": "source-manifest.json",
                    "source_manifest_sha256": "0" * 64,
                    "path_map": {},
                }
            )
            with self.assertRaisesRegex(EvaluationError, "source manifest hash mismatch"):
                build_reconstruction(manifest, repo_root=root)

    def test_summarization_model_mismatch_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest, _ = self._fixture(root)
            manifest["artifacts"][0]["summarization_model"] = "runtime:other"
            with self.assertRaisesRegex(EvaluationError, "summarization model mismatch"):
                build_reconstruction(manifest, repo_root=root)

    def test_live_manifest_dimension_metadata_is_bound_to_plan(self) -> None:
        manifest = json.loads(
            (
                ROOT
                / "evaluation/results/g5-20260908-full-v2/execution-manifest.json"
            ).read_text(encoding="utf-8")
        )
        manifest["artifacts"][0]["attack_class"] = "C4"

        with self.assertRaisesRegex(EvaluationError, "attack_class does not match matrix plan"):
            build_reconstruction(manifest, repo_root=ROOT)

    def test_live_manifest_must_match_bound_matrix_plan(self) -> None:
        manifest = json.loads(
            (ROOT / "evaluation/historical-execution-manifest.json").read_text(encoding="utf-8")
        )
        matrix = load_matrix(
            ROOT / "evaluation/matrix.yaml",
            schema_path=ROOT / "schemas/evaluation-matrix.schema.json",
        )
        plan = build_plan(matrix, repo_root=ROOT, path_map=INPUT_PATH_MAP)
        manifest.update(
            {
                "manifest_kind": "live-matrix",
                "matrix_id": matrix["id"],
                "matrix_path": "evaluation/matrix.yaml",
                "matrix_file_sha256": file_hash(ROOT / "evaluation/matrix.yaml"),
                "matrix_content_sha256": plan["matrix_sha256"],
                "plan_sha256": plan["plan_sha256"],
            }
        )
        with self.assertRaisesRegex(EvaluationError, "expected artifacts do not match"):
            build_reconstruction(manifest, repo_root=ROOT)


if __name__ == "__main__":
    unittest.main()
