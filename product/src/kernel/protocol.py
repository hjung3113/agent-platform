"""Version-independent protocol primitives for candidate contract records.

This module owns only the wire envelope shapes, the exact identity+digest
record-reference primitive, typed protocol rejection codes, and exact reader
dispatch keyed by ``(contract_kind, protocol_version, schema_version)``.

It is deliberately not a store, publisher, CAS, replay reducer, compatibility
registry, or plugin system. Parsing or constructing any value here — including
the published-record shape — is never an authority decision; Kernel authority
is introduced only in M1.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Any, Callable

from kernel.canonical import CANONICAL_FORMAT, DIGEST_ALGORITHM, content_digest


@dataclass(frozen=True)
class ReaderOutcome:
    """Successful payload-reader result.

    ``canonical_payload`` is the payload representation derived from the typed
    ``value`` itself, never the raw caller input, so a parsed envelope's
    content identity cannot diverge from its typed value through later
    mutation of the original input object.
    """

    value: Any
    canonical_payload: Any


PayloadReader = Callable[[Any], ReaderOutcome]

CANDIDATE_KEYS = frozenset(
    {"contract_kind", "protocol_version", "schema_version", "payload"}
)
FORBIDDEN_CANDIDATE_KEYS = frozenset(
    {"record_id", "content_digest", "published", "authoritative"}
)
PUBLISHED_KEYS = frozenset(
    {
        "record_id",
        "content_digest",
        "contract_kind",
        "protocol_version",
        "schema_version",
        "payload",
    }
)
RECORD_REF_KEYS = frozenset({"contract_kind", "record_id", "content_digest"})

_DIGEST_PREFIX = f"{DIGEST_ALGORITHM}:{CANONICAL_FORMAT}:"
_HEX_DIGITS = frozenset("0123456789abcdef")


class ContractKind(StrEnum):
    REQUEST = "request"
    WORKFLOW_REVISION = "workflow_revision"


class ProtocolRejectionCode(StrEnum):
    UNKNOWN_CONTRACT_KIND = "unknown_contract_kind"
    UNSUPPORTED_PROTOCOL_VERSION = "unsupported_protocol_version"
    UNSUPPORTED_SCHEMA_VERSION = "unsupported_schema_version"
    MALFORMED_ENVELOPE = "malformed_envelope"
    MALFORMED_PAYLOAD = "malformed_payload"
    MALFORMED_RECORD_REF = "malformed_record_ref"
    CONTENT_DIGEST_MISMATCH = "content_digest_mismatch"
    BINDING_MISMATCH = "binding_mismatch"


class ProtocolRejected(Exception):
    """Typed rejection raised by payload readers.

    The typed code lets callers determine the rejection class without parsing
    free-form exception text. This is a protocol-parse boundary only and is
    deliberately separate from Attempt admission in ``kernel.admission``.
    """

    def __init__(self, code: ProtocolRejectionCode, reason: str) -> None:
        super().__init__(reason)
        self.code = code
        self.reason = reason


@dataclass(frozen=True)
class ReadResult:
    """Result of reading a candidate or published record.

    ``rejection_code is None`` means the read succeeded and ``value`` holds the
    typed contract value.
    """

    value: Any = None
    rejection_code: ProtocolRejectionCode | None = None
    reason: str = ""

    @property
    def ok(self) -> bool:
        return self.rejection_code is None


def _ok(value: Any) -> ReadResult:
    return ReadResult(value=value, reason="ok")


def _reject(code: ProtocolRejectionCode, reason: str) -> ReadResult:
    return ReadResult(value=None, rejection_code=code, reason=reason)


def is_content_digest(value: Any) -> bool:
    """Return True when ``value`` is shaped like a platform content digest."""

    if not isinstance(value, str) or not value.startswith(_DIGEST_PREFIX):
        return False
    tail = value[len(_DIGEST_PREFIX) :]
    return len(tail) == 64 and all(character in _HEX_DIGITS for character in tail)


@dataclass(frozen=True)
class RecordRef:
    """Exact identity+digest binding to another contract record.

    Used in relation-specific schema fields (for example the ``request`` field
    of a Workflow Revision), never as a generic parent list.
    """

    contract_kind: str
    record_id: str
    content_digest: str

    def to_canonical_value(self) -> dict[str, Any]:
        return {
            "contract_kind": self.contract_kind,
            "record_id": self.record_id,
            "content_digest": self.content_digest,
        }


def read_record_ref(value: Any) -> RecordRef:
    """Strictly read an exact record reference or raise ``ProtocolRejected``."""

    if not isinstance(value, dict):
        raise ProtocolRejected(
            ProtocolRejectionCode.MALFORMED_RECORD_REF,
            "record_reference_not_object",
        )
    keys = set(value)
    if keys != RECORD_REF_KEYS:
        missing = sorted(RECORD_REF_KEYS - keys)
        unknown = sorted(keys - RECORD_REF_KEYS)
        raise ProtocolRejected(
            ProtocolRejectionCode.MALFORMED_RECORD_REF,
            f"record_reference_keys_missing={missing} unknown={unknown}",
        )
    contract_kind = value["contract_kind"]
    record_id = value["record_id"]
    reference_digest = value["content_digest"]
    if not isinstance(contract_kind, str) or not contract_kind:
        raise ProtocolRejected(
            ProtocolRejectionCode.MALFORMED_RECORD_REF, "record_reference_kind_empty"
        )
    if not isinstance(record_id, str) or not record_id:
        raise ProtocolRejected(
            ProtocolRejectionCode.MALFORMED_RECORD_REF, "record_reference_id_empty"
        )
    if not is_content_digest(reference_digest):
        raise ProtocolRejected(
            ProtocolRejectionCode.MALFORMED_RECORD_REF,
            "record_reference_digest_malformed",
        )
    return RecordRef(
        contract_kind=contract_kind,
        record_id=record_id,
        content_digest=reference_digest,
    )


def verify_binding(reference: RecordRef, expected: RecordRef) -> ReadResult:
    """Purely compare a child record reference against the expected parent.

    M0 binding validation is local and value-based only; resolving references
    against authoritative lineage is M1 behavior.
    """

    if reference.contract_kind != expected.contract_kind:
        return _reject(
            ProtocolRejectionCode.BINDING_MISMATCH, "binding_kind_mismatch"
        )
    if reference.record_id != expected.record_id:
        return _reject(
            ProtocolRejectionCode.BINDING_MISMATCH, "binding_record_id_mismatch"
        )
    if reference.content_digest != expected.content_digest:
        return _reject(
            ProtocolRejectionCode.BINDING_MISMATCH, "binding_content_digest_mismatch"
        )
    return _ok(reference)


@dataclass(frozen=True)
class CandidateEnvelope:
    """Validated candidate wire envelope (no publication metadata)."""

    contract_kind: ContractKind
    protocol_version: int
    schema_version: int
    payload: Any

    def to_content_value(self) -> dict[str, Any]:
        """Versioned contract content that fixes candidate content identity.

        Kernel-assigned publication identity and storage/projection metadata
        are excluded by construction: they are not envelope fields.
        """

        return {
            "contract_kind": self.contract_kind.value,
            "protocol_version": self.protocol_version,
            "schema_version": self.schema_version,
            "payload": self.payload,
        }

    def content_digest(self) -> str:
        return content_digest(self.to_content_value())


@dataclass(frozen=True)
class ParsedCandidate:
    envelope: CandidateEnvelope
    value: Any


@dataclass(frozen=True)
class PublishedRecord:
    """Parsed published-record wire shape.

    This is a data shape for future reading/binding only. Constructing or
    parsing it confers no authority; trust is established only by M1's Kernel
    publication/lineage boundary.
    """

    record_id: str
    content_digest: str
    envelope: CandidateEnvelope
    value: Any


_READERS: dict[tuple[ContractKind, int, int], PayloadReader] = {}

_BUILTIN_READERS_LOADED = False


def _load_builtin_readers() -> None:
    """Import the version-specific protocol modules so their readers register."""

    global _BUILTIN_READERS_LOADED
    if _BUILTIN_READERS_LOADED:
        return
    from kernel import protocol_v1  # noqa: F401  registers exact v1 readers

    _BUILTIN_READERS_LOADED = True


def register_reader(
    contract_kind: ContractKind,
    protocol_version: int,
    schema_version: int,
    reader: PayloadReader,
) -> None:
    """Register the single exact reader for one dispatch key."""

    _READERS[(contract_kind, protocol_version, schema_version)] = reader


def read_candidate(envelope: Any) -> ReadResult:
    """Read a candidate envelope via exact ``(kind, version, version)`` dispatch.

    There is no latest-reader fallback, semantic-version inference, runtime or
    adapter selected reader, coercion from unsupported known versions, or
    compatibility lookup.
    """

    _load_builtin_readers()
    if not isinstance(envelope, dict):
        return _reject(ProtocolRejectionCode.MALFORMED_ENVELOPE, "envelope_not_object")
    keys = set(envelope)
    forbidden = sorted(keys & FORBIDDEN_CANDIDATE_KEYS)
    if forbidden:
        return _reject(
            ProtocolRejectionCode.MALFORMED_ENVELOPE,
            f"candidate_publication_only_fields={forbidden}",
        )
    if keys != CANDIDATE_KEYS:
        missing = sorted(CANDIDATE_KEYS - keys)
        unknown = sorted(keys - CANDIDATE_KEYS)
        return _reject(
            ProtocolRejectionCode.MALFORMED_ENVELOPE,
            f"envelope_keys_missing={missing} unknown={unknown}",
        )

    raw_kind = envelope["contract_kind"]
    if not isinstance(raw_kind, str) or raw_kind not in {
        kind.value for kind in ContractKind
    }:
        return _reject(
            ProtocolRejectionCode.UNKNOWN_CONTRACT_KIND,
            f"unknown_contract_kind={raw_kind!r}",
        )
    contract_kind = ContractKind(raw_kind)

    protocol_version = envelope["protocol_version"]
    schema_version = envelope["schema_version"]
    for name, version in (
        ("protocol_version", protocol_version),
        ("schema_version", schema_version),
    ):
        if isinstance(version, bool) or not isinstance(version, int):
            return _reject(
                ProtocolRejectionCode.MALFORMED_ENVELOPE,
                f"envelope_{name}_not_integer",
            )

    parsed = CandidateEnvelope(
        contract_kind=contract_kind,
        protocol_version=protocol_version,
        schema_version=schema_version,
        payload=envelope["payload"],
    )
    return _dispatch(parsed)


def _dispatch(parsed: CandidateEnvelope) -> ReadResult:
    known_protocol_versions = {
        key[1] for key in _READERS if key[0] is parsed.contract_kind
    }
    if parsed.protocol_version not in known_protocol_versions:
        return _reject(
            ProtocolRejectionCode.UNSUPPORTED_PROTOCOL_VERSION,
            f"unsupported_protocol_version={parsed.contract_kind.value}"
            f"/{parsed.protocol_version}",
        )
    known_schema_versions = {
        key[2]
        for key in _READERS
        if key[0] is parsed.contract_kind
        and key[1] == parsed.protocol_version
    }
    if parsed.schema_version not in known_schema_versions:
        return _reject(
            ProtocolRejectionCode.UNSUPPORTED_SCHEMA_VERSION,
            f"unsupported_schema_version={parsed.contract_kind.value}"
            f"/{parsed.protocol_version}/{parsed.schema_version}",
        )
    reader = _READERS[(parsed.contract_kind, parsed.protocol_version, parsed.schema_version)]
    try:
        outcome = reader(parsed.payload)
    except ProtocolRejected as rejection:
        return ReadResult(
            value=None, rejection_code=rejection.code, reason=rejection.reason
        )
    if not isinstance(outcome, ReaderOutcome):
        raise TypeError(
            "payload reader for "
            f"{parsed.contract_kind.value}/{parsed.protocol_version}/"
            f"{parsed.schema_version} must return ReaderOutcome, "
            f"got {type(outcome).__name__}"
        )
    envelope = replace(parsed, payload=outcome.canonical_payload)
    return ReadResult(
        value=ParsedCandidate(envelope=envelope, value=outcome.value), reason="ok"
    )


def read_published_record(record: Any) -> ReadResult:
    """Read a published-record wire shape and verify its declared digest.

    The content digest is recomputed from the versioned contract content
    (contract kind, protocol version, schema version, payload) and must match
    the declared digest. Parsing this shape does not mutate any state and does
    not provide a Kernel publication API.
    """

    if not isinstance(record, dict):
        return _reject(ProtocolRejectionCode.MALFORMED_ENVELOPE, "record_not_object")
    keys = set(record)
    if keys != PUBLISHED_KEYS:
        missing = sorted(PUBLISHED_KEYS - keys)
        unknown = sorted(keys - PUBLISHED_KEYS)
        return _reject(
            ProtocolRejectionCode.MALFORMED_ENVELOPE,
            f"record_keys_missing={missing} unknown={unknown}",
        )

    record_id = record["record_id"]
    declared_digest = record["content_digest"]
    if not isinstance(record_id, str) or not record_id:
        return _reject(ProtocolRejectionCode.MALFORMED_ENVELOPE, "record_id_empty")
    if not is_content_digest(declared_digest):
        return _reject(
            ProtocolRejectionCode.MALFORMED_ENVELOPE, "record_content_digest_malformed"
        )

    candidate_result = read_candidate(
        {
            "contract_kind": record["contract_kind"],
            "protocol_version": record["protocol_version"],
            "schema_version": record["schema_version"],
            "payload": record["payload"],
        }
    )
    if not candidate_result.ok:
        return candidate_result
    parsed: ParsedCandidate = candidate_result.value
    recomputed_digest = parsed.envelope.content_digest()
    if recomputed_digest != declared_digest:
        return _reject(
            ProtocolRejectionCode.CONTENT_DIGEST_MISMATCH,
            "declared_content_digest_mismatch",
        )
    return _ok(
        PublishedRecord(
            record_id=record_id,
            content_digest=declared_digest,
            envelope=parsed.envelope,
            value=parsed.value,
        )
    )
