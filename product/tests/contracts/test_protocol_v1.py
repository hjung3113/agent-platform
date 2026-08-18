from __future__ import annotations

import unittest

from kernel.protocol import (
    ContractKind,
    ProtocolRejectionCode,
    RecordRef,
    read_candidate,
    read_published_record,
    verify_binding,
)
from kernel.protocol_v1 import (
    RequestV1,
    TaskV1,
    WorkflowRevisionV1,
    read_request_v1,
    read_workflow_revision_v1,
    request_v1_content_digest,
    workflow_revision_v1_content_digest,
)

REQUEST_DIGEST = "sha256:agent-platform-json-v1:" + "a" * 64


def request_envelope(payload: object) -> dict:
    return {
        "contract_kind": "request",
        "protocol_version": 1,
        "schema_version": 1,
        "payload": payload,
    }


def workflow_envelope(payload: object) -> dict:
    return {
        "contract_kind": "workflow_revision",
        "protocol_version": 1,
        "schema_version": 1,
        "payload": payload,
    }


def valid_request_payload() -> dict:
    return {
        "objective": "Ship the M0 protocol slice",
        "scope": ["docs/plans/active/m0-minimum-protocol-foundation.md"],
        "acceptance_criteria": ["All contract tests pass"],
    }


def valid_workflow_payload() -> dict:
    return {
        "request": {
            "contract_kind": "request",
            "record_id": "rec-request-1",
            "content_digest": REQUEST_DIGEST,
        },
        "task": {
            "task_id": "task-1",
            "objective": "Implement exact dispatch",
            "acceptance_criteria": ["Dispatch is exact"],
        },
    }


def read_request(payload: object):
    return read_candidate(request_envelope(payload))


def read_workflow(payload: object):
    return read_candidate(workflow_envelope(payload))


class RequestV1Tests(unittest.TestCase):
    def test_minimal_valid_request_parses_deterministically(self) -> None:
        expected = RequestV1(
            objective="Ship the M0 protocol slice",
            scope=("docs/plans/active/m0-minimum-protocol-foundation.md",),
            acceptance_criteria=("All contract tests pass",),
        )
        first = read_request(valid_request_payload())
        second = read_request(valid_request_payload())
        self.assertTrue(first.ok)
        self.assertEqual(first.value.value, expected)
        self.assertEqual(second.value.value, first.value.value)

    def test_empty_objective_rejects(self) -> None:
        payload = valid_request_payload()
        payload["objective"] = ""
        result = read_request(payload)
        self.assertEqual(result.rejection_code, ProtocolRejectionCode.MALFORMED_PAYLOAD)

    def test_malformed_scope_rejects(self) -> None:
        payload = valid_request_payload()
        payload["scope"] = "not-a-list"
        self.assertEqual(
            read_request(payload).rejection_code,
            ProtocolRejectionCode.MALFORMED_PAYLOAD,
        )
        payload["scope"] = ["ok", ""]
        self.assertEqual(
            read_request(payload).rejection_code,
            ProtocolRejectionCode.MALFORMED_PAYLOAD,
        )
        del payload["scope"]
        self.assertEqual(
            read_request(payload).rejection_code,
            ProtocolRejectionCode.MALFORMED_PAYLOAD,
        )

    def test_missing_or_empty_acceptance_criteria_reject(self) -> None:
        payload = valid_request_payload()
        payload["acceptance_criteria"] = []
        self.assertEqual(
            read_request(payload).rejection_code,
            ProtocolRejectionCode.MALFORMED_PAYLOAD,
        )
        del payload["acceptance_criteria"]
        self.assertEqual(
            read_request(payload).rejection_code,
            ProtocolRejectionCode.MALFORMED_PAYLOAD,
        )

    def test_unknown_payload_fields_reject(self) -> None:
        payload = valid_request_payload()
        payload["runtime_profile"] = "opencode"
        self.assertEqual(
            read_request(payload).rejection_code,
            ProtocolRejectionCode.MALFORMED_PAYLOAD,
        )

    def test_request_content_digest_excludes_nothing_semantic_and_is_stable(self) -> None:
        request = read_request(valid_request_payload()).value.value
        self.assertEqual(
            request_v1_content_digest(request),
            request_v1_content_digest(read_request(valid_request_payload()).value.value),
        )
        changed = RequestV1(
            objective=request.objective,
            scope=request.scope,
            acceptance_criteria=request.acceptance_criteria + ("Another check",),
        )
        self.assertNotEqual(
            request_v1_content_digest(request),
            request_v1_content_digest(changed),
        )

    def test_parsed_envelope_identity_survives_input_mutation(self) -> None:
        payload = valid_request_payload()
        parsed = read_request(payload).value
        digest_at_parse_time = parsed.envelope.content_digest()
        payload["scope"].append("docs/plans/active/m1-authoritative-publication.md")
        payload["objective"] = "Mutated after parse"
        self.assertEqual(parsed.envelope.content_digest(), digest_at_parse_time)
        self.assertEqual(
            parsed.envelope.content_digest(),
            request_v1_content_digest(parsed.value),
        )


class WorkflowRevisionV1Tests(unittest.TestCase):
    def test_minimal_valid_revision_parses_deterministically(self) -> None:
        expected = WorkflowRevisionV1(
            request=RecordRef(
                contract_kind="request",
                record_id="rec-request-1",
                content_digest=REQUEST_DIGEST,
            ),
            task=TaskV1(
                task_id="task-1",
                objective="Implement exact dispatch",
                acceptance_criteria=("Dispatch is exact",),
            ),
        )
        first = read_workflow(valid_workflow_payload())
        second = read_workflow(valid_workflow_payload())
        self.assertTrue(first.ok)
        self.assertEqual(first.value.value, expected)
        self.assertEqual(second.value.value, first.value.value)

    def test_missing_request_binding_rejects(self) -> None:
        payload = valid_workflow_payload()
        del payload["request"]
        self.assertEqual(
            read_workflow(payload).rejection_code,
            ProtocolRejectionCode.MALFORMED_PAYLOAD,
        )

    def test_parent_kind_other_than_request_rejects(self) -> None:
        payload = valid_workflow_payload()
        payload["request"]["contract_kind"] = "workflow_revision"
        self.assertEqual(
            read_workflow(payload).rejection_code,
            ProtocolRejectionCode.BINDING_MISMATCH,
        )

    def test_malformed_parent_digest_rejects(self) -> None:
        payload = valid_workflow_payload()
        payload["request"]["content_digest"] = "sha256:not-the-format:abc"
        self.assertEqual(
            read_workflow(payload).rejection_code,
            ProtocolRejectionCode.MALFORMED_RECORD_REF,
        )

    def test_wrong_request_id_rejects_against_expected_parent(self) -> None:
        revision = read_workflow(valid_workflow_payload()).value.value
        expected = RecordRef(
            contract_kind="request",
            record_id="rec-request-other",
            content_digest=REQUEST_DIGEST,
        )
        result = verify_binding(revision.request, expected)
        self.assertEqual(
            result.rejection_code, ProtocolRejectionCode.BINDING_MISMATCH
        )
        self.assertEqual(
            verify_binding(
                revision.request,
                RecordRef("request", "rec-request-1", REQUEST_DIGEST),
            ).ok,
            True,
        )

    def test_verify_binding_rejects_kind_and_digest_mismatch(self) -> None:
        reference = RecordRef("request", "rec-request-1", REQUEST_DIGEST)
        self.assertEqual(
            verify_binding(reference, RecordRef("decision", "rec-request-1", REQUEST_DIGEST)).rejection_code,
            ProtocolRejectionCode.BINDING_MISMATCH,
        )
        self.assertEqual(
            verify_binding(
                reference,
                RecordRef("request", "rec-request-1", "sha256:agent-platform-json-v1:" + "b" * 64),
            ).rejection_code,
            ProtocolRejectionCode.BINDING_MISMATCH,
        )

    def test_single_task_is_enforced_by_construction(self) -> None:
        payload = valid_workflow_payload()
        payload["tasks"] = [payload["task"], payload["task"]]
        self.assertEqual(
            read_workflow(payload).rejection_code,
            ProtocolRejectionCode.MALFORMED_PAYLOAD,
        )

    def test_unknown_workflow_fields_reject(self) -> None:
        payload = valid_workflow_payload()
        payload["retry_policy"] = "never"
        self.assertEqual(
            read_workflow(payload).rejection_code,
            ProtocolRejectionCode.MALFORMED_PAYLOAD,
        )

    def test_unknown_or_empty_task_fields_reject(self) -> None:
        payload = valid_workflow_payload()
        payload["task"]["resources"] = {"cpu": 1}
        self.assertEqual(
            read_workflow(payload).rejection_code,
            ProtocolRejectionCode.MALFORMED_PAYLOAD,
        )
        empty = valid_workflow_payload()
        empty["task"]["task_id"] = ""
        self.assertEqual(
            read_workflow(empty).rejection_code,
            ProtocolRejectionCode.MALFORMED_PAYLOAD,
        )
        no_criteria = valid_workflow_payload()
        no_criteria["task"]["acceptance_criteria"] = []
        self.assertEqual(
            read_workflow(no_criteria).rejection_code,
            ProtocolRejectionCode.MALFORMED_PAYLOAD,
        )

    def test_revision_digest_changes_when_binding_or_task_changes(self) -> None:
        revision = read_workflow(valid_workflow_payload()).value.value
        other_digest = workflow_revision_v1_content_digest(
            WorkflowRevisionV1(
                request=RecordRef(
                    "request", "rec-request-1", "sha256:agent-platform-json-v1:" + "c" * 64
                ),
                task=revision.task,
            )
        )
        self.assertNotEqual(workflow_revision_v1_content_digest(revision), other_digest)

    def test_parsed_envelope_identity_survives_input_mutation(self) -> None:
        payload = valid_workflow_payload()
        parsed = read_workflow(payload).value
        digest_at_parse_time = parsed.envelope.content_digest()
        payload["task"]["acceptance_criteria"].append("Later mutation")
        payload["request"]["record_id"] = "rec-request-mutated"
        self.assertEqual(parsed.envelope.content_digest(), digest_at_parse_time)
        self.assertEqual(
            parsed.envelope.content_digest(),
            workflow_revision_v1_content_digest(parsed.value),
        )

    def test_declared_published_digest_must_equal_recomputed_candidate_digest(self) -> None:
        request = read_request(valid_request_payload()).value.value
        computed = request_v1_content_digest(request)
        record = {
            "record_id": "rec-request-1",
            "content_digest": computed,
            **request_envelope(valid_request_payload()),
        }
        self.assertTrue(read_published_record(record).ok)
        record["content_digest"] = "sha256:agent-platform-json-v1:" + "d" * 64
        self.assertEqual(
            read_published_record(record).rejection_code,
            ProtocolRejectionCode.CONTENT_DIGEST_MISMATCH,
        )

    def test_declared_published_digest_must_equal_recomputed_revision_digest(self) -> None:
        revision = read_workflow(valid_workflow_payload()).value.value
        computed = workflow_revision_v1_content_digest(revision)
        record = {
            "record_id": "rec-workflow-1",
            "content_digest": computed,
            **workflow_envelope(valid_workflow_payload()),
        }
        self.assertTrue(read_published_record(record).ok)
        record["content_digest"] = "sha256:agent-platform-json-v1:" + "e" * 64
        self.assertEqual(
            read_published_record(record).rejection_code,
            ProtocolRejectionCode.CONTENT_DIGEST_MISMATCH,
        )

    def test_canonical_conversion_ignores_key_order_but_not_array_order(self) -> None:
        base = read_request(valid_request_payload()).value.value
        two_criteria = RequestV1(
            objective=base.objective,
            scope=base.scope,
            acceptance_criteria=base.acceptance_criteria + ("Second check",),
        )
        key_order_a = read_request(
            {
                "objective": base.objective,
                "scope": list(base.scope),
                "acceptance_criteria": list(two_criteria.acceptance_criteria),
            }
        ).value.value
        key_order_b = read_request(
            {
                "acceptance_criteria": list(two_criteria.acceptance_criteria),
                "scope": list(base.scope),
                "objective": base.objective,
            }
        ).value.value
        self.assertEqual(
            request_v1_content_digest(key_order_a),
            request_v1_content_digest(key_order_b),
        )
        reversed_order = RequestV1(
            objective=base.objective,
            scope=base.scope,
            acceptance_criteria=("Second check", *base.acceptance_criteria),
        )
        self.assertNotEqual(
            request_v1_content_digest(two_criteria),
            request_v1_content_digest(reversed_order),
        )

    def test_direct_readers_raise_typed_rejections(self) -> None:
        with self.assertRaisesRegex(Exception, "request_objective_empty"):
            read_request_v1({"objective": "", "scope": [], "acceptance_criteria": ["a"]})
        with self.assertRaisesRegex(Exception, "workflow_revision_payload"):
            read_workflow_revision_v1({"task": {}})


if __name__ == "__main__":
    unittest.main()
