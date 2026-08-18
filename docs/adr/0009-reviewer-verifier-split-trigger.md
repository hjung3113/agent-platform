# ADR-0009 — Reviewer/Verifier Split Trigger and Independence Shape

Status: Accepted

## Context

The baseline profile collapses Reviewer (quality/spec judgement) and Verifier (acceptance/evidence
judgement) into one independent Verifier seat. `docs/reviews/wiring-gap-register.md` and
`docs/architecture/role-responsibility-map.md` said a split happens "when policy requires it" without
saying what triggers that policy, who computes it, or how the two seats should relate once split.

The risk a split is meant to close is confirmation bias: a judge who has already decided output is
good tends to read acceptance criteria more loosely. That risk determines the shape of the decision
below, not workload balancing.

## Decision

- The split trigger is a deterministic, per-Task risk-tier predicate, evaluated by the Kernel from
  admitted Task attributes (e.g. external-effect presence, capability-grant scope) at admission time —
  not a Planner/Architect self-reported risk profile, which would let the proposer route around the
  split it's meant to be checked by.
- It reuses the same risk-tier computation Plan Check admission uses (`docs/specs/04-workflow-orchestration.md`),
  but at its own independent threshold — one predicate output, two separately tunable gates.
- The binding unit is the Task, not the Workflow Revision, so a low-risk documentation task and a
  high-risk deploy task in the same revision are judged independently.
- When split, Reviewer and Verifier run with independent, blind attempt/execution identities in
  parallel. Sequential execution was rejected: whichever seat runs first would anchor the second,
  reintroducing the same bias the split exists to remove.
- A Reviewer finding blocks on equal footing with a Verifier finding (same Finding lineage/closure
  rules) — an advisory-only Reviewer finding would make the split cosmetic.

## Consequences

- Kernel admission must be able to compute risk tier from Task attributes before Reviewer/Verifier
  seat assignment, not just before Plan Check gating.
- Reviewer and Verifier attempts for a split Task cannot share or sequence context; the runtime must
  support two genuinely independent attempt/execution identities per Task, not a role/profile switch
  inside one execution context.
- `docs/specs/06-review-verification-evidence.md` and `docs/reviews/wiring-gap-register.md` record the
  resulting normative rules.
