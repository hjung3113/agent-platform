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
10. Before implementing a capability, inspect the reference repositories and research already recorded for this project. Prefer migrating or adapting proven upstream/reference implementations and patterns to the current architecture over reimplementing them from scratch. Preserve this project's contracts, authority boundaries, and invariants; do not copy incompatible behavior blindly. When code is copied or materially adapted, retain source/revision/license provenance and record local modifications where required.
11. Follow YAGNI: implement only behavior required by the current request, acceptance criteria, or a demonstrated failure mode. Do not add speculative features, abstractions, configuration, extension points, fallback paths, or future-proofing without a concrete requirement.
12. Think before coding. Surface material assumptions, ambiguity, inconsistencies, and trade-offs before committing to an implementation; do not silently invent semantics. Prefer the simplest valid interpretation consistent with authoritative contracts.
13. Make surgical changes. Touch only code required for the task, avoid drive-by refactors/formatting/comment cleanup, match existing style, and remove only dead code introduced by the current change. Every changed line should trace to the task or its verification.
14. Execute against verifiable success criteria. Convert implementation work into explicit checks, add failing/negative tests first when practical, and iterate until the stated criteria pass rather than stopping at plausible-looking output.
15. Prefer the smallest mechanism that closes a demonstrated failure mode. If an implementation is materially larger or more general than necessary, simplify it before adding new abstractions.

Rules 12-14 adapt the Karpathy-inspired Claude Code guidelines from `multica-ai/andrej-karpathy-skills` (formerly `forrestchang/andrej-karpathy-skills`), revision `2c606141936f1eeef17fa3043a72095b4765b9c2`, MIT; project authority and safety rules above take precedence.
