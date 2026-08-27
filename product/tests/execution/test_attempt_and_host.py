from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import Any

from kernel.protocol import ContractKind, ParsedCandidate, RecordRef, read_candidate
from kernel.protocol_v1 import (
    PROTOCOL_VERSION,
    ReceiptV1,
    RequestV1,
    TaskV1,
    WorkflowRevisionV1,
    attempt_packet_v1_content_digest,
    read_attempt_packet_v1,
    read_receipt_v1,
    receipt_v1_content_digest,
    schema_version_for_kind,
)
from kernel.publish import Published, Rejected, publish
from execution import context_compiler
from execution.attempt import build_attempt_packet, build_receipt
from execution.opencode_adapter import probe_opencode_profile
from execution.workspace_snapshot import snapshot_identity

FIXTURE_BINARY = (
    Path(__file__).resolve().parent / "fixtures" / "fake_opencode" / "fake_opencode.py"
)


def _task(task_id: str) -> TaskV1:
    return TaskV1(
        task_id=task_id,
        objective="Drive the attempt packet through the host",
        acceptance_criteria=("The Attempt Packet binds to the committed Workflow Revision",),
        depends_on=(),
    )


def _as_candidate(contract_kind: str, typed: Any) -> ParsedCandidate:
    read = read_candidate(
        {
            "contract_kind": contract_kind,
            "protocol_version": PROTOCOL_VERSION,
            "schema_version": schema_version_for_kind(ContractKind(contract_kind)),
            "payload": typed.to_canonical_value(),
        }
    )
    assert read.ok, read.reason
    return read.value


def _require_published(result: Published | Rejected) -> Published:
    if isinstance(result, Rejected):
        raise RuntimeError(f"unexpected publish rejection: {result.code}")
    return result


class BuildAttemptPacketTest(unittest.TestCase):
    def setUp(self) -> None:
        self._state_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self._state_directory.cleanup)
        self.state = self._state_directory.name

        self._workspace_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self._workspace_directory.cleanup)
        self.root = Path(self._workspace_directory.name) / "repo"
        self._init_repo(self.root)
        (self.root / "tracked.txt").write_text("tracked\n", encoding="utf-8")
        self._git(self.root, "add", "tracked.txt")
        self._git(self.root, "commit", "-m", "initial attempt fixture")

        self.runs: dict[str, tuple[str, RecordRef, TaskV1]] = {}
        self._publish_run("task-1")

    def _publish_run(self, task_id: str) -> None:
        task = _task(task_id)
        request_published = _require_published(
            publish(
                self.state,
                None,
                _as_candidate(
                    "request",
                    RequestV1(
                        objective="Prove attempt/host packet identities",
                        scope=("product/tests/execution/test_attempt_and_host.py",),
                        acceptance_criteria=(
                            "The packet identities derive from real committed records",
                        ),
                    ),
                ),
                None,
                f"attempt-host-request-{task_id}",
            )
        )
        workflow_published = _require_published(
            publish(
                self.state,
                request_published.run_id,
                _as_candidate(
                    "workflow_revision",
                    WorkflowRevisionV1(
                        request=request_published.record_ref,
                        tasks=(task,),
                    ),
                ),
                request_published.record_ref,
                f"attempt-host-workflow-{task_id}",
            )
        )
        self.runs[task_id] = (
            request_published.run_id,
            workflow_published.record_ref,
            task,
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
        self._git(path, "config", "user.email", "attempt-tests@example.invalid")
        self._git(path, "config", "user.name", "Attempt Packet Tests")

    def _build_packet(self, task_id: str = "task-1"):
        run_id, workflow_revision_ref, task = self.runs[task_id]
        return build_attempt_packet(
            workflow_revision_ref=workflow_revision_ref,
            task_id=task_id,
            implementer_identity="impl-1",
            state=self.state,
            run_id=run_id,
            task=task,
            workspace_root=self.root,
            opencode_binary_path=str(FIXTURE_BINARY),
        )

    def test_binds_published_workflow_revision_ref(self) -> None:
        packet = self._build_packet()
        self.assertEqual(packet.workflow_revision, self.runs["task-1"][1])
        self.assertEqual(packet.task_id, "task-1")
        self.assertEqual(packet.implementer_identity, "impl-1")

    def test_identity_fields_are_real_and_deterministic(self) -> None:
        first = self._build_packet()
        second = self._build_packet()
        task = self.runs["task-1"][2]
        runtime_identity = probe_opencode_profile(str(FIXTURE_BINARY)).identity
        expected_pack = context_compiler.compile_context_pack(
            task_id="task-1",
            task_objective=task.objective,
            task_acceptance_criteria=task.acceptance_criteria,
            workspace_snapshot_digest=snapshot_identity(self.root).digest,
            runtime_capability_profile_identity=runtime_identity,
            contract_refs=(),
            disclosure_identity=context_compiler.disclosure_identity(
                runtime_identity, "v1"
            ),
        )
        self.assertEqual(first.context_digest, expected_pack.digest)
        self.assertEqual(first.context_digest, second.context_digest)
        self.assertEqual(
            first.workspace_snapshot_digest, snapshot_identity(self.root).digest
        )
        self.assertEqual(
            first.runtime_capability_profile_identity,
            runtime_identity,
        )
        self.assertEqual(first.workspace_snapshot_digest, second.workspace_snapshot_digest)
        self.assertEqual(
            first.runtime_capability_profile_identity,
            second.runtime_capability_profile_identity,
        )
        self._publish_run("task-2")
        other_task = self._build_packet("task-2")
        self.assertNotEqual(first.context_digest, other_task.context_digest)

    def test_packet_reads_back_through_strict_reader(self) -> None:
        packet = self._build_packet()
        outcome = read_attempt_packet_v1(packet.to_canonical_value())
        self.assertEqual(outcome.value, packet)

    def test_content_digest_deterministic(self) -> None:
        first = self._build_packet()
        second = self._build_packet()
        self.assertEqual(
            attempt_packet_v1_content_digest(first),
            attempt_packet_v1_content_digest(second),
        )


class BuildReceiptTest(unittest.TestCase):
    def test_binds_verification_ref_with_terminal_type(self) -> None:
        verification_ref = RecordRef(
            contract_kind=ContractKind.VERIFICATION.value,
            record_id="vf_1",
            content_digest="sha256:agent-platform-json-v1:" + "d" * 64,
        )
        receipt = build_receipt(verification_ref)
        self.assertEqual(receipt.verification, verification_ref)
        self.assertEqual(receipt.receipt_type, "terminal")

    def test_receipt_reads_back_and_digest_is_deterministic(self) -> None:
        verification_ref = RecordRef(
            contract_kind=ContractKind.VERIFICATION.value,
            record_id="vf_1",
            content_digest="sha256:agent-platform-json-v1:" + "d" * 64,
        )
        first = build_receipt(verification_ref)
        second = build_receipt(verification_ref)
        self.assertIsInstance(first, ReceiptV1)
        self.assertEqual(
            receipt_v1_content_digest(first), receipt_v1_content_digest(second)
        )
        outcome = read_receipt_v1(first.to_canonical_value())
        self.assertEqual(outcome.value, first)


if __name__ == "__main__":
    unittest.main()
