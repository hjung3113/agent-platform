from __future__ import annotations

import json
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from kernel import admission
from kernel.protocol import ContractKind, RecordRef
from kernel.protocol_v1 import AttemptPacketV1, TaskV1, read_result_v1
from execution import host, policy
from execution.host import (
    AdmissionRejectedError,
    RetentionBlockedError,
    RuntimeSubstitutionRejectedError,
    StaleRuntimeCapabilityProfileError,
    StaleWorkspaceSnapshotError,
    execute,
)
from execution.opencode_adapter import probe_opencode_profile
from execution.workspace_snapshot import snapshot_identity

FIXTURE_BINARY = (
    Path(__file__).resolve().parent / "fixtures" / "fake_opencode" / "fake_opencode.py"
)
FAKE_VERSION = "1.2.3"
REPORT_NAME = "fake-opencode-report.json"
DIRECTIVE_NAME = "fake-opencode-directive.txt"
SENTINEL_VARIABLE = "SENTINEL_SECRET"
WORKFLOW_REVISION_REF = RecordRef(
    contract_kind=ContractKind.WORKFLOW_REVISION.value,
    record_id="wr_host_1",
    content_digest="sha256:agent-platform-json-v1:" + "a" * 64,
)
ATTEMPT_REF = RecordRef(
    contract_kind=ContractKind.ATTEMPT_PACKET.value,
    record_id="ap_host_1",
    content_digest="sha256:agent-platform-json-v1:" + "b" * 64,
)
CONTEXT_DIGEST_FIXTURE = "sha256:agent-platform-json-v1:" + "e" * 64
TASK = TaskV1(
    task_id="task-host-1",
    objective="Prove the Host actually receives the admitted task",
    acceptance_criteria=("The runtime message contains the task objective",),
)


class HostExecuteTest(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary_directory.cleanup)
        self.root = Path(self._temporary_directory.name) / "repo"
        self._init_repo(self.root)
        (self.root / "tracked.txt").write_text("tracked\n", encoding="utf-8")
        self._git(self.root, "add", "tracked.txt")
        self._git(self.root, "commit", "-m", "initial host fixture")

    @classmethod
    def setUpClass(cls) -> None:
        mode = FIXTURE_BINARY.stat().st_mode
        if not mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH):
            FIXTURE_BINARY.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    @staticmethod
    def _git(cwd: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *arguments],
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
        )

    def _init_repo(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        self._git(path, "init")
        self._git(path, "config", "user.email", "host-tests@example.invalid")
        self._git(path, "config", "user.name", "Host Execute Tests")

    def _build_attempt(
        self,
        *,
        declared_generated_paths: tuple[str, ...] = (),
        profile_identity: str | None = None,
        snapshot_digest: str | None = None,
    ) -> AttemptPacketV1:
        return AttemptPacketV1(
            workflow_revision=WORKFLOW_REVISION_REF,
            task_id="task-host-1",
            implementer_identity="implementer-fixture",
            context_digest=CONTEXT_DIGEST_FIXTURE,
            workspace_snapshot_digest=(
                snapshot_digest
                if snapshot_digest is not None
                else snapshot_identity(self.root, declared_generated_paths).digest
            ),
            runtime_capability_profile_identity=(
                profile_identity
                if profile_identity is not None
                else probe_opencode_profile(str(FIXTURE_BINARY)).identity
            ),
        )

    def _spawned_report(self) -> Path:
        return self.root / REPORT_NAME

    def _no_required_capabilities(self) -> mock._patch:
        """Test seam: admit with the requirement set the live profile satisfies.

        The committed ``policy.M3_REQUIRED_CAPABILITIES`` names are PARTIAL in
        the honest OpenCode profile (see
        ``test_committed_policy_table_fails_closed_against_live_profile``), so
        the unpatched table currently rejects every execution. Happy-path
        tests exercise the Host mechanics with the only requirement set the
        live profile can admit: none. Production code still binds exclusively
        to the fixed table; nothing in ``host.execute`` accepts an override.
        """

        return mock.patch.object(policy, "M3_REQUIRED_CAPABILITIES", ())

    def _drift_binary(self, version: str = "9.9.9") -> Path:
        other = Path(self._temporary_directory.name) / f"fake_opencode_{version}.py"
        other.write_text(
            "#!/usr/bin/env python3\n"
            "import sys\n"
            "if sys.argv[1:] == ['--version']:\n"
            f"    print('fake-opencode {version}')\n"
            "    raise SystemExit(0)\n"
            "raise SystemExit(2)\n",
            encoding="utf-8",
        )
        other.chmod(0o755)
        return other

    def _copy_binary(self) -> Path:
        other = Path(self._temporary_directory.name) / "fake_opencode_copy.py"
        other.write_text(FIXTURE_BINARY.read_text(encoding="utf-8"), encoding="utf-8")
        other.chmod(0o755)
        return other

    def test_execute_binds_attempt_ref_and_real_observation(self) -> None:
        declared = ("generated/output.txt",)
        attempt = self._build_attempt(declared_generated_paths=declared)
        with self._no_required_capabilities():
            result = execute(
                ATTEMPT_REF,
                attempt,
                self.root,
                str(FIXTURE_BINARY),
                TASK,
                declared_generated_paths=declared,
            )

        self.assertEqual(result.attempt, ATTEMPT_REF)
        self.assertTrue(result.observation.runtime_identity.startswith(f"opencode@{FAKE_VERSION}+"))
        self.assertEqual(
            result.output_snapshot_digest,
            snapshot_identity(self.root, declared).digest,
        )
        self.assertEqual(
            result.observation.output_snapshot_digest, result.output_snapshot_digest
        )
        self.assertTrue(self._spawned_report().is_file())
        outcome = read_result_v1(result.to_canonical_value())
        self.assertEqual(outcome.value, result)

        report = json.loads(self._spawned_report().read_text(encoding="utf-8"))
        self.assertIn(TASK.objective, report["message"])
        for criterion in TASK.acceptance_criteria:
            self.assertIn(criterion, report["message"])

    def test_runtime_nonzero_exit_raises_instead_of_producing_a_result(self) -> None:
        """PR review: a genuinely failed run must not silently produce a
        Result. Exit-code 0 stays untrusted (completion is snapshot-derived,
        not stdout/exit-code-derived) -- but a nonzero exit is a real
        execution failure, not merely an unreliable success signal."""

        (self.root / DIRECTIVE_NAME).write_text("fail", encoding="utf-8")
        attempt = self._build_attempt()

        with self._no_required_capabilities():
            with self.assertRaises(host.RuntimeExecutionFailedError) as raised:
                execute(ATTEMPT_REF, attempt, self.root, str(FIXTURE_BINARY), TASK)

        self.assertEqual(raised.exception.returncode, 3)
        self.assertFalse(self._spawned_report().exists())

    def test_requested_effect_rejects_through_execute_before_spawn(self) -> None:
        """PR review: requested_effects was constructible on AttemptRequest
        directly but never reachable from execute() itself, so no real
        caller could actually exercise external-effect rejection end to end."""

        attempt = self._build_attempt()
        with self._no_required_capabilities():
            with self.assertRaises(AdmissionRejectedError) as raised:
                execute(
                    ATTEMPT_REF,
                    attempt,
                    self.root,
                    str(FIXTURE_BINARY),
                    TASK,
                    requested_effects=("github:push",),
                )

        self.assertEqual(raised.exception.reason, "external_effect_not_admitted")
        self.assertFalse(self._spawned_report().exists())

    def test_non_utf8_stdout_scans_as_unknown_and_blocks_retention(self) -> None:
        """PR review: subprocess.run(text=True) would raise UnicodeDecodeError
        on invalid bytes before scan_for_retention ever ran. Bytes are now
        captured and decoded under Host control; a decode failure becomes
        scan_for_retention(None) -> "unknown", which still blocks retention
        rather than crashing execute() outright."""

        (self.root / DIRECTIVE_NAME).write_text("invalid-utf8-stdout", encoding="utf-8")
        attempt = self._build_attempt()

        with self._no_required_capabilities():
            with self.assertRaises(RetentionBlockedError) as raised:
                execute(
                    ATTEMPT_REF,
                    attempt,
                    self.root,
                    str(FIXTURE_BINARY),
                    TASK,
                    retain_evidence=True,
                )

        self.assertIn("stdout scan status=unknown", str(raised.exception))

    def test_stale_runtime_capability_profile_rejects_before_spawn(self) -> None:
        drift_identity = probe_opencode_profile(str(self._drift_binary())).identity
        attempt = self._build_attempt(profile_identity=drift_identity)

        with self.assertRaises(StaleRuntimeCapabilityProfileError):
            execute(ATTEMPT_REF, attempt, self.root, str(FIXTURE_BINARY), TASK)

        self.assertFalse(self._spawned_report().exists())

    def test_stale_workspace_snapshot_rejects_before_spawn(self) -> None:
        attempt = self._build_attempt()
        (self.root / "untracked-late.txt").write_text("late mutation\n", encoding="utf-8")

        with self.assertRaises(StaleWorkspaceSnapshotError):
            execute(ATTEMPT_REF, attempt, self.root, str(FIXTURE_BINARY), TASK)

        self.assertFalse(self._spawned_report().exists())

    def test_mutation_between_admission_and_spawn_is_caught_by_pre_spawn_recheck(
        self,
    ) -> None:
        attempt = self._build_attempt()
        injected = self.root / "injected-between-admission-and-spawn.txt"
        real_probe = host.probe_opencode_profile
        probe_calls = {"count": 0}

        def mutating_probe(binary_path: str, config_paths: tuple[Path, ...] = ()):
            probe_calls["count"] += 1
            if probe_calls["count"] == 2:
                injected.write_text("tampered after admission\n", encoding="utf-8")
            return real_probe(binary_path, config_paths)

        with self._no_required_capabilities():
            with mock.patch.object(host, "probe_opencode_profile", mutating_probe):
                with self.assertRaises(StaleWorkspaceSnapshotError):
                    execute(ATTEMPT_REF, attempt, self.root, str(FIXTURE_BINARY), TASK)

        self.assertTrue(injected.is_file())
        self.assertFalse(self._spawned_report().exists())

    def test_required_capability_not_supported_rejects_before_spawn(self) -> None:
        """Plan §9: replaces the withdrawn "network blocked at the process
        boundary" claim (§13 BLOCKER 1). ``network_access`` is never in
        CANONICAL_ACTION_TOOL_MAPPING, so the live profile never marks it
        SUPPORTED and ``admit_attempt``/``require()`` reject the Attempt
        before the adapter is invoked. This is capability-admission
        rejection only — advisory, not process-boundary enforcement.
        """

        required = ("read_workspace", "write_workspace", "network_access")
        with mock.patch.object(policy, "M3_REQUIRED_CAPABILITIES", required):
            # Build under the same patch: M3_REQUIRED_CAPABILITIES is folded
            # into config_identity (PR-review fix), so the attempt's stored
            # profile identity must reflect the same policy the live probe
            # will see during execute(), or this hits StaleRuntimeCapability-
            # ProfileError instead of the admission rejection under test.
            attempt = self._build_attempt()
            with self.assertRaises(AdmissionRejectedError) as raised:
                execute(ATTEMPT_REF, attempt, self.root, str(FIXTURE_BINARY), TASK)

        self.assertEqual(raised.exception.reason, "required_capabilities_not_satisfied")
        self.assertFalse(self._spawned_report().exists())

    def test_committed_policy_table_admits_the_live_profile(self) -> None:
        """Resolved PR3a/PR3b/PR4 composition (orchestrator-level fix).

        An earlier draft of ``execution.policy.M3_REQUIRED_CAPABILITIES``
        named ``read_workspace``/``write_workspace``, which the honest
        OpenCode adapter can only ever mark PARTIAL (plan §2/§6) — that
        combination made every M3 execution fail closed at admission
        permanently. ``M3_REQUIRED_CAPABILITIES`` is now empty by design
        (plan §5.1): M3's real enforcement is PermissionEnvelope +
        containment + credentials allow-list, not the SUPPORTED-capability
        mechanism, so the committed table admits the live profile without
        the ``_no_required_capabilities`` test seam.
        """

        attempt = self._build_attempt()
        self.assertEqual(policy.M3_REQUIRED_CAPABILITIES, ())

        result = execute(ATTEMPT_REF, attempt, self.root, str(FIXTURE_BINARY), TASK)

        self.assertEqual(result.attempt, ATTEMPT_REF)
        self.assertTrue(self._spawned_report().is_file())

    def test_child_environment_is_allow_listed_not_inherited(self) -> None:
        """Real process-boundary credential enforcement (plan §6 step 4).

        The parent builds the child env from scratch (PATH plus the empty M3
        credentials allow-list), so ambient secrets are invisible to the
        child by omission. Claim scope is non-inheritance of the PARENT's
        environment: the child's own interpreter may add variables to itself
        after launch (macOS Xcode CommandLineTools python3 injects SDKROOT,
        CPATH, LIBRARY_PATH, MANPATH, LC_CTYPE, __CF_USER_TEXT_ENCODING),
        which the parent cannot control and which is not ambient inheritance.
        """

        attempt = self._build_attempt()
        with self._no_required_capabilities():
            with mock.patch.dict(
                "os.environ", {SENTINEL_VARIABLE: "test-sentinel-secret-value"}
            ):
                result = execute(ATTEMPT_REF, attempt, self.root, str(FIXTURE_BINARY), TASK)

        report = json.loads(self._spawned_report().read_text(encoding="utf-8"))
        self.assertFalse(report["sentinel_secret_seen"])
        self.assertNotIn(SENTINEL_VARIABLE, report["env_keys"])

        ambient_checked = 0
        for ambient_name in ("HOME", "USER", "TMPDIR"):
            if ambient_name in os.environ:
                ambient_checked += 1
                self.assertNotIn(ambient_name, report["env_keys"], ambient_name)
        self.assertGreater(ambient_checked, 0)

        self.assertEqual(report["cwd"], str(self.root.resolve()))
        self.assertEqual(report["workdir_argument"], str(self.root.resolve()))
        self.assertEqual(
            result.output_snapshot_digest,
            snapshot_identity(self.root, ()).digest,
        )

    def test_completion_derives_from_snapshot_not_stdout_or_exit_code(self) -> None:
        (self.root / DIRECTIVE_NAME).write_text("noop", encoding="utf-8")
        precondition = subprocess.run(
            [str(FIXTURE_BINARY), "run", "--workdir", str(self.root)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(precondition.returncode, 0)
        self.assertIn("success", precondition.stdout)
        self.assertFalse(self._spawned_report().exists())

        attempt = self._build_attempt()
        with self._no_required_capabilities():
            result = execute(ATTEMPT_REF, attempt, self.root, str(FIXTURE_BINARY), TASK)

        self.assertEqual(
            result.output_snapshot_digest, attempt.workspace_snapshot_digest
        )
        self.assertEqual(
            result.output_snapshot_digest, snapshot_identity(self.root, ()).digest
        )
        self.assertEqual(
            result.observation.output_snapshot_digest, result.output_snapshot_digest
        )
        self.assertFalse(self._spawned_report().exists())

    def test_binary_path_drift_between_probe_and_recheck_rejects(self) -> None:
        attempt = self._build_attempt()
        other = self._copy_binary()
        self.assertNotEqual(other.resolve(), FIXTURE_BINARY.resolve())
        real_resolver = host._resolve_runtime_binary
        resolver_calls = {"count": 0}

        def drifting_resolver(binary_path: str) -> Path:
            resolver_calls["count"] += 1
            if resolver_calls["count"] >= 2:
                return other.resolve()
            return real_resolver(binary_path)

        with self._no_required_capabilities():
            with mock.patch.object(host, "_resolve_runtime_binary", drifting_resolver):
                with self.assertRaises(RuntimeSubstitutionRejectedError):
                    execute(ATTEMPT_REF, attempt, self.root, str(FIXTURE_BINARY), TASK)

        self.assertFalse(self._spawned_report().exists())

    def test_identity_drift_between_probe_and_recheck_rejects(self) -> None:
        attempt = self._build_attempt()
        drift = self._drift_binary()
        real_probe = host.probe_opencode_profile
        probe_calls = {"count": 0}

        def drifting_probe(binary_path: str, config_paths: tuple[Path, ...] = ()):
            probe_calls["count"] += 1
            if probe_calls["count"] >= 2:
                return real_probe(str(drift), config_paths)
            return real_probe(binary_path, config_paths)

        with self._no_required_capabilities():
            with mock.patch.object(host, "probe_opencode_profile", drifting_probe):
                with self.assertRaises(RuntimeSubstitutionRejectedError):
                    execute(ATTEMPT_REF, attempt, self.root, str(FIXTURE_BINARY), TASK)

        self.assertFalse(self._spawned_report().exists())

    def test_external_effect_request_rejects_against_empty_m3_envelope(self) -> None:
        profile = probe_opencode_profile(str(FIXTURE_BINARY))
        request = admission.AttemptRequest(
            workspace_root=self.root.resolve(),
            runtime_profile=profile,
            admitted_permissions=policy.M3_ADMITTED_PERMISSIONS,
            requested_effects=("github:push",),
        )
        result = admission.admit_attempt(request)

        self.assertEqual(result.status, admission.AdmissionStatus.BLOCKED)
        self.assertEqual(result.reason, "external_effect_not_admitted")
        self.assertEqual(policy.M3_ADMITTED_PERMISSIONS.external_effects, ())

    def test_declared_generated_path_escape_rejects_before_spawn(self) -> None:
        declared = ("../outside.txt",)
        attempt = self._build_attempt(declared_generated_paths=declared)
        with self._no_required_capabilities():
            with self.assertRaises(AdmissionRejectedError) as raised:
                execute(
                    ATTEMPT_REF,
                    attempt,
                    self.root,
                    str(FIXTURE_BINARY),
                    TASK,
                    declared_generated_paths=declared,
                )

        self.assertEqual(raised.exception.reason, "candidate_path_outside_workspace")
        self.assertFalse(self._spawned_report().exists())
        self.assertFalse(
            (Path(self._temporary_directory.name) / "outside.txt").exists()
        )

    def test_canary_stdout_does_not_block_default_nonretained_execution(self) -> None:
        (self.root / DIRECTIVE_NAME).write_text("stdout-canary", encoding="utf-8")
        attempt = self._build_attempt()

        with self._no_required_capabilities():
            result = execute(ATTEMPT_REF, attempt, self.root, str(FIXTURE_BINARY), TASK)

        self.assertEqual(result.attempt, ATTEMPT_REF)

    def test_canary_stdout_blocks_retained_execution(self) -> None:
        (self.root / DIRECTIVE_NAME).write_text("stdout-canary", encoding="utf-8")
        attempt = self._build_attempt()

        with self._no_required_capabilities():
            with self.assertRaises(RetentionBlockedError) as raised:
                execute(
                    ATTEMPT_REF,
                    attempt,
                    self.root,
                    str(FIXTURE_BINARY),
                    TASK,
                    retain_evidence=True,
                )

        self.assertEqual(str(raised.exception), "stdout scan status=blocked")
        self.assertNotIn("AKIAABCDEFGHIJKLMNOP", str(raised.exception))

    def test_ordinary_stdout_allows_retained_execution(self) -> None:
        attempt = self._build_attempt()

        with self._no_required_capabilities():
            result = execute(
                ATTEMPT_REF,
                attempt,
                self.root,
                str(FIXTURE_BINARY),
                TASK,
                retain_evidence=True,
            )

        self.assertEqual(result.attempt, ATTEMPT_REF)
        self.assertTrue(self._spawned_report().is_file())


if __name__ == "__main__":
    unittest.main()
