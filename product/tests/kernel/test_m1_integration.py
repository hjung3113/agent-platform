from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from kernel.canonical import content_digest
from kernel.protocol import ParsedCandidate, RecordRef, read_candidate
from kernel.publish import (
    Published,
    PublishRejectionCode,
    Rejected,
    publish,
)
from kernel.replay import replay

ENVELOPE_KEYS = {
    "run_id",
    "sequence",
    "record_id",
    "content_digest",
    "idempotency_key",
    "candidate",
}


def dispatch_request(
    objective: str = "Prove the M1 end-to-end publication chain",
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
                "acceptance_criteria": ["The full chain works end to end"],
            },
        }
    )
    assert result.ok, result.reason
    return result.value


def dispatch_workflow(parent: RecordRef) -> ParsedCandidate:
    """Build a validated Workflow Revision candidate bound to ``parent``."""

    result = read_candidate(
        {
            "contract_kind": "workflow_revision",
            "protocol_version": 1,
            "schema_version": 3,
            "payload": {
                "request": parent.to_canonical_value(),
                "tasks": [
                    {
                        "task_id": "task-1",
                        "objective": "Wire dispatch through publish end to end",
                        "acceptance_criteria": ["Golden fixtures hold"],
                        "depends_on": [],
                    }
                ],
            },
        }
    )
    assert result.ok, result.reason
    return result.value


def dispatch_attempt(
    workflow_revision_ref: RecordRef, task_id: str = "task-1"
) -> ParsedCandidate:
    """Build a validated Attempt Packet candidate bound to a revision."""

    result = read_candidate(
        {
            "contract_kind": "attempt_packet",
            "protocol_version": 1,
            "schema_version": 1,
            "payload": {
                "workflow_revision": workflow_revision_ref.to_canonical_value(),
                "task_id": task_id,
                "implementer_identity": "implementer-1",
                "context_digest": "fixture-context",
                "workspace_snapshot_digest": "fixture-workspace",
                "runtime_capability_profile_identity": "fixture-runtime",
            },
        }
    )
    assert result.ok, result.reason
    return result.value


class M1IntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        state = tempfile.TemporaryDirectory()
        self.addCleanup(state.cleanup)
        self.state = state.name

    def publish_genesis_then_child(
        self, state_dir: str
    ) -> tuple[Published, Published, ParsedCandidate, ParsedCandidate]:
        request = dispatch_request()
        genesis = publish(state_dir, None, request, None, "key-genesis")
        assert isinstance(genesis, Published)

        workflow = dispatch_workflow(genesis.record_ref)
        child = publish(
            state_dir,
            genesis.run_id,
            workflow,
            genesis.record_ref,
            "key-child",
        )
        assert isinstance(child, Published)
        return genesis, child, request, workflow

    def test_genesis_then_child_publish_through_real_dispatch(self) -> None:
        request = dispatch_request()
        genesis = publish(self.state, None, request, None, "key-genesis")

        self.assertIsInstance(genesis, Published)
        self.assertTrue(genesis.run_id)
        self.assertEqual(genesis.record_ref.contract_kind, "request")
        self.assertEqual(
            genesis.record_ref.content_digest,
            request.envelope.content_digest(),
        )
        self.assertEqual(genesis.record_ref.record_id, f"{genesis.run_id}:0000000001")

        workflow = dispatch_workflow(genesis.record_ref)
        child = publish(
            self.state,
            genesis.run_id,
            workflow,
            genesis.record_ref,
            "key-child",
        )

        self.assertIsInstance(child, Published)
        self.assertEqual(child.run_id, genesis.run_id)
        self.assertEqual(child.record_ref.contract_kind, "workflow_revision")
        self.assertEqual(child.record_ref.record_id, f"{genesis.run_id}:0000000002")
        self.assertEqual(
            child.record_ref.content_digest,
            workflow.envelope.content_digest(),
        )

    def test_replay_reduces_full_run_to_typed_state(self) -> None:
        genesis, child, request, workflow = self.publish_genesis_then_child(
            self.state
        )

        state = replay(self.state, genesis.run_id)
        self.assertEqual(state.request, request.value)
        self.assertEqual(state.workflow_revision, workflow.value)
        self.assertEqual(state.last_sequence, 2)
        self.assertEqual(state.last_record_id, child.record_ref)

    def test_committed_record_envelope_golden_shape(self) -> None:
        genesis, child, _, _ = self.publish_genesis_then_child(self.state)

        for sequence, published in ((1, genesis), (2, child)):
            record_path = (
                Path(self.state) / "runs" / genesis.run_id / f"{sequence:010d}.json"
            )
            self.assertTrue(record_path.is_file())
            envelope = json.loads(record_path.read_bytes().decode("utf-8"))
            self.assertEqual(set(envelope), ENVELOPE_KEYS)
            self.assertEqual(envelope["run_id"], genesis.run_id)
            self.assertEqual(envelope["sequence"], sequence)
            self.assertEqual(envelope["record_id"], published.record_ref.record_id)
            self.assertEqual(
                envelope["content_digest"], published.record_ref.content_digest
            )
            self.assertTrue(read_candidate(envelope["candidate"]).ok)

    def test_content_digest_is_deterministic_across_separate_runs(self) -> None:
        _, _, request, workflow = self.publish_genesis_then_child(self.state)

        with tempfile.TemporaryDirectory() as other:
            other_genesis = publish(other, None, request, None, "key-genesis")
            self.assertIsInstance(other_genesis, Published)
            other_child = publish(
                other,
                other_genesis.run_id,
                dispatch_workflow(other_genesis.record_ref),
                other_genesis.record_ref,
                "key-child",
            )
            self.assertIsInstance(other_child, Published)

            self.assertNotEqual(
                other_genesis.run_id,
                self._first_run_id(),
            )
            self.assertEqual(
                other_genesis.record_ref.content_digest,
                request.envelope.content_digest(),
            )

        request_content = request.envelope.to_content_value()
        self.assertEqual(
            content_digest(request_content),
            request.envelope.content_digest(),
        )
        workflow_content = workflow.envelope.to_content_value()
        self.assertEqual(
            content_digest(workflow_content),
            workflow.envelope.content_digest(),
        )

    def _first_run_id(self) -> str:
        runs_dir = Path(self.state) / "runs"
        return next(entry.name for entry in runs_dir.iterdir())

    def test_stale_predecessor_rejects_through_full_chain(self) -> None:
        genesis, child, _, _ = self.publish_genesis_then_child(self.state)

        stale_predecessor = RecordRef(
            contract_kind="request",
            record_id="rec-from-earlier-state",
            content_digest=genesis.record_ref.content_digest,
        )
        stale = publish(
            self.state,
            genesis.run_id,
            dispatch_attempt(child.record_ref),
            stale_predecessor,
            "key-stale",
        )

        self.assertIsInstance(stale, Rejected)
        self.assertEqual(stale.code, PublishRejectionCode.PREDECESSOR_MISMATCH)

        run_dir = Path(self.state) / "runs" / genesis.run_id
        files = sorted(
            entry.name for entry in run_dir.iterdir()
            if entry.name.endswith(".json") and entry.name != "_head.json"
        )
        self.assertEqual(files, ["0000000001.json", "0000000002.json"])

        state = replay(self.state, genesis.run_id)
        self.assertEqual(state.last_sequence, 2)
        self.assertEqual(state.last_record_id, child.record_ref)


if __name__ == "__main__":
    unittest.main()
