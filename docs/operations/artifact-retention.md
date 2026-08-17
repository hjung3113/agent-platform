# Artifact Retention — Draft

Classes:
- durable authority: decisions, workflow revisions, terminal receipts — long-lived
- verification lineage: reviews/evidence/findings — retain while audit/replay is required
- runtime diagnostics: stdout/stderr/heartbeats — shorter retention, non-authoritative
- workspaces/staging — disposable after terminal publication and retention checks
- derived indexes — delete/regenerate freely

Do not implement automatic garbage collection until reference tracing proves an artifact is unreachable
from retained decisions/runs/receipts.
