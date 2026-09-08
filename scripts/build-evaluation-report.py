#!/usr/bin/env python3
"""Build a combined, evidence-linked G5 report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from llm_red_team.evaluation import EvaluationError, build_reconstruction
from llm_red_team.evaluation_report import (
    build_combined_report,
    build_defense_section,
    render_combined_markdown,
)


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Combine live IAM and offline defense evidence.")
    parser.add_argument("execution_manifest", type=Path)
    parser.add_argument("--review-report", type=Path)
    parser.add_argument(
        "--defense-summary",
        type=Path,
        default=Path("replays/memory-defense-selective-repair-v1/evidence/latest.summary.json"),
    )
    parser.add_argument(
        "--defense-evidence",
        type=Path,
        default=Path("replays/memory-defense-selective-repair-v1/evidence/latest.jsonl"),
    )
    parser.add_argument(
        "--defense-manifest",
        type=Path,
        default=Path("replays/memory-defense-selective-repair-v1/evidence/latest.manifest.json"),
    )
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        reconstruction = build_reconstruction(_read(args.execution_manifest), repo_root=Path.cwd())
        defense = build_defense_section(
            summary_path=args.defense_summary,
            evidence_path=args.defense_evidence,
            manifest_path=args.defense_manifest,
        )
        report = build_combined_report(
            reconstruction,
            defense,
            review_report=_read(args.review_report) if args.review_report else None,
        )
    except (OSError, json.JSONDecodeError, EvaluationError) as exc:
        parser.error(str(exc))
    rendered = (
        json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        if args.format == "json"
        else render_combined_markdown(report)
    )
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        print(f"Combined evaluation report: {args.output}")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
