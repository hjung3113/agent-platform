"""Pure, fail-closed admission contracts for an execution Attempt.

This module deliberately stops at policy admission. A host must still enforce the
returned capability envelope at the actual process/filesystem boundary, including
closing the admission-to-use race for paths.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Iterable

from .canonical import content_digest


class AdmissionStatus(StrEnum):
    ADMITTED = "ADMITTED"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True)
class CapabilityProfile:
    """Explicit capabilities; omitted network/secrets/effects remain denied."""

    filesystem: str = "read-only"
    network: bool = False
    secrets: bool = False
    external_effects: bool = False

    def as_record(self) -> dict[str, object]:
        return {
            "filesystem": self.filesystem,
            "network": self.network,
            "secrets": self.secrets,
            "external_effects": self.external_effects,
        }


@dataclass(frozen=True)
class ContextRecord:
    """Observed text. It is hashed as evidence and cannot modify policy."""

    source: str
    text: str


@dataclass(frozen=True)
class ReleaseAuthorization:
    """Exact, single-use authorization for an external-effect sequence."""

    authorization_id: str
    subject: str
    effects: tuple[str, ...]
    target: str
    snapshot_digest: str
    plan_digest: str
    consumed: bool = False


@dataclass(frozen=True)
class AttemptRequest:
    workspace_root: Path
    candidate_paths: tuple[Path, ...] = ()
    capabilities: CapabilityProfile = field(default_factory=CapabilityProfile)
    context: tuple[ContextRecord, ...] = ()
    subject: str = ""
    snapshot_digest: str = ""
    plan_digest: str = ""
    requested_effects: tuple[str, ...] = ()
    authorization: ReleaseAuthorization | None = None
    retain_evidence: bool = False
    redaction_status: str = "not_requested"


@dataclass(frozen=True)
class EvidenceEnvelope:
    workspace_root: str
    candidate_paths: tuple[str, ...]
    capability_digest: str
    context_digest: str


@dataclass(frozen=True)
class AdmissionResult:
    status: AdmissionStatus
    reason: str
    evidence: EvidenceEnvelope | None = None


def _blocked(reason: str) -> AdmissionResult:
    return AdmissionResult(AdmissionStatus.BLOCKED, reason)


def _resolve_inside(root: Path, candidate: Path) -> Path | None:
    """Resolve a candidate and return it only when it remains under root."""

    try:
        resolved_root = root.resolve(strict=True)
        resolved_candidate = candidate.resolve(strict=False)
        resolved_candidate.relative_to(resolved_root)
    except (FileNotFoundError, OSError, RuntimeError, ValueError):
        return None
    return resolved_candidate


def _authorization_matches(request: AttemptRequest) -> bool:
    auth = request.authorization
    if not request.requested_effects:
        return auth is None
    if not request.capabilities.external_effects or auth is None:
        return False
    return (
        not auth.consumed
        and auth.subject == request.subject
        and auth.effects == request.requested_effects
        and auth.target == str(request.workspace_root.resolve())
        and auth.snapshot_digest == request.snapshot_digest
        and auth.plan_digest == request.plan_digest
    )


def admit_attempt(request: AttemptRequest) -> AdmissionResult:
    """Admit a request only when every deterministic policy check passes."""

    if request.capabilities.filesystem not in {"read-only", "read-write"}:
        return _blocked("unknown_filesystem_capability")
    if request.retain_evidence and request.redaction_status != "passed":
        return _blocked("redaction_not_proven")
    if not _authorization_matches(request):
        return _blocked("missing_or_mismatched_external_authorization")

    try:
        root = request.workspace_root.resolve(strict=True)
    except (FileNotFoundError, OSError, RuntimeError):
        return _blocked("workspace_root_unresolvable")

    normalized: list[str] = []
    for candidate in request.candidate_paths:
        resolved = _resolve_inside(root, candidate)
        if resolved is None:
            return _blocked("candidate_path_outside_workspace")
        normalized.append(str(resolved))

    capability_digest = content_digest(request.capabilities.as_record())
    context_digest = content_digest(
        [{"source": record.source, "text": record.text} for record in request.context]
    )
    envelope = EvidenceEnvelope(
        workspace_root=str(root),
        candidate_paths=tuple(normalized),
        capability_digest=capability_digest,
        context_digest=context_digest,
    )
    return AdmissionResult(AdmissionStatus.ADMITTED, "ok", envelope)


def context_sources(records: Iterable[ContextRecord]) -> tuple[str, ...]:
    """Return source labels without treating observed text as instructions."""

    return tuple(record.source for record in records)
