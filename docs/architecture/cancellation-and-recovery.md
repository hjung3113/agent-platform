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
- reconcile runtime observation, workspace/content identity, and publication state
- never reuse an attempt identity after an ambiguous crash
- duplicate resume/observe commands must be idempotent
- prepared but unpublished artifacts are non-authoritative until Kernel publication

Detailed crash semantics depend on the unresolved run-state authority ADR/spike.
