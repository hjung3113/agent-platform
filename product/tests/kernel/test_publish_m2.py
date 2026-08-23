from __future__ import annotations

import re
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from kernel.canonical import content_digest
from kernel.lineage_store import open_run
from kernel.protocol import ParsedCandidate, RecordRef, read_candidate
from kernel.protocol_v1 import RESULT_SNAPSHOT_EVIDENCE_CLASS
from kernel.publish import (
    Published,
    PublishRejectionCode,
    Rejected,
    publish,
)

OTHER_DIGEST = "sha256:agent-platform-json-v1:" + "f" * 64
OUTPUT_SNAPSHOT_DIGEST = "sha256:agent-platform-json-v1:" + "e" * 64
RUNTIME_PROFILE_IDENTITY = content_digest({"fixture": "runtime-profile-m2"})
VERIFIER_PROFILE_IDENTITY = content_digest({"fixture": "verifier-profile-m2"})
TASK_ID = "task-1"
IMPLEMENTER_IDENTITY = "implementer-1"
VERIFIER_IDENTITY = "verifier-1"
CRITERIA = ["Criterion one", "Criterion two"]

_CHAIN_LENGTH = {
    "request": 1,
    "workflow_revision": 2,
    "attempt_packet": 3,
    "result": 4,
    "verification": 5,
}


def dispatch_request(
    objective: str = "Prove the M2 one-task protocol chain",
) -> ParsedCandidate:
    """Build a validated Request candidate through the real dispatch."""

    result = read_candidate(
        {
            "contract_kind": "request",
            "protocol_version": 1,
            "schema_version": 1,
            "payload": {
                "objective": objective,
                "scope": ["docs/plans/active/m2-one-task-protocol-e2e.md"],
                "acceptance_criteria": ["The six-record chain publishes"],
            },
        }
    )
    assert result.ok, result.reason
    return result.value


def dispatch_workflow(
    parent: RecordRef,
    task_id: str = TASK_ID,
    criteria: list[str] | None = None,
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
                    "objective": "Wire the attempt chain",
                    "acceptance_criteria": CRITERIA if criteria is None else criteria,
                },
            },
        }
    )
    assert result.ok, result.reason
    return result.value


def dispatch_attempt(
    workflow_revision: RecordRef,
    task_id: str = TASK_ID,
    implementer_identity: str = IMPLEMENTER_IDENTITY,
) -> ParsedCandidate:
    """Build a validated Attempt Packet candidate."""

    result = read_candidate(
        {
            "contract_kind": "attempt_packet",
            "protocol_version": 1,
            "schema_version": 1,
            "payload": {
                "workflow_revision": workflow_revision.to_canonical_value(),
                "task_id": task_id,
                "implementer_identity": implementer_identity,
                "context_digest": "fixture-context-m2",
                "workspace_snapshot_digest": "fixture-workspace-m2",
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
            "schema_version": 1,
            "payload": {
                "attempt": attempt.to_canonical_value(),
                "output_snapshot_digest": output_snapshot_digest,
                "observation": {
                    "runtime_identity": runtime_identity,
                    "output_snapshot_digest": output_snapshot_digest,
                },
            },
        }
    )
    assert result.ok, result.reason
    return result.value


def satisfied(criterion: str, evidence_digest: str) -> dict:
    return {
        "criterion": criterion,
        "status": "SATISFIED",
        "evidence_digest": evidence_digest,
        "evidence_class": RESULT_SNAPSHOT_EVIDENCE_CLASS,
    }


def unsatisfied(criterion: str) -> dict:
    return {
        "criterion": criterion,
        "status": "UNSATISFIED",
        "evidence_digest": None,
        "evidence_class": RESULT_SNAPSHOT_EVIDENCE_CLASS,
    }


def blocked(criterion: str) -> dict:
    return {
        "criterion": criterion,
        "status": "BLOCKED",
        "evidence_digest": None,
        "evidence_class": RESULT_SNAPSHOT_EVIDENCE_CLASS,
    }


def finding_payload(criterion: str, description: str) -> dict:
    return {
        "criterion": criterion,
        "fingerprint": content_digest(
            {"criterion": criterion, "description": description}
        ),
        "description": description,
        "state": "OPEN",
        "predecessor": None,
    }


def pass_coverage(evidence_digest: str = OUTPUT_SNAPSHOT_DIGEST) -> list[dict]:
    return [satisfied(criterion, evidence_digest) for criterion in CRITERIA]


def dispatch_verification(
    result: RecordRef,
    coverage: list[dict],
    verdict: str,
    findings: tuple[dict, ...] = (),
    verifier_identity: str = VERIFIER_IDENTITY,
    verifier_runtime_capability_profile_identity: str = VERIFIER_PROFILE_IDENTITY,
) -> ParsedCandidate:
    """Build a validated Verification candidate bound to ``result``."""

    result_read = read_candidate(
        {
            "contract_kind": "verification",
            "protocol_version": 1,
            "schema_version": 2,
            "payload": {
                "result": result.to_canonical_value(),
                "verifier_identity": verifier_identity,
                "verifier_runtime_capability_profile_identity": (
                    verifier_runtime_capability_profile_identity
                ),
                "coverage": coverage,
                "verdict": verdict,
                "findings": list(findings),
            },
        }
    )
    assert result_read.ok, result_read.reason
    return result_read.value


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


def with_other_digest(ref: RecordRef) -> RecordRef:
    return RecordRef(ref.contract_kind, ref.record_id, OTHER_DIGEST)


def forged_ref(contract_kind: str) -> RecordRef:
    return RecordRef(contract_kind, "rec-forged", OTHER_DIGEST)


@dataclass
class Chain:
    run_id: str
    request: Published
    key_prefix: str = ""
    workflow: Published | None = None
    attempt: Published | None = None
    result: Published | None = None
    verification: Published | None = None

    @property
    def head(self) -> Published:
        for value in (self.verification, self.result, self.attempt, self.workflow):
            if value is not None:
                return value
        return self.request


class PublishM2Tests(unittest.TestCase):
    def setUp(self) -> None:
        state = tempfile.TemporaryDirectory()
        self.addCleanup(state.cleanup)
        self.state = state.name
        self.chain_count = 0

    def run_dir(self, run_id: str) -> Path:
        return Path(self.state) / "runs" / run_id

    def sequence_files(self, run_id: str) -> list[str]:
        return sorted(
            entry.name
            for entry in self.run_dir(run_id).iterdir()
            if re.fullmatch(r"\d{10}\.json", entry.name)
        )

    def publish_run_through(self, last_kind: str) -> Chain:
        """Publish a fresh run's linear chain up through ``last_kind``.

        Each call uses its own idempotency-key prefix so the run is always
        genuinely new: identical fixture content with a reused genesis key
        would idempotently recover the earlier run instead.
        """

        self.chain_count += 1
        prefix = f"key-{self.chain_count}"
        genesis = publish(
            self.state, None, dispatch_request(), None, f"{prefix}-request"
        )
        assert isinstance(genesis, Published)
        chain = Chain(
            run_id=genesis.run_id, request=genesis, key_prefix=prefix
        )
        if last_kind == "request":
            return chain

        workflow = publish(
            self.state,
            genesis.run_id,
            dispatch_workflow(genesis.record_ref),
            genesis.record_ref,
            f"{prefix}-workflow",
        )
        assert isinstance(workflow, Published)
        chain.workflow = workflow
        if last_kind == "workflow_revision":
            return chain

        attempt = publish(
            self.state,
            genesis.run_id,
            dispatch_attempt(workflow.record_ref),
            workflow.record_ref,
            f"{prefix}-attempt",
        )
        assert isinstance(attempt, Published)
        chain.attempt = attempt
        if last_kind == "attempt_packet":
            return chain

        result = publish(
            self.state,
            genesis.run_id,
            dispatch_result(attempt.record_ref),
            attempt.record_ref,
            f"{prefix}-result",
        )
        assert isinstance(result, Published)
        chain.result = result
        if last_kind == "result":
            return chain

        verification = publish(
            self.state,
            genesis.run_id,
            dispatch_verification(
                result.record_ref, pass_coverage(), "PASS"
            ),
            result.record_ref,
            f"{prefix}-verification",
        )
        assert isinstance(verification, Published)
        chain.verification = verification
        return chain

    def test_full_chain_publishes_six_kinds_in_order(self) -> None:
        chain = self.publish_run_through("verification")
        receipt = publish(
            self.state,
            chain.run_id,
            dispatch_receipt(chain.verification.record_ref),
            chain.verification.record_ref,
            f"{chain.key_prefix}-receipt",
        )

        self.assertIsInstance(receipt, Published)
        expected_kinds = [
            "request",
            "workflow_revision",
            "attempt_packet",
            "result",
            "verification",
            "receipt",
        ]
        published = (
            chain.request,
            chain.workflow,
            chain.attempt,
            chain.result,
            chain.verification,
            receipt,
        )
        for sequence, record in enumerate(published, start=1):
            self.assertIsInstance(record, Published)
            self.assertEqual(record.run_id, chain.run_id)
            self.assertEqual(record.record_ref.contract_kind, expected_kinds[sequence - 1])
            self.assertEqual(record.record_ref.record_id, f"{chain.run_id}:{sequence:010d}")

        self.assertEqual(len(self.sequence_files(chain.run_id)), 6)
        head = open_run(self.state, chain.run_id).read_head()
        self.assertEqual(head.last_sequence, 6)
        self.assertEqual(head.last_record["record_id"], receipt.record_ref.record_id)

    def test_out_of_order_kind_rejects_at_each_step(self) -> None:
        candidate_for: dict[str, Callable[[Chain], ParsedCandidate]] = {
            "request": lambda chain: dispatch_request(),
            "workflow": lambda chain: dispatch_workflow(chain.request.record_ref),
            "attempt": lambda chain: dispatch_attempt(forged_ref("workflow_revision")),
            "result": lambda chain: dispatch_result(forged_ref("attempt_packet")),
            "verification": lambda chain: dispatch_verification(
                forged_ref("result"), pass_coverage(), "PASS"
            ),
            "receipt": lambda chain: dispatch_receipt(forged_ref("verification")),
        }
        out_of_order = {
            "request": ["attempt", "result", "verification", "receipt"],
            "workflow_revision": ["request", "result", "verification", "receipt"],
            "attempt_packet": ["request", "attempt", "verification", "receipt"],
            "result": ["request", "result", "receipt"],
            "verification": ["request", "workflow", "verification"],
        }
        for head_kind, names in out_of_order.items():
            chain = self.publish_run_through(head_kind)
            for name in names:
                with self.subTest(head_kind=head_kind, candidate=name):
                    rejected = publish(
                        self.state,
                        chain.run_id,
                        candidate_for[name](chain),
                        chain.head.record_ref,
                        f"key-ooo-{head_kind}-{name}",
                    )
                    self.assertIsInstance(rejected, Rejected)
                    self.assertEqual(
                        rejected.code,
                        PublishRejectionCode.INVALID_CANDIDATE_KIND_FOR_RUN_STATE,
                    )
            self.assertEqual(
                len(self.sequence_files(chain.run_id)), _CHAIN_LENGTH[head_kind]
            )

    def test_stale_or_conflicting_predecessor_rejects_at_each_new_step(self) -> None:
        steps: list[
            tuple[str, str, Callable[[Chain], ParsedCandidate], Callable[[Chain], RecordRef]]
        ] = [
            (
                "attempt_packet",
                "workflow_revision",
                lambda c: dispatch_attempt(c.workflow.record_ref),
                lambda c: c.request.record_ref,
            ),
            (
                "result",
                "attempt_packet",
                lambda c: dispatch_result(c.attempt.record_ref),
                lambda c: c.workflow.record_ref,
            ),
            (
                "verification",
                "result",
                lambda c: dispatch_verification(
                    c.result.record_ref, pass_coverage(), "PASS"
                ),
                lambda c: c.attempt.record_ref,
            ),
            (
                "receipt",
                "verification",
                lambda c: dispatch_receipt(c.verification.record_ref),
                lambda c: c.result.record_ref,
            ),
        ]
        for kind, head_kind, candidate_of, stale_pred_of in steps:
            with self.subTest(candidate_kind=kind):
                chain = self.publish_run_through(head_kind)
                rejected = publish(
                    self.state,
                    chain.run_id,
                    candidate_of(chain),
                    stale_pred_of(chain),
                    f"key-stale-{kind}",
                )
                self.assertIsInstance(rejected, Rejected)
                self.assertEqual(rejected.code, PublishRejectionCode.PREDECESSOR_MISMATCH)
                self.assertEqual(
                    len(self.sequence_files(chain.run_id)), _CHAIN_LENGTH[head_kind]
                )

        chain = self.publish_run_through("workflow_revision")
        conflicting = with_other_digest(chain.workflow.record_ref)
        rejected = publish(
            self.state,
            chain.run_id,
            dispatch_attempt(chain.workflow.record_ref),
            conflicting,
            "key-conflicting",
        )
        self.assertIsInstance(rejected, Rejected)
        self.assertEqual(rejected.code, PublishRejectionCode.PREDECESSOR_MISMATCH)
        self.assertEqual(len(self.sequence_files(chain.run_id)), 2)

    def test_attempt_task_id_mismatch_rejects(self) -> None:
        chain = self.publish_run_through("workflow_revision")
        rejected = publish(
            self.state,
            chain.run_id,
            dispatch_attempt(chain.workflow.record_ref, task_id="task-other"),
            chain.workflow.record_ref,
            "key-attempt-wrong-task",
        )
        self.assertIsInstance(rejected, Rejected)
        self.assertEqual(
            rejected.code, PublishRejectionCode.ATTEMPT_TASK_BINDING_MISMATCH
        )
        self.assertEqual(len(self.sequence_files(chain.run_id)), 2)

    def test_attempt_wrong_workflow_revision_binding_rejects(self) -> None:
        chain = self.publish_run_through("workflow_revision")
        rejected = publish(
            self.state,
            chain.run_id,
            dispatch_attempt(with_other_digest(chain.workflow.record_ref)),
            chain.workflow.record_ref,
            "key-attempt-wrong-binding",
        )
        self.assertIsInstance(rejected, Rejected)
        self.assertEqual(
            rejected.code, PublishRejectionCode.ATTEMPT_TASK_BINDING_MISMATCH
        )
        self.assertEqual(len(self.sequence_files(chain.run_id)), 2)

    def test_result_attempt_binding_mismatch_rejects(self) -> None:
        chain = self.publish_run_through("attempt_packet")
        rejected = publish(
            self.state,
            chain.run_id,
            dispatch_result(with_other_digest(chain.attempt.record_ref)),
            chain.attempt.record_ref,
            "key-result-wrong-binding",
        )
        self.assertIsInstance(rejected, Rejected)
        self.assertEqual(
            rejected.code, PublishRejectionCode.RESULT_ATTEMPT_BINDING_MISMATCH
        )
        self.assertEqual(len(self.sequence_files(chain.run_id)), 3)

    def test_verification_result_binding_mismatch_rejects(self) -> None:
        chain = self.publish_run_through("result")
        rejected = publish(
            self.state,
            chain.run_id,
            dispatch_verification(
                with_other_digest(chain.result.record_ref), pass_coverage(), "PASS"
            ),
            chain.result.record_ref,
            "key-verification-wrong-binding",
        )
        self.assertIsInstance(rejected, Rejected)
        self.assertEqual(
            rejected.code,
            PublishRejectionCode.VERIFICATION_RESULT_BINDING_MISMATCH,
        )
        self.assertEqual(len(self.sequence_files(chain.run_id)), 4)

    def test_verification_coverage_criteria_mismatch_rejects(self) -> None:
        chain = self.publish_run_through("result")
        mismatches = {
            "wrong_text": [
                satisfied("Criterion other", OUTPUT_SNAPSHOT_DIGEST),
                satisfied(CRITERIA[1], OUTPUT_SNAPSHOT_DIGEST),
            ],
            "wrong_order": [
                satisfied(CRITERIA[1], OUTPUT_SNAPSHOT_DIGEST),
                satisfied(CRITERIA[0], OUTPUT_SNAPSHOT_DIGEST),
            ],
            "wrong_length": [satisfied(CRITERIA[0], OUTPUT_SNAPSHOT_DIGEST)],
        }
        for name, coverage in mismatches.items():
            with self.subTest(mismatch=name):
                rejected = publish(
                    self.state,
                    chain.run_id,
                    dispatch_verification(
                        chain.result.record_ref, coverage, "PASS"
                    ),
                    chain.result.record_ref,
                    f"key-coverage-{name}",
                )
                self.assertIsInstance(rejected, Rejected)
                self.assertEqual(
                    rejected.code,
                    PublishRejectionCode.VERIFICATION_COVERAGE_MISMATCH,
                )
        self.assertEqual(len(self.sequence_files(chain.run_id)), 4)

    def test_verification_evidence_digest_mismatch_rejects(self) -> None:
        chain = self.publish_run_through("result")
        rejected = publish(
            self.state,
            chain.run_id,
            dispatch_verification(
                chain.result.record_ref, pass_coverage(OTHER_DIGEST), "PASS"
            ),
            chain.result.record_ref,
            "key-evidence-wrong-digest",
        )
        self.assertIsInstance(rejected, Rejected)
        self.assertEqual(
            rejected.code,
            PublishRejectionCode.VERIFICATION_COVERAGE_MISMATCH,
        )
        self.assertEqual(len(self.sequence_files(chain.run_id)), 4)

    def test_self_verification_rejects(self) -> None:
        chain = self.publish_run_through("result")
        rejected = publish(
            self.state,
            chain.run_id,
            dispatch_verification(
                chain.result.record_ref,
                pass_coverage(),
                "PASS",
                verifier_identity=IMPLEMENTER_IDENTITY,
            ),
            chain.result.record_ref,
            "key-self-verification",
        )
        self.assertIsInstance(rejected, Rejected)
        self.assertEqual(
            rejected.code, PublishRejectionCode.SELF_VERIFICATION_REJECTED
        )
        self.assertEqual(len(self.sequence_files(chain.run_id)), 4)

    def test_fail_or_blocked_verification_publishes_and_run_stays_open(self) -> None:
        not_passed = [
            ("FAIL", [unsatisfied(criterion) for criterion in CRITERIA], "Digest mismatch"),
            ("BLOCKED", [blocked(criterion) for criterion in CRITERIA], "Runtime blocked"),
        ]
        for verdict, coverage, finding in not_passed:
            with self.subTest(verdict=verdict):
                chain = self.publish_run_through("result")
                findings = tuple(
                    finding_payload(criterion, f"{finding}: {criterion}")
                    for criterion in CRITERIA
                )
                verification = publish(
                    self.state,
                    chain.run_id,
                    dispatch_verification(
                        chain.result.record_ref, coverage, verdict, findings
                    ),
                    chain.result.record_ref,
                    "key-verification",
                )
                self.assertIsInstance(verification, Published)
                self.assertEqual(
                    verification.record_ref.contract_kind, "verification"
                )
                self.assertEqual(len(self.sequence_files(chain.run_id)), 5)
                head = open_run(self.state, chain.run_id).read_head()
                self.assertEqual(
                    head.last_record["candidate"]["contract_kind"], "verification"
                )

                rejected = publish(
                    self.state,
                    chain.run_id,
                    dispatch_receipt(verification.record_ref),
                    verification.record_ref,
                    "key-receipt",
                )
                self.assertIsInstance(rejected, Rejected)
                self.assertEqual(
                    rejected.code,
                    PublishRejectionCode.RECEIPT_VERIFICATION_NOT_PASSED,
                )
                self.assertEqual(len(self.sequence_files(chain.run_id)), 5)

    def test_receipt_with_wrong_verification_binding_rejects(self) -> None:
        chain = self.publish_run_through("verification")
        rejected = publish(
            self.state,
            chain.run_id,
            dispatch_receipt(with_other_digest(chain.verification.record_ref)),
            chain.verification.record_ref,
            "key-receipt-wrong-binding",
        )
        self.assertIsInstance(rejected, Rejected)
        self.assertEqual(
            rejected.code,
            PublishRejectionCode.RECEIPT_VERIFICATION_NOT_PASSED,
        )
        self.assertEqual(len(self.sequence_files(chain.run_id)), 5)

    def test_terminal_receipt_retry_is_idempotent(self) -> None:
        chain = self.publish_run_through("verification")
        receipt = publish(
            self.state,
            chain.run_id,
            dispatch_receipt(chain.verification.record_ref),
            chain.verification.record_ref,
            "key-receipt",
        )
        self.assertIsInstance(receipt, Published)

        retry = publish(
            self.state,
            chain.run_id,
            dispatch_receipt(chain.verification.record_ref),
            chain.verification.record_ref,
            "key-receipt",
        )
        self.assertEqual(retry, receipt)
        self.assertEqual(len(self.sequence_files(chain.run_id)), 6)

    def test_terminal_receipt_same_key_different_content_rejects(self) -> None:
        chain = self.publish_run_through("verification")
        receipt = publish(
            self.state,
            chain.run_id,
            dispatch_receipt(chain.verification.record_ref),
            chain.verification.record_ref,
            "key-receipt",
        )
        self.assertIsInstance(receipt, Published)

        rejected = publish(
            self.state,
            chain.run_id,
            dispatch_receipt(with_other_digest(chain.verification.record_ref)),
            chain.verification.record_ref,
            "key-receipt",
        )
        self.assertIsInstance(rejected, Rejected)
        self.assertEqual(
            rejected.code,
            PublishRejectionCode.IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_CONTENT,
        )
        self.assertEqual(len(self.sequence_files(chain.run_id)), 6)

    def test_any_publish_against_terminal_run_rejects_run_already_terminal(self) -> None:
        chain = self.publish_run_through("verification")
        receipt = publish(
            self.state,
            chain.run_id,
            dispatch_receipt(chain.verification.record_ref),
            chain.verification.record_ref,
            "key-receipt",
        )
        self.assertIsInstance(receipt, Published)

        further: list[tuple[str, ParsedCandidate]] = [
            ("duplicate_receipt", dispatch_receipt(chain.verification.record_ref)),
            ("request", dispatch_request()),
            ("workflow_revision", dispatch_workflow(chain.request.record_ref)),
        ]
        for name, candidate in further:
            with self.subTest(candidate=name):
                rejected = publish(
                    self.state,
                    chain.run_id,
                    candidate,
                    chain.verification.record_ref,
                    f"key-terminal-{name}",
                )
                self.assertIsInstance(rejected, Rejected)
                self.assertEqual(
                    rejected.code, PublishRejectionCode.RUN_ALREADY_TERMINAL
                )
        self.assertEqual(len(self.sequence_files(chain.run_id)), 6)

    def test_mid_chain_idempotent_retry_after_head_advanced(self) -> None:
        chain = self.publish_run_through("verification")
        retry = publish(
            self.state,
            chain.run_id,
            dispatch_attempt(chain.workflow.record_ref),
            chain.workflow.record_ref,
            f"{chain.key_prefix}-attempt",
        )
        self.assertEqual(retry, chain.attempt)
        self.assertEqual(len(self.sequence_files(chain.run_id)), 5)


if __name__ == "__main__":
    unittest.main()
