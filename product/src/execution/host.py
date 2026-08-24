"""Deny-first Host execution of one Attempt against the real OpenCode runtime.

M3 plan §6: recompute the effective Workspace Snapshot identity, probe the
live RuntimeCapabilityProfile, admit through ``kernel.admission`` against the
fixed ``execution.policy`` table, recheck binary/profile/snapshot identity
immediately before spawn (plan §3.1's shrunk — not closed — TOCTOU window),
run the runtime with an allow-listed child environment, and derive the
Result's ``output_snapshot_digest`` from actual post-execution workspace
state — never from the runtime's exit code or stdout (plan §6 step 6).

Per-axis enforcement honesty (plan §2/§6 step 4, corrected after PR review):
credentials are a real process-boundary control (the child env is built from
scratch as PATH plus the credentials allow-list, nothing ambient); filesystem
and process axes are declared-scope policy checks (candidate paths
containment-checked before spawn, cwd pinned to the resolved workspace root),
not syscall interception; network is not enforced at all. External effects
are **declarative admission rejection only, not a process-boundary control**:
an Attempt that declares a ``requested_effects`` entry not in the admitted
envelope fails ``admit_attempt`` before spawn, but the spawned OpenCode
process (and any shell/tool it invokes) is not prevented from directly
calling ``git push``/``gh``/``curl``/an equivalent client — same unenforced-
at-process-level class as network denial, not the stronger "real process-
boundary + policy enforcement" an earlier draft claimed. The profile's honest
PARTIAL/UNKNOWN statuses plus ``admit_attempt``'s fail-closed ``require()``
are the control for the axes this milestone cannot really enforce — no fake
enforcement code exists here for them.

M4 (plan §6/§7) additionally binds the Attempt's context: ``execute()``
re-reads the run's committed Workflow Revision through the Kernel's own
record read path, recompiles the Context Pack from execute-time parameters,
and rejects any divergence from the packet's bound ``context_digest`` as
``StaleContextPackError``. That third pre-spawn check is compile/execute
parameter-consistency binding plus an authoritative re-derivation the caller
cannot spoof — stated honestly, it is *not* a same-inputs recompute that
catches compiler bugs: a deterministically-wrong compiler reproduces the
same wrong digest at compile and recheck both, and that class of defect is a
correctness bug for the compiler's own test suite, not something this
recheck can detect. What it catches is divergence between what was compiled
and what execute-time parameters/authoritative state now say. The runtime's
``run`` message renders the pack as labeled per-source-class sections
(plan §7) so the content/authority boundary survives rendering.

The execution-layer errors below are deliberately not
``PublishRejectionCode`` values: when one fires no Kernel record is produced,
because no Result exists for a run that never executed.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path

from kernel import admission
from kernel.canonical import content_digest
from kernel.protocol import ContractKind, RecordRef
from kernel.protocol_v1 import AttemptPacketV1, ResultV1, RuntimeObservationV1, TaskV1
from kernel.publish import read_committed_contract
from kernel.runtime_capability import RuntimeCapabilityProfile

from execution import policy
from execution.context_compiler import (
    compile_context_pack,
    disclosure_identity,
    reject_unverified_contract_refs,
    render_context_pack,
)
from execution.opencode_adapter import probe_opencode_profile
from execution.redaction import scan_for_retention
from execution.workspace_snapshot import snapshot_identity


class StaleWorkspaceSnapshotError(Exception):
    """Workspace state at execute time no longer matches the Attempt Packet."""


class StaleRuntimeCapabilityProfileError(Exception):
    """Live runtime profile identity no longer matches the Attempt Packet."""


class StaleContextPackError(Exception):
    """Recompiled context_digest, from execute-time parameters and the
    re-read published task, no longer matches the Attempt Packet's bound
    value."""


class RuntimeSubstitutionRejectedError(Exception):
    """Pre-spawn recheck (plan §6 step 3.5) found binary or profile drift."""


class RetentionBlockedError(Exception):
    """Captured output failed the pre-retention redaction gate."""


class RuntimeExecutionFailedError(Exception):
    """The spawned runtime exited non-zero; no Result is produced.

    Plan §6 step 6's "exit code alone does not establish completion" means
    a zero exit / success-claiming stdout is not trusted — it does not mean
    a non-zero exit is discarded. A crashed/erroring runtime process is a
    real execution failure, surfaced here rather than silently packaged into
    a Result whose digest happens to reflect unchanged workspace state.
    """

    def __init__(self, returncode: int, stderr: str) -> None:
        super().__init__(f"runtime exited {returncode}: {stderr.strip()}")
        self.returncode = returncode


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
    task: TaskV1,
    state: str,
    run_id: str,
    config_paths: tuple[Path, ...] = (),
    declared_generated_paths: tuple[str, ...] = (),
    *,
    contract_refs: tuple[RecordRef, ...] = (),
    retain_evidence: bool = False,
    requested_effects: tuple[str, ...] = (),
    run_message_template_revision: str = "v1",
) -> ResultV1:
    """Execute one Attempt inside the deny-first M3 envelope (plan §6).

    ``task`` is the authoritative published ``TaskV1`` this Attempt binds to;
    ``state``/``run_id`` locate the run whose committed Workflow Revision the
    third pre-spawn check re-reads; ``contract_refs`` are the admitted
    decision/contract refs the Attempt's Context Pack was compiled with
    (empty in every real M4 path — same frozen-candidate shape as compile
    time).

    Third pre-spawn check (M4 plan §6), run after the snapshot/profile
    staleness checks and before admission. Two independent things: (a)
    authoritative re-derivation — the run's committed Workflow Revision is
    re-read through the Kernel's own record read path and both its ref and
    its task's canonical-value digest must match the packet's bound
    ``workflow_revision`` and the execute-time ``task``; (b)
    parameter-consistency recompile — the Context Pack is recompiled from
    execute-time parameters (using the packet's own snapshot/profile
    identities, already reverified fresh by the two checks above) and its
    digest must equal ``attempt.context_digest``. Stated honestly: this is
    NOT a same-inputs recompute that catches compiler bugs — a
    deterministically-wrong compiler reproduces the same wrong digest at
    compile and recheck both, and that class of defect is a correctness bug
    caught by the compiler's own test suite, not by this check. What it
    catches is divergence between what was compiled and what execute-time
    parameters/authoritative state now say — a different ``task``/refs than
    were compiled, or render-template drift via
    ``run_message_template_revision`` (a version tag for the labeled-section
    rendering shape; bump it whenever that rendering changes) — and it
    rejects as ``StaleContextPackError`` rather than silently recompiling or
    expanding context.

    The rendered ``run`` message is that recompiled Context Pack rendered as
    labeled ``[source_class: scope]`` sections (plan §7), computed once and
    used for both the digest check and the spawn argv.

    ``declared_generated_paths`` entries become the admission request's
    candidate write paths, interpreted as relative paths under the resolved
    workspace root; an absolute entry passes through unchanged and then fails
    admission's containment check when it points outside the root. The
    containment decision itself belongs to ``admission.admit_attempt``
    (plan §4) and is never re-derived here.

    ``requested_effects`` lets a caller express that this Attempt needs an
    external effect; since the M3 admitted envelope's ``external_effects`` is
    always empty (§5.1's fixed policy), any non-empty value here fails
    admission — a real declarative rejection path, but not a process-boundary
    control (see this module's docstring).
    """

    reject_unverified_contract_refs(contract_refs)

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

    # Third pre-spawn check (M4 plan §6) — two independent bindings, after
    # the two checks above so it never re-litigates the snapshot/profile
    # identities those checks already own.
    revision_ref, revision = read_committed_contract(
        state, run_id, ContractKind.WORKFLOW_REVISION
    )
    if revision_ref != attempt.workflow_revision:
        raise StaleContextPackError(
            "committed workflow revision ref diverged from the Attempt "
            "Packet's bound ref: "
            f"attempt={attempt.workflow_revision} committed={revision_ref}"
        )
    bound_task = next(
        (
            candidate
            for candidate in getattr(revision, "tasks", ())
            if candidate.task_id == attempt.task_id
        ),
        None,
    )
    if bound_task is None:
        raise StaleContextPackError(
            "Attempt Packet's task_id is not present in the committed "
            "Workflow Revision's tasks: "
            f"task_id={attempt.task_id!r}"
        )
    committed_task_digest = content_digest(bound_task.to_canonical_value())
    execute_task_digest = content_digest(task.to_canonical_value())
    if committed_task_digest != execute_task_digest:
        raise StaleContextPackError(
            "execute-time task diverged from the committed Workflow "
            "Revision task: "
            f"execute_task_digest={execute_task_digest} "
            f"committed_task_digest={committed_task_digest}"
        )

    # Uses the packet's own bound snapshot/profile identities (reverified
    # fresh above); this recompile's job is catching task/refs/render-
    # template drift, not recomputing those identities.
    context_pack = compile_context_pack(
        task_id=attempt.task_id,
        task_objective=task.objective,
        task_acceptance_criteria=task.acceptance_criteria,
        workspace_snapshot_digest=attempt.workspace_snapshot_digest,
        runtime_capability_profile_identity=(
            attempt.runtime_capability_profile_identity
        ),
        contract_refs=contract_refs,
        disclosure_identity=disclosure_identity(
            profile.identity, run_message_template_revision
        ),
    )
    if context_pack.digest != attempt.context_digest:
        raise StaleContextPackError(
            "recompiled context digest mismatch: "
            f"attempt={attempt.context_digest} recomputed={context_pack.digest}"
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
        requested_effects=requested_effects,
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

    completed = subprocess.run(
        [
            str(resolved_binary),
            "run",
            render_context_pack(context_pack.units),
            "--workdir",
            str(resolved_root),
        ],
        cwd=resolved_root,
        env=_child_environment(),
        capture_output=True,
        check=False,
    )
    execution_identity = content_digest(
        {
            "spawned_at_ns": str(time.time_ns()),
            "nonce": os.urandom(16).hex(),
        }
    )

    if completed.returncode != 0:
        raise RuntimeExecutionFailedError(
            completed.returncode,
            completed.stderr.decode("utf-8", errors="replace"),
        )

    if retain_evidence:
        # Decode under Host control, strictly: subprocess.run's own text=True
        # decoding would raise UnicodeDecodeError on invalid bytes before
        # scan_for_retention ever runs (PR review). Invalid UTF-8 becomes
        # scan_for_retention(None) -> "unknown", which RetentionBlockedError
        # below already treats as not "passed" -- the fail-closed path stays
        # reachable instead of crashing.
        def _decode_for_scan(raw: bytes) -> str | None:
            try:
                return raw.decode("utf-8")
            except UnicodeDecodeError:
                return None

        scan_results = (
            ("stdout", scan_for_retention(_decode_for_scan(completed.stdout))),
            ("stderr", scan_for_retention(_decode_for_scan(completed.stderr))),
        )
        blocked_streams = [
            f"{stream} scan status={result.status}"
            for stream, result in scan_results
            if result.status != "passed"
        ]
        if blocked_streams:
            raise RetentionBlockedError("; ".join(blocked_streams))

    output_snapshot_digest = snapshot_identity(
        workspace_root, declared_generated_paths
    ).digest
    return ResultV1(
        attempt=attempt_ref,
        output_snapshot_digest=output_snapshot_digest,
        observation=RuntimeObservationV1(
            runtime_identity=profile.identity,
            output_snapshot_digest=output_snapshot_digest,
            execution_identity=execution_identity,
        ),
    )
