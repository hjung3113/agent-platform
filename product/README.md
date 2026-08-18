# Unified Agent Platform

A harness for running human/LLM agent roles against a deterministic kernel: models
propose, the kernel admits and publishes, humans own material decisions, verifiers judge
declared acceptance from evidence. Runtime prose, pane scrollback, exit-zero, and agent
self-reports are never completion authority by themselves.

This is the product tree — what ships. Design rationale, specs, ADRs, and architecture
docs produced while building it live outside this tree; see the root `AGENTS.md`.

## Document map

- `CONTEXT.md` — canonical domain vocabulary.
- `docs/operations/` — deployment/runtime operations.
- `docs/product/`, `docs/specs/`, `docs/adr/`, `docs/architecture/` — template-only
  placeholders; no live content here (see `../docs/` for the current versions).
- `contracts/` — machine-enforceable contract catalog and future schemas.
- `agents/` — human/LLM role and skill surfaces only.
- `src/` — deterministic product subsystems.
- `adapters/` — runtime/transport/tracker integration.
- `vendor/` — upstream skill adoption manifest; no silent copying.
