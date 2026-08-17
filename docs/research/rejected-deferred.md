# Rejected and Deferred Ideas

## Rejected as authority
- chat history / pane scrollback
- agent self-reported completion
- runtime exit-zero alone
- heartbeat/liveness
- derived summaries
- model-created decisions without human approval
- mutable run-head/current-state as an independent operational authority

## Rejected as default architecture
- hundreds of globally visible skills
- command bodies duplicating skill logic
- one universal phase machine for every workflow
- model/runtime fallback after capability failure
- context inherited wholesale from conductor sessions
- implementation agent final-verifying itself
- automatic upstream skill promotion without pinned provenance and local regression/eval gates

## Deferred pending evidence
- arbitrary graph concurrency
- generalized resource locking beyond exact paths
- visual workflow editor as first milestone
- automatic continuous learning that promotes learned patterns to authority
- container/VM multi-tenant security guarantees

## Resolved after research
- state-authority choice: [ADR-0008](../adr/0008-run-state-authority.md) selects immutable Kernel-published transition lineage as the sole authoritative operational state; mutable run-head/current-state remains derived only

All of these remain researchable; none should disappear from history merely because the initial
integrated design does not use them.
