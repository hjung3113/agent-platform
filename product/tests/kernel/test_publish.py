from __future__ import annotations

import json
import re
import tempfile
import threading
import unittest
from pathlib import Path

from kernel.lineage_store import open_run
from kernel.protocol import ParsedCandidate, RecordRef, read_candidate
from kernel.protocol_v1 import read_request_v1, request_v1_content_digest
from kernel.protocol import ContractKind
from kernel.publish import (
    Published,
    PublishRejectionCode,
    Rejected,
    UnknownRunError,
    publish,
    read_committed_contract,
)

OTHER_DIGEST = "sha256:agent-platform-json-v1:" + "f" * 64


def dispatch_request(
    objective: str = "Ship the M1 publish boundary",
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
                "acceptance_criteria": ["All publish tests pass"],
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
            "schema_version": 2,
            "payload": {
                "request": parent.to_canonical_value(),
                "tasks": [
                    {
                        "task_id": task_id,
                        "objective": "Wire the publish boundary",
                        "acceptance_criteria": ["Publish is fenced"],
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


class PublishTests(unittest.TestCase):
    def setUp(self) -> None:
        state = tempfile.TemporaryDirectory()
        self.addCleanup(state.cleanup)
        self.state = state.name

    def run_dir(self, run_id: str) -> Path:
        return Path(self.state) / "runs" / run_id

    def sequence_files(self, run_id: str) -> list[str]:
        return sorted(
            entry.name
            for entry in self.run_dir(run_id).iterdir()
            if re.fullmatch(r"\d{10}\.json", entry.name)
        )

    def test_genesis_request_publish_creates_run(self) -> None:
        candidate = dispatch_request()
        result = publish(self.state, None, candidate, None, "key-genesis")

        self.assertIsInstance(result, Published)
        self.assertTrue(result.run_id)
        self.assertEqual(result.record_ref.contract_kind, "request")
        self.assertEqual(
            result.record_ref.content_digest,
            candidate.envelope.content_digest(),
        )

        record_path = self.run_dir(result.run_id) / "0000000001.json"
        self.assertTrue(record_path.is_file())
        envelope = json.loads(record_path.read_bytes().decode("utf-8"))
        self.assertEqual(envelope["run_id"], result.run_id)
        self.assertEqual(envelope["sequence"], 1)
        self.assertEqual(envelope["record_id"], result.record_ref.record_id)
        self.assertEqual(envelope["content_digest"], result.record_ref.content_digest)
        self.assertEqual(envelope["idempotency_key"], "key-genesis")
        self.assertTrue(read_candidate(envelope["candidate"]).ok)

        head = open_run(self.state, result.run_id).read_head()
        self.assertEqual(head.last_sequence, 1)
        self.assertEqual(head.last_record_file, "0000000001.json")
        self.assertEqual(head.last_record["record_id"], result.record_ref.record_id)

    def test_bare_reader_outcome_publishes_with_dispatch_digest(self) -> None:
        outcome = read_request_v1(
            {
                "objective": "Read a bare reader outcome",
                "scope": [],
                "acceptance_criteria": ["Digest matches real dispatch"],
            }
        )
        result = publish(self.state, None, outcome, None, "key-bare")
        self.assertIsInstance(result, Published)
        self.assertEqual(
            result.record_ref.content_digest,
            request_v1_content_digest(outcome.value),
        )

    def test_workflow_revision_publish_with_correct_predecessor(self) -> None:
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
        self.assertEqual(child.run_id, genesis.run_id)
        self.assertEqual(child.record_ref.contract_kind, "workflow_revision")
        self.assertEqual(child.record_ref.record_id, f"{genesis.run_id}:0000000002")

        self.assertEqual(
            self.sequence_files(genesis.run_id),
            ["0000000001.json", "0000000002.json"],
        )
        head = open_run(self.state, genesis.run_id).read_head()
        self.assertEqual(head.last_sequence, 2)
        self.assertEqual(head.last_record["record_id"], child.record_ref.record_id)

        for sequence in (1, 2):
            envelope = json.loads(
                (
                    self.run_dir(genesis.run_id) / f"{sequence:010d}.json"
                ).read_bytes()
            )
            self.assertTrue(read_candidate(envelope["candidate"]).ok)

    def test_stale_predecessor_rejects(self) -> None:
        genesis = publish(self.state, None, dispatch_request(), None, "key-1")
        child = publish(
            self.state,
            genesis.run_id,
            dispatch_workflow(genesis.record_ref),
            genesis.record_ref,
            "key-2",
        )
        self.assertIsInstance(child, Published)

        stale = publish(
            self.state,
            genesis.run_id,
            dispatch_attempt(child.record_ref),
            genesis.record_ref,
            "key-3",
        )
        self.assertIsInstance(stale, Rejected)
        self.assertEqual(stale.code, PublishRejectionCode.PREDECESSOR_MISMATCH)
        self.assertEqual(
            self.sequence_files(genesis.run_id),
            ["0000000001.json", "0000000002.json"],
        )
        head = open_run(self.state, genesis.run_id).read_head()
        self.assertEqual(head.last_sequence, 2)

    def test_conflicting_predecessor_rejects(self) -> None:
        genesis = publish(self.state, None, dispatch_request(), None, "key-1")
        self.assertIsInstance(genesis, Published)

        conflicting = RecordRef(
            contract_kind="request",
            record_id=genesis.record_ref.record_id,
            content_digest=OTHER_DIGEST,
        )
        result = publish(
            self.state,
            genesis.run_id,
            dispatch_workflow(genesis.record_ref),
            conflicting,
            "key-2",
        )
        self.assertIsInstance(result, Rejected)
        self.assertEqual(result.code, PublishRejectionCode.PREDECESSOR_MISMATCH)
        self.assertEqual(self.sequence_files(genesis.run_id), ["0000000001.json"])

    def test_genesis_with_predecessor_rejects_without_touching_state(self) -> None:
        result = publish(
            self.state,
            None,
            dispatch_request(),
            RecordRef("request", "rec-x", OTHER_DIGEST),
            "key-genesis",
        )
        self.assertIsInstance(result, Rejected)
        self.assertEqual(result.code, PublishRejectionCode.PREDECESSOR_MISMATCH)
        self.assertFalse((Path(self.state) / "runs").exists())

    def test_idempotent_retry_returns_original_without_new_record(self) -> None:
        first = publish(self.state, None, dispatch_request(), None, "key-same")
        self.assertIsInstance(first, Published)

        retry = publish(
            self.state, first.run_id, dispatch_request(), None, "key-same"
        )
        self.assertEqual(retry, first)

        self.assertEqual(self.sequence_files(first.run_id), ["0000000001.json"])
        head = open_run(self.state, first.run_id).read_head()
        self.assertEqual(head.last_sequence, 1)
        self.assertEqual(head.last_record["record_id"], first.record_ref.record_id)

    def test_same_key_with_different_content_rejects(self) -> None:
        first = publish(
            self.state,
            None,
            dispatch_request(objective="Objective A"),
            None,
            "key-dup",
        )
        self.assertIsInstance(first, Published)

        result = publish(
            self.state,
            first.run_id,
            dispatch_request(objective="Objective B"),
            None,
            "key-dup",
        )
        self.assertIsInstance(result, Rejected)
        self.assertEqual(
            result.code,
            PublishRejectionCode.IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_CONTENT,
        )
        self.assertEqual(self.sequence_files(first.run_id), ["0000000001.json"])

    def test_unknown_run_id_rejects_without_creating_run(self) -> None:
        expected = RecordRef("request", "rec-unknown", OTHER_DIGEST)
        result = publish(
            self.state,
            "no-such-run",
            dispatch_request(),
            expected,
            "key-x",
        )
        self.assertIsInstance(result, Rejected)
        self.assertEqual(result.code, PublishRejectionCode.RUN_NOT_FOUND)
        self.assertFalse((Path(self.state) / "runs" / "no-such-run").exists())

    def test_run_without_committed_records_rejects(self) -> None:
        open_run(self.state, "empty-run")
        result = publish(
            self.state, "empty-run", dispatch_request(), None, "key-x"
        )
        self.assertIsInstance(result, Rejected)
        self.assertEqual(result.code, PublishRejectionCode.RUN_NOT_FOUND)
        self.assertEqual(self.sequence_files("empty-run"), [])

    def test_validated_candidate_alone_has_no_authoritative_effect(self) -> None:
        candidate = dispatch_request()
        self.assertTrue(candidate.envelope.content_digest())
        self.assertFalse((Path(self.state) / "runs").exists())

    def test_workflow_revision_as_genesis_rejects_without_creating_run(
        self,
    ) -> None:
        parent = RecordRef("request", "rec-elsewhere", OTHER_DIGEST)
        result = publish(
            self.state, None, dispatch_workflow(parent), None, "key-genesis"
        )
        self.assertIsInstance(result, Rejected)
        self.assertEqual(
            result.code,
            PublishRejectionCode.INVALID_CANDIDATE_KIND_FOR_RUN_STATE,
        )
        self.assertFalse((Path(self.state) / "runs").exists())

    def test_second_request_in_existing_run_rejects(self) -> None:
        genesis = publish(self.state, None, dispatch_request(), None, "key-1")
        self.assertIsInstance(genesis, Published)

        result = publish(
            self.state,
            genesis.run_id,
            dispatch_request(objective="A second Request"),
            genesis.record_ref,
            "key-2",
        )
        self.assertIsInstance(result, Rejected)
        self.assertEqual(
            result.code,
            PublishRejectionCode.INVALID_CANDIDATE_KIND_FOR_RUN_STATE,
        )
        self.assertEqual(self.sequence_files(genesis.run_id), ["0000000001.json"])

    def test_revision_with_wrong_genesis_binding_rejects(self) -> None:
        genesis = publish(self.state, None, dispatch_request(), None, "key-1")
        self.assertIsInstance(genesis, Published)

        wrong_digest = RecordRef(
            contract_kind="request",
            record_id=genesis.record_ref.record_id,
            content_digest=OTHER_DIGEST,
        )
        result = publish(
            self.state,
            genesis.run_id,
            dispatch_workflow(wrong_digest, task_id="task-3"),
            genesis.record_ref,
            "key-2",
        )
        self.assertIsInstance(result, Rejected)
        self.assertEqual(
            result.code, PublishRejectionCode.GENESIS_REQUEST_BINDING_MISMATCH
        )
        self.assertEqual(self.sequence_files(genesis.run_id), ["0000000001.json"])

    def test_revision_bound_to_other_run_genesis_rejects(self) -> None:
        genesis = publish(self.state, None, dispatch_request(), None, "key-1")
        self.assertIsInstance(genesis, Published)
        other_run = publish(
            self.state, None, dispatch_request(objective="Other run"), None, "key-other"
        )
        self.assertIsInstance(other_run, Published)

        result = publish(
            self.state,
            genesis.run_id,
            dispatch_workflow(other_run.record_ref, task_id="task-3"),
            genesis.record_ref,
            "key-2",
        )
        self.assertIsInstance(result, Rejected)
        self.assertEqual(
            result.code, PublishRejectionCode.GENESIS_REQUEST_BINDING_MISMATCH
        )
        self.assertEqual(self.sequence_files(genesis.run_id), ["0000000001.json"])

    def test_malformed_run_id_rejects_without_touching_filesystem(self) -> None:
        genesis = publish(self.state, None, dispatch_request(), None, "key-1")
        self.assertIsInstance(genesis, Published)
        candidate = dispatch_workflow(genesis.record_ref)

        bad_run_ids = [
            "../evil",
            "../../etc",
            "/etc/passwd",
            "run/with/slash",
            # Resolves through the runs directory back to the real run:
            # only the run-id format check stops this from publishing.
            f"../runs/{genesis.run_id}",
            "z" * 32,
            "0" * 31,
            "0" * 33,
            "ABCDEF0123456789ABCDEF0123456789",
            "no-such-run",
        ]
        for index, bad_run_id in enumerate(bad_run_ids):
            with self.subTest(run_id=bad_run_id):
                result = publish(
                    self.state,
                    bad_run_id,
                    candidate,
                    genesis.record_ref,
                    f"key-bad-{index}",
                )
                self.assertIsInstance(result, Rejected)
                self.assertEqual(result.code, PublishRejectionCode.RUN_NOT_FOUND)

        self.assertEqual(
            sorted(entry.name for entry in Path(self.state).iterdir()), ["runs"]
        )
        self.assertEqual(
            sorted(entry.name for entry in (Path(self.state) / "runs").iterdir()),
            [genesis.run_id],
        )
        self.assertEqual(self.sequence_files(genesis.run_id), ["0000000001.json"])

    def test_publish_rejects_lock_contention_timeout(self) -> None:
        genesis = publish(self.state, None, dispatch_request(), None, "key-1")
        self.assertIsInstance(genesis, Published)
        run = open_run(self.state, genesis.run_id)
        acquired = threading.Event()
        release = threading.Event()

        def hold_lock() -> None:
            with run.lock():
                acquired.set()
                self.assertTrue(release.wait(timeout=10))

        holder = threading.Thread(target=hold_lock)
        holder.start()
        self.assertTrue(acquired.wait(timeout=10))
        try:
            result = publish(
                self.state,
                genesis.run_id,
                dispatch_workflow(genesis.record_ref, task_id="task-late"),
                genesis.record_ref,
                "key-late",
                lock_timeout=0.2,
            )
            self.assertIsInstance(result, Rejected)
            self.assertEqual(
                result.code, PublishRejectionCode.LOCK_CONTENTION_TIMEOUT
            )
            self.assertEqual(self.sequence_files(genesis.run_id), ["0000000001.json"])
        finally:
            release.set()
            holder.join(timeout=10)
        self.assertFalse(holder.is_alive())

    def test_malformed_committed_record_fails_idempotency_scan_closed(
        self,
    ) -> None:
        genesis = publish(self.state, None, dispatch_request(), None, "key-1")
        self.assertIsInstance(genesis, Published)
        child_candidate = dispatch_workflow(genesis.record_ref)
        child = publish(
            self.state,
            genesis.run_id,
            child_candidate,
            genesis.record_ref,
            "key-2",
        )
        self.assertIsInstance(child, Published)

        (self.run_dir(genesis.run_id) / "0000000001.json").write_text(
            "{not json", encoding="utf-8"
        )
        with self.assertRaises(RuntimeError):
            publish(
                self.state,
                genesis.run_id,
                child_candidate,
                child.record_ref,
                "key-2",
            )


class ReadCommittedContractRunIdValidationTests(unittest.TestCase):
    """PR #47 review round 2 MEDIUM 1: read_committed_contract must not
    create a stray run directory (or escape runs/ entirely) for a
    malformed/unknown run_id — it validates before calling open_run."""

    def setUp(self) -> None:
        self._state_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self._state_directory.cleanup)
        self.state = self._state_directory.name

    def test_malformed_run_id_raises_without_creating_a_directory(self) -> None:
        with self.assertRaises(UnknownRunError):
            read_committed_contract(self.state, "not-32-hex-chars", ContractKind.WORKFLOW_REVISION)
        self.assertFalse((Path(self.state) / "runs" / "not-32-hex-chars").exists())

    def test_path_traversal_run_id_raises_without_escaping_runs_dir(self) -> None:
        with self.assertRaises(UnknownRunError):
            read_committed_contract(
                self.state, "../elsewhere", ContractKind.WORKFLOW_REVISION
            )
        self.assertFalse((Path(self.state) / "elsewhere").exists())

    def test_well_formed_but_unknown_run_id_raises_without_creating_a_directory(
        self,
    ) -> None:
        unknown_run_id = "0" * 32
        with self.assertRaises(UnknownRunError):
            read_committed_contract(
                self.state, unknown_run_id, ContractKind.WORKFLOW_REVISION
            )
        self.assertFalse((Path(self.state) / "runs" / unknown_run_id).exists())


if __name__ == "__main__":
    unittest.main()
