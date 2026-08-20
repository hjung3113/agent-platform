from __future__ import annotations

import unittest
from dataclasses import replace

from kernel.protocol import (
    ProtocolRejectionCode,
    RecordRef,
    read_candidate,
    verify_binding,
)
from kernel.protocol_v1 import (
    AttemptPacketV1,
    CoverageEntryV1,
    ReceiptV1,
    ResultV1,
    RuntimeObservationV1,
    VerificationV1,
    attempt_packet_v1_content_digest,
    read_attempt_packet_v1,
    read_receipt_v1,
    read_result_v1,
    read_verification_v1,
    receipt_v1_content_digest,
    result_v1_content_digest,
    verification_v1_content_digest,
)

WORKFLOW_REVISION_DIGEST = "sha256:agent-platform-json-v1:" + "a" * 64
ATTEMPT_PACKET_DIGEST = "sha256:agent-platform-json-v1:" + "b" * 64
RESULT_DIGEST = "sha256:agent-platform-json-v1:" + "c" * 64
VERIFICATION_DIGEST = "sha256:agent-platform-json-v1:" + "d" * 64
OUTPUT_SNAPSHOT_DIGEST = "sha256:agent-platform-json-v1:" + "e" * 64
OTHER_SNAPSHOT_DIGEST = "sha256:agent-platform-json-v1:" + "0" * 64


def attempt_envelope(payload: object) -> dict:
    return {
        "contract_kind": "attempt_packet",
        "protocol_version": 1,
        "schema_version": 1,
        "payload": payload,
    }


def result_envelope(payload: object) -> dict:
    return {
        "contract_kind": "result",
        "protocol_version": 1,
        "schema_version": 1,
        "payload": payload,
    }


def verification_envelope(payload: object) -> dict:
    return {
        "contract_kind": "verification",
        "protocol_version": 1,
        "schema_version": 1,
        "payload": payload,
    }


def receipt_envelope(payload: object) -> dict:
    return {
        "contract_kind": "receipt",
        "protocol_version": 1,
        "schema_version": 1,
        "payload": payload,
    }


def valid_attempt_payload() -> dict:
    return {
        "workflow_revision": {
            "contract_kind": "workflow_revision",
            "record_id": "rec-workflow-1",
            "content_digest": WORKFLOW_REVISION_DIGEST,
        },
        "task_id": "task-1",
        "implementer_identity": "implementer-1",
        "context_digest": "fixture-context-1",
        "workspace_snapshot_digest": "fixture-workspace-1",
        "runtime_capability_profile_identity": "fixture-runtime-1",
    }


def valid_result_payload() -> dict:
    return {
        "attempt": {
            "contract_kind": "attempt_packet",
            "record_id": "rec-attempt-1",
            "content_digest": ATTEMPT_PACKET_DIGEST,
        },
        "output_snapshot_digest": OUTPUT_SNAPSHOT_DIGEST,
        "observation": {
            "runtime_identity": "runtime-1",
            "output_snapshot_digest": OUTPUT_SNAPSHOT_DIGEST,
        },
    }


def satisfied_entry(criterion: str = "Criterion one") -> dict:
    return {
        "criterion": criterion,
        "status": "SATISFIED",
        "evidence_digest": OUTPUT_SNAPSHOT_DIGEST,
    }


def valid_verification_payload() -> dict:
    return {
        "result": {
            "contract_kind": "result",
            "record_id": "rec-result-1",
            "content_digest": RESULT_DIGEST,
        },
        "verifier_identity": "verifier-1",
        "coverage": [
            satisfied_entry("Criterion one"),
            satisfied_entry("Criterion two"),
        ],
        "verdict": "PASS",
        "findings": [],
    }


def valid_receipt_payload() -> dict:
    return {
        "verification": {
            "contract_kind": "verification",
            "record_id": "rec-verification-1",
            "content_digest": VERIFICATION_DIGEST,
        },
        "receipt_type": "terminal",
    }


def read_attempt(payload: object):
    return read_candidate(attempt_envelope(payload))


def read_result(payload: object):
    return read_candidate(result_envelope(payload))


def read_verification(payload: object):
    return read_candidate(verification_envelope(payload))


def read_receipt(payload: object):
    return read_candidate(receipt_envelope(payload))


def expected_attempt() -> AttemptPacketV1:
    return AttemptPacketV1(
        workflow_revision=RecordRef(
            contract_kind="workflow_revision",
            record_id="rec-workflow-1",
            content_digest=WORKFLOW_REVISION_DIGEST,
        ),
        task_id="task-1",
        implementer_identity="implementer-1",
        context_digest="fixture-context-1",
        workspace_snapshot_digest="fixture-workspace-1",
        runtime_capability_profile_identity="fixture-runtime-1",
    )


def expected_result() -> ResultV1:
    return ResultV1(
        attempt=RecordRef(
            contract_kind="attempt_packet",
            record_id="rec-attempt-1",
            content_digest=ATTEMPT_PACKET_DIGEST,
        ),
        output_snapshot_digest=OUTPUT_SNAPSHOT_DIGEST,
        observation=RuntimeObservationV1(
            runtime_identity="runtime-1",
            output_snapshot_digest=OUTPUT_SNAPSHOT_DIGEST,
        ),
    )


def expected_verification() -> VerificationV1:
    return VerificationV1(
        result=RecordRef(
            contract_kind="result",
            record_id="rec-result-1",
            content_digest=RESULT_DIGEST,
        ),
        verifier_identity="verifier-1",
        coverage=(
            CoverageEntryV1(
                criterion="Criterion one",
                status="SATISFIED",
                evidence_digest=OUTPUT_SNAPSHOT_DIGEST,
            ),
            CoverageEntryV1(
                criterion="Criterion two",
                status="SATISFIED",
                evidence_digest=OUTPUT_SNAPSHOT_DIGEST,
            ),
        ),
        verdict="PASS",
        findings=(),
    )


def expected_receipt() -> ReceiptV1:
    return ReceiptV1(
        verification=RecordRef(
            contract_kind="verification",
            record_id="rec-verification-1",
            content_digest=VERIFICATION_DIGEST,
        ),
        receipt_type="terminal",
    )


class AttemptPacketV1Tests(unittest.TestCase):
    def test_minimal_valid_attempt_packet_parses_deterministically(self) -> None:
        first = read_attempt(valid_attempt_payload())
        second = read_attempt(valid_attempt_payload())
        self.assertTrue(first.ok, first.reason)
        self.assertEqual(first.value.value, expected_attempt())
        self.assertEqual(second.value.value, first.value.value)

    def test_missing_or_unknown_payload_fields_reject(self) -> None:
        for field in (
            "workflow_revision",
            "task_id",
            "implementer_identity",
            "context_digest",
            "workspace_snapshot_digest",
            "runtime_capability_profile_identity",
        ):
            payload = valid_attempt_payload()
            del payload[field]
            self.assertEqual(
                read_attempt(payload).rejection_code,
                ProtocolRejectionCode.MALFORMED_PAYLOAD,
                field,
            )
        payload = valid_attempt_payload()
        payload["retry_policy"] = "never"
        self.assertEqual(
            read_attempt(payload).rejection_code,
            ProtocolRejectionCode.MALFORMED_PAYLOAD,
        )

    def test_empty_or_non_string_fields_reject(self) -> None:
        for field in (
            "task_id",
            "implementer_identity",
            "context_digest",
            "workspace_snapshot_digest",
            "runtime_capability_profile_identity",
        ):
            payload = valid_attempt_payload()
            payload[field] = ""
            self.assertEqual(
                read_attempt(payload).rejection_code,
                ProtocolRejectionCode.MALFORMED_PAYLOAD,
                field,
            )
            payload = valid_attempt_payload()
            payload[field] = 123
            self.assertEqual(
                read_attempt(payload).rejection_code,
                ProtocolRejectionCode.MALFORMED_PAYLOAD,
                field,
            )

    def test_parent_kind_other_than_workflow_revision_rejects(self) -> None:
        payload = valid_attempt_payload()
        payload["workflow_revision"]["contract_kind"] = "request"
        self.assertEqual(
            read_attempt(payload).rejection_code,
            ProtocolRejectionCode.BINDING_MISMATCH,
        )

    def test_malformed_parent_digest_rejects(self) -> None:
        payload = valid_attempt_payload()
        payload["workflow_revision"]["content_digest"] = "sha256:not-the-format:abc"
        self.assertEqual(
            read_attempt(payload).rejection_code,
            ProtocolRejectionCode.MALFORMED_RECORD_REF,
        )

    def test_binding_verifies_only_against_expected_workflow_revision(self) -> None:
        packet = read_attempt(valid_attempt_payload()).value.value
        expected = RecordRef(
            "workflow_revision", "rec-workflow-1", WORKFLOW_REVISION_DIGEST
        )
        self.assertTrue(verify_binding(packet.workflow_revision, expected).ok)
        wrong_id = RecordRef(
            "workflow_revision", "rec-workflow-other", WORKFLOW_REVISION_DIGEST
        )
        self.assertEqual(
            verify_binding(packet.workflow_revision, wrong_id).rejection_code,
            ProtocolRejectionCode.BINDING_MISMATCH,
        )

    def test_content_digest_is_stable_and_tracks_semantic_fields(self) -> None:
        packet = read_attempt(valid_attempt_payload()).value.value
        self.assertEqual(
            attempt_packet_v1_content_digest(packet),
            attempt_packet_v1_content_digest(expected_attempt()),
        )
        changed = replace(packet, implementer_identity="implementer-2")
        self.assertNotEqual(
            attempt_packet_v1_content_digest(packet),
            attempt_packet_v1_content_digest(changed),
        )

    def test_parsed_envelope_identity_survives_input_mutation(self) -> None:
        payload = valid_attempt_payload()
        parsed = read_attempt(payload).value
        digest_at_parse_time = parsed.envelope.content_digest()
        payload["implementer_identity"] = "mutated-after-parse"
        payload["workflow_revision"]["record_id"] = "rec-workflow-mutated"
        self.assertEqual(parsed.envelope.content_digest(), digest_at_parse_time)
        self.assertEqual(
            parsed.envelope.content_digest(),
            attempt_packet_v1_content_digest(parsed.value),
        )


class ResultV1Tests(unittest.TestCase):
    def test_minimal_valid_result_parses_deterministically(self) -> None:
        first = read_result(valid_result_payload())
        second = read_result(valid_result_payload())
        self.assertTrue(first.ok, first.reason)
        self.assertEqual(first.value.value, expected_result())
        self.assertEqual(second.value.value, first.value.value)

    def test_observation_digest_mismatch_rejects(self) -> None:
        payload = valid_result_payload()
        payload["observation"]["output_snapshot_digest"] = OTHER_SNAPSHOT_DIGEST
        self.assertEqual(
            read_result(payload).rejection_code,
            ProtocolRejectionCode.MALFORMED_PAYLOAD,
        )

    def test_missing_or_unknown_payload_fields_reject(self) -> None:
        for field in ("attempt", "output_snapshot_digest", "observation"):
            payload = valid_result_payload()
            del payload[field]
            self.assertEqual(
                read_result(payload).rejection_code,
                ProtocolRejectionCode.MALFORMED_PAYLOAD,
                field,
            )
        payload = valid_result_payload()
        payload["artifact_uris"] = []
        self.assertEqual(
            read_result(payload).rejection_code,
            ProtocolRejectionCode.MALFORMED_PAYLOAD,
        )
        observation = valid_result_payload()
        observation["observation"]["host_metrics"] = {}
        self.assertEqual(
            read_result(observation).rejection_code,
            ProtocolRejectionCode.MALFORMED_PAYLOAD,
        )

    def test_empty_observation_identity_rejects(self) -> None:
        payload = valid_result_payload()
        payload["observation"]["runtime_identity"] = ""
        self.assertEqual(
            read_result(payload).rejection_code,
            ProtocolRejectionCode.MALFORMED_PAYLOAD,
        )

    def test_parent_kind_other_than_attempt_packet_rejects(self) -> None:
        payload = valid_result_payload()
        payload["attempt"]["contract_kind"] = "workflow_revision"
        self.assertEqual(
            read_result(payload).rejection_code,
            ProtocolRejectionCode.BINDING_MISMATCH,
        )

    def test_malformed_parent_digest_rejects(self) -> None:
        payload = valid_result_payload()
        payload["attempt"]["content_digest"] = "not-a-digest"
        self.assertEqual(
            read_result(payload).rejection_code,
            ProtocolRejectionCode.MALFORMED_RECORD_REF,
        )

    def test_content_digest_is_stable_and_tracks_semantic_fields(self) -> None:
        result = read_result(valid_result_payload()).value.value
        self.assertEqual(
            result_v1_content_digest(result),
            result_v1_content_digest(expected_result()),
        )
        changed_observation = replace(
            result,
            observation=RuntimeObservationV1(
                runtime_identity="runtime-2",
                output_snapshot_digest=result.output_snapshot_digest,
            ),
        )
        self.assertNotEqual(
            result_v1_content_digest(result),
            result_v1_content_digest(changed_observation),
        )

    def test_parsed_envelope_identity_survives_input_mutation(self) -> None:
        payload = valid_result_payload()
        parsed = read_result(payload).value
        digest_at_parse_time = parsed.envelope.content_digest()
        payload["output_snapshot_digest"] = OTHER_SNAPSHOT_DIGEST
        payload["observation"]["runtime_identity"] = "mutated-after-parse"
        self.assertEqual(parsed.envelope.content_digest(), digest_at_parse_time)
        self.assertEqual(
            parsed.envelope.content_digest(),
            result_v1_content_digest(parsed.value),
        )


class VerificationV1Tests(unittest.TestCase):
    def test_minimal_valid_verification_parses_deterministically(self) -> None:
        first = read_verification(valid_verification_payload())
        second = read_verification(valid_verification_payload())
        self.assertTrue(first.ok, first.reason)
        self.assertEqual(first.value.value, expected_verification())
        self.assertEqual(second.value.value, first.value.value)

    def test_missing_or_unknown_payload_fields_reject(self) -> None:
        for field in ("result", "verifier_identity", "coverage", "verdict", "findings"):
            payload = valid_verification_payload()
            del payload[field]
            self.assertEqual(
                read_verification(payload).rejection_code,
                ProtocolRejectionCode.MALFORMED_PAYLOAD,
                field,
            )
        payload = valid_verification_payload()
        payload["risk_tier"] = "low"
        self.assertEqual(
            read_verification(payload).rejection_code,
            ProtocolRejectionCode.MALFORMED_PAYLOAD,
        )
        entry_extra = valid_verification_payload()
        entry_extra["coverage"][0]["confidence"] = 0.9
        self.assertEqual(
            read_verification(entry_extra).rejection_code,
            ProtocolRejectionCode.MALFORMED_PAYLOAD,
        )

    def test_empty_or_non_list_coverage_rejects(self) -> None:
        payload = valid_verification_payload()
        payload["coverage"] = []
        self.assertEqual(
            read_verification(payload).rejection_code,
            ProtocolRejectionCode.MALFORMED_PAYLOAD,
        )
        payload = valid_verification_payload()
        payload["coverage"] = "not-a-list"
        self.assertEqual(
            read_verification(payload).rejection_code,
            ProtocolRejectionCode.MALFORMED_PAYLOAD,
        )
        payload = valid_verification_payload()
        payload["coverage"] = (satisfied_entry(),)
        self.assertEqual(
            read_verification(payload).rejection_code,
            ProtocolRejectionCode.MALFORMED_PAYLOAD,
        )

    def test_status_outside_the_four_value_enum_rejects(self) -> None:
        for status in ("pass", "UNKNOWN", "", 1, None):
            payload = valid_verification_payload()
            payload["coverage"][0]["status"] = status
            self.assertEqual(
                read_verification(payload).rejection_code,
                ProtocolRejectionCode.MALFORMED_PAYLOAD,
                repr(status),
            )

    def test_evidence_digest_set_when_status_not_satisfied_rejects(self) -> None:
        for status in ("UNSATISFIED", "BLOCKED", "UNPROVEN"):
            payload = valid_verification_payload()
            payload["coverage"][0]["status"] = status
            payload["coverage"][0]["evidence_digest"] = OUTPUT_SNAPSHOT_DIGEST
            payload["verdict"] = "FAIL"
            self.assertEqual(
                read_verification(payload).rejection_code,
                ProtocolRejectionCode.MALFORMED_PAYLOAD,
                status,
            )

    def test_evidence_digest_missing_malformed_or_null_when_satisfied_rejects(
        self,
    ) -> None:
        for evidence in (None, "", "not-a-digest", "sha256:short:abc", 123):
            payload = valid_verification_payload()
            payload["coverage"][0]["evidence_digest"] = evidence
            self.assertEqual(
                read_verification(payload).rejection_code,
                ProtocolRejectionCode.MALFORMED_PAYLOAD,
                repr(evidence),
            )
        missing = valid_verification_payload()
        del missing["coverage"][0]["evidence_digest"]
        self.assertEqual(
            read_verification(missing).rejection_code,
            ProtocolRejectionCode.MALFORMED_PAYLOAD,
        )

    def test_declared_verdict_inconsistent_with_coverage_rejects(self) -> None:
        all_satisfied = valid_verification_payload()
        all_satisfied["verdict"] = "FAIL"
        self.assertEqual(
            read_verification(all_satisfied).rejection_code,
            ProtocolRejectionCode.MALFORMED_PAYLOAD,
        )

        one_unsatisfied = valid_verification_payload()
        one_unsatisfied["coverage"][0]["status"] = "UNSATISFIED"
        one_unsatisfied["coverage"][0]["evidence_digest"] = None
        one_unsatisfied["verdict"] = "PASS"
        self.assertEqual(
            read_verification(one_unsatisfied).rejection_code,
            ProtocolRejectionCode.MALFORMED_PAYLOAD,
        )

        blocked_declared_fail = valid_verification_payload()
        blocked_declared_fail["coverage"][0]["status"] = "BLOCKED"
        blocked_declared_fail["coverage"][0]["evidence_digest"] = None
        blocked_declared_fail["verdict"] = "FAIL"
        self.assertEqual(
            read_verification(blocked_declared_fail).rejection_code,
            ProtocolRejectionCode.MALFORMED_PAYLOAD,
        )

        unproven_declared_blocked = valid_verification_payload()
        unproven_declared_blocked["coverage"][0]["status"] = "UNPROVEN"
        unproven_declared_blocked["coverage"][0]["evidence_digest"] = None
        unproven_declared_blocked["verdict"] = "BLOCKED"
        self.assertEqual(
            read_verification(unproven_declared_blocked).rejection_code,
            ProtocolRejectionCode.MALFORMED_PAYLOAD,
        )

        invalid_verdict = valid_verification_payload()
        invalid_verdict["verdict"] = "MAYBE"
        self.assertEqual(
            read_verification(invalid_verdict).rejection_code,
            ProtocolRejectionCode.MALFORMED_PAYLOAD,
        )

    def test_verdict_total_function_accepts_each_outcome(self) -> None:
        blocked = valid_verification_payload()
        blocked["coverage"][0]["status"] = "BLOCKED"
        blocked["coverage"][0]["evidence_digest"] = None
        blocked["verdict"] = "BLOCKED"
        blocked["findings"] = ["Criterion one could not be evaluated"]
        self.assertTrue(read_verification(blocked).ok, read_verification(blocked).reason)

        unproven_mix = valid_verification_payload()
        unproven_mix["coverage"][0]["status"] = "UNSATISFIED"
        unproven_mix["coverage"][0]["evidence_digest"] = None
        unproven_mix["coverage"][1]["status"] = "UNPROVEN"
        unproven_mix["coverage"][1]["evidence_digest"] = None
        unproven_mix["verdict"] = "FAIL"
        unproven_mix["findings"] = ["Digest mismatch", "No evidence observed"]
        self.assertTrue(
            read_verification(unproven_mix).ok, read_verification(unproven_mix).reason
        )

    def test_empty_or_non_string_findings_reject(self) -> None:
        payload = valid_verification_payload()
        payload["findings"] = ["ok", ""]
        self.assertEqual(
            read_verification(payload).rejection_code,
            ProtocolRejectionCode.MALFORMED_PAYLOAD,
        )
        payload = valid_verification_payload()
        payload["findings"] = ("a finding",)
        self.assertEqual(
            read_verification(payload).rejection_code,
            ProtocolRejectionCode.MALFORMED_PAYLOAD,
        )

    def test_parent_kind_other_than_result_rejects(self) -> None:
        payload = valid_verification_payload()
        payload["result"]["contract_kind"] = "attempt_packet"
        self.assertEqual(
            read_verification(payload).rejection_code,
            ProtocolRejectionCode.BINDING_MISMATCH,
        )

    def test_content_digest_is_stable_and_tracks_semantic_fields(self) -> None:
        verification = read_verification(valid_verification_payload()).value.value
        self.assertEqual(
            verification_v1_content_digest(verification),
            verification_v1_content_digest(expected_verification()),
        )
        changed_status = replace(
            verification,
            coverage=(
                CoverageEntryV1(
                    criterion=verification.coverage[0].criterion,
                    status="UNSATISFIED",
                    evidence_digest=None,
                ),
                verification.coverage[1],
            ),
            verdict="FAIL",
            findings=("Digest mismatch",),
        )
        self.assertNotEqual(
            verification_v1_content_digest(verification),
            verification_v1_content_digest(changed_status),
        )

    def test_coverage_order_is_semantically_meaningful(self) -> None:
        verification = read_verification(valid_verification_payload()).value.value
        reordered = replace(
            verification, coverage=tuple(reversed(verification.coverage))
        )
        self.assertNotEqual(
            verification_v1_content_digest(verification),
            verification_v1_content_digest(reordered),
        )

    def test_parsed_envelope_identity_survives_input_mutation(self) -> None:
        payload = valid_verification_payload()
        parsed = read_verification(payload).value
        digest_at_parse_time = parsed.envelope.content_digest()
        payload["coverage"][0]["status"] = "UNSATISFIED"
        payload["coverage"][0]["evidence_digest"] = None
        payload["verdict"] = "FAIL"
        payload["verifier_identity"] = "mutated-after-parse"
        self.assertEqual(parsed.envelope.content_digest(), digest_at_parse_time)
        self.assertEqual(
            parsed.envelope.content_digest(),
            verification_v1_content_digest(parsed.value),
        )


class ReceiptV1Tests(unittest.TestCase):
    def test_minimal_valid_receipt_parses_deterministically(self) -> None:
        first = read_receipt(valid_receipt_payload())
        second = read_receipt(valid_receipt_payload())
        self.assertTrue(first.ok, first.reason)
        self.assertEqual(first.value.value, expected_receipt())
        self.assertEqual(second.value.value, first.value.value)

    def test_receipt_type_other_than_terminal_rejects(self) -> None:
        for receipt_type in ("checkpoint", "", "TERMINAL", None, 1):
            payload = valid_receipt_payload()
            payload["receipt_type"] = receipt_type
            self.assertEqual(
                read_receipt(payload).rejection_code,
                ProtocolRejectionCode.MALFORMED_PAYLOAD,
                repr(receipt_type),
            )
        missing = valid_receipt_payload()
        del missing["receipt_type"]
        self.assertEqual(
            read_receipt(missing).rejection_code,
            ProtocolRejectionCode.MALFORMED_PAYLOAD,
        )

    def test_missing_or_unknown_payload_fields_reject(self) -> None:
        payload = valid_receipt_payload()
        del payload["verification"]
        self.assertEqual(
            read_receipt(payload).rejection_code,
            ProtocolRejectionCode.MALFORMED_PAYLOAD,
        )
        payload = valid_receipt_payload()
        payload["issued_at"] = "2026-01-01T00:00:00Z"
        self.assertEqual(
            read_receipt(payload).rejection_code,
            ProtocolRejectionCode.MALFORMED_PAYLOAD,
        )

    def test_parent_kind_other_than_verification_rejects(self) -> None:
        payload = valid_receipt_payload()
        payload["verification"]["contract_kind"] = "result"
        self.assertEqual(
            read_receipt(payload).rejection_code,
            ProtocolRejectionCode.BINDING_MISMATCH,
        )

    def test_binding_verifies_only_against_expected_verification(self) -> None:
        receipt = read_receipt(valid_receipt_payload()).value.value
        expected = RecordRef(
            "verification", "rec-verification-1", VERIFICATION_DIGEST
        )
        self.assertTrue(verify_binding(receipt.verification, expected).ok)
        stale = RecordRef(
            "verification", "rec-verification-1", OTHER_SNAPSHOT_DIGEST
        )
        self.assertEqual(
            verify_binding(receipt.verification, stale).rejection_code,
            ProtocolRejectionCode.BINDING_MISMATCH,
        )

    def test_content_digest_is_stable(self) -> None:
        receipt = read_receipt(valid_receipt_payload()).value.value
        self.assertEqual(
            receipt_v1_content_digest(receipt),
            receipt_v1_content_digest(expected_receipt()),
        )
        substituted = replace(
            receipt,
            verification=RecordRef(
                "verification", "rec-verification-other", VERIFICATION_DIGEST
            ),
        )
        self.assertNotEqual(
            receipt_v1_content_digest(receipt),
            receipt_v1_content_digest(substituted),
        )

    def test_parsed_envelope_identity_survives_input_mutation(self) -> None:
        payload = valid_receipt_payload()
        parsed = read_receipt(payload).value
        digest_at_parse_time = parsed.envelope.content_digest()
        payload["receipt_type"] = "checkpoint"
        payload["verification"]["record_id"] = "rec-verification-mutated"
        self.assertEqual(parsed.envelope.content_digest(), digest_at_parse_time)
        self.assertEqual(
            parsed.envelope.content_digest(),
            receipt_v1_content_digest(parsed.value),
        )


class DirectReaderRejectionTests(unittest.TestCase):
    def test_direct_readers_raise_typed_rejections(self) -> None:
        with self.assertRaisesRegex(Exception, "attempt_packet_payload"):
            read_attempt_packet_v1({"task_id": "task-1"})
        with self.assertRaisesRegex(Exception, "result_observation_output_snapshot_digest_mismatch"):
            read_result_v1(
                {
                    "attempt": {
                        "contract_kind": "attempt_packet",
                        "record_id": "rec-attempt-1",
                        "content_digest": ATTEMPT_PACKET_DIGEST,
                    },
                    "output_snapshot_digest": OUTPUT_SNAPSHOT_DIGEST,
                    "observation": {
                        "runtime_identity": "runtime-1",
                        "output_snapshot_digest": OTHER_SNAPSHOT_DIGEST,
                    },
                }
            )
        with self.assertRaisesRegex(Exception, "verification_coverage_empty"):
            read_verification_v1(
                {
                    "result": {
                        "contract_kind": "result",
                        "record_id": "rec-result-1",
                        "content_digest": RESULT_DIGEST,
                    },
                    "verifier_identity": "verifier-1",
                    "coverage": [],
                    "verdict": "PASS",
                    "findings": [],
                }
            )
        with self.assertRaisesRegex(Exception, "receipt_type_not_terminal"):
            read_receipt_v1(
                {
                    "verification": {
                        "contract_kind": "verification",
                        "record_id": "rec-verification-1",
                        "content_digest": VERIFICATION_DIGEST,
                    },
                    "receipt_type": "checkpoint",
                }
            )


if __name__ == "__main__":
    unittest.main()
