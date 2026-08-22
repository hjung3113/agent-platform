from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from kernel.canonical import content_digest
from kernel.protocol_v1 import RequestV1, TaskV1
from execution import run_one_task as run_one_task_module
from execution.run_one_task import run_one_task
from execution.workspace_snapshot import snapshot_identity


FIXTURE_BINARY = (
    Path(__file__).resolve().parent / "fixtures" / "fake_opencode" / "fake_opencode.py"
)
DIRECTIVE_NAME = "fake-opencode-directive.txt"
REQUEST = RequestV1(
    objective="Prove context evidence lands outside the workspace",
    scope=("docs/plans/active/m4-deterministic-context-compiler.md",),
    acceptance_criteria=("An evidence file is written per Attempt",),
)
TASK = TaskV1(
    task_id="task-m4-evidence",
    objective="Write the compiled Context Pack evidence file",
    acceptance_criteria=("Evidence file at {state}/context-evidence/",),
)


class ContextEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._state_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self._state_directory.cleanup)
        self.state = self._state_directory.name
        self._workspace_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self._workspace_directory.cleanup)
        self.workspace_root = Path(self._workspace_directory.name) / "repo"
        self.workspace_root.mkdir(parents=True, exist_ok=True)
        self._git(self.workspace_root, "init")
        self._git(self.workspace_root, "config", "user.email", "m4-tests@example.invalid")
        self._git(self.workspace_root, "config", "user.name", "M4 Evidence Tests")
        (self.workspace_root / "tracked.txt").write_text(
            "tracked\n", encoding="utf-8"
        )
        self._git(self.workspace_root, "add", "tracked.txt")
        self._git(self.workspace_root, "commit", "-m", "initial M4 evidence fixture")
        (self.workspace_root / DIRECTIVE_NAME).write_text(
            "noop\n", encoding="utf-8"
        )

    @staticmethod
    def _git(cwd: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *arguments],
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
        )

    def test_run_one_task_writes_evidence_outside_workspace(self) -> None:
        tracked_before = (self.workspace_root / "tracked.txt").read_text(
            encoding="utf-8"
        )
        snapshot_before = snapshot_identity(self.workspace_root, ())

        chain = run_one_task(
            self.state,
            REQUEST,
            TASK,
            self.workspace_root,
            str(FIXTURE_BINARY),
            implementer_identity="implementer-1",
            verifier_identity="verifier-1",
            expected_output_digest=snapshot_before.digest,
        )

        evidence_path = (
            Path(self.state)
            / "context-evidence"
            / f"{chain.attempt.record_ref.record_id}.json"
        )
        self.assertTrue(evidence_path.is_file())
        # The evidence directory is a sibling of runs/, not inside it.
        self.assertTrue((Path(self.state) / "runs" / chain.run_id).is_dir())
        self.assertFalse(
            evidence_path.is_relative_to(Path(self.state) / "runs")
        )
        payload = json.loads(evidence_path.read_text(encoding="utf-8"))
        self.assertEqual(
            content_digest(payload), chain.attempt_value.context_digest
        )

        # The evidence write did not touch the workspace.
        self.assertEqual(
            (self.workspace_root / "tracked.txt").read_text(encoding="utf-8"),
            tracked_before,
        )
        self.assertEqual(
            snapshot_identity(self.workspace_root, ()).digest,
            snapshot_before.digest,
        )

    def test_evidence_write_failure_does_not_abort_an_admitted_run(self) -> None:
        # PR #47 review round 2 MEDIUM 3: run_one_task.py wraps the evidence
        # write in try/except OSError specifically because evidence is
        # documented non-authoritative record-keeping (context_evidence.py's
        # own module docstring) — a storage failure must never abort an
        # already-admitted, otherwise-successful run. Pin that behavior
        # directly rather than relying on it never being exercised.
        snapshot_before = snapshot_identity(self.workspace_root, ())

        with mock.patch.object(
            run_one_task_module,
            "write_context_evidence",
            side_effect=OSError("simulated evidence storage failure"),
        ):
            chain = run_one_task(
                self.state,
                REQUEST,
                TASK,
                self.workspace_root,
                str(FIXTURE_BINARY),
                implementer_identity="implementer-1",
                verifier_identity="verifier-1",
                expected_output_digest=snapshot_before.digest,
            )

        # The run completed to a Receipt despite the evidence write failing.
        self.assertEqual(chain.verification_value.verdict, "PASS")
        self.assertIsNotNone(chain.receipt)
        # And, since the write never happened, no evidence file exists.
        evidence_path = (
            Path(self.state)
            / "context-evidence"
            / f"{chain.attempt.record_ref.record_id}.json"
        )
        self.assertFalse(evidence_path.exists())


if __name__ == "__main__":
    unittest.main()
