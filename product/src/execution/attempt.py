"""Builders for execution-chain candidates with M2/M3 identity semantics.

These builders construct *unpublished* candidate payloads from identities the
caller already holds. Every ``RecordRef`` argument must be the published
record identity ``publish()`` actually returned — a candidate payload object
carries no Kernel-assigned ``record_id``/``content_digest`` and cannot fill a
contract's own binding field. M3 computes the workspace snapshot and runtime
capability profile identities from the real workspace and adapter probe here;
``context_digest`` remains M2's fixture identity until M4's Context Compiler.
"""

from __future__ import annotations

from pathlib import Path

from kernel.canonical import content_digest
from kernel.protocol import RecordRef
from kernel.protocol_v1 import (
    RECEIPT_TYPE_TERMINAL,
    AttemptPacketV1,
    ReceiptV1,
)
from execution.opencode_adapter import probe_opencode_profile
from execution.workspace_snapshot import snapshot_identity

_FIXTURE_TAG = "m2-fixture"


def _fixture_digest(purpose: str, task_id: str) -> str:
    """Deterministic content digest scoped by purpose and task, nothing else."""

    return content_digest({"fixture": _FIXTURE_TAG, "purpose": purpose, "task_id": task_id})


def build_attempt_packet(
    workflow_revision_ref: RecordRef,
    task_id: str,
    implementer_identity: str,
    workspace_root: Path,
    opencode_binary_path: str,
    config_paths: tuple[Path, ...] = (),
    declared_generated_paths: tuple[str, ...] = (),
) -> AttemptPacketV1:
    """Build an Attempt Packet candidate bound to a published Workflow Revision.

    ``workspace_snapshot_digest`` and
    ``runtime_capability_profile_identity`` are resolved from the real
    workspace and OpenCode adapter profile at packet-construction time.
    ``context_digest`` intentionally remains M2's deterministic fixture value;
    real Context Compilation is M4 scope.
    """

    return AttemptPacketV1(
        workflow_revision=workflow_revision_ref,
        task_id=task_id,
        implementer_identity=implementer_identity,
        context_digest=_fixture_digest("context", task_id),
        workspace_snapshot_digest=snapshot_identity(
            workspace_root, declared_generated_paths
        ).digest,
        runtime_capability_profile_identity=probe_opencode_profile(
            opencode_binary_path, config_paths
        ).identity,
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
