"""Deterministic campaign runner for schema-valid scenarios."""

from __future__ import annotations

import argparse
import json
import shutil
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from llm_red_team.checkpoints import Checkpoint, all_passed, evaluate_mode
from llm_red_team.evidence import EvidenceWriter
from llm_red_team.scenario import load_scenario, oracle_config, render_scenario, stage1_config
from llm_red_team.stage1 import answer_content, docker_since_now
from llm_red_team.target import StandTarget


DEFAULT_SCENARIO = Path("replays/cross-user-policy-poisoning-v1/scenario.json")


def default_validate_scenarios() -> list[Path]:
    paths = sorted(Path("replays").glob("*/scenario.json"))
    return paths or [DEFAULT_SCENARIO]


@dataclass
class ModeExecution:
    rendered: dict[str, Any]
    oracle: dict[str, Any]
    legacy: dict[str, Any]
    api_keys: dict[str, str] = field(default_factory=dict)
    sessions: dict[str, str] = field(default_factory=dict)
    results: dict[str, Any] = field(default_factory=dict)
    event_ids: dict[str, str] = field(default_factory=dict)
    since_by_step: dict[str, str] = field(default_factory=dict)
    cleanup_done: bool = False


def utc_run_id(prefix: str = "campaign") -> str:
    return f"{prefix}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"


def run_campaign(
    *,
    target: StandTarget,
    scenario: dict[str, Any],
    evidence: EvidenceWriter,
    run_id: str,
) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "scenario_id": scenario["id"],
        "run_id": run_id,
        "modes": {},
    }
    max_attempts = int(scenario.get("max_attempts", 1))
    for mode in scenario["modes"]:
        attempts: list[dict[str, Any]] = []
        result: dict[str, Any] = {}
        checkpoints: list[Checkpoint] = []
        outcome = "error"
        for attempt in range(1, max_attempts + 1):
            attempt_started = time.monotonic()
            attempt_event = evidence.record(
                "runner.mode_attempt",
                mode=mode,
                data={"attempt": attempt, "max_attempts": max_attempts},
            )
            result, checkpoints, outcome = run_mode(
                target=target,
                scenario=scenario,
                evidence=evidence,
                run_id=f"{run_id}-a{attempt}",
                mode=mode,
            )
            attempt_latency_ms = round((time.monotonic() - attempt_started) * 1000, 3)
            result.setdefault("event_ids", {})["attempt"] = attempt_event
            attempts.append(
                {
                    "attempt": attempt,
                    "outcome": outcome,
                    "passed": all_passed(checkpoints),
                    "checkpoints": [checkpoint.__dict__ for checkpoint in checkpoints],
                    "events": result.get("event_ids", {}),
                    "metrics": {"latency_ms": attempt_latency_ms},
                }
            )
            if outcome == "passed" or not _should_retry(mode, checkpoints):
                break
        selected_attempt = _best_attempt(attempts)
        summary["modes"][mode] = {
            "outcome": selected_attempt["outcome"],
            "passed": selected_attempt["passed"],
            "attempts_used": len(attempts),
            "selected_attempt": selected_attempt["attempt"],
            "checkpoints": selected_attempt["checkpoints"],
            "events": selected_attempt["events"],
            "attempts": attempts,
        }
    return summary


def _best_attempt(attempts: list[dict[str, Any]]) -> dict[str, Any]:
    if not attempts:
        return {"attempt": 0, "outcome": "error", "passed": False, "checkpoints": [], "events": {}}
    return max(attempts, key=lambda attempt: (_attempt_score(attempt), -attempt["attempt"]))


def _attempt_score(attempt: dict[str, Any]) -> tuple[int, int]:
    checkpoints = attempt.get("checkpoints", [])
    passed = sum(1 for checkpoint in checkpoints if checkpoint.get("passed"))
    outcome_rank = {"passed": 2, "failed": 1, "error": 0}.get(attempt.get("outcome"), 0)
    return passed, outcome_rank


def _should_retry(mode: str, checkpoints: list[Checkpoint]) -> bool:
    retryable_codes = {"W2", "E1", "E2", "E3"}
    return bool(checkpoints) and any(item.code in retryable_codes and not item.passed for item in checkpoints)


def run_mode(
    *,
    target: StandTarget,
    scenario: dict[str, Any],
    evidence: EvidenceWriter,
    run_id: str,
    mode: str,
) -> tuple[dict[str, Any], list[Checkpoint], str]:
    state = ModeExecution(
        rendered=render_scenario(scenario, run_id=run_id, mode=mode),
        oracle=oracle_config(scenario, mode=mode, run_id=run_id),
        legacy=stage1_config(scenario, mode=mode, run_id=run_id),
    )
    state.sessions = dict(state.rendered.get("sessions", {}))
    checkpoints: list[Checkpoint] = []
    outcome = "error"
    started = time.monotonic()
    timeout = int(state.rendered.get("timeout_seconds", 180))

    try:
        for step in state.rendered["steps"]:
            if time.monotonic() - started > timeout:
                raise TimeoutError(f"scenario mode {mode} exceeded timeout_seconds={timeout}")
            _execute_step(target=target, evidence=evidence, state=state, step=step, mode=mode)
        checkpoints = state.results.get("checkpoints") or evaluate_mode(mode, _checkpoint_result(state), state.legacy)
        outcome = "passed" if all_passed(checkpoints) else "failed"
    except Exception as exc:
        event_id = evidence.record(
            "runner.error",
            mode=mode,
            data={"error_type": exc.__class__.__name__, "error": str(exc)},
        )
        state.event_ids["error"] = event_id
        checkpoints = checkpoints or []
        outcome = "error"
    finally:
        if not state.cleanup_done:
            cleanup = target.reset_memory()
            event_id = evidence.record("target.cleanup", mode=mode, data=cleanup)
            state.event_ids["cleanup.finally"] = event_id
        if checkpoints and "checkpoints" not in state.results:
            evidence.record(
                "oracle.checkpoints",
                mode=mode,
                data={
                    "passed": all_passed(checkpoints),
                    "checkpoints": [checkpoint.__dict__ for checkpoint in checkpoints],
                },
            )
    result = _checkpoint_result(state)
    result["event_ids"] = dict(state.event_ids)
    return result, checkpoints, outcome


def _execute_step(
    *,
    target: StandTarget,
    evidence: EvidenceWriter,
    state: ModeExecution,
    step: dict[str, Any],
    mode: str,
) -> None:
    action = step["action"]
    step_id = step["id"]
    if action == "reset":
        reset = target.reset_memory()
        kind = "target.cleanup" if step["stage"] == "cleanup" else "target.reset"
        event_id = evidence.record(kind, mode=mode, data=reset)
        state.cleanup_done = step["stage"] == "cleanup"
    elif action == "provision":
        actor_name = step["actor"]
        actor = state.rendered["actors"][actor_name]
        user_id = actor["user_id"]
        raw_key = f"sk-campaign-{mode}-{actor_name}-{user_id}-{uuid.uuid4().hex}"
        label = f"campaign-{mode}-{actor_name}"
        state.api_keys[actor_name] = raw_key
        info = target.provision_api_key(user_id, raw_key, label)
        event_id = evidence.record("actor.provisioned", mode=mode, actor=user_id, data=info)
    elif action == "chat":
        actor_name = step["actor"]
        session_name = step["session"]
        user_id = state.rendered["actors"][actor_name]["user_id"]
        since = docker_since_now()
        time.sleep(1)
        response = target.chat(
            api_key=state.api_keys[actor_name],
            session_id=state.sessions[session_name],
            mode=mode,
            content=step["content"],
        )
        state.since_by_step[step_id] = since
        state.results[step.get("result", step_id)] = response
        state.results[f"{step_id}.content"] = answer_content(response)
        event_kind = "request.trigger" if step["stage"] == "trigger" else "request.inject"
        event_id = evidence.record(
            event_kind,
            mode=mode,
            actor=user_id,
            session_id=state.sessions[session_name],
            data={
                "status": response["status"],
                "prompt": step["content"],
                "response_content": answer_content(response),
            },
        )
    elif action == "finalize":
        actor_name = step["actor"]
        session_name = step["session"]
        user_id = state.rendered["actors"][actor_name]["user_id"]
        response = target.finalize(api_key=state.api_keys[actor_name], session_id=state.sessions[session_name])
        state.results[step.get("result", step_id)] = response
        event_id = evidence.record(
            "memory.finalize",
            mode=mode,
            actor=user_id,
            session_id=state.sessions[session_name],
            data={"status": response["status"], "response": response["json"]},
        )
    elif action == "snapshot_policies":
        policies = target.snapshot_policies()
        state.results[step.get("result", step_id)] = policies
        event_id = evidence.record("memory.write.snapshot", mode=mode, data={"policies": policies})
    elif action == "build_context":
        actor_name = step["actor"]
        session_name = step["session"]
        user_id = state.rendered["actors"][actor_name]["user_id"]
        context = target.build_context(user_id=user_id, session_id=state.sessions[session_name])
        state.results[step.get("result", step_id)] = context
        event_id = evidence.record(
            "memory.read.context",
            mode=mode,
            actor=user_id,
            session_id=state.sessions[session_name],
            data={"context": context},
        )
    elif action == "capture_logs":
        since_step = step["since_step"]
        since = state.since_by_step[since_step]
        container = step.get("container") or target.invest_container
        logs = target.logs_since(container=container, since=since)
        state.results[step.get("result", step_id)] = logs
        actor = state.rendered["actors"].get("target", {}).get("user_id")
        session = state.sessions.get("trigger")
        event_id = evidence.record(
            "side_effect.invest_server_logs",
            mode=mode,
            actor=actor,
            session_id=session,
            data={"container": container, "since": since, "logs": logs},
        )
    elif action == "checkpoints":
        checkpoints = evaluate_mode(mode, _checkpoint_result(state), state.legacy)
        state.results[step.get("result", step_id)] = checkpoints
        event_id = evidence.record(
            "oracle.checkpoints",
            mode=mode,
            data={
                "passed": all_passed(checkpoints),
                "checkpoints": [checkpoint.__dict__ for checkpoint in checkpoints],
            },
        )
    else:
        raise ValueError(f"unsupported action: {action}")
    state.event_ids[_event_key(step)] = event_id


def _event_key(step: dict[str, Any]) -> str:
    result = step.get("result")
    return str(result or step["id"])


def _checkpoint_result(state: ModeExecution) -> dict[str, Any]:
    finalize = state.results.get("finalize", {})
    trigger = state.results.get("trigger", {})
    return {
        "finalize_status": finalize.get("status"),
        "finalize_response": finalize.get("json") or {},
        "policies": state.results.get("policies", []),
        "memory_context": state.results.get("context", ""),
        "trigger_response_content": answer_content(trigger) if isinstance(trigger, dict) else "",
        "invest_server_logs": state.results.get("logs", ""),
        "finalize_event_id": state.event_ids.get("finalize"),
        "policy_snapshot_event_id": state.event_ids.get("policies"),
        "context_event_id": state.event_ids.get("context"),
        "trigger_event_id": state.event_ids.get("trigger"),
        "logs_event_id": state.event_ids.get("logs"),
    }


def render_report(
    *,
    scenario: dict[str, Any],
    run_id: str,
    manifest: dict[str, Any],
    runtime: dict[str, Any],
    summary: dict[str, Any],
) -> str:
    lines = [
        f"# Campaign report: {scenario['id']}",
        "",
        f"- run_id: `{run_id}`",
        f"- evidence sha256: `{manifest['sha256']}`",
        f"- stand revision: `{runtime.get('stand_revision', '')}`",
        f"- model: `{runtime.get('stand_env', {}).get('research_model', '')}`",
        f"- target: `{scenario['target']}`",
        "",
        "## Gate status",
        "",
    ]
    for mode, mode_summary in summary["modes"].items():
        status = "PASS" if mode_summary["passed"] else mode_summary["outcome"].upper()
        lines.append(f"### {mode}: {status}")
        lines.append(f"- attempts: `{mode_summary.get('attempts_used', 1)}`")
        lines.append(f"- selected attempt: `{mode_summary.get('selected_attempt', 1)}`")
        lines.append("")
        lines.append("| Checkpoint | Status | Evidence | Detail |")
        lines.append("|---|---:|---|---|")
        for checkpoint in mode_summary.get("checkpoints", []):
            ids = ", ".join(f"`{item}`" for item in checkpoint["evidence_ids"])
            mark = "PASS" if checkpoint["passed"] else "FAIL"
            lines.append(f"| `{checkpoint['code']}` | {mark} | {ids} | {checkpoint['detail']} |")
        lines.append("")
    lines.extend(
        [
            "## Funnel",
            "",
            "| Mode | Outcome | Passed checkpoints | Total checkpoints |",
            "|---|---:|---:|---:|",
        ]
    )
    for mode, mode_summary in summary["modes"].items():
        checkpoints = mode_summary.get("checkpoints", [])
        passed = sum(1 for item in checkpoints if item["passed"])
        lines.append(f"| `{mode}` | {mode_summary['outcome']} | {passed} | {len(checkpoints)} |")
    lines.append("")
    return "\n".join(lines)


def freeze_successful_run(run_dir: Path, replay_dir: Path, report_text: str) -> None:
    evidence_dir = replay_dir / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(run_dir / "evidence.jsonl", evidence_dir / "latest.jsonl")
    shutil.copy2(run_dir / "manifest.json", evidence_dir / "latest.manifest.json")
    shutil.copy2(run_dir / "summary.json", evidence_dir / "latest.summary.json")
    (replay_dir / "validation.md").write_text(report_text, encoding="utf-8")


def batch_summary(summaries: list[dict[str, Any]]) -> dict[str, Any]:
    cases = len(summaries)
    modes: dict[str, dict[str, Any]] = {}
    for summary in summaries:
        for mode, mode_summary in summary["modes"].items():
            entry = modes.setdefault(mode, {"runs": 0, "passed": 0, "failed": 0, "error": 0, "checkpoints": {}})
            entry["runs"] += 1
            entry[mode_summary["outcome"]] += 1
            for checkpoint in mode_summary.get("checkpoints", []):
                item = entry["checkpoints"].setdefault(checkpoint["code"], {"passed": 0, "total": 0})
                item["total"] += 1
                if checkpoint["passed"]:
                    item["passed"] += 1
    return {"cases": cases, "modes": modes}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run schema-valid red-team campaign scenarios.")
    parser.add_argument("--scenario", action="append", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=Path("output/runs"))
    parser.add_argument("--run-id", help="Explicit unique run id for an orchestrated evaluation.")
    parser.add_argument("--freeze", action="store_true", help="Copy successful evidence into each replay directory.")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()

    repo_root = Path.cwd()
    scenario_paths = args.scenario or (default_validate_scenarios() if args.validate_only else [DEFAULT_SCENARIO])
    scenarios = [load_scenario(path) for path in scenario_paths]
    if args.validate_only:
        for scenario, path in zip(scenarios, scenario_paths):
            print(f"OK {path}: {scenario['id']}")
        return 0

    run_id = args.run_id or utc_run_id()
    run_dir = args.output_dir / run_id
    if run_dir.exists():
        parser.error(f"run directory already exists: {run_dir}")
    target = StandTarget(repo_root=repo_root)
    ready = target.ensure_ready()
    runtime = target.inspect_runtime()

    summaries: list[dict[str, Any]] = []
    success = True
    for scenario, path in zip(scenarios, scenario_paths):
        evidence = EvidenceWriter(run_dir / scenario["id"] / "evidence.jsonl", run_id=run_id, scenario_id=scenario["id"])
        evidence.record("target.ready", data={"health": ready, "runtime": runtime})
        summary = run_campaign(target=target, scenario=scenario, evidence=evidence, run_id=run_id)
        manifest = evidence.manifest(run_dir / scenario["id"] / "manifest.json")
        report_text = render_report(
            scenario=scenario,
            run_id=run_id,
            manifest=manifest,
            runtime=runtime,
            summary=summary,
        )
        scenario_run_dir = run_dir / scenario["id"]
        (scenario_run_dir / "report.md").write_text(report_text, encoding="utf-8")
        (scenario_run_dir / "summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        summaries.append(summary)
        scenario_success = all(item["passed"] for item in summary["modes"].values())
        success = success and scenario_success
        if args.freeze and scenario_success:
            freeze_successful_run(scenario_run_dir, path.parent, report_text)
        print(report_text)
        print(f"Run artifacts: {scenario_run_dir}")

    aggregate = batch_summary(summaries)
    (run_dir / "batch-summary.json").write_text(
        json.dumps(aggregate, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Batch summary: {run_dir / 'batch-summary.json'}")
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
