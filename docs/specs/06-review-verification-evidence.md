# Spec 06 — Review, Verification & Evidence

## Goal
Judge the exact produced snapshot against approved outcomes using independent evidence.

## Required behavior
- pre-execution plan checking and post-execution verification are separate
- implementer cannot final-verify its own work
- review/verify bind to exact HEAD/content identity
- spec compliance and code quality may be two sequential review profiles
- goal-backward verification starts from observable truths
- expected evidence sources are explicit; missing required evidence blocks PASS
- composite evidence may include tests, typecheck, build, DB diff, output diff, callback, visual/manual evidence
- manual evidence records scenario, observation, remaining uncertainty
- finding fingerprint/lineage prevents silent disappearance
- known-wrong mutation/self-test should validate critical verification harnesses

## Suggested verdicts
PASS / FAIL / BLOCKED / PARTIAL.
