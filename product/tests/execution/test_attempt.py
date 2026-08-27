from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import Any

from kernel.protocol import ContractKind, ParsedCandidate, read_candidate
from kernel.protocol_v1 import (
    PROTOCOL_VERSION,
    RequestV1,
    schema_version_for_kind,
    TaskV1,
    WorkflowRevisionV1,
)
from kernel.protocol import RecordRef
from kernel.publish import Published, Rejected, publish
from execution import attempt as attempt_module
from execution import context_compiler
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
SECOND_TASK = TaskV1(
    task_id="task-attempt-second",
    objective="Prove a later task can bind to the same revision",
    acceptance_criteria=("The later task is selected by task_id",),
)


def _as_candidate(contract_kind: str, typed: Any) -> ParsedCandidate:
    read = read_candidate(
        {
            "contract_kind": contract_kind,
            "protocol_version": PROTOCOL_VERSION,
            "schema_version": schema_version_for_kind(ContractKind(contract_kind)),
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
            tasks=(TASK, SECOND_TASK),
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

    def test_task_id_argument_disagrees_with_task_rejects(self) -> None:
        with self.assertRaises(attempt_module.TaskBindingMismatchError):
            build_attempt_packet(
                workflow_revision_ref=self.workflow_revision_ref,
                task_id="a-different-task-id",
                implementer_identity="impl-1",
                state=self.state,
                run_id=self.run_id,
                task=TASK,
                workspace_root=self.root,
                opencode_binary_path=str(FIXTURE_BINARY),
            )

    def test_non_empty_contract_refs_rejected_fail_closed(self) -> None:
        ref = RecordRef(
            contract_kind="decision",
            record_id="r1",
            content_digest="sha256:agent-platform-json-v1:" + "a" * 64,
        )
        with self.assertRaises(context_compiler.UnverifiedContractRefError):
            build_attempt_packet(
                workflow_revision_ref=self.workflow_revision_ref,
                task_id=TASK_ID,
                implementer_identity="impl-1",
                state=self.state,
                run_id=self.run_id,
                task=TASK,
                workspace_root=self.root,
                opencode_binary_path=str(FIXTURE_BINARY),
                contract_refs=(ref,),
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

    def test_multi_task_revision_selects_the_bound_task(self) -> None:
        packet = build_attempt_packet(
            workflow_revision_ref=self.workflow_revision_ref,
            task_id=SECOND_TASK.task_id,
            implementer_identity="impl-1",
            state=self.state,
            run_id=self.run_id,
            task=SECOND_TASK,
            workspace_root=self.root,
            opencode_binary_path=str(FIXTURE_BINARY),
        )

        self.assertEqual(packet.task_id, SECOND_TASK.task_id)

    def test_unknown_task_id_in_multi_task_revision_rejects(self) -> None:
        unknown = TaskV1(
            task_id="task-attempt-unknown",
            objective="This task is not admitted",
            acceptance_criteria=("It must not bind",),
        )

        with self.assertRaises(attempt_module.TaskBindingMismatchError):
            build_attempt_packet(
                workflow_revision_ref=self.workflow_revision_ref,
                task_id=unknown.task_id,
                implementer_identity="impl-1",
                state=self.state,
                run_id=self.run_id,
                task=unknown,
                workspace_root=self.root,
                opencode_binary_path=str(FIXTURE_BINARY),
            )


if __name__ == "__main__":
    unittest.main()
