#!/usr/bin/env python3
"""Run the deterministic offline memory-defense evaluation."""

from __future__ import annotations

import argparse
import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from llm_red_team.defense import (
    load_guarded_case,
    render_guarded_report,
    run_guarded_case,
)
from llm_red_team.evidence import EvidenceWriter
from llm_red_team.metrics import recompute_batch_summary


DEFAULT_CASE = Path("replays/memory-defense-selective-repair-v1/guarded-case.json")


def utc_run_id() -> str:
    return f"guarded-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"


def freeze_run(run_dir: Path, replay_dir: Path, report: str) -> None:
    evidence_dir = replay_dir / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(run_dir / "evidence.jsonl", evidence_dir / "latest.jsonl")
    shutil.copy2(run_dir / "manifest.json", evidence_dir / "latest.manifest.json")
    shutil.copy2(run_dir / "summary.json", evidence_dir / "latest.summary.json")
    (replay_dir / "validation.md").write_text(report, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate memory-defense modes over a synthetic captured snapshot; no target or LLM calls."
    )
    parser.add_argument("--case", type=Path, default=DEFAULT_CASE)
    parser.add_argument("--output-dir", type=Path, default=Path("output/guarded"))
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--freeze", action="store_true")
    args = parser.parse_args()

    case = load_guarded_case(args.case)
    if args.validate_only:
        print(f"OK {args.case}: {case['id']} ({', '.join(case['modes'])})")
        return 0

    run_id = utc_run_id()
    run_root = args.output_dir / run_id
    run_dir = run_root / case["id"]
    evidence = EvidenceWriter(run_dir / "evidence.jsonl", run_id=run_id, scenario_id=case["id"])
    summary = run_guarded_case(case, run_id=run_id, record_event=evidence.record)
    manifest = evidence.manifest(run_dir / "manifest.json")
    report = render_guarded_report(case, summary, manifest)
    (run_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (run_dir / "report.md").write_text(report, encoding="utf-8")
    (run_root / "batch-summary.json").write_text(
        json.dumps(recompute_batch_summary([summary]), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if args.freeze and summary["evaluation_gate_passed"]:
        freeze_run(run_dir, args.case.parent, report)

    print(report)
    print(f"Run artifacts: {run_dir}")
    return 0 if summary["evaluation_gate_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
