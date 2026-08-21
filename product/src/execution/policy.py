"""Fixed M3 execution policy from docs/plans/active/m3-real-host-security-boundary.md §5.1.

These constants are the single source that the later ``execution/host.py`` will use to
build an ``admission.AttemptRequest``. They are not driver-supplied parameters and must
never be overridden at runtime; widening them requires a reviewable code change to this
file, not a config toggle.
"""

from kernel.runtime_capability import PermissionEnvelope


# Empty by design (orchestrator-level fix, plan §5.1): M3 never marks any
# canonical action SUPPORTED — filesystem/process are honestly PARTIAL
# (declared-scope policy checks, not syscall interception) and network is
# PARTIAL/UNKNOWN (plan §2/§6). Real M3 enforcement rests entirely on
# PermissionEnvelope subset checks, workspace containment, and the
# credentials allow-list in kernel.admission, which run independently of
# the require()/SUPPORTED-capability mechanism. Naming a capability here
# that the adapter can only ever mark PARTIAL would make every M3 execution
# permanently fail closed at admission — proven by an earlier draft of this
# table (read_workspace/write_workspace) plus product/src/execution/host.py's
# real OpenCode probe, which never marks either SUPPORTED. Add an entry here
# only once a real capability this milestone can honestly mark SUPPORTED
# exists.
M3_REQUIRED_CAPABILITIES: tuple[str, ...] = ()

M3_ADMITTED_PERMISSIONS: PermissionEnvelope = PermissionEnvelope(
    filesystem=("workspace:read", "workspace:write"),
    network=(),
    process=(),
    credentials=(),
    approval_bypass=(),
    external_effects=(),
)
