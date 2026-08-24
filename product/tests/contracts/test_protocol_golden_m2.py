from __future__ import annotations

import dataclasses
import json
import unittest
from pathlib import Path
from typing import Any

from kernel import protocol
from kernel.canonical import canonical_json_bytes, content_digest
from kernel.protocol import (
    ProtocolRejectionCode,
    RecordRef,
    read_candidate,
    read_published_record,
    verify_binding,
)
from kernel.protocol_v1 import (
    RESULT_SNAPSHOT_EVIDENCE_CLASS,
    AttemptPacketV1,
    CoverageEntryV1,
    FindingV1,
    ReceiptV1,
    ResultV1,
    RuntimeObservationV1,
    VerificationV1,
    attempt_packet_v1_content_digest,
    receipt_v1_content_digest,
    result_v1_content_digest,
    verification_v1_content_digest,
)

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "protocol" / "v1"
GOLDEN_WORKFLOW_RECORD_ID = "rec-workflow-0001"
GOLDEN_ATTEMPT_RECORD_ID = "rec-attempt-0001"
GOLDEN_RESULT_RECORD_ID = "rec-result-0001"
GOLDEN_VERIFICATION_RECORD_ID = "rec-verification-0001"

M2_FIXTURES = ("attempt-packet.json", "result.json", "verification.json", "receipt.json")


def load_fixture(name: str) -> Any:
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


def golden_digests() -> dict:
    return load_fixture("golden-digests.json")


def golden_envelope(name: str) -> dict:
    return load_fixture(name)


def read_golden(name: str):
    return read_candidate(golden_envelope(name))


def reverse_key_order(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: reverse_key_order(value[key]) for key in reversed(list(value))}
    if isinstance(value, list):
        return [reverse_key_order(item) for item in value]
    return value


class GoldenM2VectorTests(unittest.TestCase):
    def test_golden_attempt_packet_bytes_and_digest_are_fixed(self) -> None:
        result = read_golden("attempt-packet.json")
        self.assertTrue(result.ok, result.reason)
        golden = golden_digests()["attempt_packet"]
        self.assertEqual(
            canonical_json_bytes(result.value.envelope.to_content_value()),
            golden["canonical_json"].encode("utf-8"),
        )
        self.assertEqual(result.value.envelope.content_digest(), golden["content_digest"])
        self.assertTrue(protocol.is_content_digest(golden["content_digest"]))

    def test_golden_result_bytes_and_digest_are_fixed(self) -> None:
        result = read_golden("result.json")
        self.assertTrue(result.ok, result.reason)
        golden = golden_digests()["result"]
        self.assertEqual(
            canonical_json_bytes(result.value.envelope.to_content_value()),
            golden["canonical_json"].encode("utf-8"),
        )
        self.assertEqual(result.value.envelope.content_digest(), golden["content_digest"])

    def test_golden_verification_bytes_and_digest_are_fixed(self) -> None:
        result = read_golden("verification.json")
        self.assertTrue(result.ok, result.reason)
        golden = golden_digests()["verification"]
        self.assertEqual(
            canonical_json_bytes(result.value.envelope.to_content_value()),
            golden["canonical_json"].encode("utf-8"),
        )
        self.assertEqual(result.value.envelope.content_digest(), golden["content_digest"])

    def test_golden_receipt_bytes_and_digest_are_fixed(self) -> None:
        result = read_golden("receipt.json")
        self.assertTrue(result.ok, result.reason)
        golden = golden_digests()["receipt"]
        self.assertEqual(
            canonical_json_bytes(result.value.envelope.to_content_value()),
            golden["canonical_json"].encode("utf-8"),
        )
        self.assertEqual(result.value.envelope.content_digest(), golden["content_digest"])

    def test_golden_chain_binds_golden_parent_digests(self) -> None:
        digests = golden_digests()
        attempt = read_golden("attempt-packet.json").value.value
        self.assertEqual(
            attempt.workflow_revision.content_digest,
            digests["workflow_revision"]["content_digest"],
        )
        result = read_golden("result.json").value.value
        self.assertEqual(
            result.attempt.content_digest, digests["attempt_packet"]["content_digest"]
        )
        verification = read_golden("verification.json").value.value
        self.assertEqual(
            verification.result.content_digest, digests["result"]["content_digest"]
        )
        receipt = read_golden("receipt.json").value.value
        self.assertEqual(
            receipt.verification.content_digest,
            digests["verification"]["content_digest"],
        )

    def test_golden_fixture_values_round_trip_through_typed_readers(self) -> None:
        attempt = read_golden("attempt-packet.json").value.value
        self.assertIsInstance(attempt, AttemptPacketV1)
        self.assertEqual(attempt.task_id, "task-m0-1")

        result = read_golden("result.json").value.value
        self.assertIsInstance(result, ResultV1)
        self.assertEqual(
            result.observation.output_snapshot_digest,
            result.output_snapshot_digest,
        )

        verification = read_golden("verification.json").value.value
        self.assertIsInstance(verification, VerificationV1)
        self.assertEqual(verification.verdict, "PASS")
        for entry in verification.coverage:
            self.assertEqual(entry.status, "SATISFIED")
            self.assertEqual(
                entry.evidence_digest, result.output_snapshot_digest
            )

        receipt = read_golden("receipt.json").value.value
        self.assertIsInstance(receipt, ReceiptV1)
        self.assertEqual(receipt.receipt_type, "terminal")

    def test_key_insertion_order_does_not_change_identity(self) -> None:
        for name in M2_FIXTURES:
            envelope = golden_envelope(name)
            original = read_candidate(envelope)
            self.assertTrue(original.ok, f"{name}: {original.reason}")
            reordered = reverse_key_order(envelope)
            reordered = {
                "payload": reordered["payload"],
                "schema_version": reordered["schema_version"],
                "protocol_version": reordered["protocol_version"],
                "contract_kind": reordered["contract_kind"],
            }
            other = read_candidate(reordered)
            self.assertTrue(other.ok, f"{name}: {other.reason}")
            self.assertEqual(
                other.value.envelope.content_digest(),
                original.value.envelope.content_digest(),
                name,
            )
            self.assertEqual(
                other.value.envelope.to_content_value(),
                original.value.envelope.to_content_value(),
                name,
            )

    def test_coverage_array_order_remains_meaningful(self) -> None:
        verification = read_golden("verification.json").value.value
        reordered = VerificationV1(
            result=verification.result,
            verifier_identity=verification.verifier_identity,
            verifier_runtime_capability_profile_identity=(
                verification.verifier_runtime_capability_profile_identity
            ),
            verifier_execution_identity=verification.verifier_execution_identity,
            coverage=tuple(reversed(verification.coverage)),
            verdict=verification.verdict,
            findings=verification.findings,
        )
        self.assertNotEqual(
            verification_v1_content_digest(verification),
            verification_v1_content_digest(reordered),
        )

    def test_identity_changes_when_semantic_fields_or_binding_change(self) -> None:
        attempt = read_golden("attempt-packet.json").value.value
        attempt_base = attempt_packet_v1_content_digest(attempt)
        for changed in (
            AttemptPacketV1(
                workflow_revision=attempt.workflow_revision,
                task_id="task-other",
                implementer_identity=attempt.implementer_identity,
                context_digest=attempt.context_digest,
                workspace_snapshot_digest=attempt.workspace_snapshot_digest,
                runtime_capability_profile_identity=(
                    attempt.runtime_capability_profile_identity
                ),
            ),
            AttemptPacketV1(
                workflow_revision=RecordRef(
                    attempt.workflow_revision.contract_kind,
                    "rec-workflow-9999",
                    attempt.workflow_revision.content_digest,
                ),
                task_id=attempt.task_id,
                implementer_identity="stub-verifier-m2",
                context_digest=attempt.context_digest,
                workspace_snapshot_digest=attempt.workspace_snapshot_digest,
                runtime_capability_profile_identity=(
                    attempt.runtime_capability_profile_identity
                ),
            ),
        ):
            self.assertNotEqual(attempt_base, attempt_packet_v1_content_digest(changed))

        result = read_golden("result.json").value.value
        result_base = result_v1_content_digest(result)
        changed_output = ResultV1(
            attempt=result.attempt,
            output_snapshot_digest="sha256:agent-platform-json-v1:" + "9" * 64,
            observation=RuntimeObservationV1(
                runtime_identity=result.observation.runtime_identity,
                output_snapshot_digest="sha256:agent-platform-json-v1:" + "9" * 64,
                execution_identity=result.observation.execution_identity,
            ),
        )
        self.assertNotEqual(result_base, result_v1_content_digest(changed_output))

        verification = read_golden("verification.json").value.value
        verification_base = verification_v1_content_digest(verification)
        changed_verdict = VerificationV1(
            result=verification.result,
            verifier_identity=verification.verifier_identity,
            verifier_runtime_capability_profile_identity=(
                verification.verifier_runtime_capability_profile_identity
            ),
            verifier_execution_identity=verification.verifier_execution_identity,
            coverage=(
                CoverageEntryV1(
                    criterion=verification.coverage[0].criterion,
                    status="UNSATISFIED",
                    evidence_digest=None,
                    evidence_class=RESULT_SNAPSHOT_EVIDENCE_CLASS,
                ),
                *verification.coverage[1:],
            ),
            verdict="FAIL",
            findings=(
                FindingV1(
                    criterion=verification.coverage[0].criterion,
                    fingerprint=content_digest(
                        {
                            "criterion": verification.coverage[0].criterion,
                            "description": "Digest mismatch",
                        }
                    ),
                    description="Digest mismatch",
                    state="OPEN",
                    predecessor=None,
                ),
            ),
        )
        self.assertNotEqual(
            verification_base, verification_v1_content_digest(changed_verdict)
        )

        receipt = read_golden("receipt.json").value.value
        receipt_base = receipt_v1_content_digest(receipt)
        substituted_receipt = ReceiptV1(
            verification=RecordRef(
                receipt.verification.contract_kind,
                "rec-verification-9999",
                receipt.verification.content_digest,
            ),
            receipt_type=receipt.receipt_type,
        )
        self.assertNotEqual(
            receipt_base, receipt_v1_content_digest(substituted_receipt)
        )

    def test_declared_published_digest_must_equal_recomputed_content_digest(self) -> None:
        forgeries = {
            "attempt-packet.json": lambda payload: payload.update(
                implementer_identity="forged-implementer"
            ),
            "result.json": lambda payload: payload["observation"].update(
                runtime_identity="forged-runtime"
            ),
            "verification.json": lambda payload: payload.update(
                verifier_identity="forged-verifier"
            ),
            "receipt.json": lambda payload: payload["verification"].update(
                record_id="rec-verification-9999"
            ),
        }
        record_ids = {
            "attempt-packet.json": GOLDEN_ATTEMPT_RECORD_ID,
            "result.json": GOLDEN_RESULT_RECORD_ID,
            "verification.json": GOLDEN_VERIFICATION_RECORD_ID,
            "receipt.json": "rec-receipt-0001",
        }
        for name, forge in forgeries.items():
            envelope = golden_envelope(name)
            kind = envelope["contract_kind"]
            digest = golden_digests()[kind]["content_digest"]
            record = {
                "record_id": record_ids[name],
                "content_digest": digest,
                **envelope,
            }
            result = read_published_record(record)
            self.assertTrue(result.ok, f"{name}: {result.reason}")
            forged = json.loads(json.dumps(record))
            forge(forged["payload"])
            self.assertEqual(
                read_published_record(forged).rejection_code,
                ProtocolRejectionCode.CONTENT_DIGEST_MISMATCH,
                name,
            )


class StaleSubstitutedBindingM2Tests(unittest.TestCase):
    def expected_workflow_parent(self) -> RecordRef:
        return RecordRef(
            contract_kind="workflow_revision",
            record_id=GOLDEN_WORKFLOW_RECORD_ID,
            content_digest=golden_digests()["workflow_revision"]["content_digest"],
        )

    def expected_attempt_parent(self) -> RecordRef:
        return RecordRef(
            contract_kind="attempt_packet",
            record_id=GOLDEN_ATTEMPT_RECORD_ID,
            content_digest=golden_digests()["attempt_packet"]["content_digest"],
        )

    def expected_result_parent(self) -> RecordRef:
        return RecordRef(
            contract_kind="result",
            record_id=GOLDEN_RESULT_RECORD_ID,
            content_digest=golden_digests()["result"]["content_digest"],
        )

    def expected_verification_parent(self) -> RecordRef:
        return RecordRef(
            contract_kind="verification",
            record_id=GOLDEN_VERIFICATION_RECORD_ID,
            content_digest=golden_digests()["verification"]["content_digest"],
        )

    def read_substituted(self, fixture: str, ref_field: str, reference: dict):
        envelope = golden_envelope(fixture)
        envelope["payload"][ref_field] = reference
        result = read_candidate(envelope)
        self.assertTrue(result.ok, result.reason)
        return result.value.value

    def test_exact_golden_bindings_verify(self) -> None:
        attempt = read_golden("attempt-packet.json").value.value
        self.assertTrue(
            verify_binding(
                attempt.workflow_revision, self.expected_workflow_parent()
            ).ok
        )
        result = read_golden("result.json").value.value
        self.assertTrue(verify_binding(result.attempt, self.expected_attempt_parent()).ok)
        verification = read_golden("verification.json").value.value
        self.assertTrue(
            verify_binding(verification.result, self.expected_result_parent()).ok
        )
        receipt = read_golden("receipt.json").value.value
        self.assertTrue(
            verify_binding(
                receipt.verification, self.expected_verification_parent()
            ).ok
        )

    def test_wrong_parent_record_id_rejects_against_expected_parent(self) -> None:
        attempt = self.read_substituted(
            "attempt-packet.json",
            "workflow_revision",
            {
                "contract_kind": "workflow_revision",
                "record_id": "rec-workflow-0002",
                "content_digest": golden_digests()["workflow_revision"]["content_digest"],
            },
        )
        self.assertEqual(
            verify_binding(
                attempt.workflow_revision, self.expected_workflow_parent()
            ).rejection_code,
            ProtocolRejectionCode.BINDING_MISMATCH,
        )

    def test_stale_parent_digest_rejects(self) -> None:
        result = self.read_substituted(
            "result.json",
            "attempt",
            {
                "contract_kind": "attempt_packet",
                "record_id": GOLDEN_ATTEMPT_RECORD_ID,
                "content_digest": "sha256:agent-platform-json-v1:" + "8" * 64,
            },
        )
        self.assertEqual(
            verify_binding(result.attempt, self.expected_attempt_parent()).rejection_code,
            ProtocolRejectionCode.BINDING_MISMATCH,
        )

    def test_substituted_semantically_similar_parent_rejects(self) -> None:
        result = read_golden("result.json").value.value
        similar = result_v1_content_digest(
            ResultV1(
                attempt=result.attempt,
                output_snapshot_digest=result.output_snapshot_digest,
                observation=RuntimeObservationV1(
                    runtime_identity="stub-host-m2-amended",
                    output_snapshot_digest=result.observation.output_snapshot_digest,
                    execution_identity=result.observation.execution_identity,
                ),
            )
        )
        self.assertNotEqual(similar, golden_digests()["result"]["content_digest"])
        verification = self.read_substituted(
            "verification.json",
            "result",
            {
                "contract_kind": "result",
                "record_id": GOLDEN_RESULT_RECORD_ID,
                "content_digest": similar,
            },
        )
        self.assertEqual(
            verify_binding(
                verification.result, self.expected_result_parent()
            ).rejection_code,
            ProtocolRejectionCode.BINDING_MISMATCH,
        )


class ForgedPublicationMetadataM2Tests(unittest.TestCase):
    def test_parsing_m2_candidates_produces_no_publication_fields(self) -> None:
        for name in M2_FIXTURES:
            parsed = read_golden(name).value
            self.assertEqual(
                {field.name for field in dataclasses.fields(parsed.envelope)},
                {"contract_kind", "protocol_version", "schema_version", "payload"},
                name,
            )
            for forbidden in ("record_id", "published", "authoritative"):
                self.assertFalse(hasattr(parsed.value, forbidden), f"{name}:{forbidden}")

    def test_m2_digest_helpers_equal_envelope_content_digest(self) -> None:
        attempt = read_golden("attempt-packet.json").value
        self.assertEqual(
            attempt_packet_v1_content_digest(attempt.value),
            attempt.envelope.content_digest(),
        )
        result = read_golden("result.json").value
        self.assertEqual(
            result_v1_content_digest(result.value),
            result.envelope.content_digest(),
        )
        verification = read_golden("verification.json").value
        self.assertEqual(
            verification_v1_content_digest(verification.value),
            verification.envelope.content_digest(),
        )
        receipt = read_golden("receipt.json").value
        self.assertEqual(
            receipt_v1_content_digest(receipt.value),
            receipt.envelope.content_digest(),
        )
        self.assertNotEqual(
            content_digest(read_golden("attempt-packet.json").value.envelope.to_content_value()),
            content_digest(read_golden("result.json").value.envelope.to_content_value()),
        )


if __name__ == "__main__":
    unittest.main()
