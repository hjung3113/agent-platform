# Wiring Gap Register

| Gap | Severity | Current treatment |
|---|---|---|
| Event authority vs mutable run-state authority unresolved | CLOSED | ADR-0008: immutable Kernel-published transition lineage is authoritative; run-head is derived only |
| No implemented schema catalog yet | HIGH | contracts catalog first; schemas only with vertical slices |
| Deterministic eligibility semantics unspecified | CLOSED-DESIGN | Spec 04 now fixes authoritative inputs, canonical ordering, fail-closed ambiguity, and successor revision rules |
| Repair/retry/replan escalation semantics underspecified | CLOSED-DESIGN | Spec 04 distinguishes outcomes, requires bounded policy, and forbids infinite retry/repair/replan cycles |
| Fan-in conflict behavior underspecified | CLOSED-DESIGN | Spec 04 requires explicit inputs, merge strategy, conflict behavior, and merge authority |
| Plan Checker absent in earlier scaffold | CLOSED-DESIGN | explicit role exists; deterministic workflow/risk policy decides whether each exact revision requires an independent digest-bound check |
| Kernel/Host previously mixed with agent roles | CLOSED | moved to `src/` |
| Kernel vs orchestration publication boundary ambiguous | CLOSED-DESIGN | orchestration calculates deterministically; Kernel alone admits/publishes authoritative transitions |
| Context Compiler could become model-authored prompt glue | HIGH | deterministic subsystem + provenance contract |
| Reviewer vs Verifier overlap | MEDIUM | reviewer=quality/spec findings; verifier=acceptance verdict |
| Knowledge Curator might gain hidden decision authority | MEDIUM | proposal-only rule |
| Visual workflow editor could drift from kernel schema | MEDIUM | UI edits candidate contracts only |
| Upstream skill updates could silently change behavior | CLOSED-DESIGN | Spec 08 requires exact pin/content identity, license/local delta, behavior/eval gate, emitted drift validation, rollback, and forbids automatic promotion |
| Release authorization could be conflated with verified readiness | HIGH | Release Captain + separate policy |
| Parallel tasks may share logical resources despite path separation | CLOSED-DESIGN | Spec 04 requires logical resource identities/access modes; unknown overlap serializes or blocks; path separation alone is insufficient |
| Ambiguous crash/cancellation could admit conflicting successor work | CLOSED-DESIGN | reconciliation-required state blocks overlapping retry/successor/parallel work until authoritative resolution |
| Manual evidence can be vague/non-reproducible | MEDIUM | required scenario/observation/uncertainty metadata plus criterion-level evidence admissibility policy |

`CLOSED-DESIGN` means the normative architecture/specification is now explicit; corresponding implementation and verification work may still be outstanding.
