# Spec 03 — Contracts, Protocol & Run State

## Goal
Provide one durable, replayable protocol for request/workflow/task/attempt/evidence/finding/receipt lineage.

## Required behavior
- strict versioned schemas at admission
- host/kernel-assigned identities for authoritative records
- immutable artifacts after publication
- digest-bound references
- typed rejection for malformed/stale/conflicting candidates
- one single-writer publication boundary
- task and attempt are separate lifecycle concepts
- runtime observations are facts, not verdicts
- findings never mutate in place; closure is successor/event lineage
- summaries/projections are derived and rebuildable
- runtime state is outside the checkout

## Initial state model decision
Authoritative transition records are immutable; a run-head/projection may be atomically replaced as a cache/checkpoint but cannot introduce facts absent from the immutable lineage.

This decision should be spiked before implementation because source repositories contain two competing patterns: event-replay-first and mutable-run-state-as-commit-point.
