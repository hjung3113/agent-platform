"""Kernel publication boundary: the single production writer of lineage.

``publish()`` is the only production path that may commit authoritative run
records. It consumes an M0-validated candidate (the output of
``kernel.protocol`` reader dispatch), fences it against the run's current
head, and commits it through the ``kernel.lineage_store`` primitive while
holding the run lock.

Committed record envelope (one file per record, written via lineage_store):

- ``run_id`` / ``sequence`` — placement in the run's lineage
- ``record_id`` / ``content_digest`` — Kernel-assigned publication identity
  bound to the candidate's exact content identity
- ``idempotency_key`` — caller-supplied logical-operation identity
- ``candidate`` — the exact ``(contract_kind, protocol_version,
  schema_version, payload)`` wire shape, replayable through
  ``kernel.protocol.read_candidate`` without publish-specific parsing
"""

from __future__ import annotations

import json
import os
import re
import uuid
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Callable, Iterator

from kernel.canonical import canonical_json_bytes, content_digest
from kernel.lineage_store import HeadProjection, RunHandle, open_run
from kernel.protocol import (
    ContractKind,
    ParsedCandidate,
    ReaderOutcome,
    RecordRef,
)
from kernel.protocol_v1 import (
    PROTOCOL_VERSION,
    SCHEMA_VERSION,
    RequestV1,
    WorkflowRevisionV1,
)

_RECORD_FILENAME = re.compile(r"^(\d{10})\.json$")


class PublishRejectionCode(StrEnum):
    """Typed publication rejections, distinct from M0 protocol rejections."""

    RUN_NOT_FOUND = "run_not_found"
    PREDECESSOR_MISMATCH = "predecessor_mismatch"
    IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_CONTENT = (
        "idempotency_key_reused_with_different_content"
    )
    # Placeholder: lineage_store.lock() blocks without a timeout today, so
    # publish() never returns this code yet; the value exists so callers can
    # match rejection codes exhaustively once timeout support is added.
    LOCK_CONTENTION_TIMEOUT = "lock_contention_timeout"


@dataclass(frozen=True)
class Published:
    """Successful publication of one authoritative record."""

    record_ref: RecordRef
    run_id: str


@dataclass(frozen=True)
class Rejected:
    """Typed publication rejection; no record was committed."""

    code: PublishRejectionCode
    reason: str = ""


PublishResult = Published | Rejected


def _candidate_content(
    candidate: ReaderOutcome | ParsedCandidate,
) -> dict[str, Any]:
    """Exact versioned contract content that fixes the record's digest.

    The returned shape is both the digest input (identical to
    ``CandidateEnvelope.to_content_value()``) and the replayable candidate
    envelope stored on disk. For a bare ``ReaderOutcome`` from a registered
    reader, the dispatch key is derived from the typed value; M1 publishes
    only v1 Request and Workflow Revision candidates.
    """

    if isinstance(candidate, ParsedCandidate):
        return candidate.envelope.to_content_value()
    value = candidate.value
    if isinstance(value, RequestV1):
        contract_kind = ContractKind.REQUEST
    elif isinstance(value, WorkflowRevisionV1):
        contract_kind = ContractKind.WORKFLOW_REVISION
    else:
        raise TypeError(
            "unsupported candidate value type: " + type(value).__name__
        )
    return {
        "contract_kind": contract_kind.value,
        "protocol_version": PROTOCOL_VERSION,
        "schema_version": SCHEMA_VERSION,
        "payload": candidate.canonical_payload,
    }


def _committed_records(run: RunHandle) -> Iterator[dict[str, Any]]:
    """Yield parsed committed record envelopes in sequence order."""

    names = sorted(
        entry
        for entry in os.listdir(run.run_dir)
        if _RECORD_FILENAME.fullmatch(entry) is not None
    )
    for name in names:
        try:
            raw = (run.run_dir / name).read_bytes()
        except OSError:
            continue
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            continue
        if isinstance(value, dict):
            yield value


def _record_ref_of(envelope: dict[str, Any]) -> RecordRef:
    """Rebuild the publication RecordRef of a committed record envelope."""

    return RecordRef(
        contract_kind=envelope["candidate"]["contract_kind"],
        record_id=envelope["record_id"],
        content_digest=envelope["content_digest"],
    )


def _find_idempotent_publish(
    run: RunHandle, idempotency_key: str, digest: str
) -> RecordRef | Rejected | None:
    """Locate an earlier commit of ``idempotency_key`` in this run.

    Returns the earlier publication's ``RecordRef`` when the content digest
    matches, a typed rejection when the key was reused for different
    content, and None when the key is unused in this run.
    """

    for envelope in _committed_records(run):
        if envelope.get("idempotency_key") != idempotency_key:
            continue
        if envelope.get("content_digest") == digest:
            return _record_ref_of(envelope)
        return Rejected(
            PublishRejectionCode.IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_CONTENT,
            f"idempotency_key_reused={idempotency_key}",
        )
    return None


def publish(
    state_dir: str,
    run_id: str | None,
    candidate: ReaderOutcome | ParsedCandidate,
    expected_predecessor: RecordRef | None,
    idempotency_key: str,
    commit_barrier: Callable[[], None] | None = None,
) -> PublishResult:
    """Admit and commit one authoritative record under the run lock.

    ``candidate`` is the already-validated output of M0 reader dispatch:
    either the ``ParsedCandidate`` returned by ``read_candidate`` or the bare
    ``ReaderOutcome`` returned by a registered reader.

    Ordering is a correctness invariant: the admission decision, the durable
    commit, and the head-projection update all happen inside the run lock,
    and the idempotency scan runs before predecessor fencing so a retry of
    an already-committed operation succeeds even though the head has since
    advanced.

    Genesis (``run_id is None``) assigns a new run id and requires
    ``expected_predecessor is None``; passing a predecessor for a genesis
    publish is a fencing error and rejects with ``PREDECESSOR_MISMATCH``
    before any state is touched. A non-genesis publish must name an existing
    run holding at least one committed record (else ``RUN_NOT_FOUND``) and
    the current head's ``RecordRef`` (else ``PREDECESSOR_MISMATCH``).

    Idempotency is run-scoped: the scan covers only this run's committed
    records, so retrying a genesis publish with ``run_id=None`` creates a new
    run; callers retrying a genesis operation must pass the previously
    returned ``run_id`` to get the original ``Published`` result back.

    ``commit_barrier`` is a test-only fault-injection seam invoked between
    the durable commit and the head-projection update; production callers
    never pass one. ``record_id`` is derived deterministically as
    ``{run_id}:{sequence}`` so a scan-rebuilt projection reproduces
    publication identity exactly.
    """

    is_genesis = run_id is None
    if is_genesis:
        if expected_predecessor is not None:
            return Rejected(
                PublishRejectionCode.PREDECESSOR_MISMATCH,
                "genesis_expects_no_predecessor",
            )
        run_id = uuid.uuid4().hex
    elif not isinstance(run_id, str) or not run_id:
        return Rejected(PublishRejectionCode.RUN_NOT_FOUND, "run_id_empty")
    elif not (Path(state_dir) / "runs" / run_id).is_dir():
        return Rejected(
            PublishRejectionCode.RUN_NOT_FOUND,
            f"run_directory_missing={run_id}",
        )

    content = _candidate_content(candidate)
    digest = content_digest(content)

    run = open_run(state_dir, run_id)
    with run.lock():
        head = run.read_head()
        if head is None:
            try:
                head = run.rebuild_head_from_scan()
            except ValueError:
                head = None
        if not is_genesis and head is None:
            return Rejected(
                PublishRejectionCode.RUN_NOT_FOUND,
                f"run_has_no_committed_records={run_id}",
            )

        idempotent = _find_idempotent_publish(run, idempotency_key, digest)
        if isinstance(idempotent, Rejected):
            return idempotent
        if idempotent is not None:
            return Published(record_ref=idempotent, run_id=run_id)

        if not is_genesis:
            actual = _record_ref_of(head.last_record)
            if (
                expected_predecessor is None
                or actual != expected_predecessor
            ):
                return Rejected(
                    PublishRejectionCode.PREDECESSOR_MISMATCH,
                    f"expected={expected_predecessor!r} actual={actual!r}",
                )

        sequence = 1 if head is None else head.last_sequence + 1
        record_id = f"{run_id}:{sequence:010d}"
        envelope = {
            "run_id": run_id,
            "sequence": sequence,
            "record_id": record_id,
            "content_digest": digest,
            "idempotency_key": idempotency_key,
            "candidate": content,
        }
        run.append(sequence, canonical_json_bytes(envelope))

        if commit_barrier is not None:
            commit_barrier()

        run.write_head(
            HeadProjection(
                last_sequence=sequence,
                last_record_file=f"{sequence:010d}.json",
                last_record=envelope,
            )
        )

    return Published(
        record_ref=RecordRef(
            contract_kind=content["contract_kind"],
            record_id=record_id,
            content_digest=digest,
        ),
        run_id=run_id,
    )
