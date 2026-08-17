# Cancellation and Recovery

Cancellation is not equivalent to failure.

Required states/concepts:
- cancellation_requested
- cancellation_confirmed
- cancellation_unconfirmed / reconciliation_required
- runtime_failed
- blocked

## Recovery authority
Per [ADR-0008](../adr/0008-run-state-authority.md), recovery derives semantic state from immutable Kernel-published transition lineage. A mutable run-head or runtime process observation cannot override that lineage.

## Recovery rules
- never assume a killed/vanished process completed or failed cleanly
- reconcile runtime observation, workspace/content identity, side-effect/resource state, and authoritative publication state
- never reuse an attempt identity after an ambiguous crash
- duplicate resume/observe commands must be idempotent
- prepared but unpublished artifacts are non-authoritative until Kernel publication
- `reconciliation_required` is not retryable success/failure; it blocks conflicting retry, successor, and parallel work until an authoritative reconciliation transition resolves the ambiguity
- cancellation, runtime failure, retry, repair, replan, blocked, and terminal completion remain distinct transitions

When cancellation races with runtime completion or result publication, accepted observations remain separate immutable facts. The Kernel resolves the next state from their authoritative causal/order lineage; cancellation does not retroactively erase an already-published completion/result fact.

Concrete process fencing, storage primitives, and crash-consistency mechanisms are implementation concerns, but they must preserve these semantic rules on every supported platform.
