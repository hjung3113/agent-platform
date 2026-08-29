from __future__ import annotations

import unittest

from kernel.protocol import ProtocolRejectionCode, RecordRef, read_candidate
from kernel.protocol_v1 import TaskV1, WorkflowRevisionV1


REQUEST_DIGEST = "sha256:agent-platform-json-v1:" + "a" * 64


def workflow_envelope(payload: dict, *, schema_version: int) -> dict:
    return {
        "contract_kind": "workflow_revision",
        "protocol_version": 1,
        "schema_version": schema_version,
        "payload": payload,
    }


def task(task_id: str) -> dict:
    return {
        "task_id": task_id,
        "objective": f"Objective for {task_id}",
        "acceptance_criteria": [f"Criterion for {task_id}"],
    }


def request_ref() -> dict:
    return {
        "contract_kind": "request",
        "record_id": "rec-request-1",
        "content_digest": REQUEST_DIGEST,
    }


class WorkflowRevisionV1M7ReaderTests(unittest.TestCase):
    def test_schema_v2_accepts_nonempty_ordered_tasks(self) -> None:
        result = read_candidate(
            workflow_envelope(
                {"request": request_ref(), "tasks": [task("task-1"), task("task-2")]},
                schema_version=2,
            )
        )

        self.assertTrue(result.ok, result.reason)
        self.assertEqual(
            result.value.value,
            WorkflowRevisionV1(
                request=RecordRef("request", "rec-request-1", REQUEST_DIGEST),
                tasks=(
                    TaskV1("task-1", "Objective for task-1", ("Criterion for task-1",), ()),
                    TaskV1("task-2", "Objective for task-2", ("Criterion for task-2",), ()),
                ),
                schema_version=2,
            ),
        )
        self.assertEqual(
            result.value.value.to_canonical_value(), result.value.envelope.payload
        )

    def test_schema_v2_rejects_empty_tasks(self) -> None:
        result = read_candidate(
            workflow_envelope(
                {"request": request_ref(), "tasks": []}, schema_version=2
            )
        )

        self.assertEqual(result.rejection_code, ProtocolRejectionCode.MALFORMED_PAYLOAD)

    def test_schema_v2_rejects_duplicate_task_ids(self) -> None:
        result = read_candidate(
            workflow_envelope(
                {"request": request_ref(), "tasks": [task("same"), task("same")]},
                schema_version=2,
            )
        )

        self.assertEqual(result.rejection_code, ProtocolRejectionCode.MALFORMED_PAYLOAD)

    def test_schema_v1_legacy_single_task_still_parses(self) -> None:
        result = read_candidate(
            workflow_envelope(
                {"request": request_ref(), "task": task("legacy-task")},
                schema_version=1,
            )
        )

        self.assertTrue(result.ok, result.reason)
        self.assertEqual(result.value.value.task.task_id, "legacy-task")

    def test_schema_v1_tasks_shape_rejects_as_unsupported_schema(self) -> None:
        result = read_candidate(
            workflow_envelope(
                {"request": request_ref(), "tasks": [task("task-1")]},
                schema_version=1,
            )
        )

        self.assertEqual(
            result.rejection_code, ProtocolRejectionCode.UNSUPPORTED_SCHEMA_VERSION
        )


if __name__ == "__main__":
    unittest.main()
