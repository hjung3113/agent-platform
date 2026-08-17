"""Runtime capability identity and fail-closed admission primitives."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from kernel.canonical import content_digest

PROFILE_KIND = "runtime-capability-profile"
PROFILE_VERSION = 1


class CapabilityStatus(str, Enum):
    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    PARTIAL = "partial"
    UNKNOWN = "unknown"


class CapabilityAdmissionError(ValueError):
    """Raised when required capabilities are not fully supported."""


@dataclass(frozen=True)
class PermissionEnvelope:
    """Effective runtime permissions after defaults, aliases, and mappings."""

    filesystem: tuple[str, ...] = ()
    network: tuple[str, ...] = ()
    process: tuple[str, ...] = ()
    credentials: tuple[str, ...] = ()
    approval_bypass: tuple[str, ...] = ()
    external_effects: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field_name in (
            "filesystem",
            "network",
            "process",
            "credentials",
            "approval_bypass",
            "external_effects",
        ):
            values = getattr(self, field_name)
            if any(not isinstance(value, str) or not value for value in values):
                raise ValueError(f"{field_name} permissions must be non-empty strings")
            object.__setattr__(self, field_name, tuple(sorted(set(values))))

    def to_canonical_value(self) -> dict[str, list[str]]:
        return {
            "filesystem": list(self.filesystem),
            "network": list(self.network),
            "process": list(self.process),
            "credentials": list(self.credentials),
            "approval_bypass": list(self.approval_bypass),
            "external_effects": list(self.external_effects),
        }


@dataclass(frozen=True)
class Capability:
    name: str
    status: CapabilityStatus

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("capability name must not be empty")
        if not isinstance(self.status, CapabilityStatus):
            raise TypeError("capability status must be a CapabilityStatus")


@dataclass(frozen=True)
class RuntimeCapabilityProfile:
    """Immutable semantic identity used for runtime capability admission."""

    runtime: str
    adapter: str
    config_identity: str
    tool_mapping_identity: str
    permission_envelope: PermissionEnvelope
    capabilities: tuple[Capability, ...]

    def __post_init__(self) -> None:
        for field_name in (
            "runtime",
            "adapter",
            "config_identity",
            "tool_mapping_identity",
        ):
            if not getattr(self, field_name):
                raise ValueError(f"{field_name} must not be empty")

        if not isinstance(self.permission_envelope, PermissionEnvelope):
            raise TypeError("permission_envelope must be a PermissionEnvelope")

        by_name: dict[str, Capability] = {}
        for capability in self.capabilities:
            if not isinstance(capability, Capability):
                raise TypeError("capabilities must contain Capability values")
            if capability.name in by_name:
                raise ValueError(f"duplicate capability: {capability.name}")
            by_name[capability.name] = capability
        object.__setattr__(
            self,
            "capabilities",
            tuple(by_name[name] for name in sorted(by_name)),
        )

    def to_canonical_value(self) -> dict[str, object]:
        return {
            "kind": PROFILE_KIND,
            "version": PROFILE_VERSION,
            "runtime": self.runtime,
            "adapter": self.adapter,
            "config_identity": self.config_identity,
            "tool_mapping_identity": self.tool_mapping_identity,
            "permission_envelope": self.permission_envelope.to_canonical_value(),
            "capabilities": {
                capability.name: capability.status.value
                for capability in self.capabilities
            },
        }

    @property
    def identity(self) -> str:
        """Stable content identity for the exact admitted profile."""

        return content_digest(self.to_canonical_value())

    def require(self, required_capabilities: Iterable[str]) -> None:
        """Fail closed unless every required capability is fully supported."""

        statuses = {capability.name: capability.status for capability in self.capabilities}
        failures: list[str] = []
        for name in sorted(set(required_capabilities)):
            if not name:
                raise ValueError("required capability name must not be empty")
            status = statuses.get(name, CapabilityStatus.UNKNOWN)
            if status is not CapabilityStatus.SUPPORTED:
                failures.append(f"{name}={status.value}")

        if failures:
            raise CapabilityAdmissionError(
                "required capabilities are not fully supported: " + ", ".join(failures)
            )
