# Agent Instructions (Product Tree)

Rules for *operating* the built harness. For rules on building/designing it — spec/ADR
authority, engineering discipline — see the root `AGENTS.md`.

1. Human/LLM roles may propose; they do not directly publish authoritative run records.
2. Derived memory is a cache. Never create a new fact only inside `memory/derived/`.
3. Keep runtime state outside the repository checkout.
