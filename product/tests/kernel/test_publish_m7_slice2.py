from __future__ import annotations

import tempfile
import unittest

from kernel.protocol import CandidateEnvelope, ContractKind, ParsedCandidate, RecordRef, read_candidate
from kernel.protocol_v1 import TaskV1, WorkflowRevisionV1, schema_version_for_kind
from kernel.publish import Published, PublishRejectionCode, Rejected, publish
from kernel.replay import replay


def task(task_id: str, depends_on: tuple[str, ...] = ()) -> TaskV1:
    return TaskV1(
        task_id=task_id,
        objective=f"Objective for {task_id}",
        acceptance_criteria=(f"Criterion for {task_id}",),
        depends_on=depends_on,
    )


def request_candidate():
    result = read_candidate(
        {
            "contract_kind": "request",
            "protocol_version": 1,
            "schema_version": 1,
            "payload": {
                "objective": "Exercise the M7 slice-2 publish boundary",
                "scope": [],
                "acceptance_criteria": ["The graph is admitted"],
            },
        }
    )
    assert result.ok, result.reason
    return result.value


def workflow_candidate(parent: RecordRef, tasks: tuple[TaskV1, ...]) -> ParsedCandidate:
    revision = WorkflowRevisionV1(request=parent, tasks=tasks)
    return ParsedCandidate(
        envelope=CandidateEnvelope(
            contract_kind=ContractKind.WORKFLOW_REVISION,
            protocol_version=1,
            schema_version=schema_version_for_kind(ContractKind.WORKFLOW_REVISION),
            payload=revision.to_canonical_value(),
        ),
        value=revision,
    )


class PublishM7Slice2Tests(unittest.TestCase):
    def setUp(self) -> None:
        state = tempfile.TemporaryDirectory()
        self.addCleanup(state.cleanup)
        self.state = state.name

    def publish_request(self) -> Published:
        result = publish(self.state, None, request_candidate(), None, "slice2-request")
        self.assertIsInstance(result, Published)
        assert isinstance(result, Published)
        return result

    def test_valid_dag_publishes_at_workflow_revision_successor_position(self) -> None:
        request = self.publish_request()
        result = publish(
            self.state,
            request.run_id,
            workflow_candidate(
                request.record_ref,
                (task("task-a"), task("task-b", ("task-a",))),
            ),
            request.record_ref,
            "slice2-workflow",
        )

        self.assertIsInstance(result, Published)
        assert isinstance(result, Published)
        self.assertEqual(result.record_ref.record_id, f"{request.run_id}:0000000002")
        self.assertEqual(replay(self.state, request.run_id).last_sequence, 2)

    def assert_graph_rejected(
        self,
        tasks: tuple[TaskV1, ...],
        expected: PublishRejectionCode,
    ) -> None:
        request = self.publish_request()
        result = publish(
            self.state,
            request.run_id,
            workflow_candidate(request.record_ref, tasks),
            request.record_ref,
            f"slice2-{expected.value}",
        )

        self.assertIsInstance(result, Rejected)
        assert isinstance(result, Rejected)
        self.assertEqual(result.code, expected)
        self.assertEqual(replay(self.state, request.run_id).last_sequence, 1)

    def test_publish_rejects_unknown_dependency(self) -> None:
        self.assert_graph_rejected(
            (task("task-a", ("missing",)),),
            PublishRejectionCode.WORKFLOW_REVISION_UNKNOWN_DEPENDENCY,
        )

    def test_publish_rejects_self_dependency(self) -> None:
        self.assert_graph_rejected(
            (task("task-a", ("task-a",)),),
            PublishRejectionCode.WORKFLOW_REVISION_SELF_DEPENDENCY,
        )

    def test_publish_rejects_duplicate_dependency_edge(self) -> None:
        self.assert_graph_rejected(
            (task("task-a"), task("task-b", ("task-a", "task-a"))),
            PublishRejectionCode.WORKFLOW_REVISION_DUPLICATE_DEPENDENCY,
        )

    def test_publish_rejects_dependency_cycle(self) -> None:
        self.assert_graph_rejected(
            (task("task-a", ("task-b",)), task("task-b", ("task-a",))),
            PublishRejectionCode.WORKFLOW_REVISION_DEPENDENCY_CYCLE,
        )

    def test_publish_rejects_non_string_dependency_as_typed_rejection(self) -> None:
        request = self.publish_request()
        malformed_task = TaskV1(
            task_id="task-a",
            objective="Objective for task-a",
            acceptance_criteria=("Criterion for task-a",),
            depends_on=(42,),
        )

        result = publish(
            self.state,
            request.run_id,
            workflow_candidate(request.record_ref, (malformed_task,)),
            request.record_ref,
            "slice2-malformed-dependency",
        )

        self.assertIsInstance(result, Rejected)
        assert isinstance(result, Rejected)
        self.assertEqual(
            result.code,
            PublishRejectionCode.WORKFLOW_REVISION_DEPENDENCY_MALFORMED,
        )
        self.assertEqual(replay(self.state, request.run_id).last_sequence, 1)


if __name__ == "__main__":
    unittest.main()
