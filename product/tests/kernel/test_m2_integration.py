from __future__ import annotations

import subprocess
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kernel.canonical import content_digest
from kernel.protocol import ParsedCandidate, read_candidate
from kernel.protocol_v1 import (
    PROTOCOL_VERSION,
    SCHEMA_VERSION,
    AttemptPacketV1,
    RequestV1,
    ResultV1,
    TaskV1,
    WorkflowRevisionV1,
)
from kernel.publish import Published, PublishRejectionCode, Rejected, publish
from kernel.replay import replay
from execution.attempt import build_attempt_packet, build_receipt
from execution.stub_host import stub_execute
from verification.stub_verifier import stub_verify

FIXTURE_BINARY = (
    Path(__file__).resolve().parent.parent
    / "execution"
    / "fixtures"
    / "fake_opencode"
    / "fake_opencode.py"
)

IMPLEMENTER_IDENTITY = "implementer-1"
VERIFIER_IDENTITY = "verifier-1"
REQUEST = RequestV1(
    objective="Prove the M2 one-task chain end to end through publish()",
    scope=("docs/plans/active/m2-one-task-protocol-e2e.md",),
    acceptance_criteria=("The six-record chain publishes and replays",),
)
TASK = TaskV1(
    task_id="task-m2-e2e",
    objective="Wire the stub Host and stub Verifier through the Kernel",
    acceptance_criteria=(
        "The Attempt Packet binds to the published Workflow Revision",
        "The stub Host Result binds to the published Attempt Packet",
        "The stub Verifier covers every acceptance criterion in order",
    ),
)
DIFFERENT_EXPECTED_DIGEST = content_digest(
    {"fixture": "m2-integration", "expected_output": "deliberately-different"}
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


@dataclass
class ChainThroughResult:
    """One run published through its Result: identities and typed values."""

    run_id: str
    request: Published
    request_value: RequestV1
    workflow: Published
    workflow_value: WorkflowRevisionV1
    attempt: Published
    attempt_value: AttemptPacketV1
    result: Published
    result_value: ResultV1


class M2IntegrationTests(unittest.TestCase):
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
        self._git(self.workspace_root, "commit", "-m", "initial M2 fixture")

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
        self._git(path, "config", "user.email", "m2-tests@example.invalid")
        self._git(path, "config", "user.name", "M2 Integration Tests")

    def publish_chain_through_result(self) -> ChainThroughResult:
        """Drive Request -> Workflow Revision -> Attempt Packet -> Result."""

        genesis = publish(
            self.state, None, as_candidate("request", REQUEST), None, "key-request"
        )
        assert isinstance(genesis, Published)
        workflow_value = WorkflowRevisionV1(
            request=genesis.record_ref, task=TASK
        )
        workflow = publish(
            self.state,
            genesis.run_id,
            as_candidate("workflow_revision", workflow_value),
            genesis.record_ref,
            "key-workflow",
        )
        assert isinstance(workflow, Published)
        attempt_value = build_attempt_packet(
            workflow_revision_ref=workflow.record_ref,
            task_id=TASK.task_id,
            implementer_identity=IMPLEMENTER_IDENTITY,
            workspace_root=self.workspace_root,
            opencode_binary_path=str(FIXTURE_BINARY),
        )
        attempt = publish(
            self.state,
            genesis.run_id,
            as_candidate("attempt_packet", attempt_value),
            workflow.record_ref,
            "key-attempt",
        )
        assert isinstance(attempt, Published)
        result_value = stub_execute(attempt_ref=attempt.record_ref)
        result = publish(
            self.state,
            genesis.run_id,
            as_candidate("result", result_value),
            attempt.record_ref,
            "key-result",
        )
        assert isinstance(result, Published)
        return ChainThroughResult(
            run_id=genesis.run_id,
            request=genesis,
            request_value=REQUEST,
            workflow=workflow,
            workflow_value=workflow_value,
            attempt=attempt,
            attempt_value=attempt_value,
            result=result,
            result_value=result_value,
        )

    def test_pass_chain_publishes_receipt_and_replays_terminal(self) -> None:
        chain = self.publish_chain_through_result()

        verification = stub_verify(
            result_ref=chain.result.record_ref,
            result_output_snapshot_digest=(
                chain.result_value.output_snapshot_digest
            ),
            task=TASK,
            verifier_identity=VERIFIER_IDENTITY,
            expected_output_digest=chain.result_value.output_snapshot_digest,
        )
        self.assertEqual(verification.verdict, "PASS")
        verification_published = publish(
            self.state,
            chain.run_id,
            as_candidate("verification", verification),
            chain.result.record_ref,
            "key-verification",
        )
        self.assertIsInstance(verification_published, Published)

        receipt = build_receipt(
            verification_ref=verification_published.record_ref
        )
        receipt_published = publish(
            self.state,
            chain.run_id,
            as_candidate("receipt", receipt),
            verification_published.record_ref,
            "key-receipt",
        )
        self.assertIsInstance(receipt_published, Published)

        state = replay(self.state, chain.run_id)
        self.assertEqual(state.request, chain.request_value)
        self.assertEqual(state.workflow_revision, chain.workflow_value)
        self.assertEqual(state.attempt_packet, chain.attempt_value)
        self.assertEqual(state.result, chain.result_value)
        self.assertEqual(state.verification, verification)
        self.assertEqual(state.receipt, receipt)
        self.assertTrue(state.terminal)
        self.assertEqual(state.last_sequence, 6)
        self.assertEqual(state.last_record_id, receipt_published.record_ref)

    def test_fail_chain_publishes_verification_but_rejects_receipt(self) -> None:
        chain = self.publish_chain_through_result()

        verification = stub_verify(
            result_ref=chain.result.record_ref,
            result_output_snapshot_digest=(
                chain.result_value.output_snapshot_digest
            ),
            task=TASK,
            verifier_identity=VERIFIER_IDENTITY,
            expected_output_digest=DIFFERENT_EXPECTED_DIGEST,
        )
        self.assertEqual(verification.verdict, "FAIL")
        self.assertTrue(verification.findings)
        for entry in verification.coverage:
            self.assertEqual(entry.status, "UNSATISFIED")
            self.assertIsNone(entry.evidence_digest)

        verification_published = publish(
            self.state,
            chain.run_id,
            as_candidate("verification", verification),
            chain.result.record_ref,
            "key-verification",
        )
        self.assertIsInstance(verification_published, Published)

        rejected = publish(
            self.state,
            chain.run_id,
            as_candidate(
                "receipt",
                build_receipt(verification_ref=verification_published.record_ref),
            ),
            verification_published.record_ref,
            "key-receipt",
        )
        self.assertIsInstance(rejected, Rejected)
        self.assertEqual(
            rejected.code, PublishRejectionCode.RECEIPT_VERIFICATION_NOT_PASSED
        )

        state = replay(self.state, chain.run_id)
        self.assertIsNone(state.receipt)
        self.assertFalse(state.terminal)
        self.assertEqual(state.last_sequence, 5)
        self.assertEqual(state.request, chain.request_value)
        self.assertEqual(state.workflow_revision, chain.workflow_value)
        self.assertEqual(state.attempt_packet, chain.attempt_value)
        self.assertEqual(state.result, chain.result_value)
        self.assertEqual(state.verification, verification)


if __name__ == "__main__":
    unittest.main()
