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
    rendered_digest: str
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
            "rendered_digest": self.rendered_digest,
            "omitted": [record.to_canonical_value() for record in self.omitted],
        }

    @property
    def digest(self) -> str:
        return content_digest(self.to_canonical_value())


class CONTEXT_BUDGET_EXCEEDED(Exception):
    """required_cost + optional_cost + reserved_cost exceeds CONTEXT_BUDGET_MAX; no Context Pack is built.

    No real M4 candidate is ever ``optional`` (§2/§9), so ``optional_cost``
    is ``0`` on every real path today — this predicate is written as the
    general sum, not specialized to "required alone", so it is already
    correct if/when a later milestone adds real optional candidates. No
    omission-selection logic exists yet to omit optional units and retry
    under budget (PR #47 review round 2 LOW 2 — an earlier version of this
    docstring implied that machinery exists; it does not, only the
    ``OmissionRecord`` shape and an always-empty ``omitted=()`` do, as
    forward-compatible scaffolding per HANDOFF's M4 design-grilling round 2).
    """

    pass


class ConflictingContractRefError(Exception):
    """Two admitted contract refs share (contract_kind, record_id) but differ in content_digest."""

    pass


class UnverifiedContractRefError(Exception):
    """Non-empty ``contract_refs`` was rejected fail-closed.

    M4 has no Decision/Contract record type or Kernel authority-verification
    read path yet (plan §2: contract-ref compilation is "real machinery
    exercised over an always-empty list today", the same YAGNI shape as
    M3's ``M3_REQUIRED_CAPABILITIES = ()``). Accepting a caller-supplied
    ``RecordRef`` here without verifying it was actually admitted/published
    would let unverified data influence the authoritative Context Pack
    (PR #47 review). Real callers (``execution.attempt.build_attempt_packet``,
    ``execution.host.execute``) must reject any non-empty ``contract_refs``
    until a real authority-verification path exists in a later milestone;
    ``compile_context_pack`` itself stays a pure function that accepts them
    (its dedup/ordering machinery is unit-tested directly), the gate lives
    at the trust boundary instead.
    """

    pass


def reject_unverified_contract_refs(contract_refs: tuple[RecordRef, ...]) -> None:
    """Fail-closed guard for real (non-test) callers — see ``UnverifiedContractRefError``."""

    if contract_refs:
        raise UnverifiedContractRefError(
            f"{len(contract_refs)} contract_refs supplied; M4 has no "
            "authority-verification path for them yet, rejecting fail-closed"
        )


ESTIMATOR_IDENTITY = "byte_length_estimator@1"


def estimate_cost(content: str) -> int:
    return len(content.encode("utf-8"))


# ~117 KiB, safely under a conservative 128 KiB ARG_MAX floor — see plan
# §5.3 LOW 4. The predicate this bounds is the ACTUAL rendered single-argv
# message byte length (see ``compile_context_pack``'s reserved_cost
# computation below, PR #47 review P1) plus the small fixed argv-elements
# allowance, not merely an estimate of unit content.
CONTEXT_BUDGET_MAX = 120000

# Reserved cost for the runtime's own argv elements OTHER than the
# rendered message itself (plan §5.2) — the ``"run"``/``"--workdir"``/
# workspace-path argv elements ``execution.host.execute`` spawns alongside
# the message. A small constant by design — not a safety margin for the
# runtime's own unknowable system-prompt size, which is genuinely outside
# this repo's visibility. The rendered MESSAGE's own overhead (labels,
# separators — PR #47 review P1) is accounted separately and exactly, not
# folded into this constant; see ``compile_context_pack``.
RUN_MESSAGE_ENVELOPE_OVERHEAD_BYTES = 64


def render_context_pack(units: tuple[ContextUnit, ...]) -> str:
    """Render Context Units as labeled sections (plan §7).

    Each unit renders under a ``[source_class: scope]`` label so the
    content/authority boundary survives rendering; unit order is the
    compiler's deterministic order (§4), and unit content is used as-is
    (the acceptance-criteria unit's content is already the compiler's
    bullet-joined string — it is not re-split here). Single source of
    truth for both ``execution.host``'s actual spawn rendering and this
    module's own budget accounting (PR #47 review P1 — the two must never
    diverge, or budget acceptance stops meaning "the real message fits").
    """

    return "\n".join(
        f"[{unit.source_class}: {unit.scope}]\n{unit.content}\n" for unit in units
    )


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


def _conflict_key(ref: RecordRef) -> tuple[str, str]:
    """Group key for conflict detection: (contract_kind, record_id).

    Two refs with the same ``record_id`` but different ``contract_kind``
    are different identities entirely (not the same logical thing under a
    different digest) — they are neither duplicates of each other nor in
    conflict with each other; they are just two distinct refs that happen
    to share a record_id string in different id spaces. Only refs sharing
    BOTH ``contract_kind`` and ``record_id`` can be the same logical ref
    with drifted content, which is the actual conflict this function
    detects (PR #47 review P1 — record_id alone under-keyed this).
    """

    return (ref.contract_kind, ref.record_id)


def compile_context_pack(
    *,
    task_id: str,
    task_objective: str,
    task_acceptance_criteria: tuple[str, ...],
    workspace_snapshot_digest: str,
    runtime_capability_profile_identity: str,
    contract_refs: tuple[RecordRef, ...] = (),
    disclosure_identity: str,
) -> ContextPack:
    by_key: dict[tuple[str, str], list[RecordRef]] = {}
    for ref in contract_refs:
        by_key.setdefault(_conflict_key(ref), []).append(ref)

    sorted_keys = sorted(
        by_key, key=lambda key: (_utf16_sort_key(key[0]), _utf16_sort_key(key[1]))
    )
    for key in sorted_keys:
        group = by_key[key]
        if len({ref.content_digest for ref in group}) > 1:
            raise ConflictingContractRefError(
                f"contract refs share (contract_kind, record_id) {key!r} "
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
    for key in sorted_keys:
        ref = by_key[key][0]
        append_unit(
            "control",
            f"contract_ref:{ref.contract_kind}:{ref.record_id}",
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

    # reserved_cost is computed here, not caller-supplied: the real
    # rendered message's structural overhead (labels/separators, which
    # grow with the unit count — PR #47 review P1) plus the small fixed
    # argv-elements allowance. required_cost + optional_cost always equals
    # sum(unit.estimated_cost for unit in units) since every unit is
    # required or optional, so required_cost + optional_cost + reserved_cost
    # equals exactly len(rendered_message.encode("utf-8")) +
    # RUN_MESSAGE_ENVELOPE_OVERHEAD_BYTES — the predicate below bounds the
    # real spawn argv size, not an estimate of it.
    rendered_message = render_context_pack(tuple(units))
    render_overhead = len(rendered_message.encode("utf-8")) - sum(
        unit.estimated_cost for unit in units
    )
    reserved_cost = RUN_MESSAGE_ENVELOPE_OVERHEAD_BYTES + render_overhead

    if required_cost + optional_cost + reserved_cost > CONTEXT_BUDGET_MAX:
        raise CONTEXT_BUDGET_EXCEEDED(
            f"required_cost {required_cost} + optional_cost {optional_cost} "
            f"+ reserved_cost {reserved_cost} exceeds "
            f"CONTEXT_BUDGET_MAX {CONTEXT_BUDGET_MAX}"
        )

    # rendered_digest closes a gap reserved_cost alone leaves open (PR #47
    # review round 2 MEDIUM 2): reserved_cost only reflects the rendered
    # message's LENGTH, so a length-preserving edit to render_context_pack
    # (e.g. relabeling a section to same-length different text) would
    # change what the runtime actually receives on argv without changing
    # required_cost/optional_cost/reserved_cost, and therefore without
    # changing context_digest — invisible to every staleness check, caught
    # only by developer discipline in bumping run_message_template_revision.
    # Digesting the actual rendered bytes here means ANY change to the real
    # spawn argv — length-changing or not — changes context_digest.
    rendered_digest = content_digest(rendered_message)

    return ContextPack(
        task_id=task_id,
        units=tuple(units),
        selection_policy=SELECTION_POLICY_IDENTITY,
        estimator=ESTIMATOR_IDENTITY,
        required_cost=required_cost,
        optional_cost=optional_cost,
        reserved_cost=reserved_cost,
        disclosure_identity=disclosure_identity,
        rendered_digest=rendered_digest,
        omitted=(),
    )
