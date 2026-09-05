import unittest

from llm_red_team.campaign import _best_attempt, _should_retry
from llm_red_team.checkpoints import Checkpoint


class CampaignRetryTests(unittest.TestCase):
    def test_protected_mode_retries_failed_effect_checkpoints(self) -> None:
        checkpoints = [
            Checkpoint(code="W1", passed=True, evidence_ids=(), detail=""),
            Checkpoint(code="W2", passed=True, evidence_ids=(), detail=""),
            Checkpoint(code="E1", passed=True, evidence_ids=(), detail=""),
            Checkpoint(code="E2", passed=False, evidence_ids=(), detail=""),
            Checkpoint(code="E3", passed=True, evidence_ids=(), detail=""),
        ]

        self.assertTrue(_should_retry("protected", checkpoints))

    def test_does_not_retry_when_all_retryable_checkpoints_passed(self) -> None:
        checkpoints = [
            Checkpoint(code="W2", passed=True, evidence_ids=(), detail=""),
            Checkpoint(code="E1", passed=True, evidence_ids=(), detail=""),
            Checkpoint(code="E2", passed=True, evidence_ids=(), detail=""),
            Checkpoint(code="E3", passed=True, evidence_ids=(), detail=""),
        ]

        self.assertFalse(_should_retry("protected", checkpoints))

    def test_best_attempt_keeps_best_single_attempt_not_last_attempt(self) -> None:
        attempts = [
            {
                "attempt": 1,
                "outcome": "failed",
                "passed": False,
                "checkpoints": [{"passed": True}, {"passed": True}, {"passed": False}],
                "events": {"trigger": "EVT-1"},
            },
            {
                "attempt": 2,
                "outcome": "failed",
                "passed": False,
                "checkpoints": [{"passed": True}, {"passed": False}, {"passed": False}],
                "events": {"trigger": "EVT-2"},
            },
        ]

        selected = _best_attempt(attempts)

        self.assertEqual(selected["attempt"], 1)
        self.assertEqual(selected["events"]["trigger"], "EVT-1")


if __name__ == "__main__":
    unittest.main()
