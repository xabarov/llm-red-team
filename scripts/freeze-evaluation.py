#!/usr/bin/env python3
"""Freeze a verified live evaluation into a repository-portable evidence bundle."""

from __future__ import annotations

import argparse
import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from llm_red_team.evaluation import (
    EvaluationError,
    build_reconstruction,
    file_hash,
    load_matrix,
    mapped_repo_path,
    repo_path,
)


def _read(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise EvaluationError(f"expected object in {path}")
    return value


def _write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify and freeze a live G5 manifest without model or stand calls."
    )
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    repo_root = Path.cwd().resolve()
    try:
        source_manifest_path = repo_path(repo_root, str(args.manifest))
        destination = repo_path(repo_root, str(args.output_dir))
        if destination.exists():
            raise EvaluationError(f"destination already exists: {args.output_dir}")
        manifest = _read(source_manifest_path)
        if manifest.get("manifest_kind") != "live-matrix":
            raise EvaluationError("only a live-matrix manifest can be frozen")
        build_reconstruction(manifest, repo_root=repo_root)
        source_path_map = manifest.get("path_map", {})

        stage = destination.parent / f".{destination.name}.tmp-{uuid.uuid4().hex[:8]}"
        stage.mkdir(parents=True)
        destination_rel = destination.relative_to(repo_root)
        stage_rel = stage.relative_to(repo_root)
        path_map: dict[str, str] = {}

        def copy(logical: str, final_relative: Path) -> None:
            logical_source = mapped_repo_path(repo_root, logical, source_path_map)
            final_target = destination_rel / final_relative
            staged_target = stage_rel / final_relative
            if logical in path_map:
                if path_map[logical] != str(final_target):
                    raise EvaluationError(f"conflicting frozen target for {logical}")
                return
            target = repo_path(repo_root, str(staged_target))
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(logical_source, target)
            if file_hash(logical_source) != file_hash(target):
                raise EvaluationError(f"copy hash mismatch: {logical}")
            path_map[logical] = str(final_target)

        matrix = load_matrix(
            mapped_repo_path(repo_root, manifest["matrix_path"], source_path_map)
        )
        copy(manifest["matrix_path"], Path("inputs/matrix.yaml"))
        copy("infra/stand.lock", Path("inputs/stand.lock"))
        for scenario in matrix["live"]["scenarios"]:
            scenario_suffix = Path(scenario["path"]).suffix or ".json"
            copy(scenario["path"], Path("inputs/scenarios") / f"{scenario['id']}{scenario_suffix}")
            calibration = scenario["calibration"]
            calibration_dir = Path("inputs/calibration") / scenario["id"]
            copy(calibration["summary_path"], calibration_dir / "summary.json")
            copy(calibration["evidence_path"], calibration_dir / "evidence.jsonl")
        rubric = matrix["live"]["reporting"]["manual_review_rubric"]
        copy(rubric, Path("inputs/review") / Path(rubric).name)
        copy(matrix["offline"]["case_path"], Path("inputs/offline") / "guarded-case.json")

        for artifact in manifest["artifacts"]:
            artifact_dir = Path("runs") / artifact["run_id"] / artifact["scenario_id"]
            copy(artifact["summary_path"], artifact_dir / "summary.json")
            copy(artifact["evidence_path"], artifact_dir / "evidence.jsonl")
            copy(artifact["evidence_manifest_path"], artifact_dir / "manifest.json")

        staged_source_manifest = stage / "source-execution-manifest.json"
        shutil.copy2(source_manifest_path, staged_source_manifest)
        frozen = {
            **manifest,
            "frozen_at": datetime.now(timezone.utc).isoformat(),
            "source_manifest_path": str(destination_rel / "source-execution-manifest.json"),
            "source_manifest_sha256": file_hash(staged_source_manifest),
            "path_map": dict(sorted(path_map.items())),
        }
        _write(stage / "execution-manifest.json", frozen)
        stage.rename(destination)
        build_reconstruction(frozen, repo_root=repo_root)
    except (OSError, json.JSONDecodeError, EvaluationError) as exc:
        parser.error(str(exc))

    print(f"Frozen execution manifest: {destination_rel / 'execution-manifest.json'}")
    print(f"Frozen paths: {len(frozen['path_map'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
