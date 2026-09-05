"""Stage 1 runner: manual cross-user policy-memory poisoning replay."""

from __future__ import annotations

import argparse
import json
import shutil
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from llm_red_team.checkpoints import Checkpoint, all_passed, evaluate_mode
from llm_red_team.evidence import EvidenceWriter
from llm_red_team.target import StandTarget


MODES = ("vulnerable", "protected")


def load_scenario(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def answer_content(response: dict[str, Any]) -> str:
    try:
        return response["json"]["choices"][0]["message"]["content"]
    except (TypeError, KeyError, IndexError):
        return response.get("text", "")


def docker_since_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def run_mode(
    *,
    target: StandTarget,
    scenario: dict[str, Any],
    evidence: EvidenceWriter,
    run_id: str,
    mode: str,
) -> tuple[dict[str, Any], list[Checkpoint]]:
    source_actor = scenario["source_actor"]
    target_actor = scenario["target_actor"]
    source_session = f"{run_id}-{mode}-inject"
    target_session = f"{run_id}-{mode}-trigger"
    source_key = f"sk-stage1-{mode}-{source_actor}-{uuid.uuid4().hex}"
    target_key = f"sk-stage1-{mode}-{target_actor}-{uuid.uuid4().hex}"

    reset = target.reset_memory()
    reset_event_id = evidence.record("target.reset", mode=mode, data=reset)

    source_key_info = target.provision_api_key(source_actor, source_key, f"stage1-{mode}-source")
    target_key_info = target.provision_api_key(target_actor, target_key, f"stage1-{mode}-target")
    evidence.record("actor.provisioned", mode=mode, actor=source_actor, data=source_key_info)
    evidence.record("actor.provisioned", mode=mode, actor=target_actor, data=target_key_info)

    injection = target.chat(
        api_key=source_key,
        session_id=source_session,
        mode=mode,
        content=scenario["payload"],
    )
    injection_content = answer_content(injection)
    injection_event_id = evidence.record(
        "request.inject",
        mode=mode,
        actor=source_actor,
        session_id=source_session,
        data={
            "status": injection["status"],
            "prompt": scenario["payload"],
            "response_content": injection_content,
        },
    )

    finalize = target.finalize(api_key=source_key, session_id=source_session)
    finalize_event_id = evidence.record(
        "memory.finalize",
        mode=mode,
        actor=source_actor,
        session_id=source_session,
        data={"status": finalize["status"], "response": finalize["json"]},
    )

    policies = target.snapshot_policies()
    policy_snapshot_event_id = evidence.record(
        "memory.write.snapshot",
        mode=mode,
        actor=source_actor,
        session_id=source_session,
        data={"policies": policies},
    )

    context = target.build_context(user_id=target_actor, session_id=target_session)
    context_event_id = evidence.record(
        "memory.read.context",
        mode=mode,
        actor=target_actor,
        session_id=target_session,
        data={"context": context},
    )

    since = docker_since_now()
    time.sleep(1)
    trigger = target.chat(
        api_key=target_key,
        session_id=target_session,
        mode=mode,
        content=scenario["trigger"],
    )
    trigger_content = answer_content(trigger)
    trigger_event_id = evidence.record(
        "request.trigger",
        mode=mode,
        actor=target_actor,
        session_id=target_session,
        data={
            "status": trigger["status"],
            "prompt": scenario["trigger"],
            "response_content": trigger_content,
        },
    )

    logs = target.logs_since(container=target.invest_container, since=since)
    logs_event_id = evidence.record(
        "side_effect.invest_server_logs",
        mode=mode,
        actor=target_actor,
        session_id=target_session,
        data={"container": target.invest_container, "since": since, "logs": logs},
    )

    result = {
        "mode": mode,
        "reset_event_id": reset_event_id,
        "injection_event_id": injection_event_id,
        "finalize_event_id": finalize_event_id,
        "policy_snapshot_event_id": policy_snapshot_event_id,
        "context_event_id": context_event_id,
        "trigger_event_id": trigger_event_id,
        "logs_event_id": logs_event_id,
        "finalize_status": finalize["status"],
        "finalize_response": finalize["json"] or {},
        "policies": policies,
        "memory_context": context,
        "trigger_response_content": trigger_content,
        "invest_server_logs": logs,
    }
    checkpoints = evaluate_mode(mode, result, scenario)
    evidence.record(
        "oracle.checkpoints",
        mode=mode,
        data={
            "passed": all_passed(checkpoints),
            "checkpoints": [checkpoint.__dict__ for checkpoint in checkpoints],
        },
    )
    return result, checkpoints


def render_report(
    *,
    scenario: dict[str, Any],
    run_id: str,
    manifest: dict[str, Any],
    runtime: dict[str, Any],
    checkpoints_by_mode: dict[str, list[Checkpoint]],
) -> str:
    lines = [
        f"# Stage 1 replay report: {scenario['id']}",
        "",
        f"- run_id: `{run_id}`",
        f"- evidence sha256: `{manifest['sha256']}`",
        f"- stand revision: `{runtime.get('stand_revision', '')}`",
        f"- model: `{runtime.get('stand_env', {}).get('research_model', '')}`",
        f"- source actor: `{scenario['source_actor']}`",
        f"- target actor: `{scenario['target_actor']}`",
        f"- foreign CUS: `{scenario['foreign_cus']}`",
        "",
        "## Gate status",
        "",
    ]
    for mode in MODES:
        checkpoints = checkpoints_by_mode[mode]
        status = "PASS" if all_passed(checkpoints) else "FAIL"
        lines.append(f"### {mode}: {status}")
        lines.append("")
        lines.append("| Checkpoint | Status | Evidence | Detail |")
        lines.append("|---|---:|---|---|")
        for checkpoint in checkpoints:
            ids = ", ".join(f"`{item}`" for item in checkpoint.evidence_ids)
            mark = "PASS" if checkpoint.passed else "FAIL"
            lines.append(f"| `{checkpoint.code}` | {mark} | {ids} | {checkpoint.detail} |")
        lines.append("")
    lines.extend(
        [
            "## Notes",
            "",
            "- W1/W2/E1 use direct stand memory state: finalize response, Mongo policy snapshot, and MemoryStore context.",
            "- E2/E3 use observable side effects at the invest-server boundary. Stage 2 should add first-class tool-call traces, but this replay already proves the vulnerable/protected difference end to end.",
            "",
        ]
    )
    return "\n".join(lines)


def freeze_successful_run(run_dir: Path, replay_dir: Path, report_text: str) -> None:
    evidence_dir = replay_dir / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(run_dir / "evidence.jsonl", evidence_dir / "latest.jsonl")
    shutil.copy2(run_dir / "manifest.json", evidence_dir / "latest.manifest.json")
    (replay_dir / "validation.md").write_text(report_text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run stage 1 cross-user memory poisoning replay.")
    parser.add_argument(
        "--scenario",
        type=Path,
        default=Path("replays/cross-user-policy-poisoning-v1/scenario.json"),
    )
    parser.add_argument("--output-dir", type=Path, default=Path("output/runs"))
    parser.add_argument("--freeze", action="store_true", help="Copy successful evidence into the replay directory.")
    args = parser.parse_args()

    repo_root = Path.cwd()
    scenario = load_scenario(args.scenario)
    run_id = f"stage1-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
    run_dir = args.output_dir / run_id
    evidence = EvidenceWriter(run_dir / "evidence.jsonl", run_id=run_id, scenario_id=scenario["id"])
    target = StandTarget(repo_root=repo_root)

    ready = target.ensure_ready()
    runtime = target.inspect_runtime()
    evidence.record("target.ready", data={"health": ready, "runtime": runtime})

    checkpoints_by_mode: dict[str, list[Checkpoint]] = {}
    for mode in MODES:
        _, checkpoints = run_mode(target=target, scenario=scenario, evidence=evidence, run_id=run_id, mode=mode)
        checkpoints_by_mode[mode] = checkpoints

    manifest = evidence.manifest(run_dir / "manifest.json")
    report_text = render_report(
        scenario=scenario,
        run_id=run_id,
        manifest=manifest,
        runtime=runtime,
        checkpoints_by_mode=checkpoints_by_mode,
    )
    (run_dir / "report.md").write_text(report_text, encoding="utf-8")

    success = all(all_passed(items) for items in checkpoints_by_mode.values())
    if args.freeze and success:
        freeze_successful_run(run_dir, args.scenario.parent, report_text)

    print(report_text)
    print(f"Run artifacts: {run_dir}")
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())

