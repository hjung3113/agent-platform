"""M6 stub Verifier: digest-equality verification of a published Result.

No semantic judgement happens here — each acceptance criterion is compared
via plain digest equality between the Result's output snapshot digest and the
expected output digest, and the verdict is the total function of coverage
defined by the M2 plan (§3). Real evidence policy is M6.
"""

from __future__ import annotations

from kernel.canonical import content_digest
from kernel.protocol import RecordRef
from kernel.protocol_v1 import (
    RESULT_SNAPSHOT_EVIDENCE_CLASS,
    CoverageEntryV1,
    FindingV1,
    TaskV1,
    VerificationV1,
)


def stub_verify(
    result_ref: RecordRef,
    result_output_snapshot_digest: str,
    task: TaskV1,
    verifier_identity: str,
    verifier_runtime_capability_profile_identity: str,
    expected_output_digest: str,
) -> VerificationV1:
    """Build a Verification candidate by plain digest equality per criterion.

    Coverage has one entry per ``task.acceptance_criteria`` item, same order:
    SATISFIED with the Result's output snapshot digest as evidence when the
    digests match, else UNSATISFIED with no evidence. Every entry carries the
    M6 evidence-class identity. Verdict is PASS iff coverage is non-empty and
    every entry is SATISFIED, else FAIL (this stub never produces BLOCKED).
    """

    matched = result_output_snapshot_digest == expected_output_digest
    coverage = tuple(
        CoverageEntryV1(
            criterion=criterion,
            status="SATISFIED" if matched else "UNSATISFIED",
            evidence_digest=result_output_snapshot_digest if matched else None,
            evidence_class=RESULT_SNAPSHOT_EVIDENCE_CLASS,
        )
        for criterion in task.acceptance_criteria
    )
    verdict = "PASS" if coverage and matched else "FAIL"
    findings: tuple[FindingV1, ...] = ()
    if verdict != "PASS":
        findings = tuple(
            FindingV1(
                criterion=criterion,
                fingerprint=content_digest(
                    {
                        "criterion": criterion,
                        "description": f"criterion unsatisfied: {criterion}",
                    }
                ),
                description=f"criterion unsatisfied: {criterion}",
                state="OPEN",
                predecessor=None,
            )
            for criterion in task.acceptance_criteria
        )
    return VerificationV1(
        result=result_ref,
        verifier_identity=verifier_identity,
        verifier_runtime_capability_profile_identity=(
            verifier_runtime_capability_profile_identity
        ),
        coverage=coverage,
        verdict=verdict,
        findings=findings,
    )
