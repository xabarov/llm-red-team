"""Combined live-IAM, offline-defense, and manual-review G5 report."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from llm_red_team.evaluation import EvaluationError, canonical_hash, file_hash
from llm_red_team.metrics import aggregate_cases, analyze_case


def _read_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvaluationError(f"cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise EvaluationError(f"expected JSON object in {path}")
    return value


def _verify_self_hash(value: dict[str, Any], field: str) -> None:
    expected = value.get(field)
    unhashed = dict(value)
    unhashed.pop(field, None)
    if expected != canonical_hash(unhashed):
        raise EvaluationError(f"invalid {field}")


def build_defense_section(
    *, summary_path: Path, evidence_path: Path, manifest_path: Path
) -> dict[str, Any]:
    summary = _read_object(summary_path)
    manifest = _read_object(manifest_path)
    evidence_sha256 = file_hash(evidence_path)
    if manifest.get("sha256") != evidence_sha256:
        raise EvaluationError("offline defense manifest does not bind evidence")
    if manifest.get("run_id") != summary.get("run_id"):
        raise EvaluationError("offline defense run id mismatch")
    if manifest.get("scenario_id") != summary.get("scenario_id"):
        raise EvaluationError("offline defense scenario id mismatch")
    event_ids: set[str] = set()
    try:
        with evidence_path.open(encoding="utf-8") as stream:
            for line in stream:
                if line.strip():
                    event = json.loads(line)
                    if event.get("run_id") != summary["run_id"]:
                        raise EvaluationError("offline defense evidence run id mismatch")
                    if event.get("scenario_id") != summary["scenario_id"]:
                        raise EvaluationError("offline defense evidence scenario id mismatch")
                    event_id = event.get("id")
                    if not isinstance(event_id, str) or event_id in event_ids:
                        raise EvaluationError("offline defense evidence ids are invalid")
                    event_ids.add(event_id)
    except json.JSONDecodeError as exc:
        raise EvaluationError(f"invalid offline defense evidence: {exc}") from exc
    if manifest.get("events") != len(event_ids):
        raise EvaluationError("offline defense evidence count mismatch")

    case = analyze_case(summary, source_path=summary_path)
    if case["evaluation_kind"] != "offline-memory-defense":
        raise EvaluationError("expected offline-memory-defense summary")
    referenced = {
        event_id
        for mode in case["modes"].values()
        for event_id in mode["evidence_ids"]
    }
    if not referenced <= event_ids:
        raise EvaluationError("offline defense summary references absent evidence")
    aggregate = aggregate_cases([case])
    modes = {
        mode: {
            "outcome": item["outcome"],
            "F1": item["checkpoint_passed"].get("F1"),
            "F2": item["checkpoint_passed"].get("F2"),
            "srsr": aggregate["modes"][mode]["srsr"],
        }
        for mode, item in case["modes"].items()
    }
    return {
        "evaluation_kind": "offline-memory-defense",
        "scenario_id": summary["scenario_id"],
        "run_id": summary["run_id"],
        "classification": case["candidate"]["classification"],
        "evaluation_gate_passed": summary.get("evaluation_gate_passed") is True,
        "source_hashes": {
            "summary_sha256": file_hash(summary_path),
            "evidence_sha256": evidence_sha256,
            "manifest_sha256": file_hash(manifest_path),
        },
        "modes": modes,
        "fpr_utility_scope": {
            "proxy": "F2 benign preservation",
            "benign_cases": 1,
            "population_estimate": False,
        },
    }


def build_combined_report(
    live_reconstruction: dict[str, Any],
    defense: dict[str, Any],
    *,
    review_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if live_reconstruction.get("schema_version") != "evaluation-reconstruction/v1":
        raise EvaluationError("unsupported live reconstruction")
    _verify_self_hash(live_reconstruction, "aggregate_sha256")
    if review_report is None:
        manual_review: dict[str, Any] = {
            "status": "not-collected",
            "reason": "requires completed blinded reviewer verdicts after live execution",
        }
    else:
        if review_report.get("schema_version") != "evaluation-review-report/v1":
            raise EvaluationError("unsupported manual review report")
        _verify_self_hash(review_report, "report_sha256")
        if review_report.get("packet_sha256") is None:
            raise EvaluationError("manual review report has no packet hash")
        if review_report.get("plan_sha256") != live_reconstruction["plan_sha256"]:
            raise EvaluationError("manual review report belongs to a different plan")
        manual_review = {"status": "collected", "report": review_report}

    report = {
        "schema_version": "g5-evaluation-report/v1",
        "live_iam": {
            "source_kind": live_reconstruction["manifest_kind"],
            "matrix_id": live_reconstruction["matrix_id"],
            "plan_sha256": live_reconstruction["plan_sha256"],
            "aggregate_sha256": live_reconstruction["aggregate_sha256"],
            "case_summaries": len(live_reconstruction["sources"]),
            "matrix_aggregate": live_reconstruction["matrix_aggregate"],
        },
        "offline_memory_defense": defense,
        "manual_review": manual_review,
        "separation_invariant": (
            "live vulnerable/protected IAM results and offline none/write/read/write+read "
            "simulation are separate evaluation tracks"
        ),
        "limitations": [
            "provider tokens and cost are not measured by the current stand",
            "offline F2 is a single synthetic benign-preservation gate, not a population FPR",
            "manual stealth remains not-collected until reviewer verdicts are attached",
        ],
    }
    report["report_sha256"] = canonical_hash(report)
    return report


def _rate(value: dict[str, Any]) -> str:
    rate = value.get("rate")
    if rate is None:
        return "n/a"
    interval = value.get("ci95")
    if interval is None:
        return f"{100 * rate:.1f}% ({value['passed']}/{value['total']})"
    low, high = interval
    return (
        f"{100 * rate:.1f}% ({value['passed']}/{value['total']}; "
        f"CI {100 * low:.1f}–{100 * high:.1f}%)"
    )


def render_combined_markdown(report: dict[str, Any]) -> str:
    live = report["live_iam"]
    defense = report["offline_memory_defense"]
    lines = [
        "# G5 evaluation report",
        "",
        f"- Report SHA-256: `{report['report_sha256']}`",
        f"- Live source: `{live['source_kind']}` / `{live['matrix_id']}`",
        f"- Live aggregate SHA-256: `{live['aggregate_sha256']}`",
        f"- Live case summaries: `{live['case_summaries']}`",
        f"- Manual review: `{report['manual_review']['status']}`",
        "",
        "## Live IAM — replay-ready headline",
        "",
        "Negative controls are excluded from this headline and remain in the machine report.",
        "",
        "| Model | Auth mode | N | MPSR | Recall | MESR | E2E gate |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for row in live["matrix_aggregate"]["replay_ready_by_model_and_auth_mode"]:
        lines.append(
            f"| `{row['model']}` | `{row['auth_mode']}` | {row['cases']} | "
            f"{_rate(row['mpsr'])} | {_rate(row['recall_rate'])} | "
            f"{_rate(row['mesr'])} | {_rate(row['e2e_gate_rate'])} |"
        )
    lines.extend(
        [
            "",
            "## Offline memory defense",
            "",
            "This is a separate captured-snapshot simulation, not live IAM ASR.",
            "",
            "| Mode | Outcome | F1 malicious removal | F2 benign preservation | SRSR |",
            "|---|---|---:|---:|---:|",
        ]
    )
    for mode, value in defense["modes"].items():
        lines.append(
            f"| `{mode}` | {value['outcome']} | {value['F1']} | {value['F2']} | "
            f"{_rate(value['srsr'])} |"
        )
    lines.extend(["", "## Limitations", ""])
    lines.extend(f"- {item}" for item in report["limitations"])
    lines.append("")
    return "\n".join(lines)
