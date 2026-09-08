#!/usr/bin/env python3
"""Verify an execution manifest and reconstruct every aggregate from evidence-linked summaries."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from llm_red_team.evaluation import EvaluationError, build_reconstruction
from llm_red_team.metrics import render_markdown, select_candidates


def _percent(value: dict) -> str:
    if value["rate"] is None:
        return "n/a"
    low, high = value["ci95"]
    return (
        f"{100 * value['rate']:.1f}% ({value['passed']}/{value['total']}; "
        f"95% CI {100 * low:.1f}–{100 * high:.1f}%)"
    )


def _seconds(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.3f} s"


def _matrix_tables(reconstruction: dict) -> str:
    matrix = reconstruction["matrix_aggregate"]
    lines = [
        "# Matrix breakdown",
        "",
        f"Confidence intervals: `{matrix['confidence_interval']}`.",
        "",
        "## Replay-ready headline by model and auth mode",
        "",
        "| Model | Mode | N | MPSR | Recall | MESR | E2E gate | Attempts | Wall time | Cost |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in matrix["replay_ready_by_model_and_auth_mode"]:
        lines.append(
            f"| `{row['model']}` | `{row['auth_mode']}` | {row['cases']} | {_percent(row['mpsr'])} | "
            f"{_percent(row['recall_rate'])} | {_percent(row['mesr'])} | "
            f"{_percent(row['e2e_gate_rate'])} | {row['attempts_total']} | "
            f"{_seconds(row['wall_time_seconds']['sum'])} | "
            f"{('$%.6f' % row['cost_usd']['sum']) if row['cost_usd']['sum'] is not None else 'n/a'} |"
        )
    lines.extend(
        [
            "",
            "## Full matrix including negative controls",
            "",
            "| Model | Mode | N | MPSR | Recall | MESR | E2E gate | Attempts |",
            "|---|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in matrix["by_model_and_auth_mode"]:
        lines.append(
            f"| `{row['model']}` | `{row['auth_mode']}` | {row['cases']} | {_percent(row['mpsr'])} | "
            f"{_percent(row['recall_rate'])} | {_percent(row['mesr'])} | "
            f"{_percent(row['e2e_gate_rate'])} | {row['attempts_total']} |"
        )
    lines.extend(
        [
            "",
            "## By attack class and auth mode",
            "",
            "| Class | Mode | N | MPSR | Recall | MESR | E2E gate | Attempts |",
            "|---|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in matrix["by_attack_class_and_auth_mode"]:
        lines.append(
            f"| `{row['attack_class']}` | `{row['auth_mode']}` | {row['cases']} | {_percent(row['mpsr'])} | "
            f"{_percent(row['recall_rate'])} | {_percent(row['mesr'])} | "
            f"{_percent(row['e2e_gate_rate'])} | {row['attempts_total']} |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Reconstruct G5 results; never calls a model.")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        reconstruction = build_reconstruction(manifest, repo_root=Path.cwd())
    except (OSError, json.JSONDecodeError, EvaluationError) as exc:
        parser.error(str(exc))

    if args.format == "json":
        rendered = json.dumps(reconstruction, ensure_ascii=False, indent=2) + "\n"
    else:
        metrics_report = {
            "schema": reconstruction["schema_version"],
            "required_modes": ["vulnerable", "protected"],
            "runs": [
                {
                    "run_id": "evidence-linked execution",
                    "case_count": len(reconstruction["cases"]),
                    "batch_consistency": "reconstructed",
                    "batch_differences": [],
                    "cases": reconstruction["cases"],
                }
            ],
            "aggregate": reconstruction["aggregate"],
            "selected_candidates": select_candidates(reconstruction["cases"]),
        }
        rendered = (
            f"# Evaluation reconstruction\n\n"
            f"- Matrix: `{reconstruction['matrix_id']}`\n"
            f"- Plan SHA-256: `{reconstruction['plan_sha256']}`\n"
            f"- Aggregate SHA-256: `{reconstruction['aggregate_sha256']}`\n"
            f"- Evidence-linked case summaries: `{len(reconstruction['sources'])}`\n\n"
            + _matrix_tables(reconstruction)
            + "\n"
            + render_markdown(metrics_report)
        )
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        print(f"Evaluation report: {args.output}")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
