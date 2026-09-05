"""Evidence writer for replayable red-team runs."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SECRET_PATTERNS = [
    re.compile(r"Bearer\s+[A-Za-z0-9._:-]+", re.IGNORECASE),
    re.compile(r"sk-or-v1-[A-Za-z0-9._-]+"),
    re.compile(r"sk-stage1-[A-Za-z0-9._-]+"),
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def redact(value: Any) -> Any:
    if isinstance(value, str):
        out = value
        for pattern in SECRET_PATTERNS:
            out = pattern.sub("<redacted:secret>", out)
        return out
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, tuple):
        return [redact(item) for item in value]
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            lowered = str(key).lower()
            if lowered in {"authorization", "api_key", "openai_api_key", "openrouter_api_key"}:
                redacted[str(key)] = "<redacted:secret>"
            else:
                redacted[str(key)] = redact(item)
        return redacted
    return value


@dataclass
class EvidenceWriter:
    path: Path
    run_id: str
    scenario_id: str
    _counter: int = 0
    _events: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            self.path.unlink()

    @property
    def events(self) -> list[dict[str, Any]]:
        return list(self._events)

    def record(
        self,
        kind: str,
        *,
        mode: str | None = None,
        actor: str | None = None,
        session_id: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> str:
        self._counter += 1
        event = {
            "id": f"EVT-{self._counter:04d}",
            "ts": utc_now(),
            "run_id": self.run_id,
            "scenario_id": self.scenario_id,
            "kind": kind,
            "mode": mode,
            "actor": actor,
            "session_id": session_id,
            "data": redact(data or {}),
        }
        self._events.append(event)
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(event, ensure_ascii=False, sort_keys=True))
            stream.write("\n")
        return event["id"]

    def manifest(self, path: Path) -> dict[str, Any]:
        digest = hashlib.sha256(self.path.read_bytes()).hexdigest()
        manifest = {
            "run_id": self.run_id,
            "scenario_id": self.scenario_id,
            "evidence_file": str(self.path),
            "sha256": digest,
            "events": len(self._events),
            "created_at": utc_now(),
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return manifest


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    events = []
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                events.append(json.loads(line))
    return events
