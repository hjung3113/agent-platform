# Spec 03 — Contracts, Protocol & Run State

## Goal
Provide one durable, replayable protocol for request/workflow/task/attempt/evidence/finding/receipt lineage.

## Required behavior
- strict versioned schemas at admission
- Kernel-assigned durable identities for authoritative records
- immutable artifacts after publication
- digest-bound references
- typed rejection for malformed/stale/conflicting candidates
- one single-writer authoritative publication boundary: Kernel
- task and attempt are separate lifecycle concepts
- runtime observations are facts, not verdicts
- findings never mutate in place; closure is successor/event lineage
- summaries/projections are derived and rebuildable
- runtime state is outside the checkout

## Authoritative state model
The immutable transition lineage admitted and published by the Kernel is the sole authoritative operational run state.

A run-head/projection may be atomically replaced as a cache/checkpoint, but it is never authoritative and cannot introduce facts absent from the immutable lineage. Missing, stale, or conflicting projections are rebuilt from lineage.

Authoritative publication of an immutable transition is the protocol commit point. Projection updates follow that commit and are recoverable derived work.

## Replay and conflict invariants
- authoritative transitions contain deterministic ordering/causal information sufficient for replay
- replay of the same accepted lineage must derive the same state
- stale/conflicting publication attempts fail closed rather than overwrite newer state
- duplicate publication attempts are idempotent and cannot create duplicate authoritative facts
- prepared/staged candidates remain non-authoritative until Kernel publication

## Lifecycle distinctions
Failure, cancellation, retry, repair, replan, reconciliation, and terminal completion are semantically distinct protocol outcomes/transitions. Process disappearance alone does not imply any terminal state.

See ADR-0007 for the authority decision. Concrete persistence, fencing/CAS, and filesystem crash-consistency mechanisms remain implementation concerns that require validation on supported platforms.
