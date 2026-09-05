from pathlib import Path
import unittest

from llm_red_team.evidence import EvidenceWriter, read_jsonl, redact


class EvidenceTests(unittest.TestCase):
    def test_redact_api_key_and_authorization(self) -> None:
        payload = {
            "api_key": "sk-or-v1-secret",
            "header": "Authorization: Bearer sk-stage1-vulnerable-1001-secret",
            "nested": ["keep", "sk-stage1-protected-1002-secret"],
        }

        redacted = redact(payload)

        self.assertEqual(redacted["api_key"], "<redacted:secret>")
        self.assertNotIn("sk-stage1", redacted["header"])
        self.assertEqual(redacted["nested"][0], "keep")
        self.assertEqual(redacted["nested"][1], "<redacted:secret>")

    def test_evidence_writer_jsonl(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            path = tmp_path / "evidence.jsonl"
            writer = EvidenceWriter(path=path, run_id="run", scenario_id="scenario")

            event_id = writer.record("request", data={"token": "Bearer sk-stage1-demo-secret"})
            manifest = writer.manifest(tmp_path / "manifest.json")

            events = read_jsonl(path)
            self.assertEqual(event_id, "EVT-0001")
            self.assertEqual(events[0]["data"]["token"], "<redacted:secret>")
            self.assertEqual(manifest["events"], 1)
            self.assertEqual(len(manifest["sha256"]), 64)


if __name__ == "__main__":
    unittest.main()
