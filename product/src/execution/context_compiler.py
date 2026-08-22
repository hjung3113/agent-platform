"""Data shapes for the M4 deterministic Context Compiler.

This replaces the ``AttemptPacketV1.context_digest`` fixture.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from kernel.canonical import content_digest
from kernel.protocol import RecordRef


@dataclass(frozen=True)
class ContextUnit:
    source_class: str  # "control" | "lineage" | "observed" | "derived"
    source_identity: str
    scope: str
    inclusion_reason: str
    requirement: str  # "required" | "optional"
    content: str
    content_digest: str
    estimated_cost: int

    def to_canonical_value(self) -> dict[str, Any]:
        return {
            "source_class": self.source_class,
            "source_identity": self.source_identity,
            "scope": self.scope,
            "inclusion_reason": self.inclusion_reason,
            "requirement": self.requirement,
            "content": self.content,
            "content_digest": self.content_digest,
            "estimated_cost": self.estimated_cost,
        }


@dataclass(frozen=True)
class OmissionRecord:
    source_identity: str
    scope: str
    reason: str

    def to_canonical_value(self) -> dict[str, Any]:
        return {
            "source_identity": self.source_identity,
            "scope": self.scope,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class ContextPack:
    task_id: str
    units: tuple[ContextUnit, ...]
    selection_policy: str
    estimator: str
    required_cost: int
    optional_cost: int
    reserved_cost: int
    disclosure_identity: str
    omitted: tuple[OmissionRecord, ...]

    def to_canonical_value(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "units": [unit.to_canonical_value() for unit in self.units],
            "selection_policy": self.selection_policy,
            "estimator": self.estimator,
            "required_cost": self.required_cost,
            "optional_cost": self.optional_cost,
            "reserved_cost": self.reserved_cost,
            "disclosure_identity": self.disclosure_identity,
            "omitted": [record.to_canonical_value() for record in self.omitted],
        }

    @property
    def digest(self) -> str:
        return content_digest(self.to_canonical_value())


class CONTEXT_BUDGET_EXCEEDED(Exception):
    """required_cost, or required_cost + reserved_cost with no optional unit able to absorb the excess, exceeds CONTEXT_BUDGET_MAX; no Context Pack is built."""

    pass


class ConflictingContractRefError(Exception):
    """Two admitted contract refs share record_id but differ in content_digest."""

    pass


ESTIMATOR_IDENTITY = "byte_length_estimator@1"


def estimate_cost(content: str) -> int:
    return len(content.encode("utf-8"))


# 128 KiB, comfortably under a conservative ARG_MAX floor — see plan §5.3 LOW 4.
CONTEXT_BUDGET_MAX = 131072

# Reserved cost for the runtime's own run-message envelope overhead only
# (plan §5.2): the fixed argv cost of wrapping the rendered Context Pack,
# beyond the pack's own content. A constant by design — not derived from
# live state, and not a safety margin for the runtime's own unknowable
# system-prompt size, which is genuinely outside this repo's visibility.
# Shared by execution.attempt (compile time) and execution.host (execute
# time) so both sides compute the identical reserved-cost/disclosure
# identity — see attempt.py/host.py for why this must not drift between
# compile and execute.
RUN_MESSAGE_ENVELOPE_OVERHEAD_BYTES = 64


def disclosure_identity(runtime_identity: str, run_message_template_revision: str) -> str:
    """Digest-covered renderer identity for the reserved-cost envelope (§5.2).

    Folding this identity (not just the reserved-cost int) into the pack's
    canonical value means a render-template or runtime change between
    packet publication and ``execute()`` changes ``ContextPack.digest``
    itself, so the third pre-spawn staleness check actually catches it.
    """

    return content_digest(
        {
            "runtime_identity": runtime_identity,
            "run_message_template_revision": run_message_template_revision,
        }
    )

SELECTION_POLICY_IDENTITY = "m4_fixed_order@1"


def _utf16_sort_key(value: str) -> bytes:
    return value.encode("utf-16-be")


def compile_context_pack(
    *,
    task_id: str,
    task_objective: str,
    task_acceptance_criteria: tuple[str, ...],
    workspace_snapshot_digest: str,
    runtime_capability_profile_identity: str,
    contract_refs: tuple[RecordRef, ...] = (),
    reserved_cost: int,
    disclosure_identity: str,
) -> ContextPack:
    by_record_id: dict[str, list[RecordRef]] = {}
    for ref in contract_refs:
        by_record_id.setdefault(ref.record_id, []).append(ref)

    sorted_record_ids = sorted(by_record_id, key=_utf16_sort_key)
    for record_id in sorted_record_ids:
        group = by_record_id[record_id]
        if len({ref.content_digest for ref in group}) > 1:
            raise ConflictingContractRefError(
                f"contract refs share record_id {record_id!r} "
                "but differ in content_digest"
            )

    units: list[ContextUnit] = []

    def append_unit(
        source_class: str,
        source_identity: str,
        scope: str,
        content: str,
        inclusion_reason: str,
        requirement: str,
    ) -> None:
        units.append(
            ContextUnit(
                source_class=source_class,
                source_identity=source_identity,
                scope=scope,
                inclusion_reason=inclusion_reason,
                requirement=requirement,
                content=content,
                content_digest=content_digest(content),
                estimated_cost=estimate_cost(content),
            )
        )

    append_unit(
        "control",
        f"task:{task_id}",
        "task.objective",
        task_objective,
        "authoritative task objective",
        "required",
    )
    append_unit(
        "control",
        f"task:{task_id}",
        "task.acceptance_criteria",
        "\n".join(f"- {c}" for c in task_acceptance_criteria),
        "authoritative task acceptance criteria",
        "required",
    )
    append_unit(
        "derived",
        "workspace_snapshot",
        "workspace_snapshot.digest",
        workspace_snapshot_digest,
        "workspace identity at admission time",
        "required",
    )
    append_unit(
        "derived",
        "runtime_capability_profile",
        "runtime_capability_profile.identity",
        runtime_capability_profile_identity,
        "runtime capability identity at admission time",
        "required",
    )
    for record_id in sorted_record_ids:
        ref = by_record_id[record_id][0]
        append_unit(
            "control",
            f"contract_ref:{ref.record_id}",
            "contract_ref",
            ref.content_digest,
            "admitted decision/contract reference",
            "required",
        )

    required_cost = sum(
        unit.estimated_cost for unit in units if unit.requirement == "required"
    )
    optional_cost = sum(
        unit.estimated_cost for unit in units if unit.requirement == "optional"
    )
    if required_cost + optional_cost + reserved_cost > CONTEXT_BUDGET_MAX:
        raise CONTEXT_BUDGET_EXCEEDED(
            f"required_cost {required_cost} + optional_cost {optional_cost} "
            f"+ reserved_cost {reserved_cost} exceeds "
            f"CONTEXT_BUDGET_MAX {CONTEXT_BUDGET_MAX}"
        )

    return ContextPack(
        task_id=task_id,
        units=tuple(units),
        selection_policy=SELECTION_POLICY_IDENTITY,
        estimator=ESTIMATOR_IDENTITY,
        required_cost=required_cost,
        optional_cost=optional_cost,
        reserved_cost=reserved_cost,
        disclosure_identity=disclosure_identity,
        omitted=(),
    )
