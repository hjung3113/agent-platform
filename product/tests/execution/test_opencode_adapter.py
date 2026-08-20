from __future__ import annotations

import json
import stat
import tempfile
import unittest
from pathlib import Path

from kernel.runtime_capability import (
    CapabilityAdmissionError,
    CapabilityStatus,
    RuntimeCapabilityProfile,
)
from execution import policy
from execution.opencode_adapter import CANONICAL_ACTION_TOOL_MAPPING, probe_opencode_profile

FIXTURE_BINARY = (
    Path(__file__).resolve().parent / "fixtures" / "fake_opencode" / "fake_opencode.py"
)
FAKE_VERSION = "1.2.3"
_ENVELOPE_CATEGORIES = (
    "filesystem",
    "network",
    "process",
    "credentials",
    "approval_bypass",
    "external_effects",
)


def _write_config(path: Path, payload: object) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


class ProbeOpencodeProfileTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        mode = FIXTURE_BINARY.stat().st_mode
        if not mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH):
            FIXTURE_BINARY.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    def test_probe_returns_valid_profile_with_stable_identity(self) -> None:
        profile = probe_opencode_profile(str(FIXTURE_BINARY))
        self.assertIsInstance(profile, RuntimeCapabilityProfile)
        identity = profile.identity
        self.assertTrue(identity.startswith("sha256:agent-platform-json-v1:"))
        self.assertEqual(
            identity, probe_opencode_profile(str(FIXTURE_BINARY)).identity
        )

    def test_runtime_field_embeds_reported_version(self) -> None:
        profile = probe_opencode_profile(str(FIXTURE_BINARY))
        self.assertEqual(profile.runtime, f"opencode@{FAKE_VERSION}")

    def test_inherited_config_layer_change_changes_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = _write_config(root / "opencode.json", {"autoupdate": True})
            inherited = _write_config(
                root / "opencode.global.json", {"model": "glama/gpt-5.6-sol"}
            )
            before = probe_opencode_profile(
                str(FIXTURE_BINARY), (project, inherited)
            )
            self.assertEqual(
                before.config_identity,
                probe_opencode_profile(
                    str(FIXTURE_BINARY), (project, inherited)
                ).config_identity,
            )
            inherited = _write_config(
                root / "opencode.global.json", {"model": "zhipu/glm-5.3"}
            )
            after = probe_opencode_profile(
                str(FIXTURE_BINARY), (project, inherited)
            )
            self.assertNotEqual(before.config_identity, after.config_identity)
            self.assertNotEqual(before.identity, after.identity)

    def test_permission_envelope_never_wider_than_m3_admitted(self) -> None:
        profile = probe_opencode_profile(str(FIXTURE_BINARY))
        for category in _ENVELOPE_CATEGORIES:
            declared = set(getattr(profile.permission_envelope, category))
            admitted = set(getattr(policy.M3_ADMITTED_PERMISSIONS, category))
            self.assertTrue(declared <= admitted, category)

    def test_narrowing_config_keeps_envelope_within_ceiling(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = _write_config(
                Path(tmp) / "opencode.json",
                {"permissions": {"filesystem": ["workspace:read"]}},
            )
            profile = probe_opencode_profile(str(FIXTURE_BINARY), (config,))
            self.assertEqual(
                profile.permission_envelope.filesystem, ("workspace:read",)
            )
            for category in _ENVELOPE_CATEGORIES:
                declared = set(getattr(profile.permission_envelope, category))
                admitted = set(getattr(policy.M3_ADMITTED_PERMISSIONS, category))
                self.assertTrue(declared <= admitted, category)

    def test_widening_config_raises_value_error(self) -> None:
        widening_cases = (
            {"permissions": {"network": ["*"]}},
            {"permissions": {"filesystem": ["workspace:read", "/etc"]}},
            {"permissions": {"process": ["spawn:arbitrary"]}},
        )
        with tempfile.TemporaryDirectory() as tmp:
            for index, payload in enumerate(widening_cases):
                with self.subTest(payload=payload):
                    config = _write_config(
                        Path(tmp) / f"opencode-{index}.json", payload
                    )
                    with self.assertRaises(ValueError):
                        probe_opencode_profile(str(FIXTURE_BINARY), (config,))

    def test_workspace_capabilities_are_partial_not_supported(self) -> None:
        profile = probe_opencode_profile(str(FIXTURE_BINARY))
        statuses = {
            capability.name: capability.status
            for capability in profile.capabilities
        }
        for name in policy.M3_REQUIRED_CAPABILITIES:
            self.assertEqual(statuses.get(name), CapabilityStatus.PARTIAL, name)
            self.assertNotEqual(statuses.get(name), CapabilityStatus.SUPPORTED, name)

    def test_declared_capabilities_match_adapter_tool_mapping(self) -> None:
        """The adapter declares exactly its own mapped canonical actions.

        These are independent of ``policy.M3_REQUIRED_CAPABILITIES``, which
        is empty by design (plan §5.1, orchestrator-level fix): the adapter
        can only ever mark these PARTIAL, so M3 does not require() them.
        """

        profile = probe_opencode_profile(str(FIXTURE_BINARY))
        declared = {capability.name for capability in profile.capabilities}
        self.assertEqual(declared, set(CANONICAL_ACTION_TOOL_MAPPING))

    def test_require_unmapped_action_fails_closed(self) -> None:
        profile = probe_opencode_profile(str(FIXTURE_BINARY))
        with self.assertRaises(CapabilityAdmissionError):
            profile.require(("some_totally_unmapped_action",))

    def test_probed_binary_drift_changes_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            other = Path(tmp) / "fake_opencode_drift.py"
            other.write_text(
                "#!/usr/bin/env python3\n"
                "import sys\n"
                "if sys.argv[1:] == ['--version']:\n"
                "    print('fake-opencode 9.9.9')\n"
                "    raise SystemExit(0)\n"
                "raise SystemExit(2)\n",
                encoding="utf-8",
            )
            other.chmod(0o755)
            baseline = probe_opencode_profile(str(FIXTURE_BINARY))
            drifted = probe_opencode_profile(str(other))
            self.assertEqual(baseline.runtime, f"opencode@{FAKE_VERSION}")
            self.assertEqual(drifted.runtime, "opencode@9.9.9")
            self.assertNotEqual(baseline.identity, drifted.identity)

    def test_missing_binary_raises_value_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "definitely-not-installed-opencode"
            with self.assertRaises(ValueError):
                probe_opencode_profile(str(missing))


if __name__ == "__main__":
    unittest.main()
