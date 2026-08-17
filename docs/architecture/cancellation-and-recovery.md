# Cancellation and Recovery — Draft

Cancellation is not equivalent to failure.

Required states/concepts:
- cancellation_requested
- cancellation_confirmed
- cancellation_unconfirmed / reconciliation_required
- runtime_failed
- blocked

Recovery rules:
- never assume a killed/vanished process completed or failed cleanly
- reconcile runtime observation, workspace/content identity, and authoritative publication lineage
- never reuse an attempt identity after an ambiguous crash
- duplicate resume/observe commands must be idempotent
- prepared but unpublished artifacts are non-authoritative until Kernel publication
- recovery derives state from authoritative immutable lineage; `head.json` or other projections may assist but never override lineage
- retry, repair, replan, cancellation reconciliation, and terminal completion remain distinct transitions

When cancellation races with runtime completion or result publication, the Kernel records the observed facts separately and derives the next protocol transition from their accepted ordering/causal lineage; cancellation does not retroactively erase an already-authoritative fact.

ADR-0007 fixes run-state authority and commit semantics. Concrete durable-write, fencing/CAS, process-reconciliation, and platform crash-consistency mechanisms remain implementation concerns that must be validated before resume/recovery is considered complete.
