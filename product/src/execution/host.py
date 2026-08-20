"""Deny-first Host execution of one Attempt against the real OpenCode runtime.

M3 plan §6: recompute the effective Workspace Snapshot identity, probe the
live RuntimeCapabilityProfile, admit through ``kernel.admission`` against the
fixed ``execution.policy`` table, recheck binary/profile/snapshot identity
immediately before spawn (plan §3.1's shrunk — not closed — TOCTOU window),
run the runtime with an allow-listed child environment, and derive the
Result's ``output_snapshot_digest`` from actual post-execution workspace
state — never from the runtime's exit code or stdout (plan §6 step 6).

Per-axis enforcement honesty (plan §2/§6 step 4): credentials are a real
process-boundary control (the child env is built from scratch as PATH plus
the credentials allow-list, nothing ambient); external effects stay empty by
policy and any request for one fails admission; filesystem and process axes
are declared-scope policy checks (candidate paths containment-checked before
spawn, cwd pinned to the resolved workspace root), not syscall interception;
network is not enforced at all. The profile's honest PARTIAL/UNKNOWN statuses
plus ``admit_attempt``'s fail-closed ``require()`` are the control for those
axes — no fake enforcement code exists here for them.

The execution-layer errors below are deliberately not
``PublishRejectionCode`` values: when one fires no Kernel record is produced,
because no Result exists for a run that never executed.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from kernel import admission
from kernel.protocol import RecordRef
from kernel.protocol_v1 import AttemptPacketV1, ResultV1, RuntimeObservationV1
from kernel.runtime_capability import RuntimeCapabilityProfile

from execution import policy
from execution.opencode_adapter import probe_opencode_profile
from execution.workspace_snapshot import snapshot_identity


class StaleWorkspaceSnapshotError(Exception):
    """Workspace state at execute time no longer matches the Attempt Packet."""


class StaleRuntimeCapabilityProfileError(Exception):
    """Live runtime profile identity no longer matches the Attempt Packet."""


class RuntimeSubstitutionRejectedError(Exception):
    """Pre-spawn recheck (plan §6 step 3.5) found binary or profile drift."""


class AdmissionRejectedError(Exception):
    """``admit_attempt`` blocked the Attempt before any spawn (plan §6 step 3)."""

    def __init__(self, result: admission.AdmissionResult) -> None:
        super().__init__(f"admission blocked: {result.reason}")
        self.status = result.status
        self.reason = result.reason


def _resolve_runtime_binary(opencode_binary_path: str) -> Path:
    """Resolve the runtime binary to one concrete executable file path."""

    raw = Path(opencode_binary_path)
    if raw.parent == Path("."):
        found = shutil.which(opencode_binary_path)
        if found is None:
            raise ValueError(
                f"opencode binary not found on PATH: {opencode_binary_path!r}"
            )
        raw = Path(found)
    resolved = raw.resolve()
    if not (resolved.is_file() and os.access(resolved, os.X_OK)):
        raise ValueError(f"opencode binary is not an executable file: {resolved}")
    return resolved


def _child_environment() -> dict[str, str]:
    """Build the child env from scratch: credentials allow-list plus PATH only.

    Ambient environment variables are never inherited (plan §6 step 4
    credentials bullet): with M3's empty credentials allow-list the child
    sees exactly ``PATH``.
    """

    child_env = {
        name: os.environ[name]
        for name in policy.M3_ADMITTED_PERMISSIONS.credentials
        if name in os.environ
    }
    child_env["PATH"] = os.environ.get("PATH", os.defpath)
    return child_env


def _pre_spawn_recheck(
    *,
    attempt: AttemptPacketV1,
    workspace_root: Path,
    opencode_binary_path: str,
    config_paths: tuple[Path, ...],
    declared_generated_paths: tuple[str, ...],
    resolved_binary: Path,
    profile: RuntimeCapabilityProfile,
) -> None:
    """Re-verify binary path, profile identity, and snapshot right before spawn.

    Plan §6 step 3.5 with §3.1's scope: the recompute-immediately-before-spawn
    applies to the snapshot as well, not just the profile. Binary-path or
    identity drift rejects (no silent substitution); snapshot drift surfaces
    as the same staleness class as the top-of-execute check.
    """

    try:
        recheck_binary = _resolve_runtime_binary(opencode_binary_path)
    except ValueError as exc:
        raise RuntimeSubstitutionRejectedError(
            f"runtime binary became unresolvable before spawn: {exc}"
        ) from exc
    if recheck_binary != resolved_binary:
        raise RuntimeSubstitutionRejectedError(
            "resolved runtime binary drifted between probe and spawn: "
            f"probe={resolved_binary} respawn={recheck_binary}"
        )

    recheck_profile = probe_opencode_profile(str(recheck_binary), config_paths)
    if recheck_profile.identity != profile.identity:
        raise RuntimeSubstitutionRejectedError(
            "runtime profile identity drifted between probe and spawn: "
            f"probe={profile.identity} respawn={recheck_profile.identity}"
        )

    recheck_digest = snapshot_identity(
        workspace_root, declared_generated_paths
    ).digest
    if recheck_digest != attempt.workspace_snapshot_digest:
        raise StaleWorkspaceSnapshotError(
            "workspace changed between admission and spawn: "
            f"attempt={attempt.workspace_snapshot_digest} live={recheck_digest}"
        )


def execute(
    attempt_ref: RecordRef,
    attempt: AttemptPacketV1,
    workspace_root: Path,
    opencode_binary_path: str,
    config_paths: tuple[Path, ...] = (),
    declared_generated_paths: tuple[str, ...] = (),
) -> ResultV1:
    """Execute one Attempt inside the deny-first M3 envelope (plan §6).

    ``declared_generated_paths`` entries become the admission request's
    candidate write paths, interpreted as relative paths under the resolved
    workspace root; an absolute entry passes through unchanged and then fails
    admission's containment check when it points outside the root. The
    containment decision itself belongs to ``admission.admit_attempt``
    (plan §4) and is never re-derived here.
    """

    pre_snapshot = snapshot_identity(workspace_root, declared_generated_paths)
    if pre_snapshot.digest != attempt.workspace_snapshot_digest:
        raise StaleWorkspaceSnapshotError(
            "workspace snapshot drift before execution: "
            f"attempt={attempt.workspace_snapshot_digest} live={pre_snapshot.digest}"
        )

    resolved_binary = _resolve_runtime_binary(opencode_binary_path)
    profile = probe_opencode_profile(str(resolved_binary), config_paths)
    if profile.identity != attempt.runtime_capability_profile_identity:
        raise StaleRuntimeCapabilityProfileError(
            "runtime capability profile drift before execution: "
            f"attempt={attempt.runtime_capability_profile_identity} "
            f"live={profile.identity}"
        )

    resolved_root = Path(pre_snapshot.root)
    request = admission.AttemptRequest(
        workspace_root=resolved_root,
        runtime_profile=profile,
        admitted_permissions=policy.M3_ADMITTED_PERMISSIONS,
        required_capabilities=policy.M3_REQUIRED_CAPABILITIES,
        candidate_paths=tuple(
            resolved_root / Path(path) for path in declared_generated_paths
        ),
    )
    admission_result = admission.admit_attempt(request)
    if admission_result.status is not admission.AdmissionStatus.ADMITTED:
        raise AdmissionRejectedError(admission_result)

    _pre_spawn_recheck(
        attempt=attempt,
        workspace_root=workspace_root,
        opencode_binary_path=opencode_binary_path,
        config_paths=config_paths,
        declared_generated_paths=declared_generated_paths,
        resolved_binary=resolved_binary,
        profile=profile,
    )

    subprocess.run(
        [str(resolved_binary), "run", "--workdir", str(resolved_root)],
        cwd=resolved_root,
        env=_child_environment(),
        capture_output=True,
        text=True,
        check=False,
    )

    output_snapshot_digest = snapshot_identity(
        workspace_root, declared_generated_paths
    ).digest
    return ResultV1(
        attempt=attempt_ref,
        output_snapshot_digest=output_snapshot_digest,
        observation=RuntimeObservationV1(
            runtime_identity=profile.runtime,
            output_snapshot_digest=output_snapshot_digest,
        ),
    )
