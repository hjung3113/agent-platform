# ADR-0007 — Immutable event lineage is authoritative run state

Status: Superseded by [ADR-0008](0008-run-state-authority.md)

## Supersession
ADR-0008 is the canonical run-state authority decision. This ADR remains as historical decision context and must not be referenced as the current normative authority record.

## Decision
Operational run state has exactly one authoritative interpretation: the immutable transition lineage admitted and published by the Kernel.

- Host/adapters/agents may produce observations or candidate records, but they do not publish authoritative run-state records directly.
- A transition becomes authoritative only when the Kernel admits and publishes it.
- `head.json`, indexes, dashboards, summaries, and other projections are derived state only. They may accelerate recovery or reads but never introduce facts absent from the authoritative lineage.
- The authoritative commit point is publication of the immutable transition record. Projection updates occur after that commit and may be rebuilt after failure.
- Authoritative transitions carry deterministic ordering/causal information sufficient to replay the same derived state and reject stale/conflicting publication attempts.
- Duplicate publication attempts must resolve idempotently; a retry cannot create a second authoritative fact for the same admitted operation.

## Consequences
- Recovery validates/replays the immutable lineage and treats a missing, stale, or conflicting projection as rebuildable cache corruption rather than a second source of truth.
- Runtime completion, cancellation, retry, repair, and replan are recorded as distinct facts/transitions rather than inferred from process disappearance or mutable status alone.
- Prepared/staged artifacts remain non-authoritative until Kernel publication.

## Deferred implementation proof
The concrete durable-write, atomic-replace, fencing/CAS, and filesystem crash-consistency mechanisms are implementation decisions that must be validated on supported platforms before resume/recovery is considered complete.
