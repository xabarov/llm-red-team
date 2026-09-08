#!/usr/bin/env python3
"""Budget-gated orchestrator for the approved G5 OpenRouter matrix."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from llm_red_team.evaluation import (
    EvaluationError,
    assert_execution_approved,
    build_plan,
    file_hash,
    load_matrix,
    render_plan_markdown,
    verify_inputs,
)


def _safe_slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _session_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"eval-{stamp}-{uuid.uuid4().hex[:8]}"


def _artifact(repo_root: Path, run_id: str, model: str, repeat: int, scenario: dict[str, Any]) -> dict[str, Any]:
    base = Path("output/runs") / run_id / scenario["id"]
    paths = {
        "summary": base / "summary.json",
        "evidence": base / "evidence.jsonl",
        "evidence_manifest": base / "manifest.json",
    }
    for name, relative in paths.items():
        if not (repo_root / relative).is_file():
            raise EvaluationError(f"campaign did not produce {name}: {relative}")
    summary = json.loads((repo_root / paths["summary"]).read_text(encoding="utf-8"))
    if summary.get("scenario_id") != scenario["id"]:
        raise EvaluationError(f"unexpected scenario id in {paths['summary']}")
    return {
        "run_id": run_id,
        "model": model,
        "research_model": scenario["runtime_model"],
        "summarization_model": scenario["runtime_model"],
        "repeat_index": repeat,
        "scenario_id": scenario["id"],
        "attack_class": scenario["attack_class"],
        "carrier": scenario["carrier"],
        "maturity": scenario["maturity"],
        "scenario_path": scenario["path"],
        "scenario_sha256": scenario["sha256"],
        **{f"{name}_path": str(path) for name, path in paths.items()},
        **{f"{name}_sha256": file_hash(repo_root / path) for name, path in paths.items()},
    }


def _write_manifest(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Dry-run by default. Live OpenRouter execution requires matrix approval and an exact plan hash."
    )
    parser.add_argument("--matrix", type=Path, default=Path("evaluation/matrix.yaml"))
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--approve-plan-sha256", default="")
    parser.add_argument("--session-id", default=None)
    args = parser.parse_args()
    repo_root = Path.cwd()
    try:
        matrix = load_matrix(args.matrix)
        verify_inputs(matrix, repo_root=repo_root)
        plan = build_plan(matrix, repo_root=repo_root)
        if not args.execute:
            print(render_plan_markdown(plan), end="")
            print("Dry-run only. No stand or provider calls were made.")
            return 0
        assert_execution_approved(matrix, plan, args.approve_plan_sha256)
    except EvaluationError as exc:
        parser.error(str(exc))

    session_id = args.session_id or _session_id()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", session_id):
        parser.error("session id must contain only letters, digits, dot, underscore, or dash")
    session_dir = repo_root / "output/evaluations" / session_id
    if session_dir.exists():
        parser.error(f"evaluation session already exists: {session_dir}")
    matrix_snapshot = session_dir / f"matrix{args.matrix.suffix or '.yaml'}"
    matrix_snapshot.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(args.matrix, matrix_snapshot)
    manifest: dict[str, Any] = {
        "schema_version": "evaluation-execution/v1",
        "manifest_kind": "live-matrix",
        "matrix_id": matrix["id"],
        "matrix_path": str(matrix_snapshot.relative_to(repo_root)),
        "matrix_file_sha256": file_hash(matrix_snapshot),
        "matrix_content_sha256": plan["matrix_sha256"],
        "plan_sha256": plan["plan_sha256"],
        "stand_revision": matrix["stand_revision"],
        "session_id": session_id,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "expected_modes": matrix["live"]["modes"],
        "expected_artifacts": [
            {
                "model": model["id"],
                "scenario_id": scenario["id"],
                "repeat_index": repeat,
            }
            for model in matrix["live"]["models"]
            for scenario in matrix["live"]["scenarios"]
            for repeat in range(1, matrix["live"]["repeats"] + 1)
        ],
        "artifacts": [],
    }
    manifest_path = session_dir / "execution-manifest.json"
    _write_manifest(manifest_path, manifest)
    scenarios = matrix["live"]["scenarios"]
    scenario_args = [item for scenario in scenarios for item in ("--scenario", scenario["path"])]
    had_failed_gate = False
    started = time.monotonic()
    wall_limit = matrix["live"]["budget"]["maximum_wall_time_seconds"]

    for model in matrix["live"]["models"]:
        env = os.environ.copy()
        env["OPENROUTER_RESEARCH_MODEL"] = model["runtime_model"]
        env["OPENROUTER_SUMMARIZATION_MODEL"] = model["runtime_model"]
        subprocess.run(["bash", "scripts/stand.sh", "up", "openrouter"], cwd=repo_root, env=env, check=True)
        for repeat in range(1, matrix["live"]["repeats"] + 1):
            remaining = wall_limit - (time.monotonic() - started)
            if remaining <= 0:
                raise SystemExit(f"evaluation exceeded maximum_wall_time_seconds={wall_limit}")
            run_id = f"{session_id}-{_safe_slug(model['id'])}-r{repeat}"
            command = [
                sys.executable,
                "scripts/run-campaign.py",
                "--run-id",
                run_id,
                *scenario_args,
            ]
            try:
                completed = subprocess.run(
                    command,
                    cwd=repo_root,
                    env={**env, "PYTHONPATH": "src"},
                    check=False,
                    timeout=remaining,
                )
            except subprocess.TimeoutExpired as exc:
                raise SystemExit(f"evaluation exceeded maximum_wall_time_seconds={wall_limit}") from exc
            if completed.returncode not in {0, 1}:
                raise SystemExit(completed.returncode)
            had_failed_gate = had_failed_gate or completed.returncode == 1
            for scenario in scenarios:
                artifact_scenario = {**scenario, "runtime_model": model["runtime_model"]}
                manifest["artifacts"].append(
                    _artifact(repo_root, run_id, model["id"], repeat, artifact_scenario)
                )
            _write_manifest(manifest_path, manifest)

    manifest["completed_at"] = datetime.now(timezone.utc).isoformat()
    manifest["result"] = "completed-with-failed-gates" if had_failed_gate else "completed"
    _write_manifest(manifest_path, manifest)
    print(f"Execution manifest: {manifest_path.relative_to(repo_root)}")
    return 1 if had_failed_gate else 0


if __name__ == "__main__":
    raise SystemExit(main())
