from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from execution import run_one_task as driver_module
from execution.run_one_task import (
    run_workflow,
    workflow_record_idempotency_key,
    workflow_task_sequence_digest,
)
from execution.workspace_snapshot import snapshot_identity
from kernel.canonical import content_digest
from kernel.protocol_v1 import (
    RESULT_SNAPSHOT_EVIDENCE_CLASS,
    CoverageEntryV1,
    FindingV1,
    RequestV1,
    TaskV1,
    VerificationV1,
)
from kernel.replay import replay


FIXTURE_BINARY = (
    Path(__file__).resolve().parent / "fixtures" / "fake_opencode" / "fake_opencode.py"
)

REQUEST = RequestV1(
    objective="Run a linear M7 workflow",
    scope=("docs/plans/active/m7-orchestration-expansion.md",),
    acceptance_criteria=("Each admitted task is executed in order",),
)
TASKS = (
    TaskV1(
        task_id="task-m7-1",
        objective="Execute the first M7 task",
        acceptance_criteria=("The first task passes",),
    ),
    TaskV1(
        task_id="task-m7-2",
        objective="Execute the second M7 task",
        acceptance_criteria=("The second task passes",),
    ),
)
BLOCKED_RUNTIME_PROFILE = content_digest({"fixture": "m7-blocked-verifier"})
BLOCKED_EXECUTION_IDENTITY = content_digest({"fixture": "m7-blocked-execution"})


class RunWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        state = tempfile.TemporaryDirectory()
        self.addCleanup(state.cleanup)
        self.state = state.name

        workspace = tempfile.TemporaryDirectory()
        self.addCleanup(workspace.cleanup)
        self.workspace_root = Path(workspace.name) / "repo"
        self._init_repo(self.workspace_root)
        (self.workspace_root / "tracked.txt").write_text("tracked\n", encoding="utf-8")
        self._git(self.workspace_root, "add", "tracked.txt")
        self._git(
            self.workspace_root,
            "commit",
            "-m",
            "initial M7 workflow fixture",
        )
        (self.workspace_root / "fake-opencode-directive.txt").write_text(
            "noop\n", encoding="utf-8"
        )
        self.expected_output_digest = snapshot_identity(self.workspace_root, ()).digest

    @staticmethod
    def _git(cwd: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *arguments], cwd=cwd, check=True, capture_output=True, text=True
        )

    def _init_repo(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        self._git(path, "init")
        self._git(path, "config", "user.email", "m7-workflow@example.invalid")
        self._git(path, "config", "user.name", "M7 Workflow Tests")

    def run_driver(
        self,
        *,
        tasks: tuple[TaskV1, ...] = TASKS,
        expected_output_digest: str | None = None,
    ):
        return run_workflow(
            tasks,
            self.state,
            REQUEST,
            self.workspace_root,
            str(FIXTURE_BINARY),
            implementer_identity="implementer-m7",
            verifier_identity="verifier-m7",
            expected_output_digest=(
                self.expected_output_digest
                if expected_output_digest is None
                else expected_output_digest
            ),
        )

    def test_two_tasks_run_in_order_to_workflow_complete(self) -> None:
        result = self.run_driver()

        self.assertTrue(result.workflow_complete)
        self.assertIsNone(result.blocked_task)
        self.assertEqual(len(result.task_results), 2)
        self.assertEqual(
            tuple(item.attempt_value.task_id for item in result.task_results),
            ("task-m7-1", "task-m7-2"),
        )
        self.assertTrue(all(item.receipt is not None for item in result.task_results))

    def test_per_task_keys_use_structured_content_digest_composition(self) -> None:
        workflow_digest = workflow_task_sequence_digest(TASKS)
        expected = content_digest(
            {
                "workflow_revision_digest": workflow_digest,
                "task_id": "task-m7-1",
                "record": "request",
            }
        )

        self.assertEqual(
            workflow_record_idempotency_key(TASKS, "task-m7-1", "request"),
            expected,
        )
        self.assertNotEqual(
            workflow_record_idempotency_key(TASKS, "task-m7-1", "request"),
            workflow_record_idempotency_key(TASKS, "task-m7-2", "request"),
        )

    def test_fail_stops_before_publishing_next_task_attempt(self) -> None:
        result = self.run_driver(expected_output_digest=content_digest({"wrong": True}))

        self.assertTrue(result.workflow_blocked)
        self.assertEqual(result.blocked_task_id, "task-m7-1")
        self.assertEqual(result.reason, "FAIL")
        self.assertEqual(len(result.task_results), 1)
        self.assertIsNone(result.task_results[0].receipt)
        runs = [entry for entry in (Path(self.state) / "runs").iterdir() if entry.is_dir()]
        self.assertEqual(len(runs), 1)
        state = replay(self.state, runs[0].name)
        self.assertIsNotNone(state.attempt_packet)
        self.assertIsNotNone(state.verification)

    def test_blocked_stops_before_publishing_next_task_attempt(self) -> None:
        def blocked_verifier(**kwargs):
            task = kwargs["task"]
            result_ref = kwargs["result_ref"]
            criterion = task.acceptance_criteria[0]
            finding = FindingV1(
                criterion=criterion,
                fingerprint=content_digest(
                    {
                        "criterion": criterion,
                        "description": "The verifier is blocked",
                    }
                ),
                description="The verifier is blocked",
                state="OPEN",
                predecessor=None,
            )
            return VerificationV1(
                result=result_ref,
                verifier_identity="verifier-m7",
                verifier_runtime_capability_profile_identity=BLOCKED_RUNTIME_PROFILE,
                verifier_execution_identity=BLOCKED_EXECUTION_IDENTITY,
                coverage=(
                    CoverageEntryV1(
                        criterion=criterion,
                        status="BLOCKED",
                        evidence_digest=None,
                        evidence_class=RESULT_SNAPSHOT_EVIDENCE_CLASS,
                    ),
                ),
                verdict="BLOCKED",
                findings=(finding,),
            )

        with patch.object(
            driver_module, "_run_verifier_subprocess", side_effect=blocked_verifier
        ):
            result = self.run_driver()

        self.assertTrue(result.workflow_blocked)
        self.assertEqual(result.blocked_task_id, "task-m7-1")
        self.assertEqual(result.reason, "BLOCKED")
        self.assertEqual(len(result.task_results), 1)
        self.assertEqual(len([p for p in (Path(self.state) / "runs").iterdir() if p.is_dir()]), 1)

    def test_completed_workflow_reinvocation_is_idempotent(self) -> None:
        first = self.run_driver()
        second = self.run_driver()

        self.assertTrue(second.workflow_complete)
        self.assertEqual(
            tuple(item.run_id for item in first.task_results),
            tuple(item.run_id for item in second.task_results),
        )
        self.assertEqual(
            len([p for p in (Path(self.state) / "runs").iterdir() if p.is_dir()]), 2
        )
        self.assertEqual(
            tuple(replay(self.state, item.run_id).last_sequence for item in second.task_results),
            (6, 6),
        )

    def test_crashed_first_task_resumes_from_published_attempt(self) -> None:
        with patch.object(
            driver_module.host,
            "execute",
            side_effect=RuntimeError("crash after attempt publication"),
        ):
            with self.assertRaisesRegex(RuntimeError, "crash after attempt"):
                self.run_driver()

        runs_after_crash = [
            entry for entry in (Path(self.state) / "runs").iterdir() if entry.is_dir()
        ]
        self.assertEqual(len(runs_after_crash), 1)
        self.assertIsNotNone(replay(self.state, runs_after_crash[0].name).attempt_packet)

        resumed = self.run_driver()

        self.assertTrue(resumed.workflow_complete)
        self.assertEqual(len(resumed.task_results), 2)
        self.assertEqual(
            tuple(replay(self.state, item.run_id).last_sequence for item in resumed.task_results),
            (6, 6),
        )


if __name__ == "__main__":
    unittest.main()
