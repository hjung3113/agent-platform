# opencode-orchestrated-agent-workflow

Status: PRIMARY SOURCE / CONFLICT SOURCE

Evidence:
- `docs/design/task-graph.md`: graph revisions, Task vs Attempt, structural validation,
  resource conflicts, replan as successor revision.
- `docs/design/file-protocol.md`: immutable artifacts, staging, kernel publication,
  runtime observations, exact snapshot references, one atomic run-state commit point.

Adopt:
- kernel publication authority
- task vs attempt separation
- runtime observations as facts
- staging -> validation -> publication
- graph revisions and replan request semantics

Conflict:
- authoritative mutable `run.json` differs from thin-agent-harness event-authority model.
  Kept as explicit open design choice in Spec 03 and adversarial review.
