# Artifact Retention — Draft

Classes:
- durable authority: decisions, workflow revisions, terminal receipts — long-lived
- verification lineage: reviews/evidence/findings — retain while audit/replay is required
- runtime diagnostics: stdout/stderr/heartbeats — shorter retention, non-authoritative
- workspaces/staging — disposable after terminal publication and retention checks
- derived indexes — delete/regenerate freely

## Replay-support coupling

Retention applies to interpretability as well as bytes.

- if a retained authoritative artifact is reachable from a retained run, decision, receipt, or verification lineage, its protocol/schema reader must remain available
- immutable compatibility and migration rule versions referenced by retained cross-version lineage must remain available for replay
- a reader or rule version cannot be retired merely because a newer runtime, adapter, schema, or protocol has shipped
- retirement is permitted only after reference tracing proves no retained authoritative lineage depends on that reader/rule version
- migrated successors do not by themselves make source artifacts or source readers unreachable; the original lineage remains authoritative history

Do not implement automatic garbage collection until reference tracing proves an artifact is unreachable from retained decisions/runs/receipts and confirms that removing associated reader/rule support cannot break retained replay.
