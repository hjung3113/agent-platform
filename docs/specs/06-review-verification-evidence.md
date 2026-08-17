# Spec 06 — Review, Verification & Evidence

## Goal
Judge the exact produced snapshot against approved outcomes using independent, admissible evidence.

## Verification subject
- verification binds to a canonical Snapshot Manifest/content identity, not a mutable workspace label or repository HEAD alone
- the snapshot identity covers all outcome-relevant workspace/output content and, when applicable, generated/nested content plus execution-context identities needed to interpret evidence
- Result, Review, Verification, Evidence, Finding resolution, Receipt, and Release lineage must reference the exact subject snapshot they concern
- evidence from another snapshot, attempt, input set, or incompatible execution environment is stale unless its evidence contract explicitly proves that reuse is invariant-safe

## Reviewer / Verifier independence
- pre-execution Plan Check and post-execution verification are separate judgements
- an Implementer cannot final-verify its own produced snapshot
- final verification must have a distinct attempt/execution identity from the producing implementation attempt; switching only the role/profile inside the same execution context does not establish independence
- implementer result claims are candidate claims, not acceptance evidence unless independently observed or reproduced through an admissible evidence source
- spec-compliance and code-quality review may be separate sequential review profiles, but neither substitutes for acceptance verification

## Acceptance coverage and verdict admissibility
- goal-backward verification starts from declared acceptance criteria and observable truths
- every required acceptance criterion has an explicit coverage entry with status and supporting evidence references
- criterion status distinguishes at least `SATISFIED`, `UNSATISFIED`, `BLOCKED`, and `UNPROVEN`
- missing required evidence or an unproven required criterion blocks PASS
- PASS is admissible only when every required criterion is satisfied by admissible evidence and no blocking Finding remains open for the subject snapshot
- a Verifier proposes semantic judgements; the Kernel deterministically validates verdict admissibility from criterion coverage, evidence bindings, independence, and open-finding state rather than trusting a verdict string alone
- `PARTIAL` is informative progress, never terminal success

## Evidence provenance and freshness
- expected evidence sources are explicit per criterion or verification policy
- composite evidence may include tests, typecheck, build, DB diff, output diff, callback, visual, and manual evidence
- every Evidence record identifies its subject snapshot, source/producer, relevant attempt or runtime observation, collection time, execution/tool context, and raw result identity when available
- freshness/compatibility rules are defined by evidence type; stale, ambiguous, mismatched, or incompatible evidence cannot satisfy a required criterion
- flaky/retried evidence preserves failed observations and retry policy rather than presenting only the final successful attempt
- manual evidence records scenario, observation, subject identity, remaining uncertainty, and the human/agent source of the observation

## Evidence admissibility policy
- an acceptance criterion or verification policy declares the evidence classes it accepts and any minimum trust, independence, environment, or reproduction requirement needed to satisfy that criterion
- evidence strength is determined by the admitted evidence policy and provenance, not by producer role, prose confidence, or a model's assertion that the evidence is sufficient
- model inference, self-report, or derived summary cannot satisfy a criterion that requires direct observation, executable test/build output, exact diff, or explicit human evidence unless the policy explicitly permits that evidence class
- composite verification cannot silently promote weaker evidence into a stronger class; any substitution or degraded evidence mode must be explicitly admitted and remain visible in criterion coverage

## Finding lineage and closure
- a Finding has durable identity/fingerprint and cannot disappear merely because a repair attempt or later review omits it
- repair attempts create successor lineage; they do not mutate away prior Findings
- closure requires an explicit resolution transition bound to the fixing snapshot and resolution evidence
- unresolved, reopened, superseded, and resolved states remain traceable from immutable lineage
- a blocking Finding prevents PASS until an admissible closure transition is published

## Verification harness self-validation
Critical verification paths should be validated with known-wrong mutations/self-tests that demonstrate rejection of at least:
- wrong or stale snapshot bindings
- missing required evidence
- uncovered required acceptance criteria
- implementer self-verification through execution/profile reuse
- silently dropped unresolved Findings
- intentionally incorrect output that the verifier is expected to reject

## Suggested verdicts
PASS / FAIL / BLOCKED / PARTIAL.
