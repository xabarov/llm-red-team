#!/usr/bin/env python3
"""Adjudicate two or three completed blinded-review verdict files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from llm_red_team.evaluation import EvaluationError
from llm_red_team.review import aggregate_reviews


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Aggregate completed G5 manual reviews.")
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--key", type=Path, required=True)
    parser.add_argument("--verdict", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = aggregate_reviews(
            _load(args.packet),
            _load(args.key),
            [_load(path) for path in args.verdict],
        )
    except (OSError, json.JSONDecodeError, EvaluationError) as exc:
        parser.error(str(exc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Review report: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
