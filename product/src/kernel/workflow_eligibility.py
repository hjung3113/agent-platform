"""Pure DAG-workflow eligibility projection for M7 slice 2.

The projection reads only an admitted task sequence and replayed per-task
lineage. It does not publish records, inspect runtime state, or mutate a
derived cache.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from kernel.canonical import content_digest
from kernel.protocol_v1 import TaskV1, WorkflowRevisionV1
from kernel.replay import RunState


class WorkflowEligibilityStatus(StrEnum):
    NEXT_TASK = "next_task"
    WORKFLOW_COMPLETE = "workflow_complete"
    WORKFLOW_BLOCKED = "workflow_blocked"


class WorkflowEligibilityRejectionCode(StrEnum):
    UNKNOWN_TASK_ID = "unknown_task_id"
    WORKFLOW_REVISION_TASK_ID_DUPLICATE = "workflow_revision_task_id_duplicate"
    WORKFLOW_REVISION_DIGEST_DIVERGENCE = "workflow_revision_digest_divergence"
    TASK_IDENTITY_MISMATCH = "task_identity_mismatch"
    TASK_ORDER_VIOLATION = "task_order_violation"
    AMBIGUOUS_RUN_STATE = "ambiguous_run_state"


class WorkflowEligibilityRejected(Exception):
    """Eligibility could not be derived without guessing."""

    def __init__(self, code: WorkflowEligibilityRejectionCode, reason: str) -> None:
        super().__init__(reason)
        self.code = code
        self.reason = reason


@dataclass(frozen=True)
class WorkflowEligibility:
    """The deterministic ready set and next action for one admitted workflow."""

    status: WorkflowEligibilityStatus
    task: TaskV1 | None = None
    reason: str = ""
    eligible_tasks: tuple[TaskV1, ...] = ()

    @property
    def task_id(self) -> str | None:
        return None if self.task is None else self.task.task_id

    @property
    def is_complete(self) -> bool:
        return self.status is WorkflowEligibilityStatus.WORKFLOW_COMPLETE

    @property
    def is_blocked(self) -> bool:
        return self.status is WorkflowEligibilityStatus.WORKFLOW_BLOCKED


def _task_sequence_digest(tasks: tuple[TaskV1, ...]) -> str:
    return content_digest(
        {"tasks": [task.to_canonical_value() for task in tasks]}
    )


def _committed_task_sequence(state: RunState) -> tuple[TaskV1, ...] | None:
    revision = state.workflow_revision
    if revision is None:
        return None
    if isinstance(revision, WorkflowRevisionV1):
        return revision.tasks
    legacy_task = getattr(revision, "task", None)
    if isinstance(legacy_task, TaskV1):
        return (legacy_task,)
    raise WorkflowEligibilityRejected(
        WorkflowEligibilityRejectionCode.AMBIGUOUS_RUN_STATE,
        "committed_workflow_revision_shape_unknown",
    )


def _validate_revision_copies(
    admitted_revision: WorkflowRevisionV1,
    task_runs: Mapping[str, RunState | None],
) -> None:
    expected_digest = _task_sequence_digest(admitted_revision.tasks)
    observed: set[str] = set()
    for state in task_runs.values():
        if state is None:
            continue
        tasks = _committed_task_sequence(state)
        if tasks is None:
            continue
        observed.add(_task_sequence_digest(tasks))
    if observed and (observed != {expected_digest}):
        raise WorkflowEligibilityRejected(
            WorkflowEligibilityRejectionCode.WORKFLOW_REVISION_DIGEST_DIVERGENCE,
            f"expected={expected_digest} observed={sorted(observed)!r}",
        )


def _state_kind(task_id: str, state: RunState | None) -> str:
    if state is None:
        return "not_started"
    if state.attempt_packet is not None:
        committed_task_id = getattr(state.attempt_packet, "task_id", None)
        if committed_task_id != task_id:
            raise WorkflowEligibilityRejected(
                WorkflowEligibilityRejectionCode.TASK_IDENTITY_MISMATCH,
                f"expected_task_id={task_id!r} observed={committed_task_id!r}",
            )
    if state.receipt is not None:
        if (
            getattr(state.receipt, "receipt_type", None) == "terminal"
            and state.verification is not None
            and getattr(state.verification, "verdict", None) == "PASS"
        ):
            return "complete"
        raise WorkflowEligibilityRejected(
            WorkflowEligibilityRejectionCode.AMBIGUOUS_RUN_STATE,
            "terminal_receipt_without_pass_verification",
        )
    if state.verification is not None:
        verdict = getattr(state.verification, "verdict", None)
        if verdict in {"FAIL", "BLOCKED"}:
            return verdict.lower()
        if verdict == "PASS":
            return "in_flight"
        raise WorkflowEligibilityRejected(
            WorkflowEligibilityRejectionCode.AMBIGUOUS_RUN_STATE,
            f"unknown_verification_verdict={verdict!r}",
        )
    if (
        state.request is not None
        or state.workflow_revision is not None
        or state.attempt_packet is not None
        or state.result is not None
        or state.last_sequence != 0
    ):
        return "in_flight"
    return "not_started"


def project_workflow_eligibility(
    admitted_revision: WorkflowRevisionV1,
    task_runs: Mapping[str, RunState | None],
) -> WorkflowEligibility:
    """Project the next eligible task, completion, or blocking verdict.

    ``task_runs`` is keyed by the admitted task IDs. A missing key means that
    task has not started. An in-flight run is eligible for resumption because
    the driver can re-submit its existing content-derived per-record keys.
    """

    task_ids = tuple(task.task_id for task in admitted_revision.tasks)
    if not task_ids:
        raise WorkflowEligibilityRejected(
            WorkflowEligibilityRejectionCode.AMBIGUOUS_RUN_STATE,
            "admitted_workflow_revision_has_no_tasks",
        )
    if len(task_ids) != len(set(task_ids)):
        raise WorkflowEligibilityRejected(
            WorkflowEligibilityRejectionCode.WORKFLOW_REVISION_TASK_ID_DUPLICATE,
            f"duplicate_task_ids={task_ids!r}",
        )
    task_id_set = set(task_ids)
    unknown_dependencies = tuple(
        dependency
        for task in admitted_revision.tasks
        for dependency in task.depends_on
        if dependency not in task_id_set
    )
    if unknown_dependencies:
        raise WorkflowEligibilityRejected(
            WorkflowEligibilityRejectionCode.UNKNOWN_TASK_ID,
            f"unknown_dependency_ids={unknown_dependencies!r}",
        )
    unknown = sorted(set(task_runs) - set(task_ids))
    if unknown:
        raise WorkflowEligibilityRejected(
            WorkflowEligibilityRejectionCode.UNKNOWN_TASK_ID,
            f"unknown_task_ids={unknown!r}",
        )

    _validate_revision_copies(admitted_revision, task_runs)

    state_kinds = tuple(
        _state_kind(task.task_id, task_runs.get(task.task_id))
        for task in admitted_revision.tasks
    )
    state_by_task_id = dict(zip(task_ids, state_kinds))
    for task, kind in zip(admitted_revision.tasks, state_kinds):
        if kind != "not_started" and any(
            state_by_task_id[dependency] != "complete"
            for dependency in task.depends_on
        ):
            raise WorkflowEligibilityRejected(
                WorkflowEligibilityRejectionCode.TASK_ORDER_VIOLATION,
                f"task_id={task.task_id!r} kind={kind!r} "
                f"depends_on={task.depends_on!r} state_kinds={state_kinds!r}",
            )

    eligible_tasks = tuple(
        task
        for task, kind in zip(admitted_revision.tasks, state_kinds)
        if kind in {"not_started", "in_flight"}
        and all(state_by_task_id[dependency] == "complete" for dependency in task.depends_on)
    )

    for task, kind in zip(admitted_revision.tasks, state_kinds):
        if kind in {"fail", "blocked"}:
            return WorkflowEligibility(
                status=WorkflowEligibilityStatus.WORKFLOW_BLOCKED,
                task=task,
                reason=kind.upper(),
                eligible_tasks=eligible_tasks,
            )

    if all(kind == "complete" for kind in state_kinds):
        return WorkflowEligibility(
            status=WorkflowEligibilityStatus.WORKFLOW_COMPLETE,
            eligible_tasks=eligible_tasks,
        )
    if not eligible_tasks:
        raise WorkflowEligibilityRejected(
            WorkflowEligibilityRejectionCode.AMBIGUOUS_RUN_STATE,
            f"no_eligible_tasks state_kinds={state_kinds!r}",
        )
    return WorkflowEligibility(
        status=WorkflowEligibilityStatus.NEXT_TASK,
        task=eligible_tasks[0],
        eligible_tasks=eligible_tasks,
    )
