# Code-review invariant checked (grep, not unit-tested): no test in the
# kernel/contract suites authors record content directly into a run directory
# outside publish()/lineage_store.RunHandle primitives; the only direct writes
# targeting a run dir are deliberate corruption — of the derived, rebuildable
# _head.json projection (test_lineage_store.py, test_replay.py) and of
# committed record files, made to prove readers fail closed
# (test_publish.py, test_replay.py).

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from kernel.canonical import content_digest
from kernel.lineage_store import HeadProjection, open_run
from kernel.protocol import ParsedCandidate, RecordRef, read_candidate
from kernel.protocol_v1 import RESULT_SNAPSHOT_EVIDENCE_CLASS
from kernel.publish import (
    Published,
    PublishRejectionCode,
    Rejected,
    publish,
)
from kernel.replay import RunState, replay

RUNTIME_PROFILE_IDENTITY = content_digest({"fixture": "runtime-profile-fault"})
VERIFIER_PROFILE_IDENTITY = content_digest({"fixture": "verifier-profile-fault"})
EXECUTION_IDENTITY = content_digest({"fixture": "execution-identity-fault"})
VERIFIER_EXECUTION_IDENTITY = content_digest(
    {"fixture": "verifier-execution-identity-fault"}
)


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
                "runtime_capability_profile_identity": RUNTIME_PROFILE_IDENTITY,
            },
        }
    )
    assert result.ok, result.reason
    return result.value


def dispatch_result(
    attempt: RecordRef,
    output_snapshot_digest: str = "sha256:agent-platform-json-v1:" + "e" * 64,
    runtime_identity: str = RUNTIME_PROFILE_IDENTITY,
) -> ParsedCandidate:
    """Build a validated Result candidate bound to ``attempt``."""

    result = read_candidate(
        {
            "contract_kind": "result",
            "protocol_version": 1,
            "schema_version": 2,
            "payload": {
                "attempt": attempt.to_canonical_value(),
                "output_snapshot_digest": output_snapshot_digest,
                "observation": {
                    "runtime_identity": runtime_identity,
                    "output_snapshot_digest": output_snapshot_digest,
                    "execution_identity": EXECUTION_IDENTITY,
                },
            },
        }
    )
    assert result.ok, result.reason
    return result.value


def dispatch_verification(
    result: RecordRef,
    criteria: list[str],
    evidence_digest: str,
) -> ParsedCandidate:
    """Build a validated PASS Verification candidate bound to ``result``."""

    verification = read_candidate(
        {
            "contract_kind": "verification",
            "protocol_version": 1,
            "schema_version": 3,
            "payload": {
                "result": result.to_canonical_value(),
                "verifier_identity": "verifier-1",
                "verifier_runtime_capability_profile_identity": VERIFIER_PROFILE_IDENTITY,
                "verifier_execution_identity": VERIFIER_EXECUTION_IDENTITY,
                "coverage": [
                    {
                        "criterion": criterion,
                        "status": "SATISFIED",
                        "evidence_digest": evidence_digest,
                        "evidence_class": RESULT_SNAPSHOT_EVIDENCE_CLASS,
                    }
                    for criterion in criteria
                ],
                "verdict": "PASS",
                "findings": [],
            },
        }
    )
    assert verification.ok, verification.reason
    return verification.value


def dispatch_receipt(verification: RecordRef) -> ParsedCandidate:
    """Build a validated terminal Receipt candidate."""

    result = read_candidate(
        {
            "contract_kind": "receipt",
            "protocol_version": 1,
            "schema_version": 1,
            "payload": {
                "verification": verification.to_canonical_value(),
                "receipt_type": "terminal",
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

    def test_publish_self_heals_stale_head_after_crash_between_records(
        self,
    ) -> None:
        genesis = publish(self.state, None, dispatch_request(), None, "key-1")
        self.assertIsInstance(genesis, Published)

        with self.assertRaises(RuntimeError):
            publish(
                self.state,
                genesis.run_id,
                dispatch_workflow(genesis.record_ref),
                genesis.record_ref,
                "key-2",
                commit_barrier=simulated_crash,
            )

        run = open_run(self.state, genesis.run_id)
        stale = run.read_head()
        self.assertIsNotNone(stale)
        self.assertEqual(stale.last_sequence, 1)
        self.assertTrue((run.run_dir / "0000000002.json").is_file())

        # Recover the true predecessor from the committed records, not from
        # the stale projection, and prove publish() accepts it at sequence 3.
        recovered = replay(self.state, genesis.run_id)
        self.assertEqual(recovered.last_sequence, 2)
        third = publish(
            self.state,
            genesis.run_id,
            dispatch_attempt(recovered.last_record_id),
            recovered.last_record_id,
            "key-3",
        )
        self.assertIsInstance(third, Published)
        self.assertEqual(third.record_ref.record_id, f"{genesis.run_id}:0000000003")

        healed = run.read_head()
        self.assertEqual(healed.last_sequence, 3)
        self.assertEqual(healed.last_record_file, "0000000003.json")
        self.assertEqual(healed.last_record["record_id"], third.record_ref.record_id)

    def test_publish_self_heals_stale_head_after_crash_at_receipt_commit(
        self,
    ) -> None:
        genesis = publish(self.state, None, dispatch_request(), None, "key-1")
        self.assertIsInstance(genesis, Published)
        workflow = publish(
            self.state,
            genesis.run_id,
            dispatch_workflow(genesis.record_ref),
            genesis.record_ref,
            "key-2",
        )
        self.assertIsInstance(workflow, Published)
        attempt = publish(
            self.state,
            genesis.run_id,
            dispatch_attempt(workflow.record_ref),
            workflow.record_ref,
            "key-3",
        )
        self.assertIsInstance(attempt, Published)
        result = dispatch_result(attempt.record_ref)
        result_published = publish(
            self.state, genesis.run_id, result, attempt.record_ref, "key-4"
        )
        self.assertIsInstance(result_published, Published)
        verification = dispatch_verification(
            result_published.record_ref,
            ["Replay recovers authority"],
            result.value.output_snapshot_digest,
        )
        verification_published = publish(
            self.state,
            genesis.run_id,
            verification,
            result_published.record_ref,
            "key-5",
        )
        self.assertIsInstance(verification_published, Published)

        with self.assertRaises(RuntimeError):
            publish(
                self.state,
                genesis.run_id,
                dispatch_receipt(verification_published.record_ref),
                verification_published.record_ref,
                "key-6",
                commit_barrier=simulated_crash,
            )

        run = open_run(self.state, genesis.run_id)
        stale = run.read_head()
        self.assertIsNotNone(stale)
        self.assertEqual(stale.last_sequence, 5)
        self.assertTrue((run.run_dir / "0000000006.json").is_file())

        # The committed Receipt is recoverable via replay() — terminal state
        # is derived from the record files, not the stale projection.
        recovered = replay(self.state, genesis.run_id)
        self.assertEqual(recovered.last_sequence, 6)
        self.assertEqual(
            recovered.last_record_id.record_id, f"{genesis.run_id}:0000000006"
        )
        self.assertEqual(recovered.receipt.receipt_type, "terminal")
        self.assertTrue(recovered.terminal)

        # The run is genuinely terminal: a new publish rejects before any
        # head repair, and the idempotent same-key/same-content retry
        # returns the committed Published after repairing the projection.
        rejected = publish(
            self.state,
            genesis.run_id,
            dispatch_receipt(verification_published.record_ref),
            verification_published.record_ref,
            "key-6-other",
        )
        self.assertIsInstance(rejected, Rejected)
        self.assertEqual(
            rejected.code, PublishRejectionCode.RUN_ALREADY_TERMINAL
        )

        retry = publish(
            self.state,
            genesis.run_id,
            dispatch_receipt(verification_published.record_ref),
            verification_published.record_ref,
            "key-6",
        )
        self.assertIsInstance(retry, Published)
        self.assertEqual(
            retry.record_ref.record_id, f"{genesis.run_id}:0000000006"
        )

        healed = run.read_head()
        self.assertEqual(healed.last_sequence, 6)
        self.assertEqual(healed.last_record_file, "0000000006.json")
        self.assertEqual(healed.last_record["record_id"], retry.record_ref.record_id)

    def test_publish_self_heals_forged_valid_json_head(self) -> None:
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

        run = open_run(self.state, genesis.run_id)
        first_envelope = json.loads(
            (run.run_dir / "0000000001.json").read_bytes().decode("utf-8")
        )
        # Syntactically valid, semantically stale/forged: claims sequence 1
        # is the head although sequence 2 is committed.
        forged = {
            "last_sequence": 1,
            "last_record_file": "0000000001.json",
            "last_record": first_envelope,
        }
        (run.run_dir / "_head.json").write_text(
            json.dumps(forged), encoding="utf-8"
        )
        self.assertEqual(run.read_head().last_sequence, 1)

        # Even an idempotent shortcut must repair the projection first.
        retry = publish(
            self.state,
            genesis.run_id,
            dispatch_workflow(genesis.record_ref),
            child.record_ref,
            "key-2",
        )
        self.assertIsInstance(retry, Published)
        self.assertEqual(retry, child)

        healed = run.read_head()
        self.assertEqual(healed.last_sequence, 2)
        self.assertEqual(healed.last_record_file, "0000000002.json")
        self.assertEqual(healed.last_record["record_id"], child.record_ref.record_id)

    def test_genesis_retry_after_lost_response_recovers_original_run(self) -> None:
        request = dispatch_request()
        with self.assertRaises(RuntimeError):
            publish(
                self.state,
                None,
                request,
                None,
                "key-lost",
                commit_barrier=simulated_crash,
            )

        # The caller never learned the generated run_id; retry genesis with
        # run_id=None, the same idempotency key, and the same content.
        recovered = publish(self.state, None, request, None, "key-lost")
        self.assertIsInstance(recovered, Published)

        actual = sole_run_id(self.state)
        self.assertEqual(recovered.run_id, actual)
        self.assertEqual(recovered.record_ref.record_id, f"{actual}:0000000001")
        self.assertEqual(
            recovered.record_ref.content_digest,
            request.envelope.content_digest(),
        )
        state = replay(self.state, actual)
        self.assertEqual(state.last_sequence, 1)
        self.assertEqual(state.request, request.value)

    def test_lost_genesis_retry_with_different_content_rejects(self) -> None:
        with self.assertRaises(RuntimeError):
            publish(
                self.state,
                None,
                dispatch_request(objective="Objective A"),
                None,
                "key-lost",
                commit_barrier=simulated_crash,
            )

        result = publish(
            self.state,
            None,
            dispatch_request(objective="Objective B"),
            None,
            "key-lost",
        )
        self.assertIsInstance(result, Rejected)
        self.assertEqual(
            result.code,
            PublishRejectionCode.IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_CONTENT,
        )
        # No second run was created by the rejected retry.
        sole_run_id(self.state)


if __name__ == "__main__":
    unittest.main()
