from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from kernel.protocol import ContractKind, RecordRef
from kernel.protocol_v1 import (
    ReceiptV1,
    attempt_packet_v1_content_digest,
    read_attempt_packet_v1,
    read_receipt_v1,
    receipt_v1_content_digest,
)
from execution.attempt import _fixture_digest, build_attempt_packet, build_receipt
from execution.opencode_adapter import probe_opencode_profile
from execution.workspace_snapshot import snapshot_identity

FIXTURE_BINARY = (
    Path(__file__).resolve().parent / "fixtures" / "fake_opencode" / "fake_opencode.py"
)

WORKFLOW_REVISION_REF = RecordRef(
    contract_kind=ContractKind.WORKFLOW_REVISION.value,
    record_id="wr_1",
    content_digest="sha256:agent-platform-json-v1:" + "a" * 64,
)

class BuildAttemptPacketTest(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self._temporary_directory.name) / "repo"
        self._init_repo(self.root)
        (self.root / "tracked.txt").write_text("tracked\n", encoding="utf-8")
        self._git(self.root, "add", "tracked.txt")
        self._git(self.root, "commit", "-m", "initial attempt fixture")

    def tearDown(self) -> None:
        self._temporary_directory.cleanup()

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
        return build_attempt_packet(
            WORKFLOW_REVISION_REF,
            task_id,
            "impl-1",
            self.root,
            str(FIXTURE_BINARY),
        )

    def test_binds_published_workflow_revision_ref(self) -> None:
        packet = self._build_packet()
        self.assertEqual(packet.workflow_revision, WORKFLOW_REVISION_REF)
        self.assertEqual(packet.task_id, "task-1")
        self.assertEqual(packet.implementer_identity, "impl-1")

    def test_identity_fields_are_real_and_deterministic(self) -> None:
        first = self._build_packet()
        second = self._build_packet()
        self.assertEqual(first.context_digest, _fixture_digest("context", "task-1"))
        self.assertEqual(first.context_digest, second.context_digest)
        self.assertEqual(
            first.workspace_snapshot_digest, snapshot_identity(self.root).digest
        )
        self.assertEqual(
            first.runtime_capability_profile_identity,
            probe_opencode_profile(str(FIXTURE_BINARY)).identity,
        )
        self.assertEqual(first.workspace_snapshot_digest, second.workspace_snapshot_digest)
        self.assertEqual(
            first.runtime_capability_profile_identity,
            second.runtime_capability_profile_identity,
        )
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
