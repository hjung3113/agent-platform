# ADR-0001 — Separate model roles from deterministic system actors

Status: Proposed

Decision:
`agents/roles/` contains only human/LLM reasoning roles. Kernel, Host, Context Compiler,
Scheduler and validators live in `src/`.

Reason:
Authority must not depend on whether an LLM follows a persona prompt.
