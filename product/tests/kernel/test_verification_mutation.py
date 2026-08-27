from __future__ import annotations

import subprocess
import tempfile
import unittest
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable

from execution import host
from execution.attempt import build_attempt_packet
from kernel.canonical import content_digest
from kernel.protocol import (
    ContractKind,
    ParsedCandidate,
    ProtocolRejectionCode,
    read_candidate,
)
from kernel.protocol_v1 import (
    PROTOCOL_VERSION,
    AttemptPacketV1,
    CoverageEntryV1,
    FindingV1,
    RequestV1,
    ResultV1,
    RuntimeObservationV1,
    TaskV1,
    VerificationV1,
    WorkflowRevisionV1,
    RESULT_SNAPSHOT_EVIDENCE_CLASS,
    schema_version_for_kind,
)
from kernel.publish import Published, PublishRejectionCode, Rejected, publish

FIXTURE_BINARY = (
    Path(__file__).resolve().parent.parent
    / "execution"
    / "fixtures"
    / "fake_opencode"
    / "fake_opencode.py"
)
DIRECTIVE_NAME = "fake-opencode-directive.txt"
IMPLEMENTER_IDENTITY = "implementer-m6"
VERIFIER_IDENTITY = "verifier-m6"
TASK = TaskV1(
    task_id="task-m6-mutation",
    objective="Run the hardened mutation fixture",
    acceptance_criteria=("Criterion one", "Criterion two"),
    depends_on=(),
)
REQUEST = RequestV1(
    objective="Exercise M6 through the real Host producer",
    scope=("docs/plans/active/m6-verification-evidence-hardening.md",),
    acceptance_criteria=("The real producer path is exercised",),
)
WRONG_DIGEST = content_digest({"fixture": "m6-wrong-evidence"})


def as_candidate(contract_kind: str, typed: object) -> ParsedCandidate:
    result = read_candidate(
        {
            "contract_kind": contract_kind,
            "protocol_version": PROTOCOL_VERSION,
            "schema_version": schema_version_for_kind(ContractKind(contract_kind)),
            "payload": typed.to_canonical_value(),
        }
    )
    assert result.ok, result.reason
    return result.value


def read_payload(contract_kind: str, payload: dict) -> object:
    result = read_candidate(
        {
            "contract_kind": contract_kind,
            "protocol_version": PROTOCOL_VERSION,
            "schema_version": schema_version_for_kind(ContractKind(contract_kind)),
            "payload": payload,
        }
    )
    return result


def read_schema_one_payload(contract_kind: str, payload: dict) -> ParsedCandidate:
    result = read_candidate(
        {
            "contract_kind": contract_kind,
            "protocol_version": PROTOCOL_VERSION,
            "schema_version": 1,
            "payload": payload,
        }
    )
    assert result.ok, result.reason
    return result.value


def open_finding(criterion: str, description: str = "Criterion did not pass") -> FindingV1:
    return FindingV1(
        criterion=criterion,
        fingerprint=content_digest(
            {"criterion": criterion, "description": description}
        ),
        description=description,
        state="OPEN",
        predecessor=None,
    )


@dataclass(frozen=True)
class RealPrefix:
    run_id: str
    attempt: Published
    attempt_value: AttemptPacketV1
    result_value: ResultV1


class VerificationMutationTests(unittest.TestCase):
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
        self._git(self.workspace_root, "commit", "-m", "initial M6 mutation fixture")
        (self.workspace_root / DIRECTIVE_NAME).write_text(
            "noop\n", encoding="utf-8"
        )
        self.counter = 0

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
        self._git(path, "config", "user.email", "m6-tests@example.invalid")
        self._git(path, "config", "user.name", "M6 Mutation Tests")

    def build_prefix(self) -> RealPrefix:
        self.counter += 1
        key = f"mutation-{self.counter}"
        request_published = publish(
            self.state, None, as_candidate("request", REQUEST), None, f"{key}-request"
        )
        self.assertIsInstance(request_published, Published)
        assert isinstance(request_published, Published)
        workflow_value = WorkflowRevisionV1(
            request=request_published.record_ref,
            tasks=(TASK,),
        )
        workflow_published = publish(
            self.state,
            request_published.run_id,
            as_candidate("workflow_revision", workflow_value),
            request_published.record_ref,
            f"{key}-workflow",
        )
        self.assertIsInstance(workflow_published, Published)
        assert isinstance(workflow_published, Published)
        attempt_value = build_attempt_packet(
            workflow_revision_ref=workflow_published.record_ref,
            task_id=TASK.task_id,
            implementer_identity=IMPLEMENTER_IDENTITY,
            state=self.state,
            run_id=request_published.run_id,
            task=TASK,
            workspace_root=self.workspace_root,
            opencode_binary_path=str(FIXTURE_BINARY),
        )
        attempt_published = publish(
            self.state,
            request_published.run_id,
            as_candidate("attempt_packet", attempt_value),
            workflow_published.record_ref,
            f"{key}-attempt",
        )
        self.assertIsInstance(attempt_published, Published)
        assert isinstance(attempt_published, Published)
        result_value = host.execute(
            attempt_published.record_ref,
            attempt_value,
            self.workspace_root,
            str(FIXTURE_BINARY),
            TASK,
            self.state,
            request_published.run_id,
        )
        self.assertEqual(
            result_value.observation.runtime_identity,
            attempt_value.runtime_capability_profile_identity,
        )
        return RealPrefix(
            run_id=request_published.run_id,
            attempt=attempt_published,
            attempt_value=attempt_value,
            result_value=result_value,
        )

    def publish_result(self, prefix: RealPrefix, result_value: ResultV1 | None = None):
        self.counter += 1
        value = prefix.result_value if result_value is None else result_value
        return publish(
            self.state,
            prefix.run_id,
            as_candidate("result", value),
            prefix.attempt.record_ref,
            f"mutation-{self.counter}-result",
        )

    def base_verification(
        self, prefix: RealPrefix, result: Published
    ) -> VerificationV1:
        coverage = tuple(
            CoverageEntryV1(
                criterion=criterion,
                status="SATISFIED",
                evidence_digest=prefix.result_value.output_snapshot_digest,
                evidence_class=RESULT_SNAPSHOT_EVIDENCE_CLASS,
            )
            for criterion in TASK.acceptance_criteria
        )
        return VerificationV1(
            result=result.record_ref,
            verifier_identity=VERIFIER_IDENTITY,
            verifier_runtime_capability_profile_identity=(
                prefix.attempt_value.runtime_capability_profile_identity
            ),
            verifier_execution_identity=content_digest(
                {"fixture": "verifier-execution-m6"}
            ),
            coverage=coverage,
            verdict="PASS",
            findings=(),
        )

    def publish_verification(
        self, prefix: RealPrefix, result: Published, value: VerificationV1
    ):
        self.counter += 1
        return publish(
            self.state,
            prefix.run_id,
            as_candidate("verification", value),
            result.record_ref,
            f"mutation-{self.counter}-verification",
        )

    def publish_valid_sibling(self) -> None:
        prefix = self.build_prefix()
        result = self.publish_result(prefix)
        self.assertIsInstance(result, Published)
        assert isinstance(result, Published)
        verification = self.publish_verification(
            prefix, result, self.base_verification(prefix, result)
        )
        self.assertIsInstance(verification, Published)

    def assert_verification_mutation(
        self,
        mutate: Callable[[dict], None],
        expected_code: PublishRejectionCode,
    ) -> None:
        self.publish_valid_sibling()
        prefix = self.build_prefix()
        result = self.publish_result(prefix)
        self.assertIsInstance(result, Published)
        assert isinstance(result, Published)
        payload = self.base_verification(prefix, result).to_canonical_value()
        mutate(payload)
        parsed = read_payload("verification", payload)
        self.assertTrue(parsed.ok, parsed.reason)
        rejected = self.publish_verification(prefix, result, parsed.value.value)
        self.assertIsInstance(rejected, Rejected)
        assert isinstance(rejected, Rejected)
        self.assertEqual(rejected.code, expected_code)

    def test_wrong_evidence_digest_rejects(self) -> None:
        self.assert_verification_mutation(
            lambda payload: payload["coverage"][0].update(
                evidence_digest=WRONG_DIGEST
            ),
            PublishRejectionCode.VERIFICATION_COVERAGE_MISMATCH,
        )

    def test_wrong_evidence_class_rejects(self) -> None:
        self.assert_verification_mutation(
            lambda payload: payload["coverage"][0].update(
                evidence_class="other-evidence@1"
            ),
            PublishRejectionCode.VERIFICATION_COVERAGE_MISMATCH,
        )

    def test_self_verification_rejects(self) -> None:
        self.assert_verification_mutation(
            lambda payload: payload.update(verifier_identity=IMPLEMENTER_IDENTITY),
            PublishRejectionCode.SELF_VERIFICATION_REJECTED,
        )

    def test_verifier_execution_identity_collision_rejects(self) -> None:
        self.publish_valid_sibling()
        prefix = self.build_prefix()
        result = self.publish_result(prefix)
        self.assertIsInstance(result, Published)
        assert isinstance(result, Published)
        payload = self.base_verification(prefix, result).to_canonical_value()
        payload["verifier_execution_identity"] = (
            prefix.result_value.observation.execution_identity
        )
        parsed = read_payload("verification", payload)
        self.assertTrue(parsed.ok, parsed.reason)
        rejected = self.publish_verification(prefix, result, parsed.value.value)
        self.assertIsInstance(rejected, Rejected)
        assert isinstance(rejected, Rejected)
        self.assertEqual(
            rejected.code, PublishRejectionCode.SELF_VERIFICATION_REJECTED
        )

    def test_missing_finding_for_non_satisfied_coverage_rejects(self) -> None:
        def mutate(payload: dict) -> None:
            payload["coverage"][0].update(status="UNSATISFIED", evidence_digest=None)
            payload.update(verdict="FAIL")

        self.assert_verification_mutation(
            mutate, PublishRejectionCode.VERIFICATION_COVERAGE_MISMATCH
        )

    def test_finding_naming_satisfied_criterion_rejects(self) -> None:
        def mutate(payload: dict) -> None:
            payload["coverage"][0].update(status="UNSATISFIED", evidence_digest=None)
            payload.update(
                verdict="FAIL",
                findings=[open_finding(TASK.acceptance_criteria[1]).to_canonical_value()],
            )

        self.assert_verification_mutation(
            mutate, PublishRejectionCode.VERIFICATION_COVERAGE_MISMATCH
        )

    def test_pass_with_findings_rejects_at_reader(self) -> None:
        prefix = self.build_prefix()
        result = self.publish_result(prefix)
        self.assertIsInstance(result, Published)
        assert isinstance(result, Published)
        payload = self.base_verification(prefix, result).to_canonical_value()
        payload["findings"] = [open_finding(TASK.acceptance_criteria[0]).to_canonical_value()]
        parsed = read_payload("verification", payload)
        self.assertEqual(
            parsed.rejection_code, ProtocolRejectionCode.MALFORMED_PAYLOAD
        )

    def test_malformed_verifier_profile_identity_rejects_at_reader(self) -> None:
        prefix = self.build_prefix()
        result = self.publish_result(prefix)
        self.assertIsInstance(result, Published)
        assert isinstance(result, Published)
        payload = self.base_verification(prefix, result).to_canonical_value()
        payload["verifier_runtime_capability_profile_identity"] = "not-a-digest"
        parsed = read_payload("verification", payload)
        self.assertEqual(
            parsed.rejection_code, ProtocolRejectionCode.MALFORMED_PAYLOAD
        )

    def test_malformed_verifier_execution_identity_rejects_at_reader(self) -> None:
        prefix = self.build_prefix()
        result = self.publish_result(prefix)
        self.assertIsInstance(result, Published)
        assert isinstance(result, Published)
        payload = self.base_verification(prefix, result).to_canonical_value()
        payload["verifier_execution_identity"] = "not-a-digest"
        parsed = read_payload("verification", payload)
        self.assertEqual(
            parsed.rejection_code, ProtocolRejectionCode.MALFORMED_PAYLOAD
        )

    def test_malformed_observation_execution_identity_rejects_at_reader(self) -> None:
        prefix = self.build_prefix()
        payload = prefix.result_value.to_canonical_value()
        payload["observation"]["execution_identity"] = "not-a-digest"
        parsed = read_payload("result", payload)
        self.assertEqual(
            parsed.rejection_code, ProtocolRejectionCode.MALFORMED_PAYLOAD
        )

    def test_result_environment_identity_mismatch_rejects(self) -> None:
        self.publish_valid_sibling()
        prefix = self.build_prefix()
        mutated = replace(
            prefix.result_value,
            observation=RuntimeObservationV1(
                runtime_identity=WRONG_DIGEST,
                output_snapshot_digest=prefix.result_value.output_snapshot_digest,
                execution_identity=prefix.result_value.observation.execution_identity,
            ),
        )
        rejected = self.publish_result(prefix, mutated)
        self.assertIsInstance(rejected, Rejected)
        assert isinstance(rejected, Rejected)
        self.assertEqual(
            rejected.code, PublishRejectionCode.RESULT_ENVIRONMENT_BINDING_MISMATCH
        )

    def test_stale_schema_result_and_verification_reject_typed(self) -> None:
        prefix = self.build_prefix()
        output_digest = prefix.result_value.output_snapshot_digest
        legacy_result = read_schema_one_payload(
            "result",
            {
                "attempt": prefix.attempt.record_ref.to_canonical_value(),
                "output_snapshot_digest": output_digest,
                "observation": {
                    "runtime_identity": prefix.result_value.observation.runtime_identity,
                    "output_snapshot_digest": output_digest,
                },
            },
        )
        rejected_result = publish(
            self.state,
            prefix.run_id,
            legacy_result,
            prefix.attempt.record_ref,
            "mutation-stale-result",
        )
        self.assertIsInstance(rejected_result, Rejected)
        assert isinstance(rejected_result, Rejected)
        self.assertEqual(
            rejected_result.code, PublishRejectionCode.STALE_SCHEMA_VERSION
        )

        result = self.publish_result(prefix)
        self.assertIsInstance(result, Published)
        assert isinstance(result, Published)
        legacy_verification = read_schema_one_payload(
            "verification",
            {
                "result": result.record_ref.to_canonical_value(),
                "verifier_identity": VERIFIER_IDENTITY,
                "coverage": [
                    {
                        "criterion": criterion,
                        "status": "SATISFIED",
                        "evidence_digest": output_digest,
                    }
                    for criterion in TASK.acceptance_criteria
                ],
                "verdict": "PASS",
                "findings": [],
            },
        )
        rejected_verification = publish(
            self.state,
            prefix.run_id,
            legacy_verification,
            result.record_ref,
            "mutation-stale-verification",
        )
        self.assertIsInstance(rejected_verification, Rejected)
        assert isinstance(rejected_verification, Rejected)
        self.assertEqual(
            rejected_verification.code, PublishRejectionCode.STALE_SCHEMA_VERSION
        )


if __name__ == "__main__":
    unittest.main()
