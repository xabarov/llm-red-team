#!/usr/bin/env python3
"""Draft seed-family variants with an optional OpenRouter planner call."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from llm_red_team.mutator import load_seed_family
from llm_red_team.planner import (
    DEFAULT_MODEL,
    DEFAULT_PROMPT_ID,
    build_seed_family_prompt,
    call_openrouter,
    openrouter_api_key,
    parse_planner_seed_family,
    response_content,
)
from llm_red_team.scenario import load_scenario


def main() -> int:
    parser = argparse.ArgumentParser(description="Plan seed-family variants for authorized local evals.")
    parser.add_argument("--base-scenario", type=Path, default=Path("replays/cross-user-policy-poisoning-v1/scenario.json"))
    parser.add_argument("--reference-seed", type=Path, default=Path("seeds/cross-user-policy-poisoning.yaml"))
    parser.add_argument("--output-dir", type=Path, default=Path("output/planner"))
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--prompt-id", default=DEFAULT_PROMPT_ID)
    parser.add_argument("--categories", default="C1,C2,C3")
    parser.add_argument("--variants-per-category", type=int, default=1)
    parser.add_argument("--call-openrouter", action="store_true", help="Spend one OpenRouter request and save output.")
    args = parser.parse_args()

    base = load_scenario(args.base_scenario)
    reference = load_seed_family(args.reference_seed)
    categories = [item.strip() for item in args.categories.split(",") if item.strip()]
    prompt = build_seed_family_prompt(
        base_scenario=base,
        reference_family=reference,
        categories=categories,
        variants_per_category=args.variants_per_category,
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    prompt_path = args.output_dir / f"{args.prompt_id}.prompt.txt"
    prompt_path.write_text(prompt, encoding="utf-8")
    print(prompt_path)

    if not args.call_openrouter:
        return 0

    response = call_openrouter(prompt=prompt, api_key=openrouter_api_key(), model=args.model)
    content = response_content(response)
    family = parse_planner_seed_family(content, model=args.model, prompt_id=args.prompt_id)

    raw_path = args.output_dir / f"{args.prompt_id}.response.json"
    family_path = args.output_dir / f"{family['id']}.seed-family.json"
    raw_path.write_text(json.dumps(response, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    family_path.write_text(json.dumps(family, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(raw_path)
    print(family_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
