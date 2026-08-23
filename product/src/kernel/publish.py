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
from collections import Counter
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
    read_candidate,
    verify_binding,
)
from kernel.protocol_v1 import (
    PROTOCOL_VERSION,
    AttemptPacketV1,
    ReceiptV1,
    RequestV1,
    ResultV1,
    RESULT_SNAPSHOT_EVIDENCE_CLASS,
    VerificationV1,
    WorkflowRevisionV1,
    schema_version_for_kind,
)

_RECORD_FILENAME = re.compile(r"^(\d{10})\.json$")
_RUN_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")
_GENESIS_RECORD_FILENAME = "0000000001.json"
_DEFAULT_LOCK_TIMEOUT_SECONDS = 5.0

_NEXT_KIND: dict[ContractKind | None, ContractKind] = {
    None: ContractKind.REQUEST,
    ContractKind.REQUEST: ContractKind.WORKFLOW_REVISION,
    ContractKind.WORKFLOW_REVISION: ContractKind.ATTEMPT_PACKET,
    ContractKind.ATTEMPT_PACKET: ContractKind.RESULT,
    ContractKind.RESULT: ContractKind.VERIFICATION,
    ContractKind.VERIFICATION: ContractKind.RECEIPT,
}


def _next_kind(head_kind: str | None) -> ContractKind:
    """Expected next contract kind after a run head of ``head_kind``.

    ``None`` is the genesis state. A terminal Receipt head never reaches
    this lookup: it is rejected as ``RUN_ALREADY_TERMINAL`` first.
    """

    if head_kind is None:
        return _NEXT_KIND[None]
    try:
        key: ContractKind | None = ContractKind(head_kind)
    except ValueError as error:
        raise RuntimeError(
            f"committed head contract kind unknown: {head_kind!r}"
        ) from error
    return _NEXT_KIND[key]


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
    RUN_ALREADY_TERMINAL = "run_already_terminal"
    ATTEMPT_TASK_BINDING_MISMATCH = "attempt_task_binding_mismatch"
    RESULT_ATTEMPT_BINDING_MISMATCH = "result_attempt_binding_mismatch"
    RESULT_ENVIRONMENT_BINDING_MISMATCH = "result_environment_binding_mismatch"
    VERIFICATION_RESULT_BINDING_MISMATCH = (
        "verification_result_binding_mismatch"
    )
    VERIFICATION_COVERAGE_MISMATCH = "verification_coverage_mismatch"
    SELF_VERIFICATION_REJECTED = "self_verification_rejected"
    RECEIPT_VERIFICATION_NOT_PASSED = "receipt_verification_not_passed"


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
    reader, the dispatch key is derived from the typed value; the v1
    readers cover all six contract kinds.
    """

    if isinstance(candidate, ParsedCandidate):
        return candidate.envelope.to_content_value()
    value = candidate.value
    if isinstance(value, RequestV1):
        contract_kind = ContractKind.REQUEST
    elif isinstance(value, WorkflowRevisionV1):
        contract_kind = ContractKind.WORKFLOW_REVISION
    elif isinstance(value, AttemptPacketV1):
        contract_kind = ContractKind.ATTEMPT_PACKET
    elif isinstance(value, ResultV1):
        contract_kind = ContractKind.RESULT
    elif isinstance(value, VerificationV1):
        contract_kind = ContractKind.VERIFICATION
    elif isinstance(value, ReceiptV1):
        contract_kind = ContractKind.RECEIPT
    else:
        raise TypeError(
            "unsupported candidate value type: " + type(value).__name__
        )
    return {
        "contract_kind": contract_kind.value,
        "protocol_version": PROTOCOL_VERSION,
        "schema_version": schema_version_for_kind(contract_kind),
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


def _committed_contract(
    run: RunHandle, contract_kind: ContractKind
) -> tuple[RecordRef, Any]:
    """Publication identity and typed payload of the run's record of a kind.

    The linear chain holds at most one committed record of each contract
    kind, so a scan that finds none or several means the run's state is
    not what this boundary could have committed; both cases fail closed
    with ``RuntimeError`` rather than guessing which record a candidate's
    embedded reference must bind against.
    """

    envelope: dict[str, Any] | None = None
    for committed in _committed_records(run):
        if committed["candidate"]["contract_kind"] == contract_kind.value:
            if envelope is not None:
                raise RuntimeError(
                    f"multiple committed {contract_kind.value} records: "
                    f"{run.run_dir}"
                )
            envelope = committed
    if envelope is None:
        raise RuntimeError(
            f"no committed {contract_kind.value} record: {run.run_dir}"
        )
    parsed = read_candidate(envelope["candidate"])
    if not parsed.ok:
        raise RuntimeError(
            f"committed {contract_kind.value} record malformed: "
            f"{parsed.rejection_code}:{parsed.reason}"
        )
    parsed_candidate: ParsedCandidate = parsed.value
    return _record_ref_of(envelope), parsed_candidate.value


class UnknownRunError(Exception):
    """``run_id`` is malformed or has no run directory under ``state``."""


def read_committed_contract(
    state: str, run_id: str, contract_kind: ContractKind
) -> tuple[RecordRef, Any]:
    """Re-read a run's one committed record of a kind, typed.

    Public re-read path for callers (e.g. M4's Context Compiler binding
    check) that must verify a caller-held value still matches the
    authoritative published record, not a second writer — this only reads.

    Validates ``run_id`` the same way ``publish()`` does (well-formed
    32-hex-char id, an existing ``runs/{run_id}`` directory) BEFORE calling
    ``open_run`` — unlike ``publish()``, ``open_run`` itself creates the run
    directory as a side effect (``os.makedirs(..., exist_ok=True)``), and a
    malformed/mistyped ``run_id`` reaching it unvalidated would silently
    create a stray directory under ``state`` from this read-only path (PR
    #47 review round 2 MEDIUM 1) — worse, an unvalidated ``run_id`` like
    ``"../elsewhere"`` would let ``Path.joinpath`` escape ``runs/`` entirely.
    """

    if not isinstance(run_id, str) or _RUN_ID_PATTERN.fullmatch(run_id) is None:
        raise UnknownRunError(f"run_id_malformed={run_id!r}")
    run_dir = Path(state) / "runs" / run_id
    if not run_dir.is_dir():
        raise UnknownRunError(f"run_id_not_found={run_id!r}")

    run = open_run(state, run_id)
    return _committed_contract(run, contract_kind)


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


def _kind_binding_rejection(
    run: RunHandle, content: dict[str, Any], value: Any
) -> Rejected | None:
    """Explicit per-kind binding checks against actual prior records.

    Predecessor-equals-head fencing already pins position; each kind's own
    embedded reference is additionally verified against the actually-
    published record of the kind it names — the same defense-in-depth M1
    added for ``workflow_revision.request`` against the genesis Request.
    Returns the typed rejection, or None when the candidate binds
    correctly.
    """

    kind = content["contract_kind"]
    if kind == ContractKind.WORKFLOW_REVISION.value:
        binding = verify_binding(value.request, _genesis_record_ref(run))
        if not binding.ok:
            return Rejected(
                PublishRejectionCode.GENESIS_REQUEST_BINDING_MISMATCH,
                f"binding_failure={binding.rejection_code}:{binding.reason}",
            )
        return None
    if kind == ContractKind.ATTEMPT_PACKET.value:
        revision_ref, revision = _committed_contract(
            run, ContractKind.WORKFLOW_REVISION
        )
        if value.task_id != revision.task.task_id:
            return Rejected(
                PublishRejectionCode.ATTEMPT_TASK_BINDING_MISMATCH,
                f"task_id_expected={revision.task.task_id!r} "
                f"actual={value.task_id!r}",
            )
        binding = verify_binding(value.workflow_revision, revision_ref)
        if not binding.ok:
            return Rejected(
                PublishRejectionCode.ATTEMPT_TASK_BINDING_MISMATCH,
                f"binding_failure={binding.rejection_code}:{binding.reason}",
            )
        return None
    if kind == ContractKind.RESULT.value:
        attempt_ref, attempt_value = _committed_contract(
            run, ContractKind.ATTEMPT_PACKET
        )
        binding = verify_binding(value.attempt, attempt_ref)
        if not binding.ok:
            return Rejected(
                PublishRejectionCode.RESULT_ATTEMPT_BINDING_MISMATCH,
                f"binding_failure={binding.rejection_code}:{binding.reason}",
            )
        if (
            value.observation.runtime_identity
            != attempt_value.runtime_capability_profile_identity
        ):
            return Rejected(
                PublishRejectionCode.RESULT_ENVIRONMENT_BINDING_MISMATCH,
                "result_observation_runtime_identity_does_not_match_attempt_profile",
            )
        return None
    if kind == ContractKind.VERIFICATION.value:
        result_ref, result_value = _committed_contract(run, ContractKind.RESULT)
        binding = verify_binding(value.result, result_ref)
        if not binding.ok:
            return Rejected(
                PublishRejectionCode.VERIFICATION_RESULT_BINDING_MISMATCH,
                f"binding_failure={binding.rejection_code}:{binding.reason}",
            )
        _, revision = _committed_contract(run, ContractKind.WORKFLOW_REVISION)
        covered = tuple(entry.criterion for entry in value.coverage)
        if covered != revision.task.acceptance_criteria:
            return Rejected(
                PublishRejectionCode.VERIFICATION_COVERAGE_MISMATCH,
                "coverage_criteria_dont_match_bound_workflow_revision",
            )
        for entry in value.coverage:
            if (
                entry.status == "SATISFIED"
                and entry.evidence_class != RESULT_SNAPSHOT_EVIDENCE_CLASS
            ):
                return Rejected(
                    PublishRejectionCode.VERIFICATION_COVERAGE_MISMATCH,
                    f"evidence_class_mismatch_criterion={entry.criterion!r}",
                )
            if (
                entry.status == "SATISFIED"
                and entry.evidence_digest != result_value.output_snapshot_digest
            ):
                return Rejected(
                    PublishRejectionCode.VERIFICATION_COVERAGE_MISMATCH,
                    f"evidence_digest_mismatch_criterion={entry.criterion!r}",
                )
        non_satisfied_counts = Counter(
            entry.criterion
            for entry in value.coverage
            if entry.status != "SATISFIED"
        )
        finding_counts = Counter(finding.criterion for finding in value.findings)
        if finding_counts != non_satisfied_counts:
            return Rejected(
                PublishRejectionCode.VERIFICATION_COVERAGE_MISMATCH,
                "non_satisfied_coverage_finding_counts_mismatch",
            )
        for finding in value.findings:
            if finding.state != "OPEN" or finding.predecessor is not None:
                return Rejected(
                    PublishRejectionCode.VERIFICATION_COVERAGE_MISMATCH,
                    f"finding_not_open_without_predecessor={finding.criterion!r}",
                )
        _, attempt_value = _committed_contract(run, ContractKind.ATTEMPT_PACKET)
        if value.verifier_identity == attempt_value.implementer_identity:
            return Rejected(
                PublishRejectionCode.SELF_VERIFICATION_REJECTED,
                f"verifier_identity={value.verifier_identity!r}",
            )
        return None
    if kind == ContractKind.RECEIPT.value:
        verification_ref, verification_value = _committed_contract(
            run, ContractKind.VERIFICATION
        )
        binding = verify_binding(value.verification, verification_ref)
        if not binding.ok:
            return Rejected(
                PublishRejectionCode.RECEIPT_VERIFICATION_NOT_PASSED,
                f"binding_failure={binding.rejection_code}:{binding.reason}",
            )
        if verification_value.verdict != "PASS":
            return Rejected(
                PublishRejectionCode.RECEIPT_VERIFICATION_NOT_PASSED,
                f"verification_verdict={verification_value.verdict}",
            )
        return None
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
    enforced by the linear chain Request -> Workflow Revision -> Attempt
    Packet -> Result -> Verification -> Receipt: a genesis publish
    (``run_id is None``) accepts only a Request candidate and starts the
    run's sequence-1 record; each later publish must carry the contract
    kind that follows the current head's kind and must bind, via its own
    embedded reference, to the actually-published predecessor record of
    the kind it names. Once a
    terminal Receipt is committed the run is terminal: every further
    publish rejects ``RUN_ALREADY_TERMINAL`` before any other admission
    check, except a genuine idempotent retry, which still returns the
    existing publication.

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

    head_kind = (
        None
        if head is None
        else head.last_record["candidate"]["contract_kind"]
    )
    if head_kind == ContractKind.RECEIPT.value:
        return Rejected(
            PublishRejectionCode.RUN_ALREADY_TERMINAL,
            f"run_head_is_terminal_receipt={run_id}",
        )

    candidate_kind = content["contract_kind"]
    expected_kind = _next_kind(head_kind)
    if candidate_kind != expected_kind.value:
        return Rejected(
            PublishRejectionCode.INVALID_CANDIDATE_KIND_FOR_RUN_STATE,
            f"expected_next={expected_kind.value} head={head_kind} "
            f"actual={candidate_kind}",
        )

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

    binding_rejection = _kind_binding_rejection(run, content, candidate.value)
    if binding_rejection is not None:
        return binding_rejection

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
