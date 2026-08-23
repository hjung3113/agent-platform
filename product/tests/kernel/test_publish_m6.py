from __future__ import annotations

import tempfile
import unittest
from dataclasses import dataclass

from kernel.canonical import content_digest
from kernel.protocol import ParsedCandidate, RecordRef, read_candidate
from kernel.protocol_v1 import RESULT_SNAPSHOT_EVIDENCE_CLASS
from kernel.publish import Published, PublishRejectionCode, Rejected, publish

OUTPUT_DIGEST = content_digest({"fixture": "m6-output"})
RUNTIME_PROFILE_IDENTITY = content_digest({"fixture": "m6-runtime-profile"})
VERIFIER_PROFILE_IDENTITY = content_digest({"fixture": "m6-verifier-profile"})
CRITERIA = ["Criterion one", "Criterion two"]


def read_dispatch(
    contract_kind: str, payload: dict, *, schema_version: int = 1
) -> ParsedCandidate:
    result = read_candidate(
        {
            "contract_kind": contract_kind,
            "protocol_version": 1,
            "schema_version": schema_version,
            "payload": payload,
        }
    )
    assert result.ok, result.reason
    return result.value


def request_candidate() -> ParsedCandidate:
    return read_dispatch(
        "request",
        {
            "objective": "Exercise M6 publication checks",
            "scope": ["docs/plans/active/m6-verification-evidence-hardening.md"],
            "acceptance_criteria": ["The M6 checks publish safely"],
        },
    )


def workflow_candidate(parent: RecordRef, criteria: list[str]) -> ParsedCandidate:
    return read_dispatch(
        "workflow_revision",
        {
            "request": parent.to_canonical_value(),
            "task": {
                "task_id": "task-m6",
                "objective": "Exercise hardened evidence publication",
                "acceptance_criteria": criteria,
            },
        },
    )


def attempt_candidate(parent: RecordRef) -> ParsedCandidate:
    return read_dispatch(
        "attempt_packet",
        {
            "workflow_revision": parent.to_canonical_value(),
            "task_id": "task-m6",
            "implementer_identity": "implementer-m6",
            "context_digest": "fixture-context-m6",
            "workspace_snapshot_digest": "fixture-workspace-m6",
            "runtime_capability_profile_identity": RUNTIME_PROFILE_IDENTITY,
        },
    )


def result_candidate(
    parent: RecordRef, *, runtime_identity: str = RUNTIME_PROFILE_IDENTITY
) -> ParsedCandidate:
    return read_dispatch(
        "result",
        {
            "attempt": parent.to_canonical_value(),
            "output_snapshot_digest": OUTPUT_DIGEST,
            "observation": {
                "runtime_identity": runtime_identity,
                "output_snapshot_digest": OUTPUT_DIGEST,
            },
        },
    )


def finding(criterion: str, description: str = "Criterion did not pass") -> dict:
    return {
        "criterion": criterion,
        "fingerprint": content_digest(
            {"criterion": criterion, "description": description}
        ),
        "description": description,
        "state": "OPEN",
        "predecessor": None,
    }


def coverage_entry(
    criterion: str,
    status: str,
    *,
    evidence_digest: str | None = None,
    evidence_class: str = RESULT_SNAPSHOT_EVIDENCE_CLASS,
) -> dict:
    return {
        "criterion": criterion,
        "status": status,
        "evidence_digest": evidence_digest,
        "evidence_class": evidence_class,
    }


def verification_candidate(
    result: RecordRef,
    coverage: list[dict],
    verdict: str,
    *,
    findings: list[dict] | None = None,
    verifier_identity: str = "verifier-m6",
    verifier_profile: str = VERIFIER_PROFILE_IDENTITY,
) -> ParsedCandidate:
    return read_dispatch(
        "verification",
        {
            "result": result.to_canonical_value(),
            "verifier_identity": verifier_identity,
            "verifier_runtime_capability_profile_identity": verifier_profile,
            "coverage": coverage,
            "verdict": verdict,
            "findings": [] if findings is None else findings,
        },
        schema_version=2,
    )


@dataclass(frozen=True)
class Prefix:
    run_id: str
    request: Published
    workflow: Published
    attempt: Published
    criteria: tuple[str, ...]


class PublishM6Tests(unittest.TestCase):
    def setUp(self) -> None:
        state = tempfile.TemporaryDirectory()
        self.addCleanup(state.cleanup)
        self.state = state.name
        self.counter = 0

    def prefix(self, criteria: list[str] | None = None) -> Prefix:
        self.counter += 1
        key = f"m6-{self.counter}"
        criteria = CRITERIA if criteria is None else criteria
        request = publish(self.state, None, request_candidate(), None, f"{key}-request")
        self.assertIsInstance(request, Published)
        assert isinstance(request, Published)
        workflow = publish(
            self.state,
            request.run_id,
            workflow_candidate(request.record_ref, criteria),
            request.record_ref,
            f"{key}-workflow",
        )
        self.assertIsInstance(workflow, Published)
        assert isinstance(workflow, Published)
        attempt = publish(
            self.state,
            request.run_id,
            attempt_candidate(workflow.record_ref),
            workflow.record_ref,
            f"{key}-attempt",
        )
        self.assertIsInstance(attempt, Published)
        assert isinstance(attempt, Published)
        return Prefix(
            request.run_id, request, workflow, attempt, tuple(criteria)
        )

    def publish_result(self, prefix: Prefix, *, runtime_identity: str = RUNTIME_PROFILE_IDENTITY):
        self.counter += 1
        return publish(
            self.state,
            prefix.run_id,
            result_candidate(prefix.attempt.record_ref, runtime_identity=runtime_identity),
            prefix.attempt.record_ref,
            f"m6-{self.counter}-result",
        )

    def publish_verification(
        self,
        prefix: Prefix,
        result: Published,
        coverage: list[dict],
        verdict: str,
        *,
        findings: list[dict] | None = None,
        verifier_profile: str = VERIFIER_PROFILE_IDENTITY,
    ):
        self.counter += 1
        return publish(
            self.state,
            prefix.run_id,
            verification_candidate(
                result.record_ref,
                coverage,
                verdict,
                findings=findings,
                verifier_profile=verifier_profile,
            ),
            result.record_ref,
            f"m6-{self.counter}-verification",
        )

    def test_result_environment_binding_rejects_and_valid_sibling_publishes(self) -> None:
        prefix = self.prefix()
        rejected = self.publish_result(
            prefix, runtime_identity=content_digest({"fixture": "wrong-runtime"})
        )
        self.assertIsInstance(rejected, Rejected)
        assert isinstance(rejected, Rejected)
        self.assertEqual(
            rejected.code, PublishRejectionCode.RESULT_ENVIRONMENT_BINDING_MISMATCH
        )

        published = self.publish_result(prefix)
        self.assertIsInstance(published, Published)

    def test_unsatisfied_coverage_requires_matching_open_findings(self) -> None:
        prefix = self.prefix()
        result = self.publish_result(prefix)
        self.assertIsInstance(result, Published)
        assert isinstance(result, Published)
        coverage = [
            coverage_entry(criterion, "UNSATISFIED") for criterion in prefix.criteria
        ]

        rejected = self.publish_verification(prefix, result, coverage, "FAIL")
        self.assertIsInstance(rejected, Rejected)
        assert isinstance(rejected, Rejected)
        self.assertEqual(
            rejected.code, PublishRejectionCode.VERIFICATION_COVERAGE_MISMATCH
        )

        published = self.publish_verification(
            prefix,
            result,
            coverage,
            "FAIL",
            findings=[finding(criterion) for criterion in prefix.criteria],
        )
        self.assertIsInstance(published, Published)

    def test_finding_must_name_non_satisfied_criterion_and_match_counts(self) -> None:
        prefix = self.prefix()
        result = self.publish_result(prefix)
        self.assertIsInstance(result, Published)
        assert isinstance(result, Published)
        coverage = [
            coverage_entry(prefix.criteria[0], "UNSATISFIED"),
            coverage_entry(prefix.criteria[1], "SATISFIED", evidence_digest=OUTPUT_DIGEST),
        ]

        for bad_finding in (
            finding(prefix.criteria[1]),
            finding("Criterion does not exist"),
        ):
            with self.subTest(criterion=bad_finding["criterion"]):
                rejected = self.publish_verification(
                    prefix, result, coverage, "FAIL", findings=[bad_finding]
                )
                self.assertIsInstance(rejected, Rejected)
                assert isinstance(rejected, Rejected)
                self.assertEqual(
                    rejected.code, PublishRejectionCode.VERIFICATION_COVERAGE_MISMATCH
                )

    def test_duplicate_criteria_use_count_matching(self) -> None:
        prefix = self.prefix(["Duplicate criterion", "Duplicate criterion"])
        result = self.publish_result(prefix)
        self.assertIsInstance(result, Published)
        assert isinstance(result, Published)
        coverage = [
            coverage_entry("Duplicate criterion", "UNSATISFIED"),
            coverage_entry("Duplicate criterion", "UNSATISFIED"),
        ]
        published = self.publish_verification(
            prefix,
            result,
            coverage,
            "FAIL",
            findings=[finding("Duplicate criterion"), finding("Duplicate criterion")],
        )
        self.assertIsInstance(published, Published)

        prefix = self.prefix(["Duplicate criterion", "Duplicate criterion"])
        result = self.publish_result(prefix)
        self.assertIsInstance(result, Published)
        assert isinstance(result, Published)
        rejected = self.publish_verification(
            prefix,
            result,
            coverage,
            "FAIL",
            findings=[finding("Duplicate criterion")],
        )
        self.assertIsInstance(rejected, Rejected)
        assert isinstance(rejected, Rejected)
        self.assertEqual(
            rejected.code, PublishRejectionCode.VERIFICATION_COVERAGE_MISMATCH
        )

    def test_satisfied_evidence_class_is_pinned(self) -> None:
        prefix = self.prefix()
        result = self.publish_result(prefix)
        self.assertIsInstance(result, Published)
        assert isinstance(result, Published)
        wrong_class = [
            coverage_entry(
                criterion,
                "SATISFIED",
                evidence_digest=OUTPUT_DIGEST,
                evidence_class="other-evidence@1",
            )
            for criterion in prefix.criteria
        ]
        rejected = self.publish_verification(prefix, result, wrong_class, "PASS")
        self.assertIsInstance(rejected, Rejected)
        assert isinstance(rejected, Rejected)
        self.assertEqual(
            rejected.code, PublishRejectionCode.VERIFICATION_COVERAGE_MISMATCH
        )

        published = self.publish_verification(
            prefix,
            result,
            [
                coverage_entry(
                    criterion, "SATISFIED", evidence_digest=OUTPUT_DIGEST
                )
                for criterion in prefix.criteria
            ],
            "PASS",
        )
        self.assertIsInstance(published, Published)

    def test_verifier_profile_may_equal_attempt_profile(self) -> None:
        prefix = self.prefix()
        result = self.publish_result(prefix)
        self.assertIsInstance(result, Published)
        assert isinstance(result, Published)
        published = self.publish_verification(
            prefix,
            result,
            [
                coverage_entry(
                    criterion, "SATISFIED", evidence_digest=OUTPUT_DIGEST
                )
                for criterion in prefix.criteria
            ],
            "PASS",
            verifier_profile=RUNTIME_PROFILE_IDENTITY,
        )
        self.assertIsInstance(published, Published)


if __name__ == "__main__":
    unittest.main()
