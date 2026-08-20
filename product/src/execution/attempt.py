"""Pure builders for M2 fixture-level execution-chain candidates.

These builders construct *unpublished* candidate payloads from identities the
caller already holds. Every ``RecordRef`` argument must be the published
record identity ``publish()`` actually returned — a candidate payload object
carries no Kernel-assigned ``record_id``/``content_digest`` and cannot fill a
contract's own binding field. No real context compilation, workspace
inspection, or runtime execution exists here.
"""

from __future__ import annotations

from kernel.canonical import content_digest
from kernel.protocol import RecordRef
from kernel.protocol_v1 import (
    RECEIPT_TYPE_TERMINAL,
    AttemptPacketV1,
    ReceiptV1,
)

_FIXTURE_TAG = "m2-fixture"


def _fixture_digest(purpose: str, task_id: str) -> str:
    """Deterministic content digest scoped by purpose and task, nothing else."""

    return content_digest({"fixture": _FIXTURE_TAG, "purpose": purpose, "task_id": task_id})


def build_attempt_packet(
    workflow_revision_ref: RecordRef, task_id: str, implementer_identity: str
) -> AttemptPacketV1:
    """Build an Attempt Packet candidate bound to a published Workflow Revision.

    The fixture-level identity fields (``context_digest``,
    ``workspace_snapshot_digest``, ``runtime_capability_profile_identity``)
    are deterministic digests of fixed constants scoped by ``task_id``; no
    real Context Compiler or Host snapshot exists in M2.
    """

    return AttemptPacketV1(
        workflow_revision=workflow_revision_ref,
        task_id=task_id,
        implementer_identity=implementer_identity,
        context_digest=_fixture_digest("context", task_id),
        workspace_snapshot_digest=_fixture_digest("workspace_snapshot", task_id),
        runtime_capability_profile_identity=_fixture_digest(
            "runtime_capability_profile", task_id
        ),
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
