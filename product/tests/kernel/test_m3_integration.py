from __future__ import annotations

import importlib
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

from kernel.canonical import content_digest
from kernel.protocol import ParsedCandidate, read_candidate
from kernel.protocol_v1 import (
    PROTOCOL_VERSION,
    SCHEMA_VERSION,
    RequestV1,
    TaskV1,
)
from kernel.publish import PublishRejectionCode, Rejected, publish
from kernel.replay import replay
from execution.attempt import build_receipt
from execution.run_one_task import VerifierSubprocessError, run_one_task
from execution.workspace_snapshot import snapshot_identity


FIXTURE_BINARY = (
    Path(__file__).resolve().parent.parent
    / "execution"
    / "fixtures"
    / "fake_opencode"
    / "fake_opencode.py"
)
DIRECTIVE_NAME = "fake-opencode-directive.txt"
IMPLEMENTER_IDENTITY = "implementer-1"
VERIFIER_IDENTITY = "verifier-1"
REQUEST = RequestV1(
    objective="Prove the M3 real Host one-task chain end to end through publish()",
    scope=("docs/plans/active/m3-real-host-security-boundary.md",),
    acceptance_criteria=("The real Host Result binds to the Attempt Packet",),
)
TASK = TaskV1(
    task_id="task-m3-e2e",
    objective="Wire the real Host and stub Verifier through the Kernel",
    acceptance_criteria=(
        "The Attempt Packet binds to the published Workflow Revision",
        "The real Host Result binds to the published Attempt Packet",
        "The stub Verifier covers every acceptance criterion in order",
    ),
)
DIFFERENT_EXPECTED_DIGEST = content_digest(
    {"fixture": "m3-integration", "expected_output": "deliberately-different"}
)


def as_candidate(contract_kind: str, typed: Any) -> ParsedCandidate:
    """Validate a typed contract value through the real reader dispatch."""

    read = read_candidate(
        {
            "contract_kind": contract_kind,
            "protocol_version": PROTOCOL_VERSION,
            "schema_version": SCHEMA_VERSION,
            "payload": typed.to_canonical_value(),
        }
    )
    assert read.ok, read.reason
    return read.value


class M3IntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self._state_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self._state_directory.cleanup)
        self.state = self._state_directory.name
        self._workspace_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self._workspace_directory.cleanup)
        self.workspace_root = Path(self._workspace_directory.name) / "repo"
        self._init_repo(self.workspace_root)
        (self.workspace_root / "tracked.txt").write_text(
            "tracked\n", encoding="utf-8"
        )
        self._git(self.workspace_root, "add", "tracked.txt")
        self._git(self.workspace_root, "commit", "-m", "initial M3 fixture")
        # The fake runtime's noop mode makes the post-execution snapshot equal
        # to the independently computed pre-execution identity.
        (self.workspace_root / DIRECTIVE_NAME).write_text(
            "noop\n", encoding="utf-8"
        )

    @staticmethod
    def _git(cwd: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *arguments],
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
        )

    def _init_repo(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        self._git(path, "init")
        self._git(path, "config", "user.email", "m3-tests@example.invalid")
        self._git(path, "config", "user.name", "M3 Integration Tests")

    def _expected_output_digest(self) -> str:
        """The verifier knows the no-op fixture's real post-execution identity."""

        return snapshot_identity(self.workspace_root, ()).digest

    def _run_one_task(self, expected_output_digest: str):
        return run_one_task(
            self.state,
            REQUEST,
            TASK,
            self.workspace_root,
            str(FIXTURE_BINARY),
            implementer_identity=IMPLEMENTER_IDENTITY,
            verifier_identity=VERIFIER_IDENTITY,
            expected_output_digest=expected_output_digest,
        )

    def test_pass_path_replays_full_real_host_chain_as_terminal(self) -> None:
        # The expected digest is obtained from the workspace snapshot seam
        # before execution; run_one_task only passes it to the verifier.
        chain = self._run_one_task(self._expected_output_digest())

        self.assertEqual(chain.verification_value.verdict, "PASS")
        self.assertIsNotNone(chain.receipt)
        self.assertIsNotNone(chain.receipt_value)
        self.assertNotEqual(
            chain.result_value.observation.execution_identity,
            chain.verification_value.verifier_execution_identity,
        )
        assert chain.receipt_value is not None
        self.assertEqual(chain.receipt_value.receipt_type, "terminal")

        state = replay(self.state, chain.run_id)
        self.assertEqual(state.request, chain.request_value)
        self.assertEqual(state.workflow_revision, chain.workflow_value)
        self.assertEqual(state.attempt_packet, chain.attempt_value)
        self.assertEqual(state.result, chain.result_value)
        self.assertEqual(state.verification, chain.verification_value)
        self.assertEqual(state.receipt, chain.receipt_value)
        self.assertTrue(state.terminal)
        self.assertEqual(state.last_sequence, 6)
        assert chain.receipt is not None
        self.assertEqual(state.last_record_id, chain.receipt.record_ref)

    def test_fail_path_has_no_receipt_and_direct_receipt_publish_is_rejected(
        self,
    ) -> None:
        chain = self._run_one_task(DIFFERENT_EXPECTED_DIGEST)

        self.assertNotEqual(chain.verification_value.verdict, "PASS")
        self.assertIsNone(chain.receipt)
        self.assertIsNone(chain.receipt_value)

        rejected = publish(
            self.state,
            chain.run_id,
            as_candidate(
                "receipt",
                build_receipt(verification_ref=chain.verification.record_ref),
            ),
            chain.verification.record_ref,
            "run-receipt-direct",
        )
        self.assertIsInstance(rejected, Rejected)
        assert isinstance(rejected, Rejected)
        self.assertEqual(
            rejected.code, PublishRejectionCode.RECEIPT_VERIFICATION_NOT_PASSED
        )

        state = replay(self.state, chain.run_id)
        self.assertFalse(state.terminal)
        self.assertEqual(state.last_sequence, 5)
        self.assertEqual(state.request, chain.request_value)
        self.assertEqual(state.workflow_revision, chain.workflow_value)
        self.assertEqual(state.attempt_packet, chain.attempt_value)
        self.assertEqual(state.result, chain.result_value)
        self.assertEqual(state.verification, chain.verification_value)
        self.assertIsNone(state.receipt)

    def test_verifier_nonzero_exit_is_a_typed_driver_failure(self) -> None:
        run_one_task_module = importlib.import_module("execution.run_one_task")
        fake_subprocess = mock.Mock()
        fake_subprocess.CalledProcessError = subprocess.CalledProcessError
        fake_subprocess.run.side_effect = subprocess.CalledProcessError(
            17, ["stub-verifier-cli"]
        )

        with mock.patch.object(
            run_one_task_module, "subprocess", fake_subprocess
        ):
            with self.assertRaises(VerifierSubprocessError):
                self._run_one_task(self._expected_output_digest())

    def test_verifier_malformed_stdout_is_a_typed_driver_failure(self) -> None:
        run_one_task_module = importlib.import_module("execution.run_one_task")
        fake_subprocess = mock.Mock()
        fake_subprocess.CalledProcessError = subprocess.CalledProcessError
        fake_subprocess.run.return_value = subprocess.CompletedProcess(
            args=["stub-verifier-cli"],
            returncode=0,
            stdout="not-json",
            stderr="",
        )

        with mock.patch.object(
            run_one_task_module, "subprocess", fake_subprocess
        ):
            with self.assertRaises(VerifierSubprocessError):
                self._run_one_task(self._expected_output_digest())


if __name__ == "__main__":
    unittest.main()
