"""Builders for execution-chain candidates with M2/M3 identity semantics.

These builders construct *unpublished* candidate payloads from identities the
caller already holds. Every ``RecordRef`` argument must be the published
record identity ``publish()`` actually returned — a candidate payload object
carries no Kernel-assigned ``record_id``/``content_digest`` and cannot fill a
contract's own binding field. M3 computes the workspace snapshot and runtime
capability profile identities from the real workspace and adapter probe here;
M4 compiles ``context_digest`` through the deterministic Context Compiler,
after fail-closed verification of the caller-held ``task`` and
``workflow_revision_ref`` against the run's committed Workflow Revision.
"""

from __future__ import annotations

from pathlib import Path

from kernel.canonical import content_digest
from kernel.protocol import ContractKind, RecordRef
from kernel.protocol_v1 import (
    RECEIPT_TYPE_TERMINAL,
    AttemptPacketV1,
    ReceiptV1,
    TaskV1,
)
from kernel.publish import read_committed_contract
from execution.context_compiler import (
    compile_context_pack,
    disclosure_identity,
    reject_unverified_contract_refs,
)
from execution.opencode_adapter import probe_opencode_profile
from execution.workspace_snapshot import snapshot_identity

class TaskBindingMismatchError(Exception):
    """Caller-held task or workflow-revision ref disagrees with the run's
    committed Workflow Revision; no packet is built."""


def build_attempt_packet(
    workflow_revision_ref: RecordRef,
    task_id: str,
    implementer_identity: str,
    state: str,
    run_id: str,
    task: TaskV1,
    workspace_root: Path,
    opencode_binary_path: str,
    config_paths: tuple[Path, ...] = (),
    declared_generated_paths: tuple[str, ...] = (),
    contract_refs: tuple[RecordRef, ...] = (),
    run_message_template_revision: str = "v1",
) -> AttemptPacketV1:
    """Build an Attempt Packet candidate bound to a published Workflow Revision.

    Before any context is compiled, the caller-held ``task`` and
    ``workflow_revision_ref`` are verified fail-closed against the run's
    actually-committed Workflow Revision (re-read through the Kernel's own
    record read path): both must match or ``TaskBindingMismatchError`` is
    raised and no packet is built. ``workspace_snapshot_digest`` and
    ``runtime_capability_profile_identity`` are resolved from the real
    workspace and OpenCode adapter profile at packet-construction time, and
    ``context_digest`` is the digest of the real Context Pack compiled from
    the authoritative task, both derived identities, and ``contract_refs``.
    """

    reject_unverified_contract_refs(contract_refs)

    if task_id != task.task_id:
        raise TaskBindingMismatchError(
            f"task_id argument {task_id!r} disagrees with task.task_id "
            f"{task.task_id!r}"
        )

    revision_ref, revision = read_committed_contract(
        state, run_id, ContractKind.WORKFLOW_REVISION
    )
    if revision_ref != workflow_revision_ref:
        raise TaskBindingMismatchError(
            "workflow_revision_ref binding mismatch: "
            f"caller_ref={workflow_revision_ref} committed_ref={revision_ref}"
        )
    bound_task = next(
        (
            candidate
            for candidate in getattr(revision, "tasks", ())
            if candidate.task_id == task_id
        ),
        None,
    )
    if bound_task is None:
        raise TaskBindingMismatchError(
            f"task_id argument {task_id!r} is not present in the committed "
            "Workflow Revision's tasks"
        )
    committed_task_digest = content_digest(bound_task.to_canonical_value())
    caller_task_digest = content_digest(task.to_canonical_value())
    if committed_task_digest != caller_task_digest:
        raise TaskBindingMismatchError(
            "task binding mismatch against committed Workflow Revision: "
            f"caller_task_digest={caller_task_digest} "
            f"committed_task_digest={committed_task_digest}"
        )

    snapshot_digest = snapshot_identity(
        workspace_root, declared_generated_paths
    ).digest
    profile_identity = probe_opencode_profile(
        opencode_binary_path, config_paths
    ).identity
    # disclosure_identity must match host.execute()'s third pre-spawn
    # recheck exactly (same shared helper, same run_message_template_revision
    # default) — a mismatch here would make every execute() call raise
    # StaleContextPackError even with no real drift, since compile time and
    # execute time would never agree. reserved_cost is computed inside
    # compile_context_pack itself now (from the real rendered message), not
    # passed in — see context_compiler.py's compile_context_pack docstring.
    context_pack = compile_context_pack(
        task_id=task_id,
        task_objective=task.objective,
        task_acceptance_criteria=task.acceptance_criteria,
        workspace_snapshot_digest=snapshot_digest,
        runtime_capability_profile_identity=profile_identity,
        contract_refs=contract_refs,
        disclosure_identity=disclosure_identity(
            profile_identity, run_message_template_revision
        ),
    )

    return AttemptPacketV1(
        workflow_revision=workflow_revision_ref,
        task_id=task_id,
        implementer_identity=implementer_identity,
        context_digest=context_pack.digest,
        workspace_snapshot_digest=snapshot_digest,
        runtime_capability_profile_identity=profile_identity,
    )


def build_receipt(verification_ref: RecordRef) -> ReceiptV1:
    """Build a terminal Receipt candidate bound to a published Verification.

    The driver should only call this after observing ``verdict == PASS``;
    ``publish()`` remains the source of truth and rejects a Receipt against a
    non-PASS Verification regardless.
    """

    return ReceiptV1(
        verification=verification_ref,
        receipt_type=RECEIPT_TYPE_TERMINAL,
    )
