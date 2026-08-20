from __future__ import annotations

import unittest

from kernel.canonical import content_digest
from kernel.protocol import ContractKind, RecordRef
from kernel.protocol_v1 import (
    ReceiptV1,
    ResultV1,
    RuntimeObservationV1,
    attempt_packet_v1_content_digest,
    read_attempt_packet_v1,
    read_receipt_v1,
    read_result_v1,
    receipt_v1_content_digest,
    result_v1_content_digest,
)
from execution.attempt import build_attempt_packet, build_receipt
from execution.stub_host import stub_execute

WORKFLOW_REVISION_REF = RecordRef(
    contract_kind=ContractKind.WORKFLOW_REVISION.value,
    record_id="wr_1",
    content_digest="sha256:agent-platform-json-v1:" + "a" * 64,
)
ATTEMPT_REF = RecordRef(
    contract_kind=ContractKind.ATTEMPT_PACKET.value,
    record_id="ap_1",
    content_digest="sha256:agent-platform-json-v1:" + "b" * 64,
)


class BuildAttemptPacketTest(unittest.TestCase):
    def test_binds_published_workflow_revision_ref(self) -> None:
        packet = build_attempt_packet(WORKFLOW_REVISION_REF, "task-1", "impl-1")
        self.assertEqual(packet.workflow_revision, WORKFLOW_REVISION_REF)
        self.assertEqual(packet.task_id, "task-1")
        self.assertEqual(packet.implementer_identity, "impl-1")

    def test_fixture_identity_fields_are_digest_shaped_and_deterministic(self) -> None:
        first = build_attempt_packet(WORKFLOW_REVISION_REF, "task-1", "impl-1")
        second = build_attempt_packet(WORKFLOW_REVISION_REF, "task-1", "impl-1")
        for field in (
            "context_digest",
            "workspace_snapshot_digest",
            "runtime_capability_profile_identity",
        ):
            self.assertTrue(
                getattr(first, field).startswith("sha256:agent-platform-json-v1:")
            )
            self.assertEqual(getattr(first, field), getattr(second, field))
        other_task = build_attempt_packet(WORKFLOW_REVISION_REF, "task-2", "impl-1")
        self.assertNotEqual(first.context_digest, other_task.context_digest)

    def test_packet_reads_back_through_strict_reader(self) -> None:
        packet = build_attempt_packet(WORKFLOW_REVISION_REF, "task-1", "impl-1")
        outcome = read_attempt_packet_v1(packet.to_canonical_value())
        self.assertEqual(outcome.value, packet)

    def test_content_digest_deterministic(self) -> None:
        first = build_attempt_packet(WORKFLOW_REVISION_REF, "task-1", "impl-1")
        second = build_attempt_packet(WORKFLOW_REVISION_REF, "task-1", "impl-1")
        self.assertEqual(
            attempt_packet_v1_content_digest(first),
            attempt_packet_v1_content_digest(second),
        )


class StubExecuteTest(unittest.TestCase):
    def test_result_binds_attempt_ref_and_observation_digest_matches(self) -> None:
        result = stub_execute(ATTEMPT_REF)
        self.assertEqual(result.attempt, ATTEMPT_REF)
        self.assertEqual(
            result.observation.output_snapshot_digest, result.output_snapshot_digest
        )

    def test_output_digest_is_pure_function_of_attempt_content_digest(self) -> None:
        expected = content_digest(
            {"fixture": "m2-stub-host", "attempt_content_digest": ATTEMPT_REF.content_digest}
        )
        result = stub_execute(ATTEMPT_REF)
        self.assertEqual(result.output_snapshot_digest, expected)

    def test_deterministic_across_repeated_calls(self) -> None:
        first = stub_execute(ATTEMPT_REF)
        second = stub_execute(ATTEMPT_REF)
        self.assertEqual(first, second)
        self.assertEqual(
            result_v1_content_digest(first), result_v1_content_digest(second)
        )

    def test_distinct_attempt_content_produces_distinct_output(self) -> None:
        other_ref = RecordRef(
            contract_kind=ContractKind.ATTEMPT_PACKET.value,
            record_id="ap_2",
            content_digest="sha256:agent-platform-json-v1:" + "c" * 64,
        )
        self.assertNotEqual(
            stub_execute(ATTEMPT_REF).output_snapshot_digest,
            stub_execute(other_ref).output_snapshot_digest,
        )

    def test_result_reads_back_through_strict_reader(self) -> None:
        result = stub_execute(ATTEMPT_REF)
        outcome = read_result_v1(result.to_canonical_value())
        self.assertEqual(outcome.value, result)


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
