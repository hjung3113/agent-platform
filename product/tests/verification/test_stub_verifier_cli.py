from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

from kernel.canonical import content_digest
from kernel.protocol import RecordRef, is_content_digest
from kernel.protocol_v1 import TaskV1, read_verification_v1


FIXTURE_BINARY = (
    Path(__file__).resolve().parent.parent
    / "execution"
    / "fixtures"
    / "fake_opencode"
    / "fake_opencode.py"
)
OUTPUT_DIGEST = content_digest({"fixture": "stub-verifier-cli-output"})
RESULT_REF = RecordRef(
    contract_kind="result",
    record_id="result-cli-1",
    content_digest=content_digest({"fixture": "stub-verifier-cli-result"}),
)
TASK = TaskV1(
    task_id="task-cli-1",
    objective="Exercise the verifier subprocess",
    acceptance_criteria=("The verifier emits typed output",),
)


class StubVerifierCliTest(unittest.TestCase):
    def input_payload(self) -> dict:
        return {
            "result_ref": RESULT_REF.to_canonical_value(),
            "result_output_snapshot_digest": OUTPUT_DIGEST,
            "task": TASK.to_canonical_value(),
            "verifier_identity": "verifier-cli-1",
            "expected_output_digest": OUTPUT_DIGEST,
            "opencode_binary_path": str(FIXTURE_BINARY),
            "config_paths": [],
        }

    def invoke(self) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "verification.stub_verifier_cli"],
            input=json.dumps(self.input_payload()),
            capture_output=True,
            text=True,
            check=False,
        )

    def test_identical_inputs_get_distinct_execution_identities(self) -> None:
        first = self.invoke()
        second = self.invoke()
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(second.returncode, 0, second.stderr)

        first_payload = json.loads(first.stdout)
        second_payload = json.loads(second.stdout)
        self.assertNotEqual(
            first_payload["verifier_execution_identity"],
            second_payload["verifier_execution_identity"],
        )
        self.assertTrue(
            is_content_digest(first_payload["verifier_execution_identity"])
        )
        self.assertTrue(
            is_content_digest(second_payload["verifier_execution_identity"])
        )

    def test_stdout_round_trips_through_strict_reader(self) -> None:
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        parsed = read_verification_v1(json.loads(result.stdout))
        self.assertTrue(is_content_digest(parsed.value.verifier_execution_identity))
        self.assertEqual(parsed.value.verdict, "PASS")


if __name__ == "__main__":
    unittest.main()
