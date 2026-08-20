"""Pure, fail-closed admission checks for one execution Attempt.

This module validates policy bindings only. The Harness Host must still enforce the
admitted envelope at the process/filesystem boundary and close admission-to-use
races. Durable authorization consumption belongs to the authoritative Kernel path.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, fields
from enum import StrEnum
from pathlib import Path
from typing import Iterable

from kernel.canonical import content_digest
from kernel.runtime_capability import (
    CapabilityAdmissionError,
    PermissionEnvelope,
    RuntimeCapabilityProfile,
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


_MAX_SYMLINK_HOPS = 40


def _has_symlink_loop(path: Path) -> bool:
    """Bounded, explicit symlink-loop detection independent of ``Path.resolve``.

    ``Path.resolve(strict=False)``'s symlink-loop behavior is not guaranteed
    identical across Python versions/platforms (PR review flagged a
    self-referential candidate path as a case worth defense-in-depth on,
    beyond trusting the stdlib implementation alone). Walks the leaf
    component's own symlink chain, following relative/absolute targets, and
    fails closed on a revisited link or an excessively long chain.
    """

    current = path
    seen: set[Path] = set()
    hops = 0
    while os.path.islink(current):
        if current in seen:
            return True
        seen.add(current)
        hops += 1
        if hops > _MAX_SYMLINK_HOPS:
            return True
        try:
            target = os.readlink(current)
        except OSError:
            return True
        target_path = Path(target)
        current = target_path if target_path.is_absolute() else (current.parent / target_path)
    return False


def _resolve_inside(root: Path, candidate: Path) -> Path | None:
    """Resolve a candidate and return it only when it remains under root."""

    if _has_symlink_loop(candidate):
        return None
    try:
        resolved_candidate = candidate.resolve(strict=False)
        resolved_candidate.relative_to(root)
    except (FileNotFoundError, OSError, RuntimeError, ValueError):
        return None
    return resolved_candidate


def _runtime_permissions_within_admitted(
    runtime_permissions: PermissionEnvelope,
    admitted_permissions: PermissionEnvelope,
) -> bool:
    for permission_field in fields(PermissionEnvelope):
        runtime_values = set(getattr(runtime_permissions, permission_field.name))
        admitted_values = set(getattr(admitted_permissions, permission_field.name))
        if not runtime_values.issubset(admitted_values):
            return False
    return True


def _authorization_is_well_formed(auth: ReleaseAuthorization) -> bool:
    return (
        isinstance(auth.authorization_id, str)
        and bool(auth.authorization_id)
        and isinstance(auth.subject, str)
        and bool(auth.subject)
        and isinstance(auth.effects, tuple)
        and all(isinstance(effect, str) and effect for effect in auth.effects)
        and isinstance(auth.target, str)
        and bool(auth.target)
        and isinstance(auth.target_precondition, str)
        and bool(auth.target_precondition)
        and isinstance(auth.snapshot_digest, str)
        and bool(auth.snapshot_digest)
        and isinstance(auth.plan_digest, str)
        and bool(auth.plan_digest)
        and isinstance(auth.consumed, bool)
    )


def _authorization_matches(request: AttemptRequest) -> bool:
    auth = request.authorization
    if not request.requested_effects:
        return auth is None
    if auth is None or not _authorization_is_well_formed(auth) or auth.consumed:
        return False
    if not all(
        isinstance(value, str) and value
        for value in (
            request.subject,
            request.effect_target,
            request.effect_target_precondition,
            request.snapshot_digest,
            request.plan_digest,
        )
    ):
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


def _request_shape_is_valid(request: AttemptRequest) -> bool:
    return (
        isinstance(request.workspace_root, Path)
        and isinstance(request.required_capabilities, tuple)
        and isinstance(request.candidate_paths, tuple)
        and all(isinstance(candidate, Path) for candidate in request.candidate_paths)
        and isinstance(request.context, tuple)
        and all(
            isinstance(record, ContextRecord)
            and isinstance(record.source, str)
            and isinstance(record.text, str)
            for record in request.context
        )
        and isinstance(request.subject, str)
        and isinstance(request.snapshot_digest, str)
        and isinstance(request.plan_digest, str)
        and isinstance(request.requested_effects, tuple)
        and all(
            isinstance(effect, str) and effect for effect in request.requested_effects
        )
        and isinstance(request.effect_target, str)
        and isinstance(request.effect_target_precondition, str)
        and (
            request.authorization is None
            or isinstance(request.authorization, ReleaseAuthorization)
        )
        and isinstance(request.retain_evidence, bool)
        and isinstance(request.redaction_status, str)
    )


def admit_attempt(request: AttemptRequest) -> AdmissionResult:
    """Admit a request only when every deterministic policy check passes."""

    if not isinstance(request, AttemptRequest) or not _request_shape_is_valid(request):
        return _blocked("invalid_attempt_request")
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
        if not root.is_dir():
            return _blocked("workspace_root_not_directory")
    except (FileNotFoundError, OSError, RuntimeError, ValueError):
        return _blocked("workspace_root_unresolvable")

    normalized: list[str] = []
    for candidate in request.candidate_paths:
        resolved = _resolve_inside(root, candidate)
        if resolved is None:
            return _blocked("candidate_path_outside_workspace")
        normalized.append(str(resolved))

    try:
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
    except (TypeError, ValueError, UnicodeError):
        return _blocked("evidence_binding_failed")
    return AdmissionResult(AdmissionStatus.ADMITTED, "ok", envelope)


def context_sources(records: Iterable[ContextRecord]) -> tuple[str, ...]:
    """Return source labels without treating observed text as instructions."""

    return tuple(record.source for record in records)
