"""Adapter for the pinned agent-memory stand."""

from __future__ import annotations

import json
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class StandTarget:
    repo_root: Path
    api_url: str = "http://localhost:8600"
    agent_container: str = "agent-memory-stand-agent-api-1"
    invest_container: str = "agent-memory-stand-invest-server-1"
    request_timeout: int = 180

    def ensure_ready(self) -> dict[str, Any]:
        return self._request("GET", "/healthz")

    def reset_memory(self) -> dict[str, Any]:
        code = r"""
import json
from app.memory.mongo import MongoMemoryStore
from app.memory.working import WorkingMemoryStore

mongo = MongoMemoryStore()
collections = {
    "dialog_sessions": mongo.dialog.col,
    "episodic_memories": mongo.episodic.col,
    "semantic_memories": mongo.semantic.col,
    "agent_policy_memories": mongo.agent_policy.col,
}
deleted = {name: col.delete_many({}).deleted_count for name, col in collections.items()}
redis = WorkingMemoryStore()._client
keys = list(redis.scan_iter(match="working:*"))
redis_deleted = redis.delete(*keys) if keys else 0
print(json.dumps({"mongo_deleted": deleted, "redis_deleted": redis_deleted}, ensure_ascii=False))
"""
        return json.loads(self._docker_python(code))

    def provision_api_key(self, user_id: str, raw_key: str, label: str) -> dict[str, Any]:
        code = f"""
import json
from app.apikeys import hash_key
from app.memory.mongo import MongoMemoryStore
from app.memory.models import ApiKey

raw = {json.dumps(raw_key)}
record = ApiKey(key_hash=hash_key(raw), key_prefix=raw[:14], user_id={json.dumps(user_id)}, label={json.dumps(label)})
MongoMemoryStore().api_keys.col.update_one({{"key_hash": record.key_hash}}, {{"$set": record.model_dump(mode="json")}}, upsert=True)
print(json.dumps({{"user_id": record.user_id, "label": record.label, "key_prefix": record.key_prefix}}, ensure_ascii=False))
"""
        return json.loads(self._docker_python(code))

    def chat(self, *, api_key: str, session_id: str, mode: str, content: str) -> dict[str, Any]:
        body = {
            "messages": [{"role": "user", "content": content}],
            "session_id": session_id,
            "auth_mode": mode,
            "stream": False,
        }
        return self._request("POST", "/v1/chat/completions", body=body, api_key=api_key)

    def finalize(self, *, api_key: str, session_id: str) -> dict[str, Any]:
        return self._request("POST", f"/v1/sessions/{session_id}/finalize", body={}, api_key=api_key)

    def snapshot_policies(self) -> list[dict[str, Any]]:
        code = r"""
import json
from app.memory.mongo import MongoMemoryStore

docs = list(MongoMemoryStore().agent_policy.col.find({}, {"_id": 0}).sort("created_at", -1))
print(json.dumps(docs, ensure_ascii=False, default=str))
"""
        return json.loads(self._docker_python(code))

    def build_context(self, *, user_id: str, session_id: str) -> str:
        code = f"""
from app.memory.store import MemoryStore
print(MemoryStore().build_context({json.dumps(user_id)}, {json.dumps(session_id)}))
"""
        return self._docker_python(code)

    def logs_since(self, *, container: str, since: str) -> str:
        proc = subprocess.run(
            ["docker", "logs", "--since", since, container],
            text=True,
            capture_output=True,
            check=False,
        )
        return (proc.stdout or "") + (proc.stderr or "")

    def inspect_runtime(self) -> dict[str, Any]:
        lock_path = self.repo_root / "infra" / "stand.lock"
        lock = lock_path.read_text(encoding="utf-8") if lock_path.exists() else ""
        revision = ""
        for line in lock.splitlines():
            if line.startswith("STAND_REVISION="):
                revision = line.split("=", 1)[1].strip().strip('"')
        code = r"""
import json
from app.config import get_settings

s = get_settings()
print(json.dumps({
    "openai_base_url": s.openai_base_url,
    "research_model": s.research_model,
    "summarization_model": s.summarization_model,
    "max_react_tool_calls": s.max_react_tool_calls,
}, ensure_ascii=False))
"""
        env = json.loads(self._docker_python(code))
        return {"stand_revision": revision, "stand_env": env}

    def _request(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        api_key: str | None = None,
    ) -> dict[str, Any]:
        data = None
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        if body is not None:
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            self.api_url.rstrip("/") + path,
            data=data,
            headers=headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=self.request_timeout) as response:
                raw = response.read().decode("utf-8")
                return {
                    "status": response.status,
                    "headers": dict(response.headers),
                    "json": json.loads(raw) if raw else None,
                    "text": raw,
                }
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                parsed = None
            return {"status": exc.code, "headers": dict(exc.headers), "json": parsed, "text": raw}

    def _docker_python(self, code: str) -> str:
        proc = subprocess.run(
            ["docker", "exec", self.agent_container, "python", "-c", code],
            text=True,
            capture_output=True,
            check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "docker python command failed")
        return proc.stdout
