#!/usr/bin/env python3
"""Materialize seed-family variants into schema-valid scenario files."""

from __future__ import annotations

import argparse
from pathlib import Path

from llm_red_team.mutator import materialize_seed_family_file, write_materialized_scenarios


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate scenario files from deterministic seed families.")
    parser.add_argument(
        "--seed",
        action="append",
        type=Path,
        default=None,
        help="Seed family YAML/JSON file. May be passed multiple times.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output/generated/scenarios"),
        help="Directory for generated scenario JSON files.",
    )
    parser.add_argument(
        "--base-scenario",
        type=Path,
        default=None,
        help="Override base scenario path for every seed family.",
    )
    args = parser.parse_args()

    seed_paths = args.seed or [Path("seeds/cross-user-policy-poisoning.yaml")]
    written = []
    for seed_path in seed_paths:
        scenarios = materialize_seed_family_file(seed_path, base_scenario_path=args.base_scenario)
        written.extend(write_materialized_scenarios(scenarios, args.output_dir))

    for path in written:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
