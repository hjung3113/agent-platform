# ADR-0007 — Immutable Transition Lineage Is Authoritative Run State

Status: Accepted

## Context

The source research contained two competing operational-state patterns:

1. append-only/immutable transition records are authoritative and current state is replayed, or
2. an atomically replaced mutable `run.json` acts as the operational commit point.

Keeping both patterns valid would make workflow eligibility and recovery depend on which representation a component happened to read. That violates deterministic orchestration and creates ambiguous crash recovery.

## Decision

The immutable transition lineage admitted and published by the Kernel is the sole authoritative operational run state.

- Authoritative transitions are immutable after publication.
- Kernel publication of a transition is the protocol commit point.
- A run-head/current-state document may exist only as a derived checkpoint or cache.
- A projection cannot introduce facts absent from authoritative lineage.
- Missing, stale, corrupt, or conflicting projections are rebuilt or rejected from lineage rather than preferred over it.
- Authoritative transitions carry deterministic causal/ordering information sufficient to replay the same accepted lineage into the same state.
- Prepared candidates and host/runtime observations remain non-authoritative until admitted by the appropriate publication contract.

## Consequences

- Workflow eligibility, retry/replan decisions, cancellation recovery, and terminal state are derived from one authority source.
- Projection loss is recoverable and cannot change semantic state.
- Duplicate/stale publication attempts must be handled idempotently or rejected without creating competing facts.
- Concrete persistence, compare-and-swap/fencing, storage layout, and platform crash-consistency mechanisms remain implementation decisions and must preserve this authority model.

## Rejected alternative

A mutable run-state file is not accepted as an independent or competing authority source. It may still be used as an optimization if it is fully derivable from immutable lineage.
