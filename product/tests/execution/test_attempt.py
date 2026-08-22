from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import Any

from kernel.protocol import ParsedCandidate, read_candidate
from kernel.protocol_v1 import (
    PROTOCOL_VERSION,
    SCHEMA_VERSION,
    RequestV1,
    TaskV1,
    WorkflowRevisionV1,
)
from kernel.publish import Published, Rejected, publish
from execution import attempt as attempt_module
from execution.attempt import build_attempt_packet


FIXTURE_BINARY = (
    Path(__file__).resolve().parent / "fixtures" / "fake_opencode" / "fake_opencode.py"
)

TASK_ID = "task-attempt-real-identities"
TASK = TaskV1(
    task_id=TASK_ID,
    objective="Prove real attempt-packet identities bind to published records",
    acceptance_criteria=("The Attempt Packet binds to the published Workflow Revision",),
)


def _as_candidate(contract_kind: str, typed: Any) -> ParsedCandidate:
    read = read_candidate(
        {
            "contract_kind": contract_kind,
            "protocol_version": PROTOCOL_VERSION,
            "schema_version": SCHEMA_VERSION,
            "payload": typed.to_canonical_value(),
        }
    )
    assert read.ok, read.reason
    return read.value


def _require_published(result: Published | Rejected) -> Published:
    if isinstance(result, Rejected):
        raise RuntimeError(f"unexpected publish rejection: {result.code}")
    return result


class AttemptPacketRealIdentityTest(unittest.TestCase):
    def setUp(self) -> None:
        self._state_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self._state_directory.cleanup)
        self.state = self._state_directory.name

        self._workspace_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self._workspace_directory.cleanup)
        self.root = Path(self._workspace_directory.name) / "repo"
        self._init_repo(self.root)
        (self.root / "tracked.txt").write_text("tracked\n", encoding="utf-8")
        self._git(self.root, "add", "tracked.txt")
        self._git(self.root, "commit", "-m", "initial attempt identity fixture")

        request_published = _require_published(
            publish(
                self.state,
                None,
                _as_candidate(
                    "request",
                    RequestV1(
                        objective="Prove attempt-packet real identity binding",
                        scope=("product/tests/execution/test_attempt.py",),
                        acceptance_criteria=(
                            "The packet identities derive from real workspace/runtime",
                        ),
                    ),
                ),
                None,
                "attempt-test-request",
            )
        )
        workflow_value = WorkflowRevisionV1(
            request=request_published.record_ref,
            task=TASK,
        )
        workflow_published = _require_published(
            publish(
                self.state,
                request_published.run_id,
                _as_candidate("workflow_revision", workflow_value),
                request_published.record_ref,
                "attempt-test-workflow",
            )
        )
        self.run_id = request_published.run_id
        self.workflow_revision_ref = workflow_published.record_ref

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
            workflow_revision_ref=self.workflow_revision_ref,
            task_id=TASK_ID,
            implementer_identity="impl-1",
            state=self.state,
            run_id=self.run_id,
            task=TASK,
            workspace_root=self.root,
            opencode_binary_path=str(opencode_binary_path),
        )

    def _drift_binary(self) -> Path:
        other = Path(self._workspace_directory.name) / "fake_opencode_drift.py"
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

    def test_binding_mismatch_rejects(self) -> None:
        mutated_task = TaskV1(
            task_id=TASK_ID,
            objective="mutated objective not published in the Workflow Revision",
            acceptance_criteria=TASK.acceptance_criteria,
        )
        with self.assertRaises(attempt_module.TaskBindingMismatchError):
            build_attempt_packet(
                workflow_revision_ref=self.workflow_revision_ref,
                task_id=TASK_ID,
                implementer_identity="impl-1",
                state=self.state,
                run_id=self.run_id,
                task=mutated_task,
                workspace_root=self.root,
                opencode_binary_path=str(FIXTURE_BINARY),
            )


if __name__ == "__main__":
    unittest.main()
