"""Strict v1 readers for Request and one-task Workflow Revision contracts.

Owns only retained v1 contract semantics needed by M0: value types, strict
payload validation, and canonical-value conversion used by
``kernel.canonical.content_digest()``. No retry, repair, replan, resources,
fan-in, concurrency, context budget, runtime selection, evidence policy, or
release state is represented here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from kernel.canonical import content_digest
from kernel.protocol import (
    ContractKind,
    ProtocolRejectionCode,
    ProtocolRejected,
    ReaderOutcome,
    RecordRef,
    register_reader,
    read_record_ref,
)

PROTOCOL_VERSION = 1
SCHEMA_VERSION = 1

_REQUEST_KEYS = frozenset({"objective", "scope", "acceptance_criteria"})
_WORKFLOW_REVISION_KEYS = frozenset({"request", "task"})
_TASK_KEYS = frozenset({"task_id", "objective", "acceptance_criteria"})


@dataclass(frozen=True)
class RequestV1:
    objective: str
    scope: tuple[str, ...]
    acceptance_criteria: tuple[str, ...]

    def to_canonical_value(self) -> dict[str, Any]:
        return {
            "objective": self.objective,
            "scope": list(self.scope),
            "acceptance_criteria": list(self.acceptance_criteria),
        }


@dataclass(frozen=True)
class TaskV1:
    task_id: str
    objective: str
    acceptance_criteria: tuple[str, ...]

    def to_canonical_value(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "objective": self.objective,
            "acceptance_criteria": list(self.acceptance_criteria),
        }


@dataclass(frozen=True)
class WorkflowRevisionV1:
    """One-task Workflow Revision bound to an exact Request reference."""

    request: RecordRef
    task: TaskV1

    def to_canonical_value(self) -> dict[str, Any]:
        return {
            "request": self.request.to_canonical_value(),
            "task": self.task.to_canonical_value(),
        }


def request_v1_content_digest(request: RequestV1) -> str:
    """Content identity of a Request candidate (no publication metadata)."""

    return content_digest(
        {
            "contract_kind": ContractKind.REQUEST.value,
            "protocol_version": PROTOCOL_VERSION,
            "schema_version": SCHEMA_VERSION,
            "payload": request.to_canonical_value(),
        }
    )


def workflow_revision_v1_content_digest(revision: WorkflowRevisionV1) -> str:
    """Content identity of a Workflow Revision candidate."""

    return content_digest(
        {
            "contract_kind": ContractKind.WORKFLOW_REVISION.value,
            "protocol_version": PROTOCOL_VERSION,
            "schema_version": SCHEMA_VERSION,
            "payload": revision.to_canonical_value(),
        }
    )


def _require_object(value: Any, what: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ProtocolRejected(
            ProtocolRejectionCode.MALFORMED_PAYLOAD, f"{what}_not_object"
        )
    return value


def _require_exact_keys(value: dict[str, Any], allowed: frozenset[str], what: str) -> None:
    keys = set(value)
    if keys != allowed:
        missing = sorted(allowed - keys)
        unknown = sorted(keys - allowed)
        raise ProtocolRejected(
            ProtocolRejectionCode.MALFORMED_PAYLOAD,
            f"{what}_keys_missing={missing} unknown={unknown}",
        )


def _require_nonempty_string(value: Any, what: str) -> str:
    if not isinstance(value, str) or not value:
        raise ProtocolRejected(ProtocolRejectionCode.MALFORMED_PAYLOAD, f"{what}_empty")
    return value


def _require_string_sequence(
    value: Any, what: str, *, allow_empty: bool
) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise ProtocolRejected(
            ProtocolRejectionCode.MALFORMED_PAYLOAD, f"{what}_not_sequence"
        )
    if not allow_empty and not value:
        raise ProtocolRejected(ProtocolRejectionCode.MALFORMED_PAYLOAD, f"{what}_empty")
    items = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item:
            raise ProtocolRejected(
                ProtocolRejectionCode.MALFORMED_PAYLOAD, f"{what}[{index}]_empty"
            )
        items.append(item)
    return tuple(items)


def read_request_v1(payload: Any) -> ReaderOutcome:
    """Strictly read a Request v1 payload or raise ``ProtocolRejected``."""

    candidate = _require_object(payload, "request_payload")
    _require_exact_keys(candidate, _REQUEST_KEYS, "request_payload")
    objective = _require_nonempty_string(candidate["objective"], "request_objective")
    scope = _require_string_sequence(candidate["scope"], "request_scope", allow_empty=True)
    acceptance_criteria = _require_string_sequence(
        candidate["acceptance_criteria"], "request_acceptance_criteria", allow_empty=False
    )
    request = RequestV1(
        objective=objective, scope=scope, acceptance_criteria=acceptance_criteria
    )
    return ReaderOutcome(
        value=request, canonical_payload=request.to_canonical_value()
    )


def _read_task_v1(payload: Any) -> TaskV1:
    task = _require_object(payload, "task")
    _require_exact_keys(task, _TASK_KEYS, "task")
    return TaskV1(
        task_id=_require_nonempty_string(task["task_id"], "task_id"),
        objective=_require_nonempty_string(task["objective"], "task_objective"),
        acceptance_criteria=_require_string_sequence(
            task["acceptance_criteria"], "task_acceptance_criteria", allow_empty=False
        ),
    )


def read_workflow_revision_v1(payload: Any) -> ReaderOutcome:
    """Strictly read a one-task Workflow Revision v1 payload.

    Exactly one task exists by construction: the schema has a single ``task``
    object field, not a task array or dependency graph.
    """

    candidate = _require_object(payload, "workflow_revision_payload")
    _require_exact_keys(candidate, _WORKFLOW_REVISION_KEYS, "workflow_revision_payload")

    try:
        request = read_record_ref(candidate["request"])
    except ProtocolRejected:
        raise
    if request.contract_kind != ContractKind.REQUEST:
        raise ProtocolRejected(
            ProtocolRejectionCode.BINDING_MISMATCH,
            "workflow_revision_request_kind_not_request",
        )
    task = _read_task_v1(candidate["task"])
    revision = WorkflowRevisionV1(request=request, task=task)
    return ReaderOutcome(
        value=revision, canonical_payload=revision.to_canonical_value()
    )


register_reader(
    ContractKind.REQUEST, PROTOCOL_VERSION, SCHEMA_VERSION, read_request_v1
)
register_reader(
    ContractKind.WORKFLOW_REVISION, PROTOCOL_VERSION, SCHEMA_VERSION, read_workflow_revision_v1
)
