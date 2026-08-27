from __future__ import annotations

from dataclasses import replace
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from execution import run_one_task as driver_module
from execution.run_one_task import (
    run_one_task,
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
from kernel.replay import RunState, replay
from kernel.workflow_eligibility import (
    WorkflowEligibilityRejectionCode,
    WorkflowEligibilityRejected,
)


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
        request: RequestV1 = REQUEST,
        expected_output_digests: tuple[str, ...] | None = None,
    ):
        return run_workflow(
            tasks,
            self.state,
            request,
            self.workspace_root,
            str(FIXTURE_BINARY),
            implementer_identity="implementer-m7",
            verifier_identity="verifier-m7",
            expected_output_digests=(
                (self.expected_output_digest,) * len(tasks)
                if expected_output_digests is None
                else expected_output_digests
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
                "request_identity": content_digest(REQUEST.to_canonical_value()),
                "workflow_revision_digest": workflow_digest,
                "task_id": "task-m7-1",
                "record": "request",
            }
        )

        self.assertEqual(
            workflow_record_idempotency_key(REQUEST, TASKS, "task-m7-1", "request"),
            expected,
        )
        self.assertNotEqual(
            workflow_record_idempotency_key(REQUEST, TASKS, "task-m7-1", "request"),
            workflow_record_idempotency_key(REQUEST, TASKS, "task-m7-2", "request"),
        )

    def test_fail_stops_before_publishing_next_task_attempt(self) -> None:
        wrong_digest = content_digest({"wrong": True})
        result = self.run_driver(expected_output_digests=(wrong_digest, wrong_digest))

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

    def test_two_mutating_tasks_use_distinct_expected_output_digests(self) -> None:
        directive = self.workspace_root / "fake-opencode-directive.txt"
        directive.unlink()
        marker = self.workspace_root / "workflow-mutation.txt"

        marker.write_text("task-m7-1\n", encoding="utf-8")
        first_digest = snapshot_identity(self.workspace_root, ()).digest
        marker.write_text("task-m7-1\ntask-m7-2\n", encoding="utf-8")
        second_digest = snapshot_identity(self.workspace_root, ()).digest
        marker.unlink()

        original_execute = driver_module.host.execute

        def execute_and_mark(*args, **kwargs):
            result = original_execute(*args, **kwargs)
            task = args[4]
            marker.write_text(
                marker.read_text(encoding="utf-8") + f"{task.task_id}\n"
                if marker.exists()
                else f"{task.task_id}\n",
                encoding="utf-8",
            )
            report = self.workspace_root / "fake-opencode-report.json"
            if report.exists():
                report.unlink()
            output_digest = snapshot_identity(self.workspace_root, ()).digest
            return replace(
                result,
                output_snapshot_digest=output_digest,
                observation=replace(
                    result.observation, output_snapshot_digest=output_digest
                ),
            )

        with patch.object(
            driver_module.host, "execute", side_effect=execute_and_mark
        ):
            result = self.run_driver(
                expected_output_digests=(first_digest, second_digest)
            )

        self.assertTrue(result.workflow_complete)
        self.assertEqual(len(result.task_results), 2)
        self.assertNotEqual(first_digest, second_digest)
        self.assertEqual(
            tuple(
                item.result_value.output_snapshot_digest
                for item in result.task_results
            ),
            (first_digest, second_digest),
        )

    def test_order_violation_in_replayed_states_fails_closed(self) -> None:
        completed = self.run_driver()
        task_one_run_id = completed.task_results[0].run_id
        task_two_run_id = completed.task_results[1].run_id
        original_replay = driver_module.replay

        def replay_with_task_one_missing(state: str, run_id: str):
            if run_id == task_one_run_id:
                return RunState(
                    request=None,
                    workflow_revision=None,
                    last_sequence=0,
                    last_record_id=None,
                )
            self.assertEqual(run_id, task_two_run_id)
            return original_replay(state, run_id)

        with patch.object(
            driver_module, "replay", side_effect=replay_with_task_one_missing
        ):
            with self.assertRaises(WorkflowEligibilityRejected) as raised:
                self.run_driver()

        self.assertEqual(
            raised.exception.code,
            WorkflowEligibilityRejectionCode.TASK_ORDER_VIOLATION,
        )

    def test_result_commit_resume_reuses_attempt_after_workspace_mutation(self) -> None:
        with patch.object(
            driver_module,
            "_run_verifier_subprocess",
            side_effect=RuntimeError("crash after result publication"),
        ):
            with self.assertRaisesRegex(RuntimeError, "crash after result"):
                self.run_driver()

        run_directories = [
            entry for entry in (Path(self.state) / "runs").iterdir() if entry.is_dir()
        ]
        self.assertEqual(len(run_directories), 1)
        run_id = run_directories[0].name
        before_resume = replay(self.state, run_id)
        self.assertIsNotNone(before_resume.attempt_packet)
        self.assertIsNotNone(before_resume.result)

        (self.workspace_root / "after-result-crash.txt").write_text(
            "side effect completed before crash\n", encoding="utf-8"
        )
        with patch.object(
            driver_module,
            "build_attempt_packet",
            side_effect=AssertionError("Attempt Packet must be reused"),
        ):
            resumed = run_one_task(
                self.state,
                REQUEST,
                TASKS[0],
                self.workspace_root,
                str(FIXTURE_BINARY),
                implementer_identity="implementer-m7",
                verifier_identity="verifier-m7",
                expected_output_digest=self.expected_output_digest,
                admitted_tasks=TASKS,
            )

        self.assertEqual(resumed.run_id, run_id)
        self.assertIsNotNone(resumed.receipt)
        self.assertEqual(
            resumed.attempt_value.workspace_snapshot_digest,
            before_resume.attempt_packet.workspace_snapshot_digest,
        )

    def test_distinct_requests_with_identical_tasks_get_distinct_runs(self) -> None:
        first = self.run_driver()
        second_request = RequestV1(
            objective="Run a different linear M7 workflow",
            scope=REQUEST.scope,
            acceptance_criteria=REQUEST.acceptance_criteria,
        )

        second = self.run_driver(request=second_request)

        self.assertTrue(first.workflow_complete)
        self.assertTrue(second.workflow_complete)
        self.assertNotEqual(
            tuple(item.run_id for item in first.task_results),
            tuple(item.run_id for item in second.task_results),
        )
        self.assertEqual(
            len([p for p in (Path(self.state) / "runs").iterdir() if p.is_dir()]), 4
        )


if __name__ == "__main__":
    unittest.main()
