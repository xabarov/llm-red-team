"""Reproducible G5 matrix planning, budget gating, and evidence reconstruction."""

from __future__ import annotations

import hashlib
import json
import math
import statistics
from datetime import datetime
from pathlib import Path
from typing import Any

import jsonschema
import yaml

from llm_red_team.metrics import aggregate_cases, analyze_case


class EvaluationError(ValueError):
    """Raised when a matrix or its evidence cannot be trusted."""


def canonical_hash(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def repo_path(repo_root: Path, relative: str) -> Path:
    candidate = Path(relative)
    if candidate.is_absolute():
        raise EvaluationError(f"expected repository-relative path: {relative}")
    root = repo_root.resolve()
    resolved = (root / candidate).resolve()
    if not resolved.is_relative_to(root):
        raise EvaluationError(f"path escapes repository root: {relative}")
    return resolved


def mapped_repo_path(
    repo_root: Path,
    relative: str,
    path_map: dict[str, str] | None = None,
) -> Path:
    """Resolve a logical repository path, optionally through a frozen-artifact map."""
    repo_path(repo_root, relative)  # Validate the logical path even when it is remapped.
    mapped = (path_map or {}).get(relative, relative)
    return repo_path(repo_root, mapped)


def load_path_map(path: Path) -> dict[str, str]:
    """Load a repository path-alias map used for immutable archived inputs."""
    value = _read_object(path)
    if not all(isinstance(key, str) and isinstance(target, str) for key, target in value.items()):
        raise EvaluationError(f"path map must contain only string pairs: {path}")
    return value


def _read_object(path: Path) -> dict[str, Any]:
    try:
        if path.suffix in {".yaml", ".yml"}:
            value = yaml.safe_load(path.read_text(encoding="utf-8"))
        else:
            value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, yaml.YAMLError) as exc:
        raise EvaluationError(f"cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise EvaluationError(f"expected object in {path}")
    return value


def load_matrix(path: Path, *, schema_path: Path = Path("schemas/evaluation-matrix.schema.json")) -> dict[str, Any]:
    matrix = _read_object(path)
    schema = _read_object(schema_path)
    try:
        jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker()).validate(matrix)
    except jsonschema.ValidationError as exc:
        location = ".".join(str(item) for item in exc.absolute_path) or "$"
        raise EvaluationError(f"invalid matrix at {location}: {exc.message}") from exc

    model_ids = [item["id"] for item in matrix["live"]["models"]]
    scenario_ids = [item["id"] for item in matrix["live"]["scenarios"]]
    if len(model_ids) != len(set(model_ids)):
        raise EvaluationError("live model ids must be unique")
    if len(scenario_ids) != len(set(scenario_ids)):
        raise EvaluationError("live scenario ids must be unique")
    assumptions = matrix["live"]["assumptions"]
    for metric in ("llm_calls_per_attempt", "input_tokens_per_call", "output_tokens_per_call"):
        if assumptions[f"maximum_{metric}"] < assumptions[f"expected_{metric}"]:
            raise EvaluationError(f"maximum_{metric} must be >= expected_{metric}")
    return matrix


def verify_inputs(
    matrix: dict[str, Any],
    *,
    repo_root: Path,
    path_map: dict[str, str] | None = None,
) -> None:
    expected_revision = matrix["stand_revision"]
    lock = mapped_repo_path(repo_root, "infra/stand.lock", path_map).read_text(encoding="utf-8")
    if f"STAND_REVISION={expected_revision}" not in lock and f'STAND_REVISION="{expected_revision}"' not in lock:
        raise EvaluationError("matrix stand_revision differs from infra/stand.lock")
    inputs = [
        (item["path"], item["sha256"])
        for item in matrix["live"]["scenarios"]
    ]
    inputs.append((matrix["offline"]["case_path"], matrix["offline"]["case_sha256"]))
    rubric = matrix["live"]["reporting"]["manual_review_rubric"]
    inputs.append((rubric, matrix["live"]["reporting"]["manual_review_rubric_sha256"]))
    for scenario in matrix["live"]["scenarios"]:
        calibration = scenario["calibration"]
        inputs.extend(
            [
                (calibration["summary_path"], calibration["summary_sha256"]),
                (calibration["evidence_path"], calibration["evidence_sha256"]),
            ]
        )
    for relative, expected in inputs:
        path = mapped_repo_path(repo_root, relative, path_map)
        if not path.is_file():
            raise EvaluationError(f"matrix input is missing: {relative}")
        actual = file_hash(path)
        if actual != expected:
            raise EvaluationError(f"matrix input hash mismatch: {relative}; expected {expected}, found {actual}")
    for scenario in matrix["live"]["scenarios"]:
        _verify_calibration(scenario, repo_root=repo_root, path_map=path_map)


def _verify_calibration(
    scenario: dict[str, Any],
    *,
    repo_root: Path,
    path_map: dict[str, str] | None = None,
) -> None:
    calibration = scenario["calibration"]
    summary = _read_object(mapped_repo_path(repo_root, calibration["summary_path"], path_map))
    if summary.get("scenario_id") != scenario["id"]:
        raise EvaluationError(f"calibration scenario mismatch: {calibration['summary_path']}")
    modes = summary.get("modes", {})
    attempts = sum(item.get("attempts_used", 0) for item in modes.values() if isinstance(item, dict))
    if attempts != calibration["observed_attempts_total"]:
        raise EvaluationError(f"calibration attempts mismatch: {scenario['id']}")
    expected_by_mode = scenario["expected_attempts_by_mode"]
    observed_by_mode = {
        mode: item.get("attempts_used", 0)
        for mode, item in modes.items()
        if isinstance(item, dict)
    }
    if observed_by_mode != expected_by_mode:
        raise EvaluationError(f"expected attempts by mode do not match calibration: {scenario['id']}")
    events = []
    try:
        with mapped_repo_path(repo_root, calibration["evidence_path"], path_map).open(
            encoding="utf-8"
        ) as stream:
            events = [json.loads(line) for line in stream if line.strip()]
    except json.JSONDecodeError as exc:
        raise EvaluationError(f"invalid calibration evidence: {calibration['evidence_path']}") from exc
    if not events:
        raise EvaluationError(f"empty calibration evidence: {calibration['evidence_path']}")
    first = datetime.fromisoformat(events[0]["ts"].replace("Z", "+00:00"))
    last = datetime.fromisoformat(events[-1]["ts"].replace("Z", "+00:00"))
    duration = (last - first).total_seconds()
    if abs(duration - calibration["observed_duration_seconds"]) > 0.001:
        raise EvaluationError(f"calibration duration mismatch: {scenario['id']}")


def _cost(model: dict[str, Any], calls: int, input_tokens: int, output_tokens: int) -> float:
    per_call = (
        input_tokens * model["input_usd_per_million"]
        + output_tokens * model["output_usd_per_million"]
    ) / 1_000_000
    return calls * per_call


def build_plan(
    matrix: dict[str, Any],
    *,
    repo_root: Path = Path("."),
    path_map: dict[str, str] | None = None,
) -> dict[str, Any]:
    live = matrix["live"]
    assumptions = live["assumptions"]
    cells: list[dict[str, Any]] = []
    model_totals: dict[str, dict[str, Any]] = {}
    for model in live["models"]:
        expected_attempts = 0
        maximum_attempts = 0
        expected_duration = 0.0
        for scenario in live["scenarios"]:
            maximum_per_mode = _scenario_max_attempts(
                mapped_repo_path(repo_root, scenario["path"], path_map)
            )
            for repeat in range(1, live["repeats"] + 1):
                for mode in live["modes"]:
                    cell = {
                        "cell_id": f"{model['id']}::{scenario['id']}::{mode}::r{repeat}",
                        "model": model["id"],
                        "runtime_model": model["runtime_model"],
                        "scenario_id": scenario["id"],
                        "scenario_path": scenario["path"],
                        "scenario_sha256": scenario["sha256"],
                        "attack_class": scenario["attack_class"],
                        "carrier": scenario["carrier"],
                        "maturity": scenario["maturity"],
                        "auth_mode": mode,
                        "repeat_index": repeat,
                        "expected_attempts": scenario["expected_attempts_by_mode"][mode],
                        "maximum_attempts": maximum_per_mode,
                    }
                    cells.append(cell)
                    expected_attempts += cell["expected_attempts"]
                    maximum_attempts += cell["maximum_attempts"]
            expected_duration += scenario["calibration"]["observed_duration_seconds"] * live["repeats"]
        expected_calls = expected_attempts * assumptions["expected_llm_calls_per_attempt"]
        maximum_calls = maximum_attempts * assumptions["maximum_llm_calls_per_attempt"]
        model_totals[model["id"]] = {
            "cells": sum(1 for cell in cells if cell["model"] == model["id"]),
            "expected_attempts": expected_attempts,
            "maximum_attempts": maximum_attempts,
            "expected_llm_calls": expected_calls,
            "maximum_llm_calls": maximum_calls,
            "expected_duration_seconds": round(expected_duration, 3),
            "estimated_cost_usd": round(
                _cost(
                    model,
                    expected_calls,
                    assumptions["expected_input_tokens_per_call"],
                    assumptions["expected_output_tokens_per_call"],
                ),
                6,
            ),
            "maximum_estimated_cost_usd": round(
                _cost(
                    model,
                    maximum_calls,
                    assumptions["maximum_input_tokens_per_call"],
                    assumptions["maximum_output_tokens_per_call"],
                ),
                6,
            ),
        }

    expected_cost = round(sum(item["estimated_cost_usd"] for item in model_totals.values()), 6)
    maximum_cost = round(sum(item["maximum_estimated_cost_usd"] for item in model_totals.values()), 6)
    live_plan = {
        "provider": live["provider"],
        "scenario_runs": len(live["models"]) * len(live["scenarios"]) * live["repeats"],
        "mode_cells": len(cells),
        "models": model_totals,
        "totals": {
            "expected_attempts": sum(item["expected_attempts"] for item in model_totals.values()),
            "maximum_attempts": sum(item["maximum_attempts"] for item in model_totals.values()),
            "expected_llm_calls": sum(item["expected_llm_calls"] for item in model_totals.values()),
            "maximum_llm_calls": sum(item["maximum_llm_calls"] for item in model_totals.values()),
            "expected_duration_seconds": round(
                sum(item["expected_duration_seconds"] for item in model_totals.values()), 3
            ),
            "estimated_cost_usd": expected_cost,
            "maximum_estimated_cost_usd": maximum_cost,
        },
        "telemetry_status": {
            "attempts": "historical input for expected estimate",
            "llm_calls": "assumed",
            "tokens": "assumed",
            "cost": "estimated from pricing snapshot; not measured",
            "latency": "measured historical scenario duration extrapolated; stand restart overhead excluded",
        },
        "pricing": live["pricing"],
        "reporting": live["reporting"],
        "assumptions": assumptions,
        "budget": live["budget"],
        "cells": cells,
    }
    offline = matrix["offline"]
    offline_plan = {
        **offline,
        "mode_cells": len(offline["modes"]) * offline["repeats"],
        "cells": [
            {
                "cell_id": f"{offline['kind']}::{mode}::r{repeat}",
                "case_path": offline["case_path"],
                "case_sha256": offline["case_sha256"],
                "defense_mode": mode,
                "repeat_index": repeat,
            }
            for repeat in range(1, offline["repeats"] + 1)
            for mode in offline["modes"]
        ],
    }
    plan = {
        "schema_version": "evaluation-plan/v1",
        "matrix_id": matrix["id"],
        "matrix_sha256": canonical_hash(matrix),
        "matrix_status": matrix["status"],
        "stand_revision": matrix["stand_revision"],
        "live": live_plan,
        "offline": offline_plan,
    }
    plan["plan_sha256"] = canonical_hash(plan)
    return plan


def _scenario_max_attempts(path: Path) -> int:
    value = _read_object(path)
    attempts = value.get("max_attempts")
    if not isinstance(attempts, int) or isinstance(attempts, bool) or attempts < 1:
        raise EvaluationError(f"scenario has invalid max_attempts: {path}")
    return attempts


def assert_execution_approved(matrix: dict[str, Any], plan: dict[str, Any], approval_hash: str) -> None:
    if matrix["status"] != "approved" or matrix["live"]["budget"]["approved"] is not True:
        raise EvaluationError("live execution is not approved in the matrix")
    if approval_hash != plan["plan_sha256"]:
        raise EvaluationError("approval hash does not match the current plan")
    cap = matrix["live"]["budget"]["hard_cap_usd"]
    if cap is None:
        raise EvaluationError("approved live execution requires hard_cap_usd")
    maximum = plan["live"]["totals"]["maximum_estimated_cost_usd"]
    if maximum > cap:
        raise EvaluationError(f"maximum estimated cost ${maximum:.2f} exceeds hard cap ${cap:.2f}")


def build_reconstruction(manifest: dict[str, Any], *, repo_root: Path) -> dict[str, Any]:
    execution_schema = _read_object(
        Path(__file__).resolve().parents[2] / "schemas/evaluation-execution.schema.json"
    )
    try:
        jsonschema.Draft202012Validator(
            execution_schema, format_checker=jsonschema.FormatChecker()
        ).validate(manifest)
    except jsonschema.ValidationError as exc:
        location = ".".join(str(item) for item in exc.absolute_path) or "$"
        raise EvaluationError(f"invalid execution manifest at {location}: {exc.message}") from exc
    path_map = manifest.get("path_map", {})
    for logical, frozen in path_map.items():
        repo_path(repo_root, logical)
        repo_path(repo_root, frozen)
    source_manifest_path = manifest.get("source_manifest_path")
    if source_manifest_path:
        source_path = repo_path(repo_root, source_manifest_path)
        if file_hash(source_path) != manifest["source_manifest_sha256"]:
            raise EvaluationError(f"source manifest hash mismatch: {source_manifest_path}")
    planned_metadata: dict[tuple[str, str, int], dict[str, Any]] = {}
    if manifest["manifest_kind"] == "live-matrix":
        matrix_path = mapped_repo_path(repo_root, manifest["matrix_path"], path_map)
        if file_hash(matrix_path) != manifest["matrix_file_sha256"]:
            raise EvaluationError(f"matrix file hash mismatch: {manifest['matrix_path']}")
        matrix = load_matrix(
            matrix_path,
            schema_path=Path(__file__).resolve().parents[2] / "schemas/evaluation-matrix.schema.json",
        )
        verify_inputs(matrix, repo_root=repo_root, path_map=path_map)
        rebuilt_plan = build_plan(matrix, repo_root=repo_root, path_map=path_map)
        if rebuilt_plan["matrix_sha256"] != manifest["matrix_content_sha256"]:
            raise EvaluationError("execution manifest matrix content hash mismatch")
        if rebuilt_plan["plan_sha256"] != manifest["plan_sha256"]:
            raise EvaluationError("execution manifest does not match its matrix plan")
        if rebuilt_plan["matrix_id"] != manifest["matrix_id"]:
            raise EvaluationError("execution manifest matrix id mismatch")
        if rebuilt_plan["stand_revision"] != manifest["stand_revision"]:
            raise EvaluationError("execution manifest stand revision mismatch")
        planned_artifacts = {
            (cell["model"], cell["scenario_id"], cell["repeat_index"])
            for cell in rebuilt_plan["live"]["cells"]
        }
        declared_artifacts = {
            (item["model"], item["scenario_id"], item["repeat_index"])
            for item in manifest["expected_artifacts"]
        }
        if planned_artifacts != declared_artifacts:
            raise EvaluationError("expected artifacts do not match the bound matrix plan")
        for cell in rebuilt_plan["live"]["cells"]:
            key = (cell["model"], cell["scenario_id"], cell["repeat_index"])
            planned_metadata[key] = {
                "scenario_path": cell["scenario_path"],
                "scenario_sha256": cell["scenario_sha256"],
                "attack_class": cell["attack_class"],
                "carrier": cell["carrier"],
                "maturity": cell["maturity"],
                "research_model": cell["runtime_model"],
                "summarization_model": cell["runtime_model"],
            }
    cases: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    seen: set[tuple[str, str, int]] = set()
    expected_artifacts = {
        (item["model"], item["scenario_id"], item["repeat_index"])
        for item in manifest.get("expected_artifacts", [])
    }
    for artifact in manifest.get("artifacts", []):
        key = (artifact["model"], artifact["scenario_id"], artifact["repeat_index"])
        if key in seen:
            raise EvaluationError(f"duplicate execution artifact: {key}")
        seen.add(key)
        for field, expected in planned_metadata.get(key, {}).items():
            if artifact.get(field) != expected:
                raise EvaluationError(
                    f"artifact {field} does not match matrix plan: {key}"
                )
        checked: dict[str, str] = {}
        scenario_path = mapped_repo_path(repo_root, artifact["scenario_path"], path_map)
        if not scenario_path.is_file() or file_hash(scenario_path) != artifact["scenario_sha256"]:
            raise EvaluationError(f"scenario hash mismatch: {artifact['scenario_path']}")
        for name in ("summary", "evidence", "evidence_manifest"):
            path = mapped_repo_path(repo_root, artifact[f"{name}_path"], path_map)
            expected_hash = artifact[f"{name}_sha256"]
            if not path.is_file():
                raise EvaluationError(f"missing {name}: {path}")
            actual = file_hash(path)
            if actual != expected_hash:
                raise EvaluationError(f"{name} hash mismatch: {path}")
            checked[name] = actual
        summary_path = mapped_repo_path(repo_root, artifact["summary_path"], path_map)
        summary = _read_object(summary_path)
        if summary.get("scenario_id") != artifact["scenario_id"]:
            raise EvaluationError(f"scenario id mismatch in {summary_path}")
        if summary.get("run_id") != artifact["run_id"]:
            raise EvaluationError(f"run id mismatch in {summary_path}")
        evidence_manifest = _read_object(
            mapped_repo_path(repo_root, artifact["evidence_manifest_path"], path_map)
        )
        if evidence_manifest.get("sha256") != checked["evidence"]:
            raise EvaluationError(f"evidence manifest does not bind evidence: {artifact['evidence_manifest_path']}")
        if evidence_manifest.get("run_id") != artifact["run_id"]:
            raise EvaluationError(f"run id mismatch in {artifact['evidence_manifest_path']}")
        if evidence_manifest.get("scenario_id") != artifact["scenario_id"]:
            raise EvaluationError(f"scenario id mismatch in {artifact['evidence_manifest_path']}")
        event_ids: set[str] = set()
        runtime: dict[str, Any] = {}
        event_count = 0
        mode_timestamps: dict[str, list[datetime]] = {}
        try:
            with mapped_repo_path(repo_root, artifact["evidence_path"], path_map).open(
                encoding="utf-8"
            ) as stream:
                for line_number, line in enumerate(stream, 1):
                    if not line.strip():
                        continue
                    event = json.loads(line)
                    event_id = event.get("id")
                    if not isinstance(event_id, str):
                        raise EvaluationError(
                            f"missing evidence id at line {line_number}: {artifact['evidence_path']}"
                        )
                    if event_id in event_ids:
                        raise EvaluationError(f"duplicate evidence id {event_id}: {artifact['evidence_path']}")
                    event_ids.add(event_id)
                    event_count += 1
                    if (
                        event.get("run_id") != artifact["run_id"]
                        or event.get("scenario_id") != artifact["scenario_id"]
                    ):
                        raise EvaluationError(
                            f"evidence identity mismatch at line {line_number}: "
                            f"{artifact['evidence_path']}"
                        )
                    mode = event.get("mode")
                    timestamp = event.get("ts")
                    if isinstance(mode, str) and isinstance(timestamp, str):
                        try:
                            mode_timestamps.setdefault(mode, []).append(
                                datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                            )
                        except ValueError as exc:
                            raise EvaluationError(
                                f"invalid evidence timestamp at line {line_number}: {artifact['evidence_path']}"
                            ) from exc
                    if event.get("kind") == "target.ready":
                        runtime = event.get("data", {}).get("runtime", {})
        except json.JSONDecodeError as exc:
            raise EvaluationError(f"invalid evidence JSONL: {artifact['evidence_path']}: {exc}") from exc
        if evidence_manifest.get("events") != event_count:
            raise EvaluationError(f"evidence event count mismatch: {artifact['evidence_manifest_path']}")
        case = analyze_case(summary, source_path=Path(artifact["summary_path"]))
        expected_modes = set(manifest.get("expected_modes", ("vulnerable", "protected")))
        if set(case["modes"]) != expected_modes:
            raise EvaluationError(f"mode set mismatch in {summary_path}")
        stand_env = runtime.get("stand_env", {})
        if stand_env.get("research_model") != artifact["research_model"]:
            raise EvaluationError(
                f"research model mismatch in {artifact['evidence_path']}"
            )
        if stand_env.get("summarization_model") != artifact["summarization_model"]:
            raise EvaluationError(f"summarization model mismatch in {artifact['evidence_path']}")
        if runtime.get("stand_revision") != manifest["stand_revision"]:
            raise EvaluationError(f"stand revision mismatch in {artifact['evidence_path']}")
        referenced = {
            event_id
            for mode in case["modes"].values()
            for event_id in mode["evidence_ids"]
        }
        missing_ids = sorted(referenced - event_ids)
        if missing_ids:
            raise EvaluationError(f"summary references absent evidence ids: {missing_ids[:5]}")
        cases.append(case)
        sources.append({
            "model": artifact["model"],
            "scenario_id": artifact["scenario_id"],
            "repeat_index": artifact["repeat_index"],
            "attack_class": artifact.get("attack_class"),
            "carrier": artifact.get("carrier"),
            "maturity": artifact.get("maturity"),
            "wall_time_seconds_by_mode": {
                mode: round((max(values) - min(values)).total_seconds(), 3)
                for mode, values in mode_timestamps.items()
                if values
            },
            "hashes": checked,
            "referenced_evidence_ids": sorted(referenced),
        })
    if expected_artifacts and seen != expected_artifacts:
        missing = sorted(expected_artifacts - seen)
        extra = sorted(seen - expected_artifacts)
        raise EvaluationError(f"execution manifest is incomplete; missing={missing[:3]}, extra={extra[:3]}")
    aggregate = aggregate_cases(cases)
    matrix_aggregate = _matrix_aggregate(cases, sources)
    reconstruction = {
        "schema_version": "evaluation-reconstruction/v1",
        "manifest_kind": manifest["manifest_kind"],
        "matrix_id": manifest["matrix_id"],
        "plan_sha256": manifest["plan_sha256"],
        "sources": sources,
        "cases": cases,
        "aggregate": aggregate,
        "matrix_aggregate": matrix_aggregate,
    }
    reconstruction["aggregate_sha256"] = canonical_hash(reconstruction)
    return reconstruction


def _wilson(passed: int, total: int) -> dict[str, Any]:
    ratio = {"passed": passed, "total": total, "rate": passed / total if total else None}
    if not total:
        return {**ratio, "ci95": None}
    z = 1.959963984540054
    p = passed / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    margin = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return {**ratio, "ci95": [max(0.0, center - margin), min(1.0, center + margin)]}


def _matrix_aggregate(cases: list[dict[str, Any]], sources: list[dict[str, Any]]) -> dict[str, Any]:
    observations: list[dict[str, Any]] = []
    for case, source in zip(cases, sources):
        for mode, result in case["modes"].items():
            observations.append(
                {
                    "model": source["model"],
                    "attack_class": source["attack_class"],
                    "carrier": source["carrier"],
                    "maturity": source["maturity"],
                    "scenario_id": source["scenario_id"],
                    "repeat_index": source["repeat_index"],
                    "auth_mode": mode,
                    "attempts_used": result["attempts_used"],
                    "wall_time_seconds": source["wall_time_seconds_by_mode"].get(mode),
                    "cost_usd": result["telemetry"]["cost_usd"],
                    "funnel": result["funnel"],
                }
            )

    def rows(keys: tuple[str, ...], population: list[dict[str, Any]] = observations) -> list[dict[str, Any]]:
        grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
        for item in population:
            grouped.setdefault(tuple(item[key] for key in keys), []).append(item)
        result = []
        for values, items in sorted(grouped.items(), key=lambda pair: tuple(str(value) for value in pair[0])):
            dimensions = dict(zip(keys, values))
            wall_times = [item["wall_time_seconds"] for item in items if item["wall_time_seconds"] is not None]
            costs = [item["cost_usd"] for item in items if item["cost_usd"] is not None]
            result.append(
                {
                    **dimensions,
                    "cases": len(items),
                    "attempts_total": sum(item["attempts_used"] for item in items),
                    "wall_time_seconds": {
                        "sum": sum(wall_times) if wall_times else None,
                        "mean": statistics.fmean(wall_times) if wall_times else None,
                        "median": statistics.median(wall_times) if wall_times else None,
                        "observations": len(wall_times),
                        "expected": len(items),
                    },
                    "cost_usd": {
                        "sum": sum(costs) if costs else None,
                        "observations": len(costs),
                        "expected": len(items),
                    },
                    "mpsr": _wilson(sum(item["funnel"]["poison"] for item in items), len(items)),
                    "recall_rate": _wilson(sum(item["funnel"]["recall"] for item in items), len(items)),
                    "mesr": _wilson(
                        sum(
                            item["funnel"]["e2e"]
                            for item in items
                            if item["funnel"]["poison"]
                        ),
                        sum(item["funnel"]["poison"] for item in items),
                    ),
                    "e2e_gate_rate": _wilson(sum(item["funnel"]["e2e"] for item in items), len(items)),
                }
            )
        return result

    return {
        "confidence_interval": "wilson-95",
        "observations": len(observations),
        "overall_by_auth_mode": rows(("auth_mode",)),
        "replay_ready_by_model_and_auth_mode": rows(
            ("model", "auth_mode"),
            [item for item in observations if item["maturity"] == "replay-ready"],
        ),
        "by_model_and_auth_mode": rows(("model", "auth_mode")),
        "by_attack_class_and_auth_mode": rows(("attack_class", "auth_mode")),
        "by_carrier_and_auth_mode": rows(("carrier", "auth_mode")),
        "by_maturity_and_auth_mode": rows(("maturity", "auth_mode")),
    }


def render_plan_markdown(plan: dict[str, Any]) -> str:
    total = plan["live"]["totals"]
    budget = plan["live"]["budget"]
    lines = [
        f"# Evaluation plan: {plan['matrix_id']}",
        "",
        f"- Status: `{plan['matrix_status']}`",
        f"- Plan SHA-256: `{plan['plan_sha256']}`",
        f"- Live scenario runs / mode cells: `{plan['live']['scenario_runs']}` / `{plan['live']['mode_cells']}`",
        f"- Expected / maximum attempts: `{total['expected_attempts']}` / `{total['maximum_attempts']}`",
        f"- Expected / maximum LLM calls: `{total['expected_llm_calls']}` / `{total['maximum_llm_calls']}` (assumed)",
        f"- Historical-duration extrapolation: `{total['expected_duration_seconds']:.1f}s` (stand restarts excluded)",
        f"- Estimated / maximum estimated cost: `${total['estimated_cost_usd']:.2f}` / "
        f"`${total['maximum_estimated_cost_usd']:.2f}`",
        f"- Budget: `{'approved' if budget['approved'] else 'not approved'}`; "
        f"hard cap: `{budget['hard_cap_usd'] if budget['hard_cap_usd'] is not None else 'n/a'}`; "
        f"proposed cap: `${budget['proposed_cap_usd']:.2f}`",
        f"- Maximum live wall time: `{budget['maximum_wall_time_seconds']}s`",
        "- Cost and call counts are estimates; existing evidence has no provider token/cost telemetry.",
        "- Offline memory-defense is a separate track and is not a live auth-mode comparison.",
        "",
        "## Per-model estimate",
        "",
        "| Model | Cells | Attempts exp/max | Calls exp/max | Cost exp/max, USD |",
        "|---|---:|---:|---:|---:|",
    ]
    for model, item in plan["live"]["models"].items():
        lines.append(
            f"| `{model}` | {item['cells']} | {item['expected_attempts']}/{item['maximum_attempts']} | "
            f"{item['expected_llm_calls']}/{item['maximum_llm_calls']} | "
            f"{item['estimated_cost_usd']:.2f}/{item['maximum_estimated_cost_usd']:.2f} |"
        )
    lines.extend(
        [
            "",
            "## Cells",
            "",
            "| Model | Class | Carrier | Scenario | Mode | Repeat | Maturity |",
            "|---|---|---|---|---|---:|---|",
        ]
    )
    for cell in plan["live"]["cells"]:
        lines.append(
            f"| `{cell['model']}` | {cell['attack_class']} | `{cell['carrier']}` | `{cell['scenario_id']}` | "
            f"`{cell['auth_mode']}` | {cell['repeat_index']} | {cell['maturity']} |"
        )
    lines.extend(
        [
            "",
            "## Offline defense cells",
            "",
            f"- Mode cells: `{plan['offline']['mode_cells']}`",
            f"- Modes: `{', '.join(plan['offline']['modes'])}`",
            f"- Frozen case SHA-256: `{plan['offline']['case_sha256']}`",
            "",
        ]
    )
    return "\n".join(lines)
