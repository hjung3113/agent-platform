from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from execution.run_one_task import run_one_task
from execution.workspace_snapshot import snapshot_identity
from kernel.canonical import content_digest
from kernel.protocol_v1 import RequestV1, TaskV1, RESULT_SNAPSHOT_EVIDENCE_CLASS
from kernel.replay import replay

FIXTURE_BINARY = (
    Path(__file__).resolve().parent.parent
    / "execution"
    / "fixtures"
    / "fake_opencode"
    / "fake_opencode.py"
)
DIRECTIVE_NAME = "fake-opencode-directive.txt"
REQUEST = RequestV1(
    objective="Prove M6 evidence hardening through the real driver",
    scope=("docs/plans/active/m6-verification-evidence-hardening.md",),
    acceptance_criteria=("The real M6 chain is publishable",),
)
TASK = TaskV1(
    task_id="task-m6-integration",
    objective="Run the real Host and M6 verifier",
    acceptance_criteria=(
        "The Host Result binds to the admitted runtime profile",
        "The Verifier emits pinned evidence classes",
        "A failed criterion has an embedded open Finding",
    ),
)
DIFFERENT_EXPECTED_DIGEST = content_digest(
    {"fixture": "m6-integration", "expected_output": "different"}
)


class M6IntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        state = tempfile.TemporaryDirectory()
        self.addCleanup(state.cleanup)
        self.state = state.name
        workspace = tempfile.TemporaryDirectory()
        self.addCleanup(workspace.cleanup)
        self.workspace_root = Path(workspace.name) / "repo"
        self._init_repo(self.workspace_root)
        (self.workspace_root / "tracked.txt").write_text(
            "tracked\n", encoding="utf-8"
        )
        self._git(self.workspace_root, "add", "tracked.txt")
        self._git(self.workspace_root, "commit", "-m", "initial M6 integration fixture")
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

    def _init_repo(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        self._git(path, "init")
        self._git(path, "config", "user.email", "m6-integration@example.invalid")
        self._git(path, "config", "user.name", "M6 Integration Tests")

    def run_chain(self, expected_output_digest: str):
        return run_one_task(
            self.state,
            REQUEST,
            TASK,
            self.workspace_root,
            str(FIXTURE_BINARY),
            implementer_identity="implementer-m6",
            verifier_identity="verifier-m6",
            expected_output_digest=expected_output_digest,
        )

    def test_real_pass_path_publishes_and_replays_hardened_evidence(self) -> None:
        chain = self.run_chain(snapshot_identity(self.workspace_root, ()).digest)

        self.assertEqual(chain.verification_value.verdict, "PASS")
        self.assertIsNotNone(chain.receipt)
        self.assertEqual(
            chain.result_value.observation.runtime_identity,
            chain.attempt_value.runtime_capability_profile_identity,
        )
        self.assertEqual(
            chain.verification_value.verifier_runtime_capability_profile_identity,
            chain.attempt_value.runtime_capability_profile_identity,
        )
        self.assertEqual(chain.verification_value.findings, ())
        for entry in chain.verification_value.coverage:
            self.assertEqual(entry.status, "SATISFIED")
            self.assertEqual(entry.evidence_class, RESULT_SNAPSHOT_EVIDENCE_CLASS)
            self.assertEqual(
                entry.evidence_digest, chain.result_value.output_snapshot_digest
            )

        state = replay(self.state, chain.run_id)
        self.assertEqual(state.request, chain.request_value)
        self.assertEqual(state.workflow_revision, chain.workflow_value)
        self.assertEqual(state.attempt_packet, chain.attempt_value)
        self.assertEqual(state.result, chain.result_value)
        self.assertEqual(state.verification, chain.verification_value)
        self.assertEqual(state.receipt, chain.receipt_value)
        self.assertTrue(state.terminal)
        self.assertEqual(state.last_sequence, 6)

    def test_real_fail_path_publishes_findings_and_stays_open(self) -> None:
        chain = self.run_chain(DIFFERENT_EXPECTED_DIGEST)

        self.assertEqual(chain.verification_value.verdict, "FAIL")
        self.assertIsNone(chain.receipt)
        self.assertIsNone(chain.receipt_value)
        self.assertEqual(
            len(chain.verification_value.findings), len(chain.verification_value.coverage)
        )
        self.assertEqual(
            tuple(finding.criterion for finding in chain.verification_value.findings),
            tuple(entry.criterion for entry in chain.verification_value.coverage),
        )
        for entry, finding in zip(
            chain.verification_value.coverage, chain.verification_value.findings
        ):
            self.assertEqual(entry.status, "UNSATISFIED")
            self.assertIsNone(entry.evidence_digest)
            self.assertEqual(entry.evidence_class, RESULT_SNAPSHOT_EVIDENCE_CLASS)
            self.assertEqual(finding.state, "OPEN")
            self.assertIsNone(finding.predecessor)

        state = replay(self.state, chain.run_id)
        self.assertFalse(state.terminal)
        self.assertEqual(state.last_sequence, 5)
        self.assertEqual(state.result, chain.result_value)
        self.assertEqual(state.verification, chain.verification_value)
        self.assertIsNone(state.receipt)


if __name__ == "__main__":
    unittest.main()
