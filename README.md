# Unified Agent Platform — Scaffold Draft

A consolidated agent-engineering platform derived from the owner's existing
harness/workflow repositories plus selected patterns from ECC, GSD,
Superpowers, and Matt Pocock's skills.

This scaffold deliberately separates four things that were repeatedly mixed
across earlier experiments:

1. **Human/LLM roles** — who reasons, proposes, implements, reviews.
2. **Deterministic host/kernel responsibilities** — who admits, publishes,
   schedules, compiles context, and computes state.
3. **Durable authority and protocol** — specs, decisions, contracts, evidence.
4. **Runtime/platform integration** — Codex/Claude/OpenCode/Roo, worktrees,
   transports, installation, observability.

## Eight product specifications

1. Intake & Alignment
2. Knowledge, Decisions & Research
3. Contracts, Protocol & Run State
4. Workflow & Orchestration
5. Runtime & Execution
6. Review, Verification & Evidence
7. Governance, Safety & Release
8. Platform, Integration & Operations

See `docs/specs/`.

## Core design rule

**Models propose. The kernel admits and publishes. Humans own material
decisions. Verifiers judge declared acceptance from evidence.**

Runtime prose, pane scrollback, exit-zero, and agent self-reports are never
completion authority by themselves.

## Document map

- `CONTEXT.md` — canonical domain vocabulary.
- `docs/product/` — purpose, scope, principles.
- `docs/specs/` — normative product requirements.
- `docs/architecture/` — system wiring and boundaries.
- `docs/adr/` — durable architecture decisions.
- `docs/research/` — all surveyed source material, including rejected/deferred ideas.
- `docs/reviews/` — adversarial review and open gap register.
- `contracts/` — machine-enforceable contract catalog and future schemas.
- `agents/` — human/LLM role and skill surfaces only.
- `src/` — deterministic product subsystems.
- `adapters/` — runtime/transport/tracker integration.
- `vendor/` — upstream skill adoption manifest; no silent copying.
