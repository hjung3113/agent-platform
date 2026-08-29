from __future__ import annotations

import unittest
from types import SimpleNamespace

from kernel.protocol import RecordRef
from kernel.protocol_v1 import TaskV1, WorkflowRevisionV1
from kernel.replay import RunState
from kernel.workflow_eligibility import (
    WorkflowEligibilityRejectionCode,
    WorkflowEligibilityRejected,
    WorkflowEligibilityStatus,
    project_workflow_eligibility,
)


REQUEST_REF = RecordRef(
    "request", "request-dag", "sha256:agent-platform-json-v1:" + "a" * 64
)


def task(task_id: str, depends_on: tuple[str, ...] = ()) -> TaskV1:
    return TaskV1(
        task_id=task_id,
        objective=f"Objective for {task_id}",
        acceptance_criteria=(f"Criterion for {task_id}",),
        depends_on=depends_on,
    )


DIAMOND_TASKS = (
    task("A"),
    task("B", ("A",)),
    task("C", ("A",)),
    task("D", ("B", "C")),
)
DIAMOND = WorkflowRevisionV1(request=REQUEST_REF, tasks=DIAMOND_TASKS)


def run_state(
    revision: WorkflowRevisionV1,
    task_id: str,
    *,
    kind: str = "not_started",
) -> RunState:
    if kind == "not_started":
        return RunState(None, None, 0, None)
    return RunState(
        request=object(),
        workflow_revision=revision,
        last_sequence=6 if kind == "complete" else 3,
        last_record_id=None,
        attempt_packet=SimpleNamespace(task_id=task_id),
        result=object() if kind in {"complete", "fail", "blocked"} else None,
        verification=(
            SimpleNamespace(verdict="PASS" if kind == "complete" else kind.upper())
            if kind in {"complete", "fail", "blocked"}
            else None
        ),
        receipt=(
            SimpleNamespace(receipt_type="terminal") if kind == "complete" else None
        ),
    )


def complete(revision: WorkflowRevisionV1, task_id: str) -> RunState:
    return run_state(revision, task_id, kind="complete")


class WorkflowEligibilityDagTests(unittest.TestCase):
    def test_diamond_ready_set_and_declaration_order_tie_break(self) -> None:
        initial = project_workflow_eligibility(DIAMOND, {})
        after_a = project_workflow_eligibility(
            DIAMOND, {"A": complete(DIAMOND, "A")}
        )
        after_branches = project_workflow_eligibility(
            DIAMOND,
            {
                "A": complete(DIAMOND, "A"),
                "B": complete(DIAMOND, "B"),
                "C": complete(DIAMOND, "C"),
            },
        )
        finished = project_workflow_eligibility(
            DIAMOND,
            {
                task_id: complete(DIAMOND, task_id)
                for task_id in ("A", "B", "C", "D")
            },
        )

        self.assertEqual(initial.status, WorkflowEligibilityStatus.NEXT_TASK)
        self.assertEqual(initial.eligible_tasks, (DIAMOND_TASKS[0],))
        self.assertEqual(initial.task, DIAMOND_TASKS[0])
        self.assertEqual(after_a.eligible_tasks, (DIAMOND_TASKS[1], DIAMOND_TASKS[2]))
        self.assertEqual(after_a.task, DIAMOND_TASKS[1])
        self.assertEqual(after_branches.eligible_tasks, (DIAMOND_TASKS[3],))
        self.assertEqual(after_branches.task, DIAMOND_TASKS[3])
        self.assertEqual(finished.status, WorkflowEligibilityStatus.WORKFLOW_COMPLETE)
        self.assertEqual(finished.eligible_tasks, ())
        self.assertIsNone(finished.task)

    def test_out_of_order_committed_dependency_fails_closed(self) -> None:
        with self.assertRaises(WorkflowEligibilityRejected) as raised:
            project_workflow_eligibility(
                DIAMOND, {"B": run_state(DIAMOND, "B", kind="in_flight")}
            )

        self.assertEqual(
            raised.exception.code,
            WorkflowEligibilityRejectionCode.TASK_ORDER_VIOLATION,
        )

    def test_unknown_dependency_reference_fails_closed(self) -> None:
        revision = WorkflowRevisionV1(
            request=REQUEST_REF,
            tasks=(task("A", ("ghost",)),),
        )

        with self.assertRaises(WorkflowEligibilityRejected) as raised:
            project_workflow_eligibility(revision, {})

        self.assertEqual(
            raised.exception.code,
            WorkflowEligibilityRejectionCode.UNKNOWN_TASK_ID,
        )

    def test_failed_task_blocks_workflow_but_ready_set_keeps_independent_task(self) -> None:
        tasks = (*DIAMOND_TASKS, task("E"))
        revision = WorkflowRevisionV1(request=REQUEST_REF, tasks=tasks)
        result = project_workflow_eligibility(
            revision, {"A": run_state(revision, "A", kind="fail")}
        )

        self.assertEqual(result.status, WorkflowEligibilityStatus.WORKFLOW_BLOCKED)
        self.assertEqual(result.task, tasks[0])
        self.assertEqual(result.reason, "FAIL")
        self.assertEqual(result.eligible_tasks, (tasks[4],))

    def test_same_revision_and_lineage_are_deterministic(self) -> None:
        states = {"A": complete(DIAMOND, "A")}

        first = project_workflow_eligibility(DIAMOND, states)
        second = project_workflow_eligibility(DIAMOND, states)

        self.assertEqual(first.status, second.status)
        self.assertEqual(first.eligible_tasks, second.eligible_tasks)
        self.assertEqual(first.task, second.task)

    def test_in_flight_task_with_satisfied_dependencies_is_resume_eligible(self) -> None:
        result = project_workflow_eligibility(
            DIAMOND,
            {
                "A": complete(DIAMOND, "A"),
                "B": run_state(DIAMOND, "B", kind="in_flight"),
            },
        )

        self.assertEqual(result.status, WorkflowEligibilityStatus.NEXT_TASK)
        self.assertEqual(result.eligible_tasks, (DIAMOND_TASKS[1], DIAMOND_TASKS[2]))
        self.assertEqual(result.task, DIAMOND_TASKS[1])

    def test_dependency_only_digest_divergence_fails_closed(self) -> None:
        divergent_tasks = (
            DIAMOND_TASKS[0],
            task("B", ("C",)),
            DIAMOND_TASKS[2],
            DIAMOND_TASKS[3],
        )
        divergent = WorkflowRevisionV1(request=REQUEST_REF, tasks=divergent_tasks)

        with self.assertRaises(WorkflowEligibilityRejected) as raised:
            project_workflow_eligibility(
                DIAMOND,
                {
                    "A": run_state(DIAMOND, "A", kind="in_flight"),
                    "B": run_state(divergent, "B", kind="in_flight"),
                },
            )

        self.assertEqual(
            raised.exception.code,
            WorkflowEligibilityRejectionCode.WORKFLOW_REVISION_DIGEST_DIVERGENCE,
        )


if __name__ == "__main__":
    unittest.main()
