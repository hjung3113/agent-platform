# Agent Instructions

1. Read `CONTEXT.md`, `docs/product/scope.md`, and the relevant spec before changing design.
2. Treat only human-approved, Kernel-admitted/published revisions of specs, accepted ADRs, and machine contracts as authority; path presence or schema validity alone does not confer authority.
3. Human/LLM roles may propose; they do not directly publish authoritative run records.
4. Do not place Kernel, Host, Context Compiler, Scheduler, or admission logic under `agents/roles/`.
5. Commands are thin entry points. Durable workflow logic belongs in skills/workflows or product code.
6. Derived memory is a cache. Never create a new fact only inside `memory/derived/`.
7. Any external skill copied from upstream must be recorded in `vendor/upstream-skills.lock.yaml`
   with source, revision, license, and local modifications.
8. Keep runtime state outside the repository checkout.
9. Every implementation or design claim must point to an acceptance criterion or cited research/decision.
10. Prefer the smallest mechanism that closes a demonstrated failure mode; do not add speculative seams.
