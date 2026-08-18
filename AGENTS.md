# Repo Layout

> **All product implementation (code, adapters, contracts, agent roles/skills/workflows,
> tests, vendor) MUST be written inside `product/`. Never implement product functionality
> at repo root or under `dev-env/`. `dev-env/` is strictly for the environment/tooling used
> to build the product, physically separate from the product itself — do not blur this
> boundary.**

This repo is split into two physically separate trees:

- `product/` — the shipped Unified Agent Platform harness: source, adapters, contracts,
  agent roles/skills/workflows, tests, vendor, operating docs. See `product/AGENTS.md` for
  rules on *using* the built harness.
- `dev-env/` — everything about *building* `product/`: design authority (specs, ADRs,
  architecture, product vision/scope), research, reviews, delivery plans, build-session
  artifacts, tooling. Not shipped, no runtime dependency on `product/`.

`product/docs/` holds only operating guidance plus empty `README.md`+`TEMPLATE.md`
placeholders for `product/`, `specs/`, `adr/`, `architecture/` — never live design content.
All live specs/ADRs/architecture/vision docs, plus research, reviews, and plans, live
under `dev-env/docs/`.

All rules below govern *building* the product (this dev environment). Rules for
*operating* the already-built harness live in `product/AGENTS.md` only.

## Document map (dev-env)

### Authoritative (governs product design decisions)
1. `dev-env/docs/product/` — durable product intent and boundaries
2. `dev-env/docs/specs/` — normative behavior requirements
3. accepted `dev-env/docs/adr/` — durable architectural choices
4. `dev-env/authority-map.yaml` — which of these paths counts as authority, and what
   admission requires (human approval, kernel admission, immutable published revision)

### Explanatory
- `dev-env/docs/architecture/` — how normative pieces connect

### Non-authoritative but preserved
- `dev-env/docs/research/` — source survey, alternatives, rejected/deferred concepts
- `dev-env/docs/reviews/` — critiques and open gaps
- `dev-env/docs/plans/` — temporary delivery plans
- `dev-env/HANDOFF.md`, `dev-env/SCAFFOLD-REPORT.md`, `dev-env/TREE.txt` — build-session
  process artifacts

Research/reviews/plans remain available even when not adopted. Machine contracts
(`product/contracts/`) are authoritative in their own right and stay in the product tree.

## Rules

1. **All product implementation lives under `product/`. Never write product code, adapters,
   contracts, agent roles/skills/workflows, tests, or vendor content at repo root or under
   `dev-env/`. Keep the product tree and the dev environment physically separate at all
   times.**
2. Read `product/CONTEXT.md`, `dev-env/docs/product/scope.md`, and the relevant spec
   before changing product design.
3. Treat only human-approved, Kernel-admitted/published revisions of specs, accepted ADRs,
   and machine contracts as authority; path presence or schema validity alone does not
   confer authority.
4. Do not place Kernel, Host, Context Compiler, Scheduler, or admission logic under
   `product/agents/roles/`.
5. Commands are thin entry points. Durable workflow logic belongs in skills/workflows or
   product code.
6. Any external skill copied from upstream must be recorded in
   `product/vendor/upstream-skills.lock.yaml` with source, revision, license, and local
   modifications. Any external dev-env tooling/skill copied from upstream must be recorded
   the same way, scoped to `dev-env/`.
7. Every implementation or design claim must point to an acceptance criterion or cited
   research/decision.
8. Before implementing a capability, inspect the reference repositories and research
   already recorded for this project. Prefer migrating or adapting proven upstream/reference
   implementations and patterns to the current architecture over reimplementing them from
   scratch. Preserve the product's contracts, authority boundaries, and invariants; do not
   copy incompatible behavior blindly. When code is copied or materially adapted, retain
   source/revision/license provenance and record local modifications where required.
9. Follow YAGNI: implement only behavior required by the current request, acceptance
   criteria, or a demonstrated failure mode. Do not add speculative features, abstractions,
   configuration, extension points, fallback paths, or future-proofing without a concrete
   requirement.
10. Think before coding. Surface material assumptions, ambiguity, inconsistencies, and
    trade-offs before committing to an implementation; do not silently invent semantics.
    Prefer the simplest valid interpretation consistent with authoritative contracts.
11. Make surgical changes. Touch only code required for the task, avoid drive-by
    refactors/formatting/comment cleanup, match existing style, and remove only dead code
    introduced by the current change. Every changed line should trace to the task or its
    verification.
12. Execute against verifiable success criteria. Convert implementation work into explicit
    checks, add failing/negative tests first when practical, and iterate until the stated
    criteria pass rather than stopping at plausible-looking output.
13. Prefer the smallest mechanism that closes a demonstrated failure mode. If an
    implementation is materially larger or more general than necessary, simplify it before
    adding new abstractions.
14. Nothing under `dev-env/` may be imported or referenced by code under `product/src` or
    `product/adapters`.
15. If a rule here starts only describing the shipped product's own runtime/operating
    behavior (not build authority or process), it belongs in `product/AGENTS.md` instead —
    move it rather than let it accumulate here.

Rules 9-12 adapt the Karpathy-inspired Claude Code guidelines from
`multica-ai/andrej-karpathy-skills` (formerly `forrestchang/andrej-karpathy-skills`),
revision `2c606141936f1eeef17fa3043a72095b4765b9c2`, MIT; project authority and safety
rules above take precedence.
