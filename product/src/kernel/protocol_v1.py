"""Strict v1 readers for the one-task run chain contracts.

Owns only retained v1 contract semantics: Request, one-task Workflow
Revision, Attempt Packet, Result (with embedded Runtime Observation),
Verification, and terminal Receipt value types, strict payload validation,
and canonical-value conversion used by ``kernel.canonical.content_digest()``.
No retry, repair, replan, resources, fan-in, concurrency, context budget,
runtime selection, evidence policy, or release state is represented here.
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
    is_content_digest,
    register_reader,
    read_record_ref,
)
from kernel.runtime_capability import _require_versioned_identity

PROTOCOL_VERSION = 1
SCHEMA_VERSION = 1
# Reader/function names remain protocol-v1 names; the current Result wire shape is schema 2.
RESULT_SCHEMA_VERSION = 2
VERIFICATION_SCHEMA_VERSION = 3

_REQUEST_KEYS = frozenset({"objective", "scope", "acceptance_criteria"})
_WORKFLOW_REVISION_KEYS = frozenset({"request", "task"})
_TASK_KEYS = frozenset({"task_id", "objective", "acceptance_criteria"})
_ATTEMPT_PACKET_KEYS = frozenset(
    {
        "workflow_revision",
        "task_id",
        "implementer_identity",
        "context_digest",
        "workspace_snapshot_digest",
        "runtime_capability_profile_identity",
    }
)
_RESULT_KEYS = frozenset({"attempt", "output_snapshot_digest", "observation"})
_LEGACY_RESULT_KEYS = _RESULT_KEYS
_OBSERVATION_KEYS = frozenset(
    {"runtime_identity", "output_snapshot_digest", "execution_identity"}
)
_LEGACY_OBSERVATION_KEYS = frozenset({"runtime_identity", "output_snapshot_digest"})
_VERIFICATION_KEYS = frozenset(
    {
        "result",
        "verifier_identity",
        "verifier_runtime_capability_profile_identity",
        "verifier_execution_identity",
        "coverage",
        "verdict",
        "findings",
    }
)
_LEGACY_VERIFICATION_ROUND_ONE_KEYS = frozenset(
    {
        "result",
        "verifier_identity",
        "verifier_runtime_capability_profile_identity",
        "coverage",
        "verdict",
        "findings",
    }
)
_LEGACY_VERIFICATION_KEYS = frozenset(
    {"result", "verifier_identity", "coverage", "verdict", "findings"}
)
_COVERAGE_ENTRY_KEYS = frozenset(
    {"criterion", "status", "evidence_digest", "evidence_class"}
)
_LEGACY_COVERAGE_ENTRY_KEYS = frozenset(
    {"criterion", "status", "evidence_digest"}
)
_FINDING_KEYS = frozenset(
    {"criterion", "fingerprint", "description", "state", "predecessor"}
)
_FINDING_STATES = frozenset({"OPEN", "RESOLVED", "REOPENED", "SUPERSEDED"})
_COVERAGE_STATUSES = frozenset({"SATISFIED", "UNSATISFIED", "BLOCKED", "UNPROVEN"})
_VERDICTS = frozenset({"PASS", "FAIL", "BLOCKED"})
_RECEIPT_KEYS = frozenset({"verification", "receipt_type"})
RESULT_SNAPSHOT_EVIDENCE_CLASS = "result_snapshot_digest_equality@1"
RECEIPT_TYPE_TERMINAL = "terminal"

_SCHEMA_VERSION_BY_KIND = {
    ContractKind.RESULT: RESULT_SCHEMA_VERSION,
    ContractKind.VERIFICATION: VERIFICATION_SCHEMA_VERSION,
}


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


@dataclass(frozen=True)
class AttemptPacketV1:
    """One-task Attempt Packet bound to an exact Workflow Revision reference."""

    workflow_revision: RecordRef
    task_id: str
    implementer_identity: str
    context_digest: str
    workspace_snapshot_digest: str
    runtime_capability_profile_identity: str

    def to_canonical_value(self) -> dict[str, Any]:
        return {
            "workflow_revision": self.workflow_revision.to_canonical_value(),
            "task_id": self.task_id,
            "implementer_identity": self.implementer_identity,
            "context_digest": self.context_digest,
            "workspace_snapshot_digest": self.workspace_snapshot_digest,
            "runtime_capability_profile_identity": (
                self.runtime_capability_profile_identity
            ),
        }


@dataclass(frozen=True)
class RuntimeObservationV1:
    """Runtime Observation embedded in a Result, never a separate record."""

    runtime_identity: str
    output_snapshot_digest: str
    execution_identity: str

    def to_canonical_value(self) -> dict[str, Any]:
        return {
            "runtime_identity": self.runtime_identity,
            "output_snapshot_digest": self.output_snapshot_digest,
            "execution_identity": self.execution_identity,
        }


@dataclass(frozen=True)
class ResultV1:
    """Execution Result bound to an exact Attempt Packet reference."""

    attempt: RecordRef
    output_snapshot_digest: str
    observation: RuntimeObservationV1

    def to_canonical_value(self) -> dict[str, Any]:
        return {
            "attempt": self.attempt.to_canonical_value(),
            "output_snapshot_digest": self.output_snapshot_digest,
            "observation": self.observation.to_canonical_value(),
        }


@dataclass(frozen=True)
class _LegacyRuntimeObservationV1:
    """Retained pre-round-2 Runtime Observation shape used for replay only."""

    runtime_identity: str
    output_snapshot_digest: str

    def to_canonical_value(self) -> dict[str, Any]:
        return {
            "runtime_identity": self.runtime_identity,
            "output_snapshot_digest": self.output_snapshot_digest,
        }


@dataclass(frozen=True)
class _LegacyResultV1:
    """Retained pre-round-2 Result shape used for replay only."""

    attempt: RecordRef
    output_snapshot_digest: str
    observation: _LegacyRuntimeObservationV1

    def to_canonical_value(self) -> dict[str, Any]:
        return {
            "attempt": self.attempt.to_canonical_value(),
            "output_snapshot_digest": self.output_snapshot_digest,
            "observation": self.observation.to_canonical_value(),
        }


@dataclass(frozen=True)
class FindingV1:
    criterion: str
    fingerprint: str
    description: str
    state: str
    predecessor: RecordRef | None

    def to_canonical_value(self) -> dict[str, Any]:
        return {
            "criterion": self.criterion,
            "fingerprint": self.fingerprint,
            "description": self.description,
            "state": self.state,
            "predecessor": (
                None
                if self.predecessor is None
                else self.predecessor.to_canonical_value()
            ),
        }


@dataclass(frozen=True)
class CoverageEntryV1:
    criterion: str
    status: str
    evidence_digest: str | None
    evidence_class: str

    def to_canonical_value(self) -> dict[str, Any]:
        return {
            "criterion": self.criterion,
            "status": self.status,
            "evidence_digest": self.evidence_digest,
            "evidence_class": self.evidence_class,
        }


@dataclass(frozen=True)
class VerificationV1:
    """Verification bound to an exact Result reference."""

    result: RecordRef
    verifier_identity: str
    verifier_runtime_capability_profile_identity: str
    verifier_execution_identity: str
    coverage: tuple[CoverageEntryV1, ...]
    verdict: str
    findings: tuple[FindingV1, ...]

    def to_canonical_value(self) -> dict[str, Any]:
        return {
            "result": self.result.to_canonical_value(),
            "verifier_identity": self.verifier_identity,
            "verifier_runtime_capability_profile_identity": (
                self.verifier_runtime_capability_profile_identity
            ),
            "verifier_execution_identity": self.verifier_execution_identity,
            "coverage": [entry.to_canonical_value() for entry in self.coverage],
            "verdict": self.verdict,
            "findings": [finding.to_canonical_value() for finding in self.findings],
        }


@dataclass(frozen=True)
class _LegacyCoverageEntryV1:
    criterion: str
    status: str
    evidence_digest: str | None

    def to_canonical_value(self) -> dict[str, Any]:
        return {
            "criterion": self.criterion,
            "status": self.status,
            "evidence_digest": self.evidence_digest,
        }


@dataclass(frozen=True)
class _LegacyVerificationV1:
    """Retained pre-M6 Verification shape used for replay only."""

    result: RecordRef
    verifier_identity: str
    coverage: tuple[_LegacyCoverageEntryV1, ...]
    verdict: str
    findings: tuple[str, ...]

    def to_canonical_value(self) -> dict[str, Any]:
        return {
            "result": self.result.to_canonical_value(),
            "verifier_identity": self.verifier_identity,
            "coverage": [entry.to_canonical_value() for entry in self.coverage],
            "verdict": self.verdict,
            "findings": list(self.findings),
        }


@dataclass(frozen=True)
class _LegacyVerificationV1RoundOne:
    """Retained round-1 Verification schema-2 shape used for replay only."""

    result: RecordRef
    verifier_identity: str
    verifier_runtime_capability_profile_identity: str
    coverage: tuple[CoverageEntryV1, ...]
    verdict: str
    findings: tuple[FindingV1, ...]

    def to_canonical_value(self) -> dict[str, Any]:
        return {
            "result": self.result.to_canonical_value(),
            "verifier_identity": self.verifier_identity,
            "verifier_runtime_capability_profile_identity": (
                self.verifier_runtime_capability_profile_identity
            ),
            "coverage": [entry.to_canonical_value() for entry in self.coverage],
            "verdict": self.verdict,
            "findings": [finding.to_canonical_value() for finding in self.findings],
        }


def schema_version_for_kind(contract_kind: ContractKind) -> int:
    """Return the current schema version for one protocol contract kind."""

    return _SCHEMA_VERSION_BY_KIND.get(contract_kind, SCHEMA_VERSION)


@dataclass(frozen=True)
class ReceiptV1:
    """Terminal Receipt bound to an exact Verification reference."""

    verification: RecordRef
    receipt_type: str

    def to_canonical_value(self) -> dict[str, Any]:
        return {
            "verification": self.verification.to_canonical_value(),
            "receipt_type": self.receipt_type,
        }


def request_v1_content_digest(request: RequestV1) -> str:
    """Content identity of a Request candidate (no publication metadata)."""

    return content_digest(
        {
            "contract_kind": ContractKind.REQUEST.value,
            "protocol_version": PROTOCOL_VERSION,
            "schema_version": schema_version_for_kind(ContractKind.REQUEST),
            "payload": request.to_canonical_value(),
        }
    )


def workflow_revision_v1_content_digest(revision: WorkflowRevisionV1) -> str:
    """Content identity of a Workflow Revision candidate."""

    return content_digest(
        {
            "contract_kind": ContractKind.WORKFLOW_REVISION.value,
            "protocol_version": PROTOCOL_VERSION,
            "schema_version": schema_version_for_kind(ContractKind.WORKFLOW_REVISION),
            "payload": revision.to_canonical_value(),
        }
    )


def attempt_packet_v1_content_digest(packet: AttemptPacketV1) -> str:
    """Content identity of an Attempt Packet candidate."""

    return content_digest(
        {
            "contract_kind": ContractKind.ATTEMPT_PACKET.value,
            "protocol_version": PROTOCOL_VERSION,
            "schema_version": schema_version_for_kind(ContractKind.ATTEMPT_PACKET),
            "payload": packet.to_canonical_value(),
        }
    )


def result_v1_content_digest(result: ResultV1) -> str:
    """Content identity of a Result candidate."""

    return content_digest(
        {
            "contract_kind": ContractKind.RESULT.value,
            "protocol_version": PROTOCOL_VERSION,
            "schema_version": schema_version_for_kind(ContractKind.RESULT),
            "payload": result.to_canonical_value(),
        }
    )


def verification_v1_content_digest(verification: VerificationV1) -> str:
    """Content identity of a Verification candidate."""

    return content_digest(
        {
            "contract_kind": ContractKind.VERIFICATION.value,
            "protocol_version": PROTOCOL_VERSION,
            "schema_version": schema_version_for_kind(ContractKind.VERIFICATION),
            "payload": verification.to_canonical_value(),
        }
    )


def receipt_v1_content_digest(receipt: ReceiptV1) -> str:
    """Content identity of a Receipt candidate."""

    return content_digest(
        {
            "contract_kind": ContractKind.RECEIPT.value,
            "protocol_version": PROTOCOL_VERSION,
            "schema_version": schema_version_for_kind(ContractKind.RECEIPT),
            "payload": receipt.to_canonical_value(),
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


def _require_content_digest(value: Any, what: str) -> str:
    if not is_content_digest(value):
        raise ProtocolRejected(
            ProtocolRejectionCode.MALFORMED_PAYLOAD, f"{what}_malformed"
        )
    return value


def _require_versioned_identity_shape(value: Any, what: str) -> str:
    try:
        _require_versioned_identity(what, value)
    except (TypeError, ValueError) as error:
        raise ProtocolRejected(
            ProtocolRejectionCode.MALFORMED_PAYLOAD, f"{what}_malformed"
        ) from error
    return value


def _require_string_sequence(
    value: Any, what: str, *, allow_empty: bool
) -> tuple[str, ...]:
    if not isinstance(value, list):
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


def read_attempt_packet_v1(payload: Any) -> ReaderOutcome:
    """Strictly read an Attempt Packet v1 payload or raise ``ProtocolRejected``.

    The fixture-level identity fields (``context_digest``,
    ``workspace_snapshot_digest``, ``runtime_capability_profile_identity``)
    are opaque non-empty strings here: no real Context Compiler, Host
    snapshot, or capability profile exists yet, so this reader fixes only
    their shape, not their meaning. Whether ``task_id`` matches the bound
    Workflow Revision's task is lineage-aware and checked at the publish
    boundary, not here.
    """

    candidate = _require_object(payload, "attempt_packet_payload")
    _require_exact_keys(candidate, _ATTEMPT_PACKET_KEYS, "attempt_packet_payload")

    workflow_revision = read_record_ref(candidate["workflow_revision"])
    if workflow_revision.contract_kind != ContractKind.WORKFLOW_REVISION:
        raise ProtocolRejected(
            ProtocolRejectionCode.BINDING_MISMATCH,
            "attempt_packet_workflow_revision_kind_not_workflow_revision",
        )
    packet = AttemptPacketV1(
        workflow_revision=workflow_revision,
        task_id=_require_nonempty_string(
            candidate["task_id"], "attempt_packet_task_id"
        ),
        implementer_identity=_require_nonempty_string(
            candidate["implementer_identity"], "attempt_packet_implementer_identity"
        ),
        context_digest=_require_nonempty_string(
            candidate["context_digest"], "attempt_packet_context_digest"
        ),
        workspace_snapshot_digest=_require_nonempty_string(
            candidate["workspace_snapshot_digest"],
            "attempt_packet_workspace_snapshot_digest",
        ),
        runtime_capability_profile_identity=_require_nonempty_string(
            candidate["runtime_capability_profile_identity"],
            "attempt_packet_runtime_capability_profile_identity",
        ),
    )
    return ReaderOutcome(
        value=packet, canonical_payload=packet.to_canonical_value()
    )


def _read_observation_v1(payload: Any) -> RuntimeObservationV1:
    observation = _require_object(payload, "observation")
    _require_exact_keys(observation, _OBSERVATION_KEYS, "observation")
    return RuntimeObservationV1(
        runtime_identity=_require_nonempty_string(
            observation["runtime_identity"], "observation_runtime_identity"
        ),
        output_snapshot_digest=_require_content_digest(
            observation["output_snapshot_digest"],
            "observation_output_snapshot_digest",
        ),
        execution_identity=_require_content_digest(
            observation["execution_identity"], "observation_execution_identity"
        ),
    )


def _read_legacy_observation_v1(payload: Any) -> _LegacyRuntimeObservationV1:
    observation = _require_object(payload, "observation")
    _require_exact_keys(observation, _LEGACY_OBSERVATION_KEYS, "observation")
    return _LegacyRuntimeObservationV1(
        runtime_identity=_require_nonempty_string(
            observation["runtime_identity"], "observation_runtime_identity"
        ),
        output_snapshot_digest=_require_content_digest(
            observation["output_snapshot_digest"],
            "observation_output_snapshot_digest",
        ),
    )


def read_result_v1(payload: Any) -> ReaderOutcome:
    """Strictly read the current protocol-v1 Result payload.

    The Observation/Observation binding — ``observation
    .output_snapshot_digest`` equal to the sibling ``output_snapshot_digest``
    field — is entirely payload-local and therefore enforced here. Only the
    binding of ``result.attempt`` to the actually-published Attempt Packet is
    lineage-aware and belongs to the publish boundary.
    """

    candidate = _require_object(payload, "result_payload")
    _require_exact_keys(candidate, _RESULT_KEYS, "result_payload")

    attempt = read_record_ref(candidate["attempt"])
    if attempt.contract_kind != ContractKind.ATTEMPT_PACKET:
        raise ProtocolRejected(
            ProtocolRejectionCode.BINDING_MISMATCH,
            "result_attempt_kind_not_attempt_packet",
        )
    output_snapshot_digest = _require_content_digest(
        candidate["output_snapshot_digest"], "result_output_snapshot_digest"
    )
    observation = _read_observation_v1(candidate["observation"])
    if observation.output_snapshot_digest != output_snapshot_digest:
        raise ProtocolRejected(
            ProtocolRejectionCode.MALFORMED_PAYLOAD,
            "result_observation_output_snapshot_digest_mismatch",
        )
    result = ResultV1(
        attempt=attempt,
        output_snapshot_digest=output_snapshot_digest,
        observation=observation,
    )
    return ReaderOutcome(
        value=result, canonical_payload=result.to_canonical_value()
    )


def read_legacy_result_v1(payload: Any) -> ReaderOutcome:
    """Read the retained pre-round-2 Result v1 wire shape for replay."""

    candidate = _require_object(payload, "result_payload")
    observation_payload = candidate.get("observation")
    has_v2_fields = "execution_identity" in candidate or (
        isinstance(observation_payload, dict)
        and "execution_identity" in observation_payload
    )
    if has_v2_fields:
        raise ProtocolRejected(
            ProtocolRejectionCode.UNSUPPORTED_SCHEMA_VERSION,
            "result_v2_fields_under_schema_v1",
        )
    _require_exact_keys(candidate, _LEGACY_RESULT_KEYS, "result_payload")

    attempt = read_record_ref(candidate["attempt"])
    if attempt.contract_kind != ContractKind.ATTEMPT_PACKET:
        raise ProtocolRejected(
            ProtocolRejectionCode.BINDING_MISMATCH,
            "result_attempt_kind_not_attempt_packet",
        )
    output_snapshot_digest = _require_content_digest(
        candidate["output_snapshot_digest"], "result_output_snapshot_digest"
    )
    observation = _read_legacy_observation_v1(candidate["observation"])
    if observation.output_snapshot_digest != output_snapshot_digest:
        raise ProtocolRejected(
            ProtocolRejectionCode.MALFORMED_PAYLOAD,
            "result_observation_output_snapshot_digest_mismatch",
        )
    result = _LegacyResultV1(
        attempt=attempt,
        output_snapshot_digest=output_snapshot_digest,
        observation=observation,
    )
    return ReaderOutcome(
        value=result, canonical_payload=result.to_canonical_value()
    )


def _read_coverage_entry_v1(payload: Any, what: str) -> CoverageEntryV1:
    entry = _require_object(payload, what)
    _require_exact_keys(entry, _COVERAGE_ENTRY_KEYS, what)
    criterion = _require_nonempty_string(entry["criterion"], f"{what}_criterion")
    status = entry["status"]
    if not isinstance(status, str) or status not in _COVERAGE_STATUSES:
        raise ProtocolRejected(
            ProtocolRejectionCode.MALFORMED_PAYLOAD, f"{what}_status_invalid"
        )
    evidence_class = _require_versioned_identity_shape(
        entry["evidence_class"], f"{what}_evidence_class"
    )
    evidence_digest = entry["evidence_digest"]
    if status == "SATISFIED":
        if not is_content_digest(evidence_digest):
            raise ProtocolRejected(
                ProtocolRejectionCode.MALFORMED_PAYLOAD,
                f"{what}_evidence_digest_malformed",
            )
    elif evidence_digest is not None:
        raise ProtocolRejected(
            ProtocolRejectionCode.MALFORMED_PAYLOAD,
            f"{what}_evidence_digest_not_null",
        )
    return CoverageEntryV1(
        criterion=criterion,
        status=status,
        evidence_digest=evidence_digest,
        evidence_class=evidence_class,
    )


def _read_coverage_v1(payload: Any) -> tuple[CoverageEntryV1, ...]:
    if not isinstance(payload, list):
        raise ProtocolRejected(
            ProtocolRejectionCode.MALFORMED_PAYLOAD, "verification_coverage_not_sequence"
        )
    if not payload:
        raise ProtocolRejected(
            ProtocolRejectionCode.MALFORMED_PAYLOAD, "verification_coverage_empty"
        )
    return tuple(
        _read_coverage_entry_v1(item, f"verification_coverage[{index}]")
        for index, item in enumerate(payload)
    )


def _read_finding_v1(payload: Any, what: str) -> FindingV1:
    finding = _require_object(payload, what)
    _require_exact_keys(finding, _FINDING_KEYS, what)
    criterion = _require_nonempty_string(finding["criterion"], f"{what}_criterion")
    description = _require_nonempty_string(
        finding["description"], f"{what}_description"
    )
    fingerprint = _require_content_digest(
        finding["fingerprint"], f"{what}_fingerprint"
    )
    expected_fingerprint = content_digest(
        {"criterion": criterion, "description": description}
    )
    if fingerprint != expected_fingerprint:
        raise ProtocolRejected(
            ProtocolRejectionCode.MALFORMED_PAYLOAD,
            f"{what}_fingerprint_mismatch",
        )
    state = finding["state"]
    if not isinstance(state, str) or state not in _FINDING_STATES:
        raise ProtocolRejected(
            ProtocolRejectionCode.MALFORMED_PAYLOAD, f"{what}_state_invalid"
        )
    predecessor_value = finding["predecessor"]
    predecessor = (
        None if predecessor_value is None else read_record_ref(predecessor_value)
    )
    if state == "OPEN" and predecessor is not None:
        raise ProtocolRejected(
            ProtocolRejectionCode.MALFORMED_PAYLOAD,
            f"{what}_open_predecessor_must_be_null",
        )
    if state != "OPEN" and predecessor is None:
        raise ProtocolRejected(
            ProtocolRejectionCode.MALFORMED_PAYLOAD,
            f"{what}_non_open_predecessor_required",
        )
    return FindingV1(
        criterion=criterion,
        fingerprint=fingerprint,
        description=description,
        state=state,
        predecessor=predecessor,
    )


def _read_findings_v1(payload: Any) -> tuple[FindingV1, ...]:
    if not isinstance(payload, list):
        raise ProtocolRejected(
            ProtocolRejectionCode.MALFORMED_PAYLOAD,
            "verification_findings_not_sequence",
        )
    return tuple(
        _read_finding_v1(item, f"verification_findings[{index}]")
        for index, item in enumerate(payload)
    )


def _computed_verdict(coverage: tuple[CoverageEntryV1, ...]) -> str:
    """Total verdict function of coverage (M2 §3): PASS, else BLOCKED, else FAIL."""

    if coverage and all(
        entry.status == "SATISFIED" and entry.evidence_digest is not None
        for entry in coverage
    ):
        return "PASS"
    if any(entry.status == "BLOCKED" for entry in coverage):
        return "BLOCKED"
    return "FAIL"


def _read_legacy_coverage_entry_v1(
    payload: Any, what: str
) -> _LegacyCoverageEntryV1:
    entry = _require_object(payload, what)
    _require_exact_keys(entry, _LEGACY_COVERAGE_ENTRY_KEYS, what)
    criterion = _require_nonempty_string(entry["criterion"], f"{what}_criterion")
    status = entry["status"]
    if not isinstance(status, str) or status not in _COVERAGE_STATUSES:
        raise ProtocolRejected(
            ProtocolRejectionCode.MALFORMED_PAYLOAD, f"{what}_status_invalid"
        )
    evidence_digest = entry["evidence_digest"]
    if status == "SATISFIED":
        if not is_content_digest(evidence_digest):
            raise ProtocolRejected(
                ProtocolRejectionCode.MALFORMED_PAYLOAD,
                f"{what}_evidence_digest_malformed",
            )
    elif evidence_digest is not None:
        raise ProtocolRejected(
            ProtocolRejectionCode.MALFORMED_PAYLOAD,
            f"{what}_evidence_digest_not_null",
        )
    return _LegacyCoverageEntryV1(
        criterion=criterion, status=status, evidence_digest=evidence_digest
    )


def _read_legacy_coverage_v1(
    payload: Any,
) -> tuple[_LegacyCoverageEntryV1, ...]:
    if not isinstance(payload, list):
        raise ProtocolRejected(
            ProtocolRejectionCode.MALFORMED_PAYLOAD,
            "verification_coverage_not_sequence",
        )
    if not payload:
        raise ProtocolRejected(
            ProtocolRejectionCode.MALFORMED_PAYLOAD, "verification_coverage_empty"
        )
    return tuple(
        _read_legacy_coverage_entry_v1(item, f"verification_coverage[{index}]")
        for index, item in enumerate(payload)
    )


def read_legacy_verification_v1(payload: Any) -> ReaderOutcome:
    """Read the retained pre-M6 Verification v1 wire shape for replay."""

    candidate = _require_object(payload, "verification_payload")
    coverage_payload = candidate.get("coverage")
    findings_payload = candidate.get("findings")
    has_v2_fields = (
        "verifier_runtime_capability_profile_identity" in candidate
        or "verifier_execution_identity" in candidate
    )
    if isinstance(coverage_payload, list) and any(
        isinstance(entry, dict) and "evidence_class" in entry
        for entry in coverage_payload
    ):
        has_v2_fields = True
    if isinstance(findings_payload, list) and any(
        isinstance(finding, dict) for finding in findings_payload
    ):
        has_v2_fields = True
    if has_v2_fields:
        raise ProtocolRejected(
            ProtocolRejectionCode.UNSUPPORTED_SCHEMA_VERSION,
            "verification_v2_fields_under_schema_v1",
        )
    _require_exact_keys(candidate, _LEGACY_VERIFICATION_KEYS, "verification_payload")
    result = read_record_ref(candidate["result"])
    if result.contract_kind != ContractKind.RESULT:
        raise ProtocolRejected(
            ProtocolRejectionCode.BINDING_MISMATCH,
            "verification_result_kind_not_result",
        )
    coverage = _read_legacy_coverage_v1(candidate["coverage"])
    verdict = candidate["verdict"]
    if not isinstance(verdict, str) or verdict not in _VERDICTS:
        raise ProtocolRejected(
            ProtocolRejectionCode.MALFORMED_PAYLOAD, "verification_verdict_invalid"
        )
    computed = _computed_verdict(coverage)  # type: ignore[arg-type]
    if verdict != computed:
        raise ProtocolRejected(
            ProtocolRejectionCode.MALFORMED_PAYLOAD,
            f"verification_verdict_mismatch_declared={verdict}_computed={computed}",
        )
    findings = _require_string_sequence(
        candidate["findings"], "verification_findings", allow_empty=True
    )
    if verdict == "PASS" and findings:
        raise ProtocolRejected(
            ProtocolRejectionCode.MALFORMED_PAYLOAD,
            "verification_findings_nonempty_for_pass_verdict",
        )
    verification = _LegacyVerificationV1(
        result=result,
        verifier_identity=_require_nonempty_string(
            candidate["verifier_identity"], "verification_verifier_identity"
        ),
        coverage=coverage,
        verdict=verdict,
        findings=findings,
    )
    return ReaderOutcome(
        value=verification, canonical_payload=verification.to_canonical_value()
    )


def read_legacy_verification_v1_round_one(payload: Any) -> ReaderOutcome:
    """Read the retained round-1 Verification schema-2 wire shape for replay."""

    candidate = _require_object(payload, "verification_payload")
    _require_exact_keys(
        candidate, _LEGACY_VERIFICATION_ROUND_ONE_KEYS, "verification_payload"
    )

    result = read_record_ref(candidate["result"])
    if result.contract_kind != ContractKind.RESULT:
        raise ProtocolRejected(
            ProtocolRejectionCode.BINDING_MISMATCH,
            "verification_result_kind_not_result",
        )
    coverage = _read_coverage_v1(candidate["coverage"])
    verdict = candidate["verdict"]
    if not isinstance(verdict, str) or verdict not in _VERDICTS:
        raise ProtocolRejected(
            ProtocolRejectionCode.MALFORMED_PAYLOAD, "verification_verdict_invalid"
        )
    computed = _computed_verdict(coverage)
    if verdict != computed:
        raise ProtocolRejected(
            ProtocolRejectionCode.MALFORMED_PAYLOAD,
            f"verification_verdict_mismatch_declared={verdict}_computed={computed}",
        )
    verifier_runtime_capability_profile_identity = _require_content_digest(
        candidate["verifier_runtime_capability_profile_identity"],
        "verification_verifier_runtime_capability_profile_identity",
    )
    findings = _read_findings_v1(candidate["findings"])
    if verdict == "PASS" and findings:
        raise ProtocolRejected(
            ProtocolRejectionCode.MALFORMED_PAYLOAD,
            "verification_findings_nonempty_for_pass_verdict",
        )
    verification = _LegacyVerificationV1RoundOne(
        result=result,
        verifier_identity=_require_nonempty_string(
            candidate["verifier_identity"], "verification_verifier_identity"
        ),
        verifier_runtime_capability_profile_identity=(
            verifier_runtime_capability_profile_identity
        ),
        coverage=coverage,
        verdict=verdict,
        findings=findings,
    )
    return ReaderOutcome(
        value=verification, canonical_payload=verification.to_canonical_value()
    )


def read_verification_v1(payload: Any) -> ReaderOutcome:
    """Strictly read a Verification v1 payload or raise ``ProtocolRejected``.

    ``verdict`` is a total function of ``coverage`` recomputed here; a
    declared value that differs rejects as ``MALFORMED_PAYLOAD``. Whether
    ``coverage`` matches the bound Workflow Revision's acceptance criteria,
    and whether a ``SATISFIED`` entry's evidence digest equals the bound
    Result's output snapshot digest, are lineage-aware and belong to the
    publish boundary, not here.
    """

    candidate = _require_object(payload, "verification_payload")
    _require_exact_keys(candidate, _VERIFICATION_KEYS, "verification_payload")

    result = read_record_ref(candidate["result"])
    if result.contract_kind != ContractKind.RESULT:
        raise ProtocolRejected(
            ProtocolRejectionCode.BINDING_MISMATCH,
            "verification_result_kind_not_result",
        )
    coverage = _read_coverage_v1(candidate["coverage"])
    verdict = candidate["verdict"]
    if not isinstance(verdict, str) or verdict not in _VERDICTS:
        raise ProtocolRejected(
            ProtocolRejectionCode.MALFORMED_PAYLOAD, "verification_verdict_invalid"
        )
    computed = _computed_verdict(coverage)
    if verdict != computed:
        raise ProtocolRejected(
            ProtocolRejectionCode.MALFORMED_PAYLOAD,
            f"verification_verdict_mismatch_declared={verdict}_computed={computed}",
        )
    verifier_runtime_capability_profile_identity = _require_content_digest(
        candidate["verifier_runtime_capability_profile_identity"],
        "verification_verifier_runtime_capability_profile_identity",
    )
    verifier_execution_identity = _require_content_digest(
        candidate["verifier_execution_identity"],
        "verification_verifier_execution_identity",
    )
    findings = _read_findings_v1(candidate["findings"])
    if verdict == "PASS" and findings:
        raise ProtocolRejected(
            ProtocolRejectionCode.MALFORMED_PAYLOAD,
            "verification_findings_nonempty_for_pass_verdict",
        )
    verification = VerificationV1(
        result=result,
        verifier_identity=_require_nonempty_string(
            candidate["verifier_identity"], "verification_verifier_identity"
        ),
        verifier_runtime_capability_profile_identity=(
            verifier_runtime_capability_profile_identity
        ),
        verifier_execution_identity=verifier_execution_identity,
        coverage=coverage,
        verdict=verdict,
        findings=findings,
    )
    return ReaderOutcome(
        value=verification, canonical_payload=verification.to_canonical_value()
    )


def read_receipt_v1(payload: Any) -> ReaderOutcome:
    """Strictly read a Receipt v1 payload or raise ``ProtocolRejected``.

    M2 accepts only ``receipt_type == "terminal"``; the field exists so the
    schema does not change shape when a checkpoint variant arrives later.
    Whether the bound Verification's verdict is ``PASS`` is lineage-aware and
    belongs to the publish boundary, not here.
    """

    candidate = _require_object(payload, "receipt_payload")
    _require_exact_keys(candidate, _RECEIPT_KEYS, "receipt_payload")

    verification = read_record_ref(candidate["verification"])
    if verification.contract_kind != ContractKind.VERIFICATION:
        raise ProtocolRejected(
            ProtocolRejectionCode.BINDING_MISMATCH,
            "receipt_verification_kind_not_verification",
        )
    receipt_type = candidate["receipt_type"]
    if receipt_type != RECEIPT_TYPE_TERMINAL:
        raise ProtocolRejected(
            ProtocolRejectionCode.MALFORMED_PAYLOAD, "receipt_type_not_terminal"
        )
    receipt = ReceiptV1(verification=verification, receipt_type=receipt_type)
    return ReaderOutcome(
        value=receipt, canonical_payload=receipt.to_canonical_value()
    )


register_reader(
    ContractKind.REQUEST, PROTOCOL_VERSION, SCHEMA_VERSION, read_request_v1
)
register_reader(
    ContractKind.WORKFLOW_REVISION, PROTOCOL_VERSION, SCHEMA_VERSION, read_workflow_revision_v1
)
register_reader(
    ContractKind.ATTEMPT_PACKET, PROTOCOL_VERSION, SCHEMA_VERSION, read_attempt_packet_v1
)
register_reader(
    ContractKind.RESULT,
    PROTOCOL_VERSION,
    SCHEMA_VERSION,
    read_legacy_result_v1,
)
register_reader(
    ContractKind.RESULT,
    PROTOCOL_VERSION,
    RESULT_SCHEMA_VERSION,
    read_result_v1,
)
register_reader(
    ContractKind.VERIFICATION,
    PROTOCOL_VERSION,
    SCHEMA_VERSION,
    read_legacy_verification_v1,
)
register_reader(
    ContractKind.VERIFICATION,
    PROTOCOL_VERSION,
    2,
    read_legacy_verification_v1_round_one,
)
register_reader(
    ContractKind.VERIFICATION,
    PROTOCOL_VERSION,
    VERIFICATION_SCHEMA_VERSION,
    read_verification_v1,
)
register_reader(
    ContractKind.RECEIPT, PROTOCOL_VERSION, SCHEMA_VERSION, read_receipt_v1
)
