from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from kernel.protocol import ContractKind, RecordRef
from execution.attempt import build_attempt_packet

FIXTURE_BINARY = (
    Path(__file__).resolve().parent / "fixtures" / "fake_opencode" / "fake_opencode.py"
)

WORKFLOW_REVISION_REF = RecordRef(
    contract_kind=ContractKind.WORKFLOW_REVISION.value,
    record_id="wr_attempt_test",
    content_digest="sha256:agent-platform-json-v1:" + "a" * 64,
)


class AttemptPacketRealIdentityTest(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self._temporary_directory.name) / "repo"
        self._init_repo(self.root)
        (self.root / "tracked.txt").write_text("tracked\n", encoding="utf-8")
        self._git(self.root, "add", "tracked.txt")
        self._git(self.root, "commit", "-m", "initial attempt identity fixture")

    def tearDown(self) -> None:
        self._temporary_directory.cleanup()

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
        self._git(path, "config", "user.email", "attempt-tests@example.invalid")
        self._git(path, "config", "user.name", "Attempt Packet Tests")

    def _build_packet(self, opencode_binary_path: Path = FIXTURE_BINARY):
        return build_attempt_packet(
            workflow_revision_ref=WORKFLOW_REVISION_REF,
            task_id="task-attempt-real-identities",
            implementer_identity="impl-1",
            workspace_root=self.root,
            opencode_binary_path=str(opencode_binary_path),
        )

    def _drift_binary(self) -> Path:
        other = Path(self._temporary_directory.name) / "fake_opencode_drift.py"
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
        return other

    def test_workspace_and_runtime_drift_change_packet_identities(self) -> None:
        baseline = self._build_packet()

        (self.root / "untracked.txt").write_text("first\n", encoding="utf-8")
        changed_workspace = self._build_packet()
        self.assertNotEqual(
            baseline.workspace_snapshot_digest,
            changed_workspace.workspace_snapshot_digest,
        )

        changed_runtime = self._build_packet(self._drift_binary())
        self.assertNotEqual(
            changed_workspace.runtime_capability_profile_identity,
            changed_runtime.runtime_capability_profile_identity,
        )


if __name__ == "__main__":
    unittest.main()
