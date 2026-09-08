#!/usr/bin/env python3
"""Create blinded G5 review material from an evidence-verified execution."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from llm_red_team.evaluation import EvaluationError, file_hash
from llm_red_team.review import build_review_bundle, load_rubric


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare a blind review packet; never calls a model.")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--rubric", type=Path, default=Path("evaluation/judge-rubric.yaml"))
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        manifest = _load_json(args.manifest)
        rubric = load_rubric(args.rubric)
        packet, key, template = build_review_bundle(
            manifest,
            rubric,
            rubric_sha256=file_hash(args.rubric),
            repo_root=Path.cwd(),
        )
    except (OSError, json.JSONDecodeError, EvaluationError) as exc:
        parser.error(str(exc))
    _write(args.output_dir / "review-packet.json", packet)
    _write(args.output_dir / "review-key.private.json", key)
    _write(args.output_dir / "verdict-template.json", template)
    print(f"Review items: {len(packet['items'])}")
    print(f"Packet: {args.output_dir / 'review-packet.json'}")
    print(f"Private key: {args.output_dir / 'review-key.private.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
