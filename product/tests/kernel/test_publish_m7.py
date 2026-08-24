from __future__ import annotations

import tempfile
import unittest

from kernel.canonical import content_digest
from kernel.protocol import (
    CandidateEnvelope,
    ContractKind,
    ParsedCandidate,
    RecordRef,
    read_candidate,
)
from kernel.protocol_v1 import (
    RESULT_SNAPSHOT_EVIDENCE_CLASS,
    TaskV1,
    WorkflowRevisionV1,
    schema_version_for_kind,
)
from kernel.publish import Published, PublishRejectionCode, Rejected, publish


REQUEST_CONTENT_DIGEST = content_digest({"fixture": "m7-request"})
OUTPUT_DIGEST = content_digest({"fixture": "m7-output"})
RUNTIME_PROFILE = content_digest({"fixture": "m7-runtime"})
VERIFIER_PROFILE = content_digest({"fixture": "m7-verifier-profile"})
EXECUTION_IDENTITY = content_digest({"fixture": "m7-execution"})
VERIFIER_EXECUTION_IDENTITY = content_digest({"fixture": "m7-verifier-execution"})

TASK_ONE_CRITERIA = ["task one criterion"]
TASK_TWO_CRITERIA = ["task two criterion"]


def dispatch(contract_kind: str, payload: dict):
    result = read_candidate(
        {
            "contract_kind": contract_kind,
            "protocol_version": 1,
            "schema_version": schema_version_for_kind(ContractKind(contract_kind)),
            "payload": payload,
        }
    )
    assert result.ok, result.reason
    return result.value


def request_candidate():
    return dispatch(
        "request",
        {
            "objective": "Exercise M7 publication",
            "scope": ["docs/plans/active/m7-orchestration-expansion.md"],
            "acceptance_criteria": ["The M7 revision publishes"],
        },
    )


def task_payload(task_id: str, criteria: list[str]) -> dict:
    return {
        "task_id": task_id,
        "objective": f"Objective for {task_id}",
        "acceptance_criteria": criteria,
    }


def workflow_candidate(parent: RecordRef, tasks: list[dict]):
    return dispatch(
        "workflow_revision",
        {"request": parent.to_canonical_value(), "tasks": tasks},
    )


def attempt_candidate(parent: RecordRef, task_id: str):
    return dispatch(
        "attempt_packet",
        {
            "workflow_revision": parent.to_canonical_value(),
            "task_id": task_id,
            "implementer_identity": "implementer-m7",
            "context_digest": content_digest({"fixture": "m7-context", "task": task_id}),
            "workspace_snapshot_digest": content_digest({"fixture": "m7-workspace"}),
            "runtime_capability_profile_identity": RUNTIME_PROFILE,
        },
    )


def result_candidate(parent: RecordRef):
    return dispatch(
        "result",
        {
            "attempt": parent.to_canonical_value(),
            "output_snapshot_digest": OUTPUT_DIGEST,
            "observation": {
                "runtime_identity": RUNTIME_PROFILE,
                "output_snapshot_digest": OUTPUT_DIGEST,
                "execution_identity": EXECUTION_IDENTITY,
            },
        },
    )


def verification_candidate(parent: RecordRef, criteria: list[str]):
    return dispatch(
        "verification",
        {
            "result": parent.to_canonical_value(),
            "verifier_identity": "verifier-m7",
            "verifier_runtime_capability_profile_identity": VERIFIER_PROFILE,
            "verifier_execution_identity": VERIFIER_EXECUTION_IDENTITY,
            "coverage": [
                {
                    "criterion": criterion,
                    "status": "SATISFIED",
                    "evidence_digest": OUTPUT_DIGEST,
                    "evidence_class": RESULT_SNAPSHOT_EVIDENCE_CLASS,
                }
                for criterion in criteria
            ],
            "verdict": "PASS",
            "findings": [],
        },
    )


class PublishM7Tests(unittest.TestCase):
    def setUp(self) -> None:
        state = tempfile.TemporaryDirectory()
        self.addCleanup(state.cleanup)
        self.state = state.name

    def publish_request(self) -> Published:
        result = publish(self.state, None, request_candidate(), None, "m7-request")
        self.assertIsInstance(result, Published)
        assert isinstance(result, Published)
        return result

    def publish_two_task_workflow(self) -> tuple[Published, Published]:
        request = self.publish_request()
        result = publish(
            self.state,
            request.run_id,
            workflow_candidate(
                request.record_ref,
                [
                    task_payload("task-1", TASK_ONE_CRITERIA),
                    task_payload("task-2", TASK_TWO_CRITERIA),
                ],
            ),
            request.record_ref,
            "m7-workflow",
        )
        self.assertIsInstance(result, Published)
        assert isinstance(result, Published)
        return request, result

    def test_multi_task_workflow_publishes_and_any_task_id_binds(self) -> None:
        request, workflow = self.publish_two_task_workflow()
        attempt = publish(
            self.state,
            request.run_id,
            attempt_candidate(workflow.record_ref, "task-2"),
            workflow.record_ref,
            "m7-attempt-task-2",
        )

        self.assertIsInstance(attempt, Published)

    def test_unknown_task_id_rejects_attempt_binding(self) -> None:
        request, workflow = self.publish_two_task_workflow()
        rejected = publish(
            self.state,
            request.run_id,
            attempt_candidate(workflow.record_ref, "unknown-task"),
            workflow.record_ref,
            "m7-attempt-unknown",
        )

        self.assertIsInstance(rejected, Rejected)
        assert isinstance(rejected, Rejected)
        self.assertEqual(
            rejected.code, PublishRejectionCode.ATTEMPT_TASK_BINDING_MISMATCH
        )

    def test_verification_coverage_uses_attempt_bound_task(self) -> None:
        request, workflow = self.publish_two_task_workflow()
        attempt = publish(
            self.state,
            request.run_id,
            attempt_candidate(workflow.record_ref, "task-2"),
            workflow.record_ref,
            "m7-attempt-task-2",
        )
        self.assertIsInstance(attempt, Published)
        assert isinstance(attempt, Published)
        result = publish(
            self.state,
            request.run_id,
            result_candidate(attempt.record_ref),
            attempt.record_ref,
            "m7-result-task-2",
        )
        self.assertIsInstance(result, Published)
        assert isinstance(result, Published)
        verification = publish(
            self.state,
            request.run_id,
            verification_candidate(result.record_ref, TASK_TWO_CRITERIA),
            result.record_ref,
            "m7-verification-task-2",
        )

        self.assertIsInstance(verification, Published)

    def test_publish_boundary_rejects_duplicate_task_ids(self) -> None:
        request = self.publish_request()
        duplicate = WorkflowRevisionV1(
            request=request.record_ref,
            tasks=(
                TaskV1("same", "first", ("first criterion",)),
                TaskV1("same", "second", ("second criterion",)),
            ),
        )
        candidate = ParsedCandidate(
            envelope=CandidateEnvelope(
                contract_kind=ContractKind.WORKFLOW_REVISION,
                protocol_version=1,
                schema_version=2,
                payload=duplicate.to_canonical_value(),
            ),
            value=duplicate,
        )
        rejected = publish(
            self.state,
            request.run_id,
            candidate,
            request.record_ref,
            "m7-duplicate-workflow",
        )

        self.assertIsInstance(rejected, Rejected)
        assert isinstance(rejected, Rejected)
        self.assertEqual(
            rejected.code, PublishRejectionCode.WORKFLOW_REVISION_TASK_ID_DUPLICATE
        )


if __name__ == "__main__":
    unittest.main()
