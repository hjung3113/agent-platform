# thin-agent-harness

Status: PRIMARY SOURCE

Evidence:
- `docs/architecture.md`: Human Authority -> Host admission -> Memory -> Orchestrator ->
  Context Compiler -> Executor -> Verifier -> Receipt authority flow.
- `docs/orchestration.md`: immutable workflow revision, event replay, bounded repair,
  context budget/conflict rules.
- `docs/memory-and-decisions.md`: decisions/findings/evidence/derived-index distinctions,
  supersession and freshness semantics.
- `docs/roles/`: explicit role contracts.

Adopt:
- authority separation
- task/attempt/finding/receipt vocabulary
- deterministic context compilation
- event/replay concepts
- bounded repair and typed refusal

Modify:
- deterministic roles are moved out of `agents/roles`.
- event-store design must be reconciled with atomic run-state alternative before implementation.
