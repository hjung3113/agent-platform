from __future__ import annotations

import unittest
from types import SimpleNamespace

from kernel.protocol import RecordRef
from kernel.protocol_v1 import TaskV1, WorkflowRevisionV1
from kernel.replay import RunState
from kernel.workflow_eligibility import (
    WorkflowEligibilityRejectionCode,
    WorkflowEligibilityStatus,
    WorkflowEligibilityRejected,
    project_workflow_eligibility,
)


REQUEST_REF = RecordRef(
    "request", "request-1", "sha256:agent-platform-json-v1:" + "a" * 64
)


TASKS = (
    TaskV1("task-1", "First task", ("First criterion",)),
    TaskV1("task-2", "Second task", ("Second criterion",)),
)


def revision(tasks: tuple[TaskV1, ...] = TASKS) -> WorkflowRevisionV1:
    return WorkflowRevisionV1(request=REQUEST_REF, tasks=tasks)


def run_state(
    workflow_revision: WorkflowRevisionV1 | None,
    *,
    head: str | None = None,
    verdict: str | None = None,
    task_id: str | None = None,
) -> RunState:
    packet_task_id = task_id
    if packet_task_id is None and workflow_revision is not None:
        packet_task_id = workflow_revision.tasks[0].task_id
    has_attempt_packet = workflow_revision is not None and (
        head is not None or verdict is not None
    )
    return RunState(
        request=object() if workflow_revision is not None else None,
        workflow_revision=workflow_revision,
        last_sequence=0 if head is None else 1,
        last_record_id=None,
        attempt_packet=(
            SimpleNamespace(task_id=packet_task_id)
            if has_attempt_packet
            else None
        ),
        result=object() if head == "result" else None,
        verification=(SimpleNamespace(verdict=verdict) if verdict is not None else None),
        receipt=(SimpleNamespace(receipt_type="terminal") if head == "receipt" else None),
    )


class WorkflowEligibilityTests(unittest.TestCase):
    def test_same_revision_and_states_are_deterministic(self) -> None:
        states = {"task-1": run_state(revision(), head="receipt", verdict="PASS")}

        first = project_workflow_eligibility(revision(), states)
        second = project_workflow_eligibility(revision(), states)

        self.assertEqual(first, second)
        self.assertEqual(first.status, WorkflowEligibilityStatus.NEXT_TASK)
        self.assertEqual(first.task, TASKS[1])

    def test_all_pass_receipts_make_workflow_complete(self) -> None:
        states = {
            task.task_id: run_state(
                revision(), head="receipt", verdict="PASS", task_id=task.task_id
            )
            for task in TASKS
        }

        result = project_workflow_eligibility(revision(), states)

        self.assertEqual(result.status, WorkflowEligibilityStatus.WORKFLOW_COMPLETE)
        self.assertIsNone(result.task)

    def test_fail_blocks_at_that_task(self) -> None:
        states = {
            "task-1": run_state(
                revision(), head="receipt", verdict="PASS", task_id="task-1"
            ),
            "task-2": run_state(revision(), verdict="FAIL", task_id="task-2"),
        }

        result = project_workflow_eligibility(revision(), states)

        self.assertEqual(result.status, WorkflowEligibilityStatus.WORKFLOW_BLOCKED)
        self.assertEqual(result.task, TASKS[1])
        self.assertEqual(result.reason, "FAIL")

    def test_blocked_verdict_blocks_without_skipping(self) -> None:
        states = {"task-1": run_state(revision(), verdict="BLOCKED")}

        result = project_workflow_eligibility(revision(), states)

        self.assertEqual(result.status, WorkflowEligibilityStatus.WORKFLOW_BLOCKED)
        self.assertEqual(result.task, TASKS[0])
        self.assertEqual(result.reason, "BLOCKED")

    def test_incomplete_earlier_task_keeps_later_task_ineligible(self) -> None:
        states = {"task-1": run_state(revision(), head="result")}

        result = project_workflow_eligibility(revision(), states)

        self.assertEqual(result.status, WorkflowEligibilityStatus.NEXT_TASK)
        self.assertEqual(result.task, TASKS[0])

    def test_unknown_task_id_fails_closed(self) -> None:
        with self.assertRaises(WorkflowEligibilityRejected) as raised:
            project_workflow_eligibility(
                revision(), {"unknown-task": run_state(revision())}
            )

        self.assertEqual(
            raised.exception.code, WorkflowEligibilityRejectionCode.UNKNOWN_TASK_ID
        )

    def test_in_flight_task_is_eligible_for_resume(self) -> None:
        result = project_workflow_eligibility(
            revision(), {"task-1": run_state(revision(), head="attempt_packet")}
        )

        self.assertEqual(result.status, WorkflowEligibilityStatus.NEXT_TASK)
        self.assertEqual(result.task, TASKS[0])

    def test_attempt_packet_task_identity_mismatch_fails_closed(self) -> None:
        with self.assertRaises(WorkflowEligibilityRejected) as raised:
            project_workflow_eligibility(
                revision(),
                {
                    "task-1": run_state(
                        revision(),
                        head="receipt",
                        verdict="PASS",
                        task_id="task-2",
                    )
                },
            )

        self.assertEqual(
            raised.exception.code,
            WorkflowEligibilityRejectionCode.TASK_IDENTITY_MISMATCH,
        )

    def test_later_in_flight_task_before_earlier_task_fails_closed(self) -> None:
        with self.assertRaises(WorkflowEligibilityRejected) as raised:
            project_workflow_eligibility(
                revision(),
                {
                    "task-2": run_state(
                        revision(), head="attempt_packet", task_id="task-2"
                    )
                },
            )

        self.assertEqual(
            raised.exception.code,
            WorkflowEligibilityRejectionCode.TASK_ORDER_VIOLATION,
        )

    def test_later_complete_task_before_earlier_task_fails_closed(self) -> None:
        with self.assertRaises(WorkflowEligibilityRejected) as raised:
            project_workflow_eligibility(
                revision(),
                {
                    "task-2": run_state(
                        revision(),
                        head="receipt",
                        verdict="PASS",
                        task_id="task-2",
                    )
                },
            )

        self.assertEqual(
            raised.exception.code,
            WorkflowEligibilityRejectionCode.TASK_ORDER_VIOLATION,
        )

    def test_task_sequence_digest_ignores_legitimate_per_run_request_refs(self) -> None:
        other_request_revision = WorkflowRevisionV1(
            request=RecordRef(
                "request", "request-2", "sha256:agent-platform-json-v1:" + "b" * 64
            ),
            tasks=TASKS,
        )

        result = project_workflow_eligibility(
            revision(),
            {
                "task-1": run_state(
                    revision(), head="receipt", verdict="PASS", task_id="task-1"
                ),
                "task-2": run_state(
                    other_request_revision,
                    head="attempt_packet",
                    task_id="task-2",
                ),
            },
        )

        self.assertEqual(result.status, WorkflowEligibilityStatus.NEXT_TASK)
        self.assertEqual(result.task, TASKS[1])

    def test_task_sequence_digest_divergence_fails_closed(self) -> None:
        divergent = (
            TaskV1("task-1", "First task", ("Changed criterion",)),
            TASKS[1],
        )
        other_request_revision = WorkflowRevisionV1(
            request=RecordRef(
                "request", "request-2", "sha256:agent-platform-json-v1:" + "b" * 64
            ),
            tasks=divergent,
        )
        states = {
            "task-1": run_state(revision()),
            "task-2": run_state(other_request_revision),
        }

        with self.assertRaises(WorkflowEligibilityRejected) as raised:
            project_workflow_eligibility(revision(), states)

        self.assertEqual(
            raised.exception.code,
            WorkflowEligibilityRejectionCode.WORKFLOW_REVISION_DIGEST_DIVERGENCE,
        )


if __name__ == "__main__":
    unittest.main()
