"""Deterministic seed-family materialization for scenario variants."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import yaml

from llm_red_team.scenario import ScenarioValidationError, assert_valid_scenario, render_templates


class SeedFamilyValidationError(ValueError):
    """Raised when a seed family cannot be materialized."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("\n".join(errors))


def load_seed_family(path: Path) -> dict[str, Any]:
    suffix = path.suffix.lower()
    if suffix == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
    elif suffix in {".yaml", ".yml"}:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    else:
        raise SeedFamilyValidationError([f"unsupported seed family file extension: {suffix}"])
    if not isinstance(data, dict):
        raise SeedFamilyValidationError(["seed family root must be an object"])
    errors = validate_seed_family(data)
    if errors:
        raise SeedFamilyValidationError(errors)
    return data


def validate_seed_family(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if data.get("schema_version") != "seed-family/v1":
        errors.append("schema_version must be seed-family/v1")
    if not data.get("id"):
        errors.append("id is required")
    if not data.get("base_scenario"):
        errors.append("base_scenario is required")

    variants = data.get("variants")
    if not isinstance(variants, list) or not variants:
        errors.append("variants must be a non-empty list")
        return errors

    seen_ids: set[str] = set()
    for index, variant in enumerate(variants):
        if not isinstance(variant, dict):
            errors.append(f"variants[{index}] must be an object")
            continue
        variant_id = variant.get("id")
        if not variant_id:
            errors.append(f"variants[{index}].id is required")
        elif variant_id in seen_ids:
            errors.append(f"variants[{index}].id is duplicated")
        elif not str(variant_id).replace("-", "").replace("_", "").replace(".", "").isalnum():
            errors.append(f"variants[{index}].id contains unsupported characters")
        seen_ids.add(str(variant_id))

        patches = variant.get("patches", [])
        if not isinstance(patches, list):
            errors.append(f"variants[{index}].patches must be a list")
            continue
        for patch_index, patch in enumerate(patches):
            if not isinstance(patch, dict):
                errors.append(f"variants[{index}].patches[{patch_index}] must be an object")
                continue
            if not patch.get("path"):
                errors.append(f"variants[{index}].patches[{patch_index}].path is required")
            if "value" not in patch:
                errors.append(f"variants[{index}].patches[{patch_index}].value is required")
    return errors


def materialize_seed_family_file(
    seed_path: Path,
    *,
    base_scenario_path: Path | None = None,
) -> list[dict[str, Any]]:
    family = load_seed_family(seed_path)
    base_path = base_scenario_path or Path(str(family["base_scenario"]))
    from llm_red_team.scenario import load_scenario

    return materialize_family(family, load_scenario(base_path))


def write_materialized_scenarios(scenarios: list[dict[str, Any]], output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for scenario in scenarios:
        path = output_dir / f"{scenario['id']}.json"
        path.write_text(json.dumps(scenario, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        written.append(path)
    return written


def materialize_family(family: dict[str, Any], base_scenario: dict[str, Any]) -> list[dict[str, Any]]:
    errors = validate_seed_family(family)
    if errors:
        raise SeedFamilyValidationError(errors)

    scenarios = []
    for variant in family["variants"]:
        try:
            scenario = materialize_variant(family, variant, base_scenario)
            assert_valid_scenario(scenario)
        except ScenarioValidationError as exc:
            raise SeedFamilyValidationError([f"{variant['id']}: {error}" for error in exc.errors]) from exc
        scenarios.append(scenario)
    return scenarios


def materialize_variant(
    family: dict[str, Any],
    variant: dict[str, Any],
    base_scenario: dict[str, Any],
) -> dict[str, Any]:
    scenario = copy.deepcopy(base_scenario)
    variables = _variant_variables(family, variant)
    scenario["id"] = str(render_templates(variant.get("scenario_id") or f"{scenario['id']}-{variant['id']}", variables))
    if variant.get("description"):
        scenario["description"] = str(render_templates(variant["description"], variables))

    parameters = copy.deepcopy(family.get("parameters", {}))
    parameters.update(variant.get("parameters", {}))
    if parameters:
        rendered_parameters = render_templates(parameters, variables)
        scenario.setdefault("parameters", {}).update(rendered_parameters)
        variables.update({key: str(value) for key, value in rendered_parameters.items()})

    for patch in variant.get("patches", []):
        _set_path(scenario, _split_path(patch["path"]), render_templates(patch["value"], variables))

    scenario["provenance"] = _provenance(family, variant)
    return scenario


def _variant_variables(family: dict[str, Any], variant: dict[str, Any]) -> dict[str, str]:
    variables = {
        "family_id": str(family["id"]),
        "variant_id": str(variant["id"]),
        "category": str(variant.get("category", "")),
    }
    variables.update({key: str(value) for key, value in family.get("parameters", {}).items()})
    variables.update({key: str(value) for key, value in variant.get("parameters", {}).items()})
    return variables


def _provenance(family: dict[str, Any], variant: dict[str, Any]) -> dict[str, Any]:
    family_provenance = family.get("provenance", {})
    variant_provenance = variant.get("provenance", {})
    return {
        "kind": variant_provenance.get("kind") or family_provenance.get("kind") or "seed_family",
        "family_id": family["id"],
        "variant_id": variant["id"],
        "generator": variant_provenance.get("generator") or family_provenance.get("generator") or "manual",
        "backend": variant_provenance.get("backend") or family_provenance.get("backend") or "deterministic",
        "model": variant_provenance.get("model", family_provenance.get("model")),
        "prompt_id": variant_provenance.get("prompt_id", family_provenance.get("prompt_id")),
        "source_hash": variant_provenance.get("source_hash", family_provenance.get("source_hash")),
    }


def _split_path(path: Any) -> list[str]:
    if isinstance(path, str):
        return [part for part in path.split(".") if part]
    if isinstance(path, list) and all(isinstance(part, str) for part in path):
        return path
    raise SeedFamilyValidationError([f"unsupported patch path: {path!r}"])


def _set_path(document: dict[str, Any], path: list[str], value: Any) -> None:
    if not path:
        raise SeedFamilyValidationError(["patch path must not be empty"])
    current: Any = document
    for part in path[:-1]:
        current = _descend(current, part)
    final = path[-1]
    if isinstance(current, list):
        target = _find_by_id(current, final)
        if not isinstance(value, dict):
            raise SeedFamilyValidationError([f"list target {'.'.join(path)} must be replaced with an object"])
        target.clear()
        target.update(value)
    elif isinstance(current, dict):
        current[final] = value
    else:
        raise SeedFamilyValidationError([f"cannot set path {'.'.join(path)}"])


def _descend(current: Any, part: str) -> Any:
    if isinstance(current, dict):
        if part not in current:
            raise SeedFamilyValidationError([f"unknown patch path component: {part}"])
        return current[part]
    if isinstance(current, list):
        return _find_by_id(current, part)
    raise SeedFamilyValidationError([f"cannot descend into path component: {part}"])


def _find_by_id(items: list[Any], item_id: str) -> dict[str, Any]:
    for item in items:
        if isinstance(item, dict) and item.get("id") == item_id:
            return item
    raise SeedFamilyValidationError([f"no list item with id={item_id!r}"])
