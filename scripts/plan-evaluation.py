#!/usr/bin/env python3
"""Validate and expand the G5 evaluation matrix without making provider calls."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from llm_red_team.evaluation import EvaluationError, build_plan, load_matrix, render_plan_markdown, verify_inputs


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the deterministic G5 plan; never calls a model.")
    parser.add_argument("--matrix", type=Path, default=Path("evaluation/matrix.yaml"))
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        matrix = load_matrix(args.matrix)
        verify_inputs(matrix, repo_root=Path.cwd())
        plan = build_plan(matrix, repo_root=Path.cwd())
    except EvaluationError as exc:
        parser.error(str(exc))
    rendered = (
        json.dumps(plan, ensure_ascii=False, indent=2) + "\n"
        if args.format == "json"
        else render_plan_markdown(plan)
    )
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        print(f"Evaluation plan: {args.output}")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
