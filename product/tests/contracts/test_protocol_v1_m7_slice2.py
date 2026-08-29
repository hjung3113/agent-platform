from __future__ import annotations

import tempfile
import unittest

from kernel.canonical import canonical_json_bytes, content_digest
from kernel.lineage_store import open_run
from kernel.protocol import (
    ContractKind,
    ProtocolRejectionCode,
    RecordRef,
    read_candidate,
)
from kernel.protocol_v1 import (
    TaskV1,
    WorkflowRevisionV1,
    workflow_revision_v1_content_digest,
)
from kernel.publish import Published, publish
from kernel.replay import replay


REQUEST_DIGEST = "sha256:agent-platform-json-v1:" + "a" * 64


def request_ref() -> dict[str, str]:
    return {
        "contract_kind": "request",
        "record_id": "rec-request-slice2",
        "content_digest": REQUEST_DIGEST,
    }


def task_payload(task_id: str, depends_on: tuple[str, ...] = ()) -> dict:
    return {
        "task_id": task_id,
        "objective": f"Objective for {task_id}",
        "acceptance_criteria": [f"Criterion for {task_id}"],
        "depends_on": list(depends_on),
    }


def legacy_task_payload(task_id: str) -> dict:
    return {
        "task_id": task_id,
        "objective": f"Objective for {task_id}",
        "acceptance_criteria": [f"Criterion for {task_id}"],
    }


def workflow_payload(tasks: list[dict]) -> dict:
    return {"request": request_ref(), "tasks": tasks}


def workflow_envelope(payload: dict, schema_version: int) -> dict:
    return {
        "contract_kind": ContractKind.WORKFLOW_REVISION.value,
        "protocol_version": 1,
        "schema_version": schema_version,
        "payload": payload,
    }


class ProtocolV1M7Slice2Tests(unittest.TestCase):
    def test_v3_dependencies_round_trip_through_wire_shape(self) -> None:
        result = read_candidate(
            workflow_envelope(
                workflow_payload(
                    [
                        task_payload("task-a"),
                        task_payload("task-b"),
                        task_payload("task-c", ("task-a", "task-b")),
                    ]
                ),
                3,
            )
        )

        self.assertTrue(result.ok, result.reason)
        revision = result.value.value
        self.assertEqual(
            revision.tasks,
            (
                TaskV1("task-a", "Objective for task-a", ("Criterion for task-a",), ()),
                TaskV1("task-b", "Objective for task-b", ("Criterion for task-b",), ()),
                TaskV1(
                    "task-c",
                    "Objective for task-c",
                    ("Criterion for task-c",),
                    ("task-a", "task-b"),
                ),
            ),
        )
        self.assertEqual(
            result.value.envelope.payload["tasks"][2]["depends_on"],
            ["task-a", "task-b"],
        )

    def test_schema_v2_is_retained_and_rejects_new_task_field(self) -> None:
        legacy = read_candidate(
            workflow_envelope(
                workflow_payload(
                    [legacy_task_payload("task-1"), legacy_task_payload("task-2")]
                ),
                2,
            )
        )
        self.assertTrue(legacy.ok, legacy.reason)
        self.assertEqual(legacy.value.value.tasks[0].depends_on, ())
        self.assertNotIn("depends_on", legacy.value.envelope.payload["tasks"][0])

        rejected = read_candidate(
            workflow_envelope(workflow_payload([task_payload("task-1")]), 2)
        )
        self.assertEqual(
            rejected.rejection_code,
            ProtocolRejectionCode.UNSUPPORTED_SCHEMA_VERSION,
        )

    def test_schema_v2_typed_value_round_trips_without_introducing_depends_on(
        self,
    ) -> None:
        """A replayed-v2 typed value must not silently canonicalize as v3.

        Round-1 PR review found that ``WorkflowRevisionV1.to_canonical_value()``
        always emitted ``depends_on`` regardless of which schema version
        actually produced the value, so ``ReaderOutcome.value.to_canonical_value()``
        diverged from ``ReaderOutcome.canonical_payload`` for the retained v2
        reader specifically — the one place in this module where that
        equality did not already hold by construction. This asserts the
        equality holds for v2 too, and that the typed value's own
        re-canonicalization never introduces a ``depends_on`` key that was
        never in the original wire payload.
        """

        legacy = read_candidate(
            workflow_envelope(
                workflow_payload(
                    [legacy_task_payload("task-1"), legacy_task_payload("task-2")]
                ),
                2,
            )
        )
        self.assertTrue(legacy.ok, legacy.reason)

        retyped = legacy.value.value.to_canonical_value()
        self.assertEqual(retyped, legacy.value.envelope.payload)
        for retyped_task in retyped["tasks"]:
            self.assertNotIn("depends_on", retyped_task)

    def test_schema_v1_legacy_task_gets_empty_dependencies(self) -> None:
        result = read_candidate(
            workflow_envelope(
                {"request": request_ref(), "task": legacy_task_payload("legacy")},
                1,
            )
        )

        self.assertTrue(result.ok, result.reason)
        self.assertEqual(result.value.value.task.depends_on, ())
        self.assertNotIn("depends_on", result.value.envelope.payload["task"])

    def test_unknown_dependency_is_rejected_as_malformed_payload(self) -> None:
        result = read_candidate(
            workflow_envelope(
                workflow_payload([task_payload("task-a", ("missing",))]), 3
            )
        )

        self.assertEqual(result.rejection_code, ProtocolRejectionCode.MALFORMED_PAYLOAD)

    def test_self_dependency_is_rejected_as_malformed_payload(self) -> None:
        result = read_candidate(
            workflow_envelope(
                workflow_payload([task_payload("task-a", ("task-a",))]), 3
            )
        )

        self.assertEqual(result.rejection_code, ProtocolRejectionCode.MALFORMED_PAYLOAD)

    def test_duplicate_dependency_edge_is_rejected_as_malformed_payload(self) -> None:
        result = read_candidate(
            workflow_envelope(
                workflow_payload([task_payload("task-a"), task_payload("task-b", ("task-a", "task-a"))]),
                3,
            )
        )

        self.assertEqual(result.rejection_code, ProtocolRejectionCode.MALFORMED_PAYLOAD)

    def test_two_and_three_node_cycles_are_rejected_as_malformed_payload(self) -> None:
        two_node = read_candidate(
            workflow_envelope(
                workflow_payload(
                    [task_payload("task-a", ("task-b",)), task_payload("task-b", ("task-a",))]
                ),
                3,
            )
        )
        three_node = read_candidate(
            workflow_envelope(
                workflow_payload(
                    [
                        task_payload("task-a", ("task-b",)),
                        task_payload("task-b", ("task-c",)),
                        task_payload("task-c", ("task-a",)),
                    ]
                ),
                3,
            )
        )

        self.assertEqual(two_node.rejection_code, ProtocolRejectionCode.MALFORMED_PAYLOAD)
        self.assertEqual(
            three_node.rejection_code, ProtocolRejectionCode.MALFORMED_PAYLOAD
        )

    def test_deep_acyclic_graph_uses_typed_validation_without_recursion(self) -> None:
        task_count = 10_001
        tasks = [
            task_payload(
                f"task-{index}", (f"task-{index - 1}",) if index else ()
            )
            for index in range(task_count)
        ]

        result = read_candidate(workflow_envelope(workflow_payload(tasks), 3))

        self.assertTrue(result.ok, result.reason)
        self.assertEqual(len(result.value.value.tasks), task_count)

    def test_dependency_order_changes_workflow_digest(self) -> None:
        base = WorkflowRevisionV1(
            request=RecordRef("request", "request-1", REQUEST_DIGEST),
            tasks=(
                TaskV1("task-a", "A", ("A passes",), ()),
                TaskV1("task-b", "B", ("B passes",), ("task-a",)),
            ),
        )
        changed = WorkflowRevisionV1(
            request=base.request,
            tasks=(
                base.tasks[0],
                TaskV1("task-b", "B", ("B passes",), ()),
            ),
        )

        self.assertNotEqual(
            workflow_revision_v1_content_digest(base),
            workflow_revision_v1_content_digest(changed),
        )

    def test_committed_schema_v2_workflow_replays_with_empty_dependencies(self) -> None:
        request_payload = {
            "objective": "A retained request",
            "scope": [],
            "acceptance_criteria": ["It replays"],
        }
        request_candidate = read_candidate(
            {
                "contract_kind": "request",
                "protocol_version": 1,
                "schema_version": 1,
                "payload": request_payload,
            }
        )
        self.assertTrue(request_candidate.ok, request_candidate.reason)

        with tempfile.TemporaryDirectory() as state:
            request = publish(state, None, request_candidate.value, None, "request")
            self.assertIsInstance(request, Published)
            assert isinstance(request, Published)
            legacy_workflow = read_candidate(
                workflow_envelope(
                    {
                        "request": request.record_ref.to_canonical_value(),
                        "tasks": [legacy_task_payload("task-1")],
                    },
                    2,
                )
            )
            self.assertTrue(legacy_workflow.ok, legacy_workflow.reason)
            legacy_candidate = legacy_workflow.value.envelope.to_content_value()
            workflow_record = {
                "run_id": request.run_id,
                "sequence": 2,
                "record_id": f"{request.run_id}:0000000002",
                "content_digest": content_digest(legacy_candidate),
                "idempotency_key": "workflow",
                "candidate": legacy_candidate,
            }
            open_run(state, request.run_id).append(
                2, canonical_json_bytes(workflow_record)
            )

            folded = replay(state, request.run_id)

        self.assertIsInstance(folded.workflow_revision, WorkflowRevisionV1)
        assert isinstance(folded.workflow_revision, WorkflowRevisionV1)
        self.assertEqual(folded.workflow_revision.tasks[0].depends_on, ())


if __name__ == "__main__":
    unittest.main()
