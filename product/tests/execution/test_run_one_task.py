from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from execution import run_one_task
from kernel.protocol import RecordRef
from kernel.protocol_v1 import TaskV1

IDENTITY = "sha256:agent-platform-json-v1:" + "a" * 64


class VerifierSubprocessTests(unittest.TestCase):
    def invoke_verifier(self) -> None:
        run_one_task._run_verifier_subprocess(
            result_ref=RecordRef("result", "rec-result", IDENTITY),
            result_output_snapshot_digest=IDENTITY,
            task=TaskV1(
                task_id="task-verifier-error",
                objective="Exercise verifier diagnostics",
                acceptance_criteria=("The child is invoked",),
                depends_on=(),
            ),
            verifier_identity="verifier-test",
            expected_output_digest=IDENTITY,
            opencode_binary_path="/tmp/fake-opencode",
            config_paths=(),
        )

    def test_child_environment_and_failure_diagnostics_are_explicit(self) -> None:
        observed: dict[str, object] = {}
        error_command = ["explicit-python", "-m", "verifier"]

        def fail(command: list[str], **kwargs: object) -> None:
            observed["command"] = command
            observed.update(kwargs)
            raise subprocess.CalledProcessError(
                23,
                error_command,
                output="child stdout",
                stderr="child stderr",
            )

        with patch.object(run_one_task.subprocess, "run", side_effect=fail):
            with self.assertRaises(run_one_task.VerifierSubprocessError) as raised:
                self.invoke_verifier()

        expected_src_root = str(Path(run_one_task.__file__).resolve().parents[1])
        child_environment = observed["env"]
        assert isinstance(child_environment, dict)
        self.assertTrue(
            child_environment["PYTHONPATH"].split(os.pathsep)[0]
            == expected_src_root
        )
        self.assertEqual(
            observed["command"],
            [sys.executable, "-m", "verification.stub_verifier_cli"],
        )
        message = str(raised.exception)
        self.assertIn(repr(error_command), message)
        self.assertIn("child stdout", message)
        self.assertIn("child stderr", message)


if __name__ == "__main__":
    unittest.main()
