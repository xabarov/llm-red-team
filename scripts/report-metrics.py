#!/usr/bin/env python3
"""Build an offline metrics report from existing campaign summaries."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from llm_red_team.metrics import (
    DEFAULT_REQUIRED_MODES,
    MetricsInputError,
    build_report,
    render_markdown,
    resolve_run_dirs,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read existing summary.json/batch-summary.json files; never runs a campaign."
    )
    parser.add_argument(
        "inputs",
        nargs="*",
        type=Path,
        help="run dirs, batch-summary.json files, or case summary.json files (default: all runs below --runs-root)",
    )
    parser.add_argument("--runs-root", type=Path, default=Path("output/runs"))
    parser.add_argument(
        "--required-mode",
        action="append",
        dest="required_modes",
        help="required mode for replay selection; repeat to override vulnerable+protected",
    )
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    parser.add_argument("--output", type=Path, help="write the report to this path instead of stdout")
    parser.add_argument(
        "--strict-batch",
        action="store_true",
        help="return exit code 2 if a batch summary is missing or differs from case summaries",
    )
    args = parser.parse_args()

    required_modes = tuple(args.required_modes or DEFAULT_REQUIRED_MODES)
    try:
        run_dirs = resolve_run_dirs(args.inputs, root=args.runs_root)
        report = build_report(run_dirs, required_modes=required_modes)
    except MetricsInputError as exc:
        parser.error(str(exc))

    if args.format == "json":
        rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    else:
        rendered = render_markdown(report)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        print(f"Metrics report: {args.output}")
    else:
        print(rendered, end="")

    inconsistent = any(run["batch_consistency"] != "matched" for run in report["runs"])
    return 2 if args.strict_batch and inconsistent else 0


if __name__ == "__main__":
    raise SystemExit(main())
