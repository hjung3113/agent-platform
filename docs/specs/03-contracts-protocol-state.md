# Spec 03 — Contracts, Protocol & Run State

## Goal
Provide one durable, replayable protocol for request/workflow/task/attempt/evidence/finding/receipt lineage.

## Required behavior
- strict versioned schemas at admission
- Kernel-assigned durable identities for authoritative records
- immutable artifacts after publication
- protocol-defined canonical content digests
- explicit parent/source identity and digest bindings for every authoritative handoff
- typed rejection for malformed/stale/conflicting/mismatched candidates
- one single-writer authoritative publication boundary: Kernel
- task and attempt are separate lifecycle concepts
- runtime observations are facts, not verdicts
- findings never mutate in place; closure is successor/event lineage
- summaries/projections are derived and rebuildable
- runtime state is outside the checkout
- mixed-version parent/child handoffs fail closed unless an explicit compatibility or migration rule permits them
- a later artifact cannot silently substitute a different parent/source merely because it is newer or semantically similar

## Authoritative state model
The immutable transition lineage admitted and published by the Kernel is the sole authoritative operational run state.

A run-head/projection may be atomically replaced as a cache/checkpoint, but it is never authoritative and cannot introduce facts absent from the immutable lineage. Missing, stale, or conflicting projections are rebuilt from lineage.

Authoritative publication of an immutable transition is the protocol commit point. Projection updates follow that commit and are recoverable derived work.

## Replay and conflict invariants
- authoritative transitions contain deterministic ordering plus causal/predecessor information sufficient for replay
- replay of the same accepted lineage must derive the same state
- a publication candidate is validated against the exact predecessor lineage/state it claims to extend
- stale/conflicting publication attempts fail closed rather than overwrite or reinterpret newer state
- each retriable logical publication operation carries a stable idempotency identity independent of process/transport retries
- repeating the same logical publication cannot create duplicate authoritative facts; the same idempotency identity with conflicting content is rejected
- prepared/staged candidates remain non-authoritative until Kernel publication
- child artifacts are admissible only against the exact parent/source identities and digests declared by their contract

## Lifecycle distinctions
Failure, cancellation, retry, repair, replan, reconciliation, checkpoint, and terminal completion are semantically distinct protocol outcomes/transitions. Process disappearance alone does not imply any terminal state.

A Receipt is explicitly typed as `checkpoint` or `terminal`. A checkpoint Receipt records durable progress but never terminates the run; only a terminal Receipt establishes terminal run state.

See [ADR-0007](../adr/0007-run-state-authority.md) for the authority decision. Concrete persistence, fencing/CAS, canonicalization encoding, and filesystem crash-consistency mechanisms remain implementation concerns that require validation on supported platforms.
