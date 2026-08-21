"""OpenCode runtime adapter probe (M3 plan §5, PR §10.3).

``probe_opencode_profile`` constructs a real ``RuntimeCapabilityProfile`` from
a live binary version query and the effective merged OpenCode configuration.
This module owns profile construction only; the process wrapper and deny-first
execution live in the later Host increment (plan §10.4).

Modeled configuration precedence (documented first-adapter scope, corrected
after PR review — the calling convention below was previously stated
backwards, which would have made an inherited/global layer silently win over
a project-specific one): OpenCode's layered config resolution is not fully
discoverable from the CLI alone, so the caller-supplied ``config_paths`` are
merged in the given order — later layers override earlier ones, so **callers
must pass layers from most general/inherited first to most specific last**,
e.g. ``(<global>/opencode.json, <project>/opencode.json)``. Layers that parse
as JSON objects shallow-merge; any other layer (plain text such as a jsonc
tail, or a JSON non-object) is retained verbatim as an opaque text layer in
order. Missing paths contribute nothing. ``config_identity`` digests the full
merged result plus the current M3 execution policy (``execution.policy``'s
admitted-permissions/required-capabilities tables), so drift in any
inherited/default config layer, or in the M3 policy table itself, is visible
in ``RuntimeCapabilityProfile.identity`` and causes the Host's execution-time
recheck to fail closed on stale attempts (plan §5.1's staleness gap, closed
here rather than by a contract change).

Known unenforceable gap (documented honestly, not solved here): OpenCode's
CLI has no flag to pin execution to exactly this probed/merged configuration
or to suppress its own further discovery of an inherited/global config layer
at spawn time. The Host pins the *project*-layer config by launching OpenCode
with ``cwd`` set to the exact resolved workspace root this profile was probed
against (same binding class as workspace containment), but cannot prove the
live process did not additionally discover an unprobed global/default layer
— the same enforceability class as network denial (plan §2/§6): unproven,
not falsely claimed as proven.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import fields
from pathlib import Path

from kernel.canonical import content_digest
from kernel.runtime_capability import (
    Capability,
    CapabilityStatus,
    PermissionEnvelope,
    RuntimeCapabilityProfile,
)

from execution import policy
from execution.policy import M3_ADMITTED_PERMISSIONS

ADAPTER_IDENTITY = "opencode-adapter@1"

# Canonical actions (names shared with execution.policy.M3_REQUIRED_CAPABILITIES)
# mapped to OpenCode tools. Any change here changes ``tool_mapping_identity``
# and therefore ``RuntimeCapabilityProfile.identity``; bump the revision suffix
# in ADAPTER_IDENTITY when a mapping change matters to callers.
CANONICAL_ACTION_TOOL_MAPPING: dict[str, str] = {
    "read_workspace": "opencode.read",
    "write_workspace": "opencode.write",
}

_PERMISSIONS_CONFIG_KEY = "permissions"
_ENVELOPE_CATEGORIES = tuple(field.name for field in fields(PermissionEnvelope))


def _resolve_version(binary_path: str) -> str:
    """Return the runtime's reported version; fail closed on any query failure.

    Deterministic for both ``1.2.3`` and ``<name> 1.2.3`` report shapes: the
    version is the last whitespace-separated token of the first stdout line.
    """

    try:
        completed = subprocess.run(
            [binary_path, "--version"],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or "").strip() or f"exit status {exc.returncode}"
        raise ValueError(
            f"opencode version query failed for {binary_path!r}: {detail}"
        ) from exc
    except OSError as exc:
        raise ValueError(
            f"opencode binary could not be executed at {binary_path!r}: {exc}"
        ) from exc

    lines = (completed.stdout or "").strip().splitlines()
    if not lines or not lines[0].strip():
        raise ValueError(
            f"opencode version query for {binary_path!r} produced no version output"
        )
    return lines[0].strip().split()[-1]


def _binary_content_digest(binary_path: str) -> str:
    """Hash the executable's actual bytes; a reported version is not identity.

    PR review: a binary replaced in place with different code that reports
    the same ``--version`` would keep ``runtime`` unchanged under a
    version-only identity, defeating the Attempt Packet's exact-runtime
    binding and the Host's pre-spawn no-silent-substitution recheck. This
    digest is folded into the ``runtime`` field itself (not a separate
    profile field, since ``RuntimeCapabilityProfile``'s schema is frozen
    M0-era shape) so drift is caught by the identity checks that already
    exist end to end.
    """

    hasher = hashlib.sha256()
    try:
        with open(binary_path, "rb") as handle:
            for chunk in iter(lambda: handle.read(1 << 20), b""):
                hasher.update(chunk)
    except OSError as exc:
        raise ValueError(f"unable to read opencode binary at {binary_path!r}: {exc}") from exc
    return hasher.hexdigest()[:16]


def _effective_config(config_paths: tuple[Path, ...]) -> dict[str, object]:
    """Merge config layers in order into the digestable effective config.

    Later entries in ``config_paths`` override earlier ones (standard
    last-write-wins ``dict.update``): callers pass most general/inherited
    layers first, most specific last, so a project-level layer wins over an
    inherited/global one — the calling convention this function's callers
    must honor is stated in this module's docstring.
    """

    merged: dict[str, object] = {}
    raw_layers: list[str] = []
    for path in config_paths:
        try:
            text = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            continue
        try:
            layer = json.loads(text)
        except json.JSONDecodeError:
            raw_layers.append(text)
            continue
        if isinstance(layer, dict):
            merged.update(layer)
        else:
            raw_layers.append(text)
    return {"merged": merged, "raw_layers": raw_layers}


def _m3_policy_snapshot() -> dict[str, object]:
    """Digest input for the current M3 execution policy table.

    Folded into ``config_identity`` (plan §5.1, PR-review fix): a future
    change to ``execution.policy``'s admitted-permissions/required-
    capabilities tables must change ``RuntimeCapabilityProfile.identity``, so
    an already-published Attempt Packet's bound identity goes stale and the
    Host's execution-time recheck rejects it, rather than silently executing
    an old packet under new grants/requirements.
    """

    return {
        "required_capabilities": list(policy.M3_REQUIRED_CAPABILITIES),
        "admitted_permissions": policy.M3_ADMITTED_PERMISSIONS.to_canonical_value(),
    }


def _resolve_permission_envelope(
    effective_config: dict[str, object],
) -> PermissionEnvelope:
    """Resolve the effective envelope; never silently exceed the M3 ceiling.

    Without a config ``permissions`` declaration the effective envelope is
    ``M3_ADMITTED_PERMISSIONS`` itself. A declared envelope must be a
    per-category subset of that ceiling; any widening or malformed declaration
    raises ``ValueError`` rather than being silently clamped — M3 has no config
    UI to "fix" a widening request, and widening requires a reviewable change
    to ``execution/policy.py``, not a runtime config toggle.
    """

    merged = effective_config["merged"]
    if not isinstance(merged, dict):
        return M3_ADMITTED_PERMISSIONS
    declaration = merged.get(_PERMISSIONS_CONFIG_KEY)
    if declaration is None:
        return M3_ADMITTED_PERMISSIONS
    if not isinstance(declaration, dict):
        raise ValueError(
            "opencode config 'permissions' must be an object mapping envelope "
            f"categories to lists of strings, got {type(declaration).__name__}"
        )
    unknown_categories = sorted(set(declaration) - set(_ENVELOPE_CATEGORIES))
    if unknown_categories:
        raise ValueError(
            "opencode config 'permissions' declares unknown categories "
            f"{unknown_categories}; expected a subset of {list(_ENVELOPE_CATEGORIES)}"
        )
    grants: dict[str, tuple[str, ...]] = {}
    excess: list[str] = []
    for category in _ENVELOPE_CATEGORIES:
        if category not in declaration:
            continue
        value = declaration[category]
        if not isinstance(value, list) or any(
            not isinstance(item, str) or not item for item in value
        ):
            raise ValueError(
                f"opencode config 'permissions.{category}' must be a list of "
                "non-empty strings"
            )
        declared = set(value)
        admitted = set(getattr(M3_ADMITTED_PERMISSIONS, category))
        excess.extend(f"{category}:{grant}" for grant in sorted(declared - admitted))
        grants[category] = tuple(value)
    if excess:
        raise ValueError(
            "merged opencode config declares permissions wider than the M3 "
            f"admitted envelope: {', '.join(excess)}; widening requires a "
            "reviewable change to execution/policy.py, not a runtime config"
        )
    return PermissionEnvelope(**grants)


def _mapped_capabilities() -> tuple[Capability, ...]:
    """Declare every mapped canonical action at its honest M3 status.

    Plan §2/§6: ``read_workspace``/``write_workspace`` get declared-scope
    containment checks (candidate paths pre-resolved before spawn), not
    syscall interception, so both are ``PARTIAL`` — never ``SUPPORTED`` — and
    ``RuntimeCapabilityProfile.require`` fails closed for any Attempt that
    needs real enforcement. Canonical actions absent from the mapping stay
    ``UNKNOWN`` under ``require`` by default.
    """

    return tuple(
        Capability(name, CapabilityStatus.PARTIAL)
        for name in sorted(CANONICAL_ACTION_TOOL_MAPPING)
    )


def probe_opencode_profile(
    binary_path: str, config_paths: tuple[Path, ...] = ()
) -> RuntimeCapabilityProfile:
    """Probe the live OpenCode runtime and return its capability profile."""

    version = _resolve_version(binary_path)
    binary_digest = _binary_content_digest(binary_path)
    effective_config = _effective_config(config_paths)
    config_and_policy = {
        "config": effective_config,
        "m3_policy": _m3_policy_snapshot(),
    }
    return RuntimeCapabilityProfile(
        runtime=f"opencode@{version}+{binary_digest}",
        adapter=ADAPTER_IDENTITY,
        config_identity=content_digest(config_and_policy),
        tool_mapping_identity=content_digest(CANONICAL_ACTION_TOOL_MAPPING),
        permission_envelope=_resolve_permission_envelope(effective_config),
        capabilities=_mapped_capabilities(),
    )
