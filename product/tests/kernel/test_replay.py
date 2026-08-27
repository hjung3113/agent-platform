from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from kernel.canonical import canonical_json_bytes, content_digest
from kernel.lineage_store import open_run
from kernel.protocol import ParsedCandidate, RecordRef, read_candidate
from kernel.publish import Published, publish
from kernel.protocol_v1 import RESULT_SNAPSHOT_EVIDENCE_CLASS
from kernel.replay import RunState, replay

OTHER_DIGEST = "sha256:agent-platform-json-v1:" + "f" * 64
OUTPUT_SNAPSHOT_DIGEST = "sha256:agent-platform-json-v1:" + "e" * 64
RUNTIME_PROFILE_IDENTITY = content_digest({"fixture": "runtime-profile-replay"})
VERIFIER_PROFILE_IDENTITY = content_digest({"fixture": "verifier-profile-replay"})
EXECUTION_IDENTITY = content_digest({"fixture": "execution-identity-replay"})
VERIFIER_EXECUTION_IDENTITY = content_digest(
    {"fixture": "verifier-execution-identity-replay"}
)
CRITERIA = ["Replay is deterministic"]


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
            "schema_version": 2,
            "payload": {
                "request": parent.to_canonical_value(),
                "tasks": [
                    {
                        "task_id": task_id,
                        "objective": "Fold the committed records",
                        "acceptance_criteria": ["Replay is deterministic"],
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
                "runtime_capability_profile_identity": RUNTIME_PROFILE_IDENTITY,
            },
        }
    )
    assert result.ok, result.reason
    return result.value


def dispatch_result(
    attempt: RecordRef,
    output_snapshot_digest: str = OUTPUT_SNAPSHOT_DIGEST,
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
    coverage: list[dict],
    verdict: str,
    findings: tuple[dict, ...] = (),
) -> ParsedCandidate:
    """Build a validated Verification candidate bound to ``result``."""

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
                "coverage": coverage,
                "verdict": verdict,
                "findings": list(findings),
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
            dispatch_attempt(child.record_ref),
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

    def test_full_six_record_run_replays_terminal(self) -> None:
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
        attempt = dispatch_attempt(workflow.record_ref)
        attempt_published = publish(
            self.state, genesis.run_id, attempt, workflow.record_ref, "key-3"
        )
        self.assertIsInstance(attempt_published, Published)
        result = dispatch_result(attempt_published.record_ref)
        result_published = publish(
            self.state, genesis.run_id, result, attempt_published.record_ref, "key-4"
        )
        self.assertIsInstance(result_published, Published)
        coverage = [
            {
                "criterion": criterion,
                "status": "SATISFIED",
                "evidence_digest": OUTPUT_SNAPSHOT_DIGEST,
                "evidence_class": RESULT_SNAPSHOT_EVIDENCE_CLASS,
            }
            for criterion in CRITERIA
        ]
        verification = dispatch_verification(
            result_published.record_ref, coverage, "PASS"
        )
        verification_published = publish(
            self.state,
            genesis.run_id,
            verification,
            result_published.record_ref,
            "key-5",
        )
        self.assertIsInstance(verification_published, Published)
        receipt = dispatch_receipt(verification_published.record_ref)
        receipt_published = publish(
            self.state,
            genesis.run_id,
            receipt,
            verification_published.record_ref,
            "key-6",
        )
        self.assertIsInstance(receipt_published, Published)

        first = replay(self.state, genesis.run_id)
        second = replay(self.state, genesis.run_id)
        self.assertEqual(first, second)
        self.assertTrue(first.terminal)
        self.assertEqual(first.last_sequence, 6)
        self.assertEqual(first.last_record_id, receipt_published.record_ref)
        self.assertEqual(first.attempt_packet, attempt.value)
        self.assertEqual(first.result, result.value)
        self.assertEqual(first.verification, verification.value)
        self.assertEqual(first.receipt, receipt.value)

    def test_legacy_v1_verification_record_replays(self) -> None:
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
        result = publish(
            self.state,
            genesis.run_id,
            dispatch_result(attempt.record_ref),
            attempt.record_ref,
            "key-4",
        )
        self.assertIsInstance(result, Published)

        candidate = {
            "contract_kind": "verification",
            "protocol_version": 1,
            "schema_version": 1,
            "payload": {
                "result": result.record_ref.to_canonical_value(),
                "verifier_identity": "legacy-verifier",
                "coverage": [
                    {
                        "criterion": "Replay is deterministic",
                        "status": "SATISFIED",
                        "evidence_digest": OUTPUT_SNAPSHOT_DIGEST,
                    }
                ],
                "verdict": "PASS",
                "findings": [],
            },
        }
        sequence = 5
        record_id = f"{genesis.run_id}:{sequence:010d}"
        record = {
            "run_id": genesis.run_id,
            "sequence": sequence,
            "record_id": record_id,
            "content_digest": content_digest(candidate),
            "idempotency_key": "legacy-verification-fixture",
            "candidate": candidate,
        }
        run_dir = Path(self.state) / "runs" / genesis.run_id
        (run_dir / f"{sequence:010d}.json").write_bytes(canonical_json_bytes(record))

        state = replay(self.state, genesis.run_id)
        self.assertEqual(state.last_sequence, 5)
        self.assertIsNotNone(state.verification)
        self.assertEqual(state.verification.verdict, "PASS")
        self.assertEqual(state.verification.findings, ())
        self.assertFalse(state.terminal)

    def test_legacy_v1_workflow_revision_replays_its_folded_value(self) -> None:
        genesis = publish(self.state, None, dispatch_request(), None, "key-legacy-request")
        self.assertIsInstance(genesis, Published)
        assert isinstance(genesis, Published)
        candidate = {
            "contract_kind": "workflow_revision",
            "protocol_version": 1,
            "schema_version": 1,
            "payload": {
                "request": genesis.record_ref.to_canonical_value(),
                "task": {
                    "task_id": "legacy-task",
                    "objective": "Replay a pre-M7 Workflow Revision",
                    "acceptance_criteria": ["The legacy value is preserved"],
                },
            },
        }
        parsed = read_candidate(candidate)
        self.assertTrue(parsed.ok, parsed.reason)
        sequence = 2
        record = {
            "run_id": genesis.run_id,
            "sequence": sequence,
            "record_id": f"{genesis.run_id}:{sequence:010d}",
            "content_digest": content_digest(candidate),
            "idempotency_key": "legacy-workflow-fixture",
            "candidate": candidate,
        }
        run_dir = Path(self.state) / "runs" / genesis.run_id
        (run_dir / f"{sequence:010d}.json").write_bytes(canonical_json_bytes(record))

        state = replay(self.state, genesis.run_id)
        self.assertEqual(state.workflow_revision, parsed.value.value)

    def test_legacy_v1_result_record_replays_after_result_schema_bump(self) -> None:
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

        candidate = {
            "contract_kind": "result",
            "protocol_version": 1,
            "schema_version": 1,
            "payload": {
                "attempt": attempt.record_ref.to_canonical_value(),
                "output_snapshot_digest": OUTPUT_SNAPSHOT_DIGEST,
                "observation": {
                    "runtime_identity": RUNTIME_PROFILE_IDENTITY,
                    "output_snapshot_digest": OUTPUT_SNAPSHOT_DIGEST,
                },
            },
        }
        sequence = 4
        record_id = f"{genesis.run_id}:{sequence:010d}"
        record = {
            "run_id": genesis.run_id,
            "sequence": sequence,
            "record_id": record_id,
            "content_digest": content_digest(candidate),
            "idempotency_key": "legacy-result-fixture",
            "candidate": candidate,
        }
        run_dir = Path(self.state) / "runs" / genesis.run_id
        (run_dir / f"{sequence:010d}.json").write_bytes(canonical_json_bytes(record))

        state = replay(self.state, genesis.run_id)
        self.assertEqual(state.last_sequence, 4)
        self.assertIsNotNone(state.result)
        assert state.result is not None
        self.assertFalse(hasattr(state.result.observation, "execution_identity"))
        self.assertEqual(state.result.observation.runtime_identity, RUNTIME_PROFILE_IDENTITY)

    def test_round_one_v2_verification_record_replays_after_verification_schema_bump(
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
        result = publish(
            self.state,
            genesis.run_id,
            dispatch_result(attempt.record_ref),
            attempt.record_ref,
            "key-4",
        )
        self.assertIsInstance(result, Published)

        candidate = {
            "contract_kind": "verification",
            "protocol_version": 1,
            "schema_version": 2,
            "payload": {
                "result": result.record_ref.to_canonical_value(),
                "verifier_identity": "round-one-verifier",
                "verifier_runtime_capability_profile_identity": VERIFIER_PROFILE_IDENTITY,
                "coverage": [
                    {
                        "criterion": "Replay is deterministic",
                        "status": "SATISFIED",
                        "evidence_digest": OUTPUT_SNAPSHOT_DIGEST,
                        "evidence_class": RESULT_SNAPSHOT_EVIDENCE_CLASS,
                    }
                ],
                "verdict": "PASS",
                "findings": [],
            },
        }
        sequence = 5
        record_id = f"{genesis.run_id}:{sequence:010d}"
        record = {
            "run_id": genesis.run_id,
            "sequence": sequence,
            "record_id": record_id,
            "content_digest": content_digest(candidate),
            "idempotency_key": "round-one-verification-fixture",
            "candidate": candidate,
        }
        run_dir = Path(self.state) / "runs" / genesis.run_id
        (run_dir / f"{sequence:010d}.json").write_bytes(canonical_json_bytes(record))

        state = replay(self.state, genesis.run_id)
        self.assertEqual(state.last_sequence, 5)
        self.assertIsNotNone(state.verification)
        assert state.verification is not None
        self.assertEqual(state.verification.verdict, "PASS")
        self.assertEqual(state.verification.coverage[0].evidence_class, RESULT_SNAPSHOT_EVIDENCE_CLASS)
        self.assertFalse(hasattr(state.verification, "verifier_execution_identity"))

    def test_fail_terminated_five_record_run_is_not_terminal(self) -> None:
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
        attempt = dispatch_attempt(workflow.record_ref)
        attempt_published = publish(
            self.state, genesis.run_id, attempt, workflow.record_ref, "key-3"
        )
        self.assertIsInstance(attempt_published, Published)
        result = dispatch_result(attempt_published.record_ref)
        result_published = publish(
            self.state,
            genesis.run_id,
            result,
            attempt_published.record_ref,
            "key-4",
        )
        self.assertIsInstance(result_published, Published)
        coverage = [
            {
                "criterion": criterion,
                "status": "UNSATISFIED",
                "evidence_digest": None,
                "evidence_class": RESULT_SNAPSHOT_EVIDENCE_CLASS,
            }
            for criterion in CRITERIA
        ]
        findings = tuple(
            {
                "criterion": criterion,
                "fingerprint": content_digest(
                    {"criterion": criterion, "description": "Digest mismatch"}
                ),
                "description": "Digest mismatch",
                "state": "OPEN",
                "predecessor": None,
            }
            for criterion in CRITERIA
        )
        verification = dispatch_verification(
            result_published.record_ref, coverage, "FAIL", findings
        )
        verification_published = publish(
            self.state,
            genesis.run_id,
            verification,
            result_published.record_ref,
            "key-5",
        )
        self.assertIsInstance(verification_published, Published)

        state = replay(self.state, genesis.run_id)
        self.assertFalse(state.terminal)
        self.assertEqual(state.last_sequence, 5)
        self.assertEqual(state.request, dispatch_request().value)
        self.assertEqual(state.attempt_packet, attempt.value)
        self.assertEqual(state.result, result.value)
        self.assertEqual(state.verification, verification.value)
        self.assertIsNone(state.receipt)

    def test_new_fields_stay_none_at_intermediate_chain_points(self) -> None:
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
        attempt = dispatch_attempt(workflow.record_ref)
        attempt_published = publish(
            self.state, genesis.run_id, attempt, workflow.record_ref, "key-3"
        )
        self.assertIsInstance(attempt_published, Published)

        state = replay(self.state, genesis.run_id)
        self.assertEqual(state.last_sequence, 3)
        self.assertIsNotNone(state.request)
        self.assertIsNotNone(state.workflow_revision)
        self.assertEqual(state.attempt_packet, attempt.value)
        self.assertIsNone(state.result)
        self.assertIsNone(state.verification)
        self.assertIsNone(state.receipt)
        self.assertFalse(state.terminal)


if __name__ == "__main__":
    unittest.main()
