from __future__ import annotations

from contextlib import ExitStack
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from execution import run_one_task as driver_module
from execution.run_one_task import run_workflow
from execution.workspace_snapshot import snapshot_identity
from kernel import publish as publish_module
from kernel.canonical import content_digest
from kernel.protocol import ContractKind, read_candidate
from kernel.protocol_v1 import RequestV1, TaskV1
from kernel.replay import replay


FIXTURE_BINARY = (
    Path(__file__).resolve().parent / "fixtures" / "fake_opencode" / "fake_opencode.py"
)

REQUEST = RequestV1(
    objective="Run a branching M7 workflow",
    scope=("docs/plans/active/m7-orchestration-expansion.md",),
    acceptance_criteria=("Each dependency is satisfied before its task runs",),
)
TASKS = (
    TaskV1(
        task_id="A",
        objective="Execute A",
        acceptance_criteria=("A passes",),
        depends_on=(),
    ),
    TaskV1(
        task_id="B",
        objective="Execute B",
        acceptance_criteria=("B passes",),
        depends_on=("A",),
    ),
    TaskV1(
        task_id="C",
        objective="Execute C",
        acceptance_criteria=("C passes",),
        depends_on=("A",),
    ),
    TaskV1(
        task_id="D",
        objective="Execute D",
        acceptance_criteria=("D passes",),
        depends_on=("B", "C"),
    ),
)
BLOCKED_TASKS = (*TASKS, TaskV1("E", "Execute E", ("E passes",), ()))
LEGACY_TASKS = (TaskV1("legacy", "Execute legacy", ("Legacy passes",), ()),)
NON_TOPOLOGICAL_TASKS = (TASKS[1], TASKS[0], TASKS[2], TASKS[3])


class RunWorkflowDagTests(unittest.TestCase):
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
        self._git(self.workspace_root, "commit", "-m", "initial DAG workflow fixture")
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
        self._git(path, "config", "user.email", "m7-dag@example.invalid")
        self._git(path, "config", "user.name", "M7 DAG Tests")

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
            implementer_identity="implementer-m7-dag",
            verifier_identity="verifier-m7-dag",
            expected_output_digests=(
                (self.expected_output_digest,) * len(tasks)
                if expected_output_digests is None
                else expected_output_digests
            ),
        )

    def test_diamond_runs_in_dependency_respecting_order(self) -> None:
        result = self.run_driver()

        self.assertTrue(result.workflow_complete)
        self.assertEqual(
            tuple(item.attempt_value.task_id for item in result.task_results),
            ("A", "B", "C", "D"),
        )
        self.assertTrue(all(item.receipt is not None for item in result.task_results))

    def test_driver_uses_task_identity_when_declaration_order_is_not_topological(self) -> None:
        result = self.run_driver(tasks=NON_TOPOLOGICAL_TASKS)

        self.assertTrue(result.workflow_complete)
        self.assertEqual(
            tuple(item.attempt_value.task_id for item in result.task_results),
            ("A", "B", "C", "D"),
        )

    def test_failed_root_stops_all_dependent_tasks_before_attempt_publication(self) -> None:
        wrong_digest = content_digest({"wrong": "root"})

        result = self.run_driver(
            expected_output_digests=(wrong_digest,) + (self.expected_output_digest,) * 3
        )

        self.assertTrue(result.workflow_blocked)
        self.assertEqual(result.blocked_task_id, "A")
        self.assertEqual(len(result.task_results), 1)
        self.assertEqual(result.task_results[0].attempt_value.task_id, "A")
        self.assertEqual(
            len([p for p in (Path(self.state) / "runs").iterdir() if p.is_dir()]), 1
        )

    def test_crash_resume_reuses_ready_branch_and_does_not_start_join_early(self) -> None:
        original_execute = driver_module.host.execute
        call_count = 0

        def crash_on_c(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 3:
                raise RuntimeError("crash after C attempt publication")
            return original_execute(*args, **kwargs)

        with patch.object(driver_module.host, "execute", side_effect=crash_on_c):
            with self.assertRaisesRegex(RuntimeError, "crash after C"):
                self.run_driver()

        before = {
            state.attempt_packet.task_id: run_dir.name
            for run_dir in (Path(self.state) / "runs").iterdir()
            if run_dir.is_dir()
            for state in (replay(self.state, run_dir.name),)
            if state.attempt_packet is not None
        }
        self.assertEqual(set(before), {"A", "B", "C"})

        resumed = self.run_driver()

        self.assertTrue(resumed.workflow_complete)
        self.assertEqual(
            {item.attempt_value.task_id for item in resumed.task_results},
            {"A", "B", "C", "D"},
        )
        self.assertEqual(
            {item.attempt_value.task_id: item.run_id for item in resumed.task_results}["C"],
            before["C"],
        )
        self.assertEqual(
            len([p for p in (Path(self.state) / "runs").iterdir() if p.is_dir()]), 4
        )

    def test_completed_dag_reinvocation_returns_existing_results_without_new_runs(self) -> None:
        first = self.run_driver()
        second = self.run_driver()

        self.assertTrue(second.workflow_complete)
        self.assertEqual(
            {item.attempt_value.task_id: item.run_id for item in first.task_results},
            {item.attempt_value.task_id: item.run_id for item in second.task_results},
        )
        self.assertEqual(
            len([p for p in (Path(self.state) / "runs").iterdir() if p.is_dir()]), 4
        )
        self.assertEqual(
            {
                item.attempt_value.task_id: replay(
                    self.state, item.run_id
                ).last_sequence
                for item in second.task_results
            },
            {"A": 6, "B": 6, "C": 6, "D": 6},
        )

    def test_blocked_reinvocation_returns_committed_chain_but_not_untouched_independent_task(
        self,
    ) -> None:
        wrong_digest = content_digest({"wrong": "root"})
        first = self.run_driver(
            tasks=BLOCKED_TASKS,
            expected_output_digests=(wrong_digest,)
            + (self.expected_output_digest,) * (len(BLOCKED_TASKS) - 1),
        )
        second = self.run_driver(
            tasks=BLOCKED_TASKS,
            expected_output_digests=(wrong_digest,)
            + (self.expected_output_digest,) * (len(BLOCKED_TASKS) - 1),
        )

        self.assertTrue(first.workflow_blocked)
        self.assertTrue(second.workflow_blocked)
        self.assertEqual(
            tuple(item.attempt_value.task_id for item in second.task_results), ("A",)
        )
        self.assertEqual(
            len([p for p in (Path(self.state) / "runs").iterdir() if p.is_dir()]), 1
        )

    def test_v2_workflow_idempotency_keys_are_orphaned_and_v3_reinvocation_starts_fresh_run(
        self,
    ) -> None:
        original_as_candidate = driver_module._as_candidate
        original_schema_version_for_kind = publish_module.schema_version_for_kind

        def legacy_sequence_digest(tasks: tuple[TaskV1, ...]) -> str:
            return content_digest(
                {
                    "tasks": [
                        {
                            "task_id": task.task_id,
                            "objective": task.objective,
                            "acceptance_criteria": list(task.acceptance_criteria),
                        }
                        for task in tasks
                    ]
                }
            )

        def legacy_as_candidate(contract_kind: str, typed: object):
            if contract_kind != ContractKind.WORKFLOW_REVISION.value:
                return original_as_candidate(contract_kind, typed)
            payload = {
                "request": typed.request.to_canonical_value(),
                "tasks": [
                    {
                        "task_id": task.task_id,
                        "objective": task.objective,
                        "acceptance_criteria": list(task.acceptance_criteria),
                    }
                    for task in typed.tasks
                ],
            }
            parsed = read_candidate(
                {
                    "contract_kind": ContractKind.WORKFLOW_REVISION.value,
                    "protocol_version": 1,
                    "schema_version": 2,
                    "payload": payload,
                }
            )
            self.assertTrue(parsed.ok, parsed.reason)
            return parsed.value

        def legacy_schema_version_for_kind(kind: ContractKind) -> int:
            if kind is ContractKind.WORKFLOW_REVISION:
                return 2
            return original_schema_version_for_kind(kind)

        with ExitStack() as stack:
            stack.enter_context(
                patch.object(
                    driver_module,
                    "_as_candidate",
                    side_effect=legacy_as_candidate,
                )
            )
            stack.enter_context(
                patch.object(
                    driver_module,
                    "workflow_task_sequence_digest",
                    side_effect=legacy_sequence_digest,
                )
            )
            stack.enter_context(
                patch.object(
                    publish_module,
                    "schema_version_for_kind",
                    side_effect=legacy_schema_version_for_kind,
                )
            )
            historical = self.run_driver(tasks=LEGACY_TASKS)

        self.assertTrue(historical.workflow_complete)
        fresh = self.run_driver(tasks=LEGACY_TASKS)

        self.assertTrue(fresh.workflow_complete)
        self.assertNotEqual(
            historical.task_results[0].run_id, fresh.task_results[0].run_id
        )
        self.assertEqual(
            len([p for p in (Path(self.state) / "runs").iterdir() if p.is_dir()]), 2
        )


if __name__ == "__main__":
    unittest.main()
