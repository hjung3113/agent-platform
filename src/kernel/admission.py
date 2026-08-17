"""Pure, fail-closed admission checks for one execution Attempt.

This module validates policy bindings only. The Harness Host must still enforce the
admitted envelope at the process/filesystem boundary and close admission-to-use
races. Durable authorization consumption belongs to the authoritative Kernel path.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Iterable

from kernel.canonical import content_digest
from kernel.runtime_capability import (
    CapabilityAdmissionError,
    PermissionEnvelope,
    RuntimeCapabilityProfile,
)

_PERMISSION_FIELDS = (
    "filesystem",
    "network",
    "process",
    "credentials",
    "approval_bypass",
    "external_effects",
)


class AdmissionStatus(StrEnum):
    ADMITTED = "ADMITTED"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True)
class ContextRecord:
    """Observed text hashed as evidence; it cannot modify admission policy."""

    source: str
    text: str


@dataclass(frozen=True)
class ReleaseAuthorization:
    """Authorization for an exact external-effect request that is not yet consumed."""

    authorization_id: str
    subject: str
    effects: tuple[str, ...]
    target: str
    target_precondition: str
    snapshot_digest: str
    plan_digest: str
    consumed: bool = False


@dataclass(frozen=True)
class AttemptRequest:
    workspace_root: Path
    runtime_profile: RuntimeCapabilityProfile
    admitted_permissions: PermissionEnvelope = field(default_factory=PermissionEnvelope)
    required_capabilities: tuple[str, ...] = ()
    candidate_paths: tuple[Path, ...] = ()
    context: tuple[ContextRecord, ...] = ()
    subject: str = ""
    snapshot_digest: str = ""
    plan_digest: str = ""
    requested_effects: tuple[str, ...] = ()
    effect_target: str = ""
    effect_target_precondition: str = ""
    authorization: ReleaseAuthorization | None = None
    retain_evidence: bool = False
    redaction_status: str = "not_requested"


@dataclass(frozen=True)
class EvidenceEnvelope:
    workspace_root: str
    candidate_paths: tuple[str, ...]
    runtime_profile_identity: str
    admitted_permission_digest: str
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


def _runtime_permissions_within_admitted(
    runtime_permissions: PermissionEnvelope,
    admitted_permissions: PermissionEnvelope,
) -> bool:
    for field_name in _PERMISSION_FIELDS:
        runtime_values = set(getattr(runtime_permissions, field_name))
        admitted_values = set(getattr(admitted_permissions, field_name))
        if not runtime_values.issubset(admitted_values):
            return False
    return True


def _authorization_matches(request: AttemptRequest) -> bool:
    auth = request.authorization
    if not request.requested_effects:
        return auth is None
    if auth is None or auth.consumed:
        return False
    if not request.effect_target or not request.effect_target_precondition:
        return False
    return (
        auth.subject == request.subject
        and auth.effects == request.requested_effects
        and auth.target == request.effect_target
        and auth.target_precondition == request.effect_target_precondition
        and auth.snapshot_digest == request.snapshot_digest
        and auth.plan_digest == request.plan_digest
    )


def _effects_are_admitted(request: AttemptRequest) -> bool:
    requested = set(request.requested_effects)
    if len(requested) != len(request.requested_effects):
        return False
    return requested.issubset(set(request.runtime_profile.permission_envelope.external_effects))


def admit_attempt(request: AttemptRequest) -> AdmissionResult:
    """Admit a request only when every deterministic policy check passes."""

    if not isinstance(request.runtime_profile, RuntimeCapabilityProfile):
        return _blocked("invalid_runtime_capability_profile")
    if not isinstance(request.admitted_permissions, PermissionEnvelope):
        return _blocked("invalid_admitted_permission_envelope")

    try:
        request.runtime_profile.require(request.required_capabilities)
    except (CapabilityAdmissionError, TypeError, ValueError):
        return _blocked("required_capabilities_not_satisfied")

    if not _runtime_permissions_within_admitted(
        request.runtime_profile.permission_envelope,
        request.admitted_permissions,
    ):
        return _blocked("runtime_permission_widening")

    if request.requested_effects and not _effects_are_admitted(request):
        return _blocked("external_effect_not_admitted")
    if not _authorization_matches(request):
        return _blocked("missing_or_mismatched_external_authorization")
    if request.retain_evidence and request.redaction_status != "passed":
        return _blocked("redaction_not_proven")

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

    context_digest = content_digest(
        [{"source": record.source, "text": record.text} for record in request.context]
    )
    envelope = EvidenceEnvelope(
        workspace_root=str(root),
        candidate_paths=tuple(normalized),
        runtime_profile_identity=request.runtime_profile.identity,
        admitted_permission_digest=content_digest(
            request.admitted_permissions.to_canonical_value()
        ),
        context_digest=context_digest,
    )
    return AdmissionResult(AdmissionStatus.ADMITTED, "ok", envelope)


def context_sources(records: Iterable[ContextRecord]) -> tuple[str, ...]:
    """Return source labels without treating observed text as instructions."""

    return tuple(record.source for record in records)
