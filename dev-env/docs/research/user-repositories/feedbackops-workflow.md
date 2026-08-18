# feedbackops-workflow

Status: PRIMARY SOURCE

Evidence:
- `toolkit/docs/agents/conductor-persona.md`: read-only conductor, state from disk,
  liveness vs correctness, prompt authoring, scope lock, risk tier, repeated-round control.
- `toolkit/docs/agents/artifact-lifecycle.md`: PR-DRAFT/BLOCKER/REVIEW/ROUND-STATE/VERIFY,
  exact HEAD/content binding, lifecycle, freshness, immutable review snapshots.
- multi-agent workflow playbook: independent runtime/role/transport axes.

Adopt:
- read-only conductor
- runtime/role/transport independence
- exact snapshot-bound evidence
- risk tiers
- origin-classified retry circuit breaker
- liveness != correctness
- visual review as verifier profile

Simplify:
- issue-specific artifact names become generic protocol contracts.
