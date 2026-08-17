from __future__ import annotations

import unittest

from kernel.runtime_capability import (
    Capability,
    CapabilityAdmissionError,
    CapabilityStatus,
    PermissionEnvelope,
    RuntimeCapabilityProfile,
)


def make_profile(**overrides: object) -> RuntimeCapabilityProfile:
    values: dict[str, object] = {
        "runtime": "opencode@1.2.3",
        "adapter": "opencode-adapter@0.4.0",
        "config_identity": "sha256:config",
        "tool_mapping_identity": "sha256:mapping",
        "permission_envelope": PermissionEnvelope(
            filesystem=("workspace:read", "workspace:write"),
            network=("github.com",),
            process=("git",),
        ),
        "capabilities": (
            Capability("file.read", CapabilityStatus.SUPPORTED),
            Capability("file.write", CapabilityStatus.SUPPORTED),
        ),
    }
    values.update(overrides)
    return RuntimeCapabilityProfile(**values)  # type: ignore[arg-type]


class RuntimeCapabilityProfileTests(unittest.TestCase):
    def test_identity_is_stable_for_equivalent_profile_content(self) -> None:
        first = make_profile()
        second = make_profile(
            permission_envelope=PermissionEnvelope(
                process=("git",),
                network=("github.com",),
                filesystem=("workspace:write", "workspace:read", "workspace:read"),
            ),
            capabilities=(
                Capability("file.write", CapabilityStatus.SUPPORTED),
                Capability("file.read", CapabilityStatus.SUPPORTED),
            ),
        )

        self.assertEqual(first.identity, second.identity)
        self.assertRegex(
            first.identity,
            r"^sha256:agent-platform-json-v1:[0-9a-f]{64}$",
        )

    def test_profile_content_changes_identity(self) -> None:
        baseline = make_profile()
        changed_profiles = (
            make_profile(runtime="opencode@1.2.4"),
            make_profile(adapter="opencode-adapter@0.4.1"),
            make_profile(config_identity="sha256:other-config"),
            make_profile(tool_mapping_identity="sha256:other-mapping"),
            make_profile(
                permission_envelope=PermissionEnvelope(
                    filesystem=("workspace:read",),
                    network=("github.com",),
                    process=("git",),
                )
            ),
            make_profile(
                capabilities=(
                    Capability("file.read", CapabilityStatus.SUPPORTED),
                    Capability("file.write", CapabilityStatus.PARTIAL),
                )
            ),
        )

        for changed in changed_profiles:
            with self.subTest(changed=changed.to_canonical_value()):
                self.assertNotEqual(baseline.identity, changed.identity)

    def test_supported_required_capability_is_admitted(self) -> None:
        make_profile().require(("file.read", "file.write"))

    def test_non_supported_required_capabilities_fail_closed(self) -> None:
        for status in (
            CapabilityStatus.UNSUPPORTED,
            CapabilityStatus.UNKNOWN,
            CapabilityStatus.PARTIAL,
        ):
            with self.subTest(status=status):
                profile = make_profile(
                    capabilities=(Capability("tool.call", status),)
                )
                with self.assertRaises(CapabilityAdmissionError):
                    profile.require(("tool.call",))

    def test_missing_required_capability_is_unknown_and_fails_closed(self) -> None:
        with self.assertRaisesRegex(
            CapabilityAdmissionError, r"tool\.call=unknown"
        ):
            make_profile().require(("tool.call",))


if __name__ == "__main__":
    unittest.main()
