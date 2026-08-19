# Code-review invariant checked (grep, not unit-tested): no test in the
# kernel/contract suites writes record content directly into a run directory
# outside publish()/lineage_store.RunHandle primitives; the only direct writes
# targeting a run dir are deliberate _head.json corruption (a derived,
# rebuildable projection) in test_lineage_store.py and test_replay.py.

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from kernel.lineage_store import HeadProjection, open_run
from kernel.protocol import ParsedCandidate, RecordRef, read_candidate
from kernel.publish import Published, publish
from kernel.replay import RunState, replay


def dispatch_request(
    objective: str = "Survive a crash before projection",
) -> ParsedCandidate:
    """Build a validated Request candidate through the real dispatch."""

    result = read_candidate(
        {
            "contract_kind": "request",
            "protocol_version": 1,
            "schema_version": 1,
            "payload": {
                "objective": objective,
                "scope": ["docs/plans/active/m1-kernel-authoritative-publication.md"],
                "acceptance_criteria": ["All fault-injection tests pass"],
            },
        }
    )
    assert result.ok, result.reason
    return result.value


def dispatch_workflow(
    parent: RecordRef, task_id: str = "task-1"
) -> ParsedCandidate:
    """Build a validated Workflow Revision candidate bound to ``parent``."""

    result = read_candidate(
        {
            "contract_kind": "workflow_revision",
            "protocol_version": 1,
            "schema_version": 1,
            "payload": {
                "request": parent.to_canonical_value(),
                "task": {
                    "task_id": task_id,
                    "objective": "Prove commit-before-projection ordering",
                    "acceptance_criteria": ["Replay recovers authority"],
                },
            },
        }
    )
    assert result.ok, result.reason
    return result.value


def simulated_crash() -> None:
    raise RuntimeError("simulated crash")


def sole_run_id(state_dir: str) -> str:
    runs = [
        entry.name
        for entry in (Path(state_dir) / "runs").iterdir()
        if entry.is_dir()
    ]
    assert len(runs) == 1, runs
    return runs[0]


class FaultInjectionTests(unittest.TestCase):
    def setUp(self) -> None:
        state = tempfile.TemporaryDirectory()
        self.addCleanup(state.cleanup)
        self.state = state.name

    def assert_heads_equivalent(self, rebuilt, clean) -> None:
        """Compare rebuild-from-scan against a clean run's written head.

        ``record_id`` embeds the run id, so run-unique fields are compared
        by value rather than by whole-envelope equality.
        """

        self.assertEqual(rebuilt.last_sequence, clean.last_sequence)
        self.assertEqual(rebuilt.last_record_file, clean.last_record_file)
        for key in ("sequence", "candidate", "content_digest", "idempotency_key"):
            self.assertEqual(rebuilt.last_record[key], clean.last_record[key])

    def test_crash_before_first_head_write_keeps_commit_recoverable(self) -> None:
        request = dispatch_request()
        with self.assertRaises(RuntimeError):
            publish(
                self.state,
                None,
                request,
                None,
                "key-1",
                commit_barrier=simulated_crash,
            )

        run_id = sole_run_id(self.state)
        run_dir = Path(self.state) / "runs" / run_id
        self.assertFalse((run_dir / "_head.json").exists())

        state = replay(self.state, run_id)
        self.assertEqual(
            state,
            RunState(
                request=request.value,
                workflow_revision=None,
                last_sequence=1,
                last_record_id=RecordRef(
                    contract_kind="request",
                    record_id=f"{run_id}:0000000001",
                    content_digest=request.envelope.content_digest(),
                ),
            ),
        )

        clean_state = tempfile.TemporaryDirectory()
        self.addCleanup(clean_state.cleanup)
        clean = publish(clean_state.name, None, dispatch_request(), None, "key-1")
        self.assertIsInstance(clean, Published)
        self.assert_heads_equivalent(
            open_run(self.state, run_id).rebuild_head_from_scan(),
            open_run(clean_state.name, clean.run_id).read_head(),
        )

    def test_crash_between_records_leaves_stale_head_recoverable(self) -> None:
        request = dispatch_request()
        genesis = publish(self.state, None, request, None, "key-1")
        self.assertIsInstance(genesis, Published)
        head_before_crash = open_run(self.state, genesis.run_id).read_head()

        workflow = dispatch_workflow(genesis.record_ref)
        with self.assertRaises(RuntimeError):
            publish(
                self.state,
                genesis.run_id,
                workflow,
                genesis.record_ref,
                "key-2",
                commit_barrier=simulated_crash,
            )

        run_dir = Path(self.state) / "runs" / genesis.run_id
        self.assertEqual(
            open_run(self.state, genesis.run_id).read_head(), head_before_crash
        )
        self.assertEqual(head_before_crash.last_sequence, 1)
        self.assertTrue((run_dir / "0000000002.json").is_file())

        state = replay(self.state, genesis.run_id)
        self.assertEqual(state.request, request.value)
        self.assertEqual(state.workflow_revision, workflow.value)
        self.assertEqual(state.last_sequence, 2)
        self.assertEqual(
            state.last_record_id,
            RecordRef(
                contract_kind="workflow_revision",
                record_id=f"{genesis.run_id}:0000000002",
                content_digest=workflow.envelope.content_digest(),
            ),
        )

        # A clean (non-interrupted) publish of record 2 would have written
        # exactly the head over the envelope it appended; the workflow
        # candidate embeds the run-unique parent RecordRef, so the expected
        # projection is constructed from this run's committed record.
        committed = json.loads(
            (run_dir / "0000000002.json").read_bytes().decode("utf-8")
        )
        self.assertEqual(
            open_run(self.state, genesis.run_id).rebuild_head_from_scan(),
            HeadProjection(
                last_sequence=2,
                last_record_file="0000000002.json",
                last_record=committed,
            ),
        )


if __name__ == "__main__":
    unittest.main()
