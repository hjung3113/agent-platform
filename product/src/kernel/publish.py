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
from kernel.lineage_store import (
    HeadProjection,
    LockTimeoutError,
    RunHandle,
    open_run,
)
from kernel.protocol import (
    ContractKind,
    ParsedCandidate,
    ReaderOutcome,
    RecordRef,
    verify_binding,
)
from kernel.protocol_v1 import (
    PROTOCOL_VERSION,
    SCHEMA_VERSION,
    RequestV1,
    WorkflowRevisionV1,
)

_RECORD_FILENAME = re.compile(r"^(\d{10})\.json$")
_RUN_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")
_GENESIS_RECORD_FILENAME = "0000000001.json"
_DEFAULT_LOCK_TIMEOUT_SECONDS = 5.0


class PublishRejectionCode(StrEnum):
    """Typed publication rejections, distinct from M0 protocol rejections."""

    RUN_NOT_FOUND = "run_not_found"
    PREDECESSOR_MISMATCH = "predecessor_mismatch"
    INVALID_CANDIDATE_KIND_FOR_RUN_STATE = (
        "invalid_candidate_kind_for_run_state"
    )
    GENESIS_REQUEST_BINDING_MISMATCH = "genesis_request_binding_mismatch"
    IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_CONTENT = (
        "idempotency_key_reused_with_different_content"
    )
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
    """Yield parsed committed record envelopes in sequence order.

    Fails closed: an unreadable or malformed committed record raises
    ``RuntimeError`` naming the file rather than being silently skipped,
    because a skipped record could hide a matching idempotency key and
    allow a duplicate commit.
    """

    names = sorted(
        entry
        for entry in os.listdir(run.run_dir)
        if _RECORD_FILENAME.fullmatch(entry) is not None
    )
    for name in names:
        path = run.run_dir / name
        try:
            raw = path.read_bytes()
        except OSError as error:
            raise RuntimeError(f"committed record unreadable: {path}") from error
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as error:
            raise RuntimeError(f"committed record malformed: {path}") from error
        if not isinstance(value, dict):
            raise RuntimeError(
                f"committed record is not a JSON object: {path}"
            )
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


def _find_genesis_idempotent_publish(
    state_dir: str, idempotency_key: str, digest: str
) -> Published | Rejected | None:
    """Locate an earlier genesis commit of ``idempotency_key`` across runs.

    Recovers a genesis publication whose ``Published`` result was lost
    (crash between durable commit and caller return): the key can only
    ever have been used for one genesis publish, so peeking at each
    run's sequence-1 record is sufficient. Returns the earlier
    publication on a matching digest, a typed rejection on key reuse
    with different content, and None when the key is unused.
    """

    runs_dir = Path(state_dir) / "runs"
    if not runs_dir.is_dir():
        return None
    for entry in sorted(runs_dir.iterdir()):
        if not entry.is_dir():
            continue
        first_record_path = entry / _GENESIS_RECORD_FILENAME
        if not first_record_path.exists():
            continue
        try:
            raw = first_record_path.read_bytes()
            envelope = json.loads(raw.decode("utf-8"))
        except (OSError, UnicodeDecodeError, ValueError) as error:
            raise RuntimeError(
                f"committed record unreadable: {first_record_path}"
            ) from error
        if not isinstance(envelope, dict):
            raise RuntimeError(
                f"committed record is not a JSON object: {first_record_path}"
            )
        if envelope.get("idempotency_key") != idempotency_key:
            continue
        if envelope.get("content_digest") == digest:
            return Published(
                record_ref=_record_ref_of(envelope), run_id=entry.name
            )
        return Rejected(
            PublishRejectionCode.IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_CONTENT,
            f"idempotency_key_reused={idempotency_key}",
        )
    return None


def _genesis_record_ref(run: RunHandle) -> RecordRef:
    """Read the run's sequence-1 genesis Request publication identity."""

    first_record_path = run.run_dir / _GENESIS_RECORD_FILENAME
    try:
        raw = first_record_path.read_bytes()
        envelope = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as error:
        raise RuntimeError(
            f"committed genesis record unreadable: {first_record_path}"
        ) from error
    return _record_ref_of(envelope)


def publish(
    state_dir: str,
    run_id: str | None,
    candidate: ReaderOutcome | ParsedCandidate,
    expected_predecessor: RecordRef | None,
    idempotency_key: str,
    commit_barrier: Callable[[], None] | None = None,
    lock_timeout: float = _DEFAULT_LOCK_TIMEOUT_SECONDS,
) -> PublishResult:
    """Admit and commit one authoritative record under the run lock.

    ``candidate`` is the already-validated output of M0 reader dispatch:
    either the ``ParsedCandidate`` returned by ``read_candidate`` or the bare
    ``ReaderOutcome`` returned by a registered reader. Run shape is
    enforced: a genesis publish (``run_id is None``) accepts only a
    Request candidate and starts the run's sequence-1 record; every
    non-genesis publish accepts only a Workflow Revision candidate whose
    embedded ``request`` RecordRef binds to this run's genesis Request.

    Ordering is a correctness invariant: the admission decision, the durable
    commit, and the head-projection update all happen inside the run lock,
    and the idempotency scan runs before predecessor fencing so a retry of
    an already-committed operation succeeds even though the head has since
    advanced. The authoritative head is always re-derived by scanning
    committed records inside the lock; a missing, corrupt, or stale
    ``_head.json`` is repaired from the scan before any admission decision.

    Genesis (``run_id is None``) assigns a new run id and requires
    ``expected_predecessor is None``; passing a predecessor for a genesis
    publish is a fencing error and rejects with ``PREDECESSOR_MISMATCH``
    before any state is touched. A genesis retry with the same idempotency
    key — even with ``run_id=None`` if the original result was lost —
    returns the existing publication instead of creating a second run.
    A non-genesis publish must name an existing run (a 32-hex-char run id
    holding at least one committed record, else ``RUN_NOT_FOUND``) and the
    current head's ``RecordRef`` (else ``PREDECESSOR_MISMATCH``).

    ``commit_barrier`` is a test-only fault-injection seam invoked between
    the durable commit and the head-projection update; production callers
    never pass one. ``lock_timeout`` bounds how long publish() waits for
    the run lock before rejecting with ``LOCK_CONTENTION_TIMEOUT``.
    ``record_id`` is derived deterministically as ``{run_id}:{sequence}``
    so a scan-rebuilt projection reproduces publication identity exactly.
    """

    is_genesis = run_id is None
    if is_genesis:
        if expected_predecessor is not None:
            return Rejected(
                PublishRejectionCode.PREDECESSOR_MISMATCH,
                "genesis_expects_no_predecessor",
            )
    elif not isinstance(run_id, str) or not run_id:
        return Rejected(PublishRejectionCode.RUN_NOT_FOUND, "run_id_empty")
    elif _RUN_ID_PATTERN.fullmatch(run_id) is None:
        return Rejected(
            PublishRejectionCode.RUN_NOT_FOUND,
            f"run_id_malformed={run_id!r}",
        )
    elif not (Path(state_dir) / "runs" / run_id).is_dir():
        return Rejected(
            PublishRejectionCode.RUN_NOT_FOUND,
            f"run_directory_missing={run_id}",
        )

    content = _candidate_content(candidate)
    digest = content_digest(content)

    if is_genesis:
        if content["contract_kind"] != ContractKind.REQUEST.value:
            return Rejected(
                PublishRejectionCode.INVALID_CANDIDATE_KIND_FOR_RUN_STATE,
                "genesis_requires_request_candidate",
            )
        recovered = _find_genesis_idempotent_publish(
            state_dir, idempotency_key, digest
        )
        if recovered is not None:
            return recovered
        run_id = uuid.uuid4().hex

    run = open_run(state_dir, run_id)
    try:
        with run.lock(timeout=lock_timeout):
            return _publish_locked(
                run=run,
                run_id=run_id,
                is_genesis=is_genesis,
                candidate=candidate,
                content=content,
                digest=digest,
                expected_predecessor=expected_predecessor,
                idempotency_key=idempotency_key,
                commit_barrier=commit_barrier,
            )
    except LockTimeoutError:
        return Rejected(
            PublishRejectionCode.LOCK_CONTENTION_TIMEOUT,
            f"lock_timeout={lock_timeout}s run_id={run_id}",
        )


def _publish_locked(
    *,
    run: RunHandle,
    run_id: str,
    is_genesis: bool,
    candidate: ReaderOutcome | ParsedCandidate,
    content: dict[str, Any],
    digest: str,
    expected_predecessor: RecordRef | None,
    idempotency_key: str,
    commit_barrier: Callable[[], None] | None,
) -> PublishResult:
    """In-lock admission and commit for one authoritative record.

    The authoritative head is the scan of committed records, never trust in
    the ``_head.json`` projection: a projection that is missing, corrupt, or
    stale relative to the scan is repaired before any admission decision,
    including on the idempotency-shortcut path.
    """

    head = run.read_head()
    try:
        scanned = run.rebuild_head_from_scan()
    except ValueError:
        scanned = None
    if scanned is not None and scanned != head:
        run.write_head(scanned)
    head = scanned

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
        if content["contract_kind"] != ContractKind.WORKFLOW_REVISION.value:
            return Rejected(
                PublishRejectionCode.INVALID_CANDIDATE_KIND_FOR_RUN_STATE,
                "run_requires_workflow_revision_candidate",
            )
        actual = _record_ref_of(head.last_record)
        if (
            expected_predecessor is None
            or actual != expected_predecessor
        ):
            return Rejected(
                PublishRejectionCode.PREDECESSOR_MISMATCH,
                f"expected={expected_predecessor!r} actual={actual!r}",
            )
        revision_value = candidate.value
        genesis_ref = _genesis_record_ref(run)
        binding = verify_binding(revision_value.request, genesis_ref)
        if not binding.ok:
            return Rejected(
                PublishRejectionCode.GENESIS_REQUEST_BINDING_MISMATCH,
                f"binding_failure={binding.rejection_code}:{binding.reason}",
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
