from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from kernel.lineage_store import open_run
from kernel.protocol import ParsedCandidate, RecordRef, read_candidate
from kernel.publish import Published, publish
from kernel.replay import RunState, replay

OTHER_DIGEST = "sha256:agent-platform-json-v1:" + "f" * 64


def dispatch_request(
    objective: str = "Replay the committed lineage",
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
                "acceptance_criteria": ["All replay tests pass"],
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
                    "objective": "Fold the committed records",
                    "acceptance_criteria": ["Replay is deterministic"],
                },
            },
        }
    )
    assert result.ok, result.reason
    return result.value


class ReplayTests(unittest.TestCase):
    def setUp(self) -> None:
        state = tempfile.TemporaryDirectory()
        self.addCleanup(state.cleanup)
        self.state = state.name

    def publish_two_record_run(self) -> tuple[Published, Published]:
        genesis = publish(self.state, None, dispatch_request(), None, "key-1")
        self.assertIsInstance(genesis, Published)
        child = publish(
            self.state,
            genesis.run_id,
            dispatch_workflow(genesis.record_ref),
            genesis.record_ref,
            "key-2",
        )
        self.assertIsInstance(child, Published)
        return genesis, child

    def test_replayed_run_state_is_stable_across_calls(self) -> None:
        _, child = self.publish_two_record_run()
        run_id = child.run_id

        first = replay(self.state, run_id)
        second = replay(self.state, run_id)
        self.assertEqual(first, second)

    def test_replay_matches_published_typed_values(self) -> None:
        request = dispatch_request()
        genesis = publish(self.state, None, request, None, "key-1")
        self.assertIsInstance(genesis, Published)
        workflow = dispatch_workflow(genesis.record_ref)
        child = publish(
            self.state, genesis.run_id, workflow, genesis.record_ref, "key-2"
        )
        self.assertIsInstance(child, Published)

        state = replay(self.state, genesis.run_id)
        self.assertEqual(state.request, request.value)
        self.assertEqual(state.workflow_revision, workflow.value)
        self.assertEqual(state.last_sequence, 2)
        self.assertEqual(state.last_record_id, child.record_ref)

    def test_head_projection_loss_or_corruption_does_not_change_replay(
        self,
    ) -> None:
        _, child = self.publish_two_record_run()
        run_id = child.run_id
        before = replay(self.state, run_id)
        head_path = Path(self.state) / "runs" / run_id / "_head.json"
        self.assertTrue(head_path.is_file())

        head_path.unlink()
        self.assertEqual(replay(self.state, run_id), before)

        head_path.write_text("{corrupt not json", encoding="utf-8")
        self.assertEqual(replay(self.state, run_id), before)

    def test_missing_run_dir_returns_empty_state_without_creating_it(self) -> None:
        expected = RunState(
            request=None, workflow_revision=None, last_sequence=0, last_record_id=None
        )
        self.assertEqual(replay(self.state, "never-published"), expected)
        self.assertFalse((Path(self.state) / "runs" / "never-published").exists())

    def test_run_dir_without_records_returns_empty_state(self) -> None:
        open_run(self.state, "empty-run")
        expected = RunState(
            request=None, workflow_revision=None, last_sequence=0, last_record_id=None
        )
        self.assertEqual(replay(self.state, "empty-run"), expected)

    def test_forged_envelope_metadata_fails_closed(self) -> None:
        genesis, child = self.publish_two_record_run()
        record_path = (
            Path(self.state) / "runs" / genesis.run_id / "0000000002.json"
        )
        original = record_path.read_bytes()

        forgeries = [
            ("content_digest", OTHER_DIGEST),
            ("record_id", f"{genesis.run_id}:0000000009"),
            ("run_id", "0000000000000000000000000000000f"),
            ("sequence", 99),
        ]
        for field, forged_value in forgeries:
            with self.subTest(field=field):
                envelope = json.loads(original.decode("utf-8"))
                envelope[field] = forged_value
                record_path.write_text(
                    json.dumps(envelope), encoding="utf-8"
                )
                with self.assertRaises(ValueError):
                    replay(self.state, genesis.run_id)
                record_path.write_bytes(original)

        self.assertEqual(replay(self.state, genesis.run_id).last_record_id, child.record_ref)

    def test_sequence_gap_fails_closed(self) -> None:
        genesis = publish(self.state, None, dispatch_request(), None, "key-1")
        self.assertIsInstance(genesis, Published)
        child = publish(
            self.state,
            genesis.run_id,
            dispatch_workflow(genesis.record_ref),
            genesis.record_ref,
            "key-2",
        )
        self.assertIsInstance(child, Published)
        third = publish(
            self.state,
            genesis.run_id,
            dispatch_workflow(genesis.record_ref, task_id="task-3"),
            child.record_ref,
            "key-3",
        )
        self.assertIsInstance(third, Published)

        run_dir = Path(self.state) / "runs" / genesis.run_id
        for missing in ("0000000002.json", "0000000001.json"):
            with self.subTest(missing=missing):
                backup = (run_dir / missing).read_bytes()
                (run_dir / missing).unlink()
                with self.assertRaises(ValueError):
                    replay(self.state, genesis.run_id)
                (run_dir / missing).write_bytes(backup)

        self.assertEqual(replay(self.state, genesis.run_id).last_sequence, 3)


if __name__ == "__main__":
    unittest.main()
