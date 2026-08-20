"""OpenCode runtime adapter probe (M3 plan §5, PR §10.3).

``probe_opencode_profile`` constructs a real ``RuntimeCapabilityProfile`` from
a live binary version query and the effective merged OpenCode configuration.
This module owns profile construction only; the process wrapper and deny-first
execution live in the later Host increment (plan §10.4).

Modeled configuration precedence (documented first-adapter scope): OpenCode's
layered config resolution is not fully discoverable from the CLI alone, so the
caller-supplied ``config_paths`` are merged in the given order — later layers
override earlier ones (callers pass layers from most specific to most
inherited/global, e.g. ``(<project>/opencode.json, <global>/opencode.json)``).
Layers that parse as JSON objects shallow-merge; any other layer (plain text
such as a jsonc tail, or a JSON non-object) is retained verbatim as an opaque
text layer in order. Missing paths contribute nothing. ``config_identity``
digests the full merged result, so drift in any inherited/default layer is
visible in ``RuntimeCapabilityProfile.identity``.
"""

from __future__ import annotations

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


def _effective_config(config_paths: tuple[Path, ...]) -> dict[str, object]:
    """Merge config layers in order into the digestable effective config."""

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
    effective_config = _effective_config(config_paths)
    return RuntimeCapabilityProfile(
        runtime=f"opencode@{version}",
        adapter=ADAPTER_IDENTITY,
        config_identity=content_digest(effective_config),
        tool_mapping_identity=content_digest(CANONICAL_ACTION_TOOL_MAPPING),
        permission_envelope=_resolve_permission_envelope(effective_config),
        capabilities=_mapped_capabilities(),
    )
