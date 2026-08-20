from __future__ import annotations

import unittest

from kernel.canonical import content_digest
from kernel.protocol import ContractKind, RecordRef
from kernel.protocol_v1 import (
    TaskV1,
    VerificationV1,
    read_verification_v1,
    verification_v1_content_digest,
)
from verification.stub_verifier import stub_verify

RESULT_REF = RecordRef(
    contract_kind=ContractKind.RESULT.value,
    record_id="rs_1",
    content_digest="sha256:agent-platform-json-v1:" + "a" * 64,
)
TASK = TaskV1(
    task_id="task-1",
    objective="do the one thing",
    acceptance_criteria=("criterion one", "criterion two"),
)
EXPECTED = content_digest({"fixture": "expected-output"})


def _output_digest(seed: str) -> str:
    return content_digest({"fixture": "actual-output", "seed": seed})


class StubVerifyTest(unittest.TestCase):
    def test_pass_when_digests_match(self) -> None:
        verification = stub_verify(
            RESULT_REF, EXPECTED, TASK, "verifier-1", EXPECTED
        )
        self.assertEqual(verification.verdict, "PASS")
        self.assertEqual(verification.findings, ())
        self.assertEqual(len(verification.coverage), len(TASK.acceptance_criteria))
        for entry, criterion in zip(verification.coverage, TASK.acceptance_criteria):
            self.assertEqual(entry.criterion, criterion)
            self.assertEqual(entry.status, "SATISFIED")
            self.assertEqual(entry.evidence_digest, EXPECTED)

    def test_fail_with_findings_when_digests_differ(self) -> None:
        actual = _output_digest("not-expected")
        verification = stub_verify(
            RESULT_REF, actual, TASK, "verifier-1", EXPECTED
        )
        self.assertEqual(verification.verdict, "FAIL")
        self.assertTrue(verification.findings)
        for entry in verification.coverage:
            self.assertEqual(entry.status, "UNSATISFIED")
            self.assertIsNone(entry.evidence_digest)

    def test_binds_result_ref_and_verifier_identity(self) -> None:
        verification = stub_verify(
            RESULT_REF, EXPECTED, TASK, "verifier-1", EXPECTED
        )
        self.assertEqual(verification.result, RESULT_REF)
        self.assertEqual(verification.verifier_identity, "verifier-1")

    def test_reads_back_through_strict_reader(self) -> None:
        actual = _output_digest("not-expected")
        for output_digest in (EXPECTED, actual):
            verification = stub_verify(
                RESULT_REF, output_digest, TASK, "verifier-1", EXPECTED
            )
            outcome = read_verification_v1(verification.to_canonical_value())
            self.assertEqual(outcome.value, verification)

    def test_content_digest_deterministic(self) -> None:
        first = stub_verify(RESULT_REF, EXPECTED, TASK, "verifier-1", EXPECTED)
        second = stub_verify(RESULT_REF, EXPECTED, TASK, "verifier-1", EXPECTED)
        self.assertIsInstance(first, VerificationV1)
        self.assertEqual(
            verification_v1_content_digest(first),
            verification_v1_content_digest(second),
        )


if __name__ == "__main__":
    unittest.main()
