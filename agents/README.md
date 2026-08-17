# Agent Surface

Only human/LLM reasoning roles live here.

Deterministic system actors such as Kernel, Harness Host, Scheduler, Context Compiler,
admission service, and state projection are product code, not agent personas.

## Canonical surfaces

- `roles/` — responsibility and permission envelopes
- `skills/` — reusable discipline/workflow knowledge
- `commands/` — thin user-invoked routing wrappers
- `workflows/` — role composition templates

## Invocation taxonomy

Adopt Matt Pocock's useful distinction:
- **user-invoked**: explicit human entry point; orchestration-oriented; zero model auto-routing need
- **model-invoked**: reusable discipline the model may reach automatically

When user-invoked surfaces grow, route through a small namespace/router layer rather than
exposing every command description in every context.
