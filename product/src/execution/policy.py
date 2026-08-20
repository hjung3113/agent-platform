"""Fixed M3 execution policy from docs/plans/active/m3-real-host-security-boundary.md §5.1.

These constants are the single source that the later ``execution/host.py`` will use to
build an ``admission.AttemptRequest``. They are not driver-supplied parameters and must
never be overridden at runtime; widening them requires a reviewable code change to this
file, not a config toggle.
"""

from kernel.runtime_capability import PermissionEnvelope


M3_REQUIRED_CAPABILITIES: tuple[str, ...] = (
    "read_workspace",
    "write_workspace",
)

M3_ADMITTED_PERMISSIONS: PermissionEnvelope = PermissionEnvelope(
    filesystem=("workspace:read", "workspace:write"),
    network=(),
    process=(),
    credentials=(),
    approval_bypass=(),
    external_effects=(),
)
