"""Scenario DSL loading, validation, and rendering."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from string import Template
from typing import Any

import yaml
from jsonschema import Draft202012Validator


STAGE_ORDER = ("setup", "inject", "persist", "trigger", "verify", "cleanup")
KNOWN_ACTIONS = {
    "reset",
    "provision",
    "chat",
    "finalize",
    "snapshot_policies",
    "build_context",
    "capture_logs",
    "checkpoints",
}


class ScenarioValidationError(ValueError):
    """Raised when a scenario is not schema-valid or semantically valid."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("\n".join(errors))


def default_schema_path() -> Path:
    return Path(__file__).resolve().parents[2] / "schemas" / "scenario.schema.json"


def _load_schema(schema_path: Path | None = None) -> dict[str, Any]:
    path = schema_path or default_schema_path()
    return json.loads(path.read_text(encoding="utf-8"))


def _load_raw(path: Path) -> dict[str, Any]:
    suffix = path.suffix.lower()
    if suffix == ".json":
        text = path.read_text(encoding="utf-8")
        data = json.loads(text)
    elif suffix in {".yaml", ".yml"}:
        text = path.read_text(encoding="utf-8")
        data = yaml.safe_load(text)
    else:
        raise ScenarioValidationError([f"unsupported scenario file extension: {suffix}"])
    if not isinstance(data, dict):
        raise ScenarioValidationError(["scenario root must be an object"])
    return data


def validate_scenario(data: dict[str, Any], schema_path: Path | None = None) -> list[str]:
    errors: list[str] = []
    schema = _load_schema(schema_path)
    validator = Draft202012Validator(schema)
    for error in sorted(validator.iter_errors(data), key=lambda item: list(item.path)):
        path = ".".join(str(part) for part in error.absolute_path) or "<root>"
        errors.append(f"{path}: {error.message}")

    steps = data.get("steps")
    actors = data.get("actors") if isinstance(data.get("actors"), dict) else {}
    sessions = data.get("sessions") if isinstance(data.get("sessions"), dict) else {}
    if isinstance(steps, list):
        errors.extend(_validate_steps(steps, actors, sessions))
    return errors


def _validate_steps(
    steps: list[Any],
    actors: dict[str, Any],
    sessions: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    seen_ids: set[str] = set()
    stage_index = -1
    known_steps: set[str] = set()
    has_cleanup_reset = False
    has_checkpoints = False

    for index, step in enumerate(steps):
        if not isinstance(step, dict):
            continue
        step_label = step.get("id", f"steps[{index}]")
        step_id = step.get("id")
        stage = step.get("stage")
        action = step.get("action")

        if isinstance(step_id, str):
            if step_id in seen_ids:
                errors.append(f"{step_label}: duplicate step id")
            seen_ids.add(step_id)

        if stage in STAGE_ORDER:
            current_stage_index = STAGE_ORDER.index(stage)
            if current_stage_index < stage_index:
                errors.append(f"{step_label}: stage order must be monotonic")
            stage_index = max(stage_index, current_stage_index)

        if action and action not in KNOWN_ACTIONS:
            errors.append(f"{step_label}: unknown action {action!r}")

        actor = step.get("actor")
        if actor is not None and actor not in actors:
            errors.append(f"{step_label}: unknown actor {actor!r}")

        session = step.get("session")
        if session is not None and session not in sessions:
            errors.append(f"{step_label}: unknown session {session!r}")

        since_step = step.get("since_step")
        if since_step is not None and since_step not in known_steps:
            errors.append(f"{step_label}: since_step must reference an earlier step")

        if stage == "cleanup" and action == "reset":
            has_cleanup_reset = True
        if stage == "verify" and action == "checkpoints":
            has_checkpoints = True

        if isinstance(step_id, str):
            known_steps.add(step_id)

    if not has_cleanup_reset:
        errors.append("steps: scenario must include a cleanup/reset step")
    if not has_checkpoints:
        errors.append("steps: scenario must include a verify/checkpoints step")
    return errors


def assert_valid_scenario(data: dict[str, Any], schema_path: Path | None = None) -> None:
    errors = validate_scenario(data, schema_path)
    if errors:
        raise ScenarioValidationError(errors)


def load_scenario(path: Path, schema_path: Path | None = None) -> dict[str, Any]:
    data = _load_raw(path)
    assert_valid_scenario(data, schema_path)
    return data


def render_templates(value: Any, variables: dict[str, Any]) -> Any:
    string_vars = {key: str(item) for key, item in variables.items()}
    if isinstance(value, str):
        return Template(value).safe_substitute(string_vars)
    if isinstance(value, list):
        return [render_templates(item, variables) for item in value]
    if isinstance(value, dict):
        return {key: render_templates(item, variables) for key, item in value.items()}
    return copy.deepcopy(value)


def scenario_variables(scenario: dict[str, Any], run_id: str = "", mode: str = "") -> dict[str, Any]:
    base_variables: dict[str, Any] = {
        "run_id": run_id,
        "mode": mode,
    }
    for actor_name, actor in scenario.get("actors", {}).items():
        if isinstance(actor, dict) and "user_id" in actor:
            base_variables[f"{actor_name}_user_id"] = actor["user_id"]
    rendered_parameters = render_templates(scenario.get("parameters", {}), base_variables)
    variables: dict[str, Any] = dict(rendered_parameters)
    variables.update(base_variables)
    return variables


def render_scenario(scenario: dict[str, Any], run_id: str = "", mode: str = "") -> dict[str, Any]:
    return render_templates(scenario, scenario_variables(scenario, run_id=run_id, mode=mode))


def oracle_config(scenario: dict[str, Any], mode: str = "", run_id: str = "") -> dict[str, Any]:
    rendered = render_scenario(scenario, run_id=run_id, mode=mode)
    oracle = dict(rendered["oracle"])
    oracle.setdefault("foreign_cus", rendered.get("parameters", {}).get("foreign_cus", ""))
    oracle.setdefault("target_actor", rendered.get("actors", {}).get("target", {}).get("user_id", ""))
    return oracle


def _first_chat_content(scenario: dict[str, Any], stage: str) -> str:
    for step in scenario.get("steps", []):
        if step.get("stage") == stage and step.get("action") == "chat":
            return str(step.get("content", ""))
    raise ScenarioValidationError([f"missing {stage}/chat step"])


def stage1_config(scenario: dict[str, Any], mode: str = "", run_id: str = "") -> dict[str, Any]:
    rendered = render_scenario(scenario, run_id=run_id, mode=mode)
    oracle = oracle_config(scenario, mode=mode, run_id=run_id)
    actors = rendered["actors"]
    parameters = rendered.get("parameters", {})
    return {
        "id": rendered["id"],
        "source_actor": actors["source"]["user_id"],
        "target_actor": actors["target"]["user_id"],
        "foreign_cus": oracle.get("foreign_cus") or parameters.get("foreign_cus", ""),
        "marker": oracle["marker"],
        "payload": _first_chat_content(rendered, "inject"),
        "trigger": _first_chat_content(rendered, "trigger"),
        "required_policy_terms": oracle["required_policy_terms"],
        "expected_service_path": oracle["expected_service_path"],
    }
