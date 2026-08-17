# Upstream Direct-Reuse Candidates

All listed upstreams are MIT-licensed as of the research date (2026-08-17).
Pin revisions and preserve notices before copying.

## Superpowers — strongest direct reuse
Potentially vendor mostly unchanged:
- `test-driven-development`
- `systematic-debugging`
- `verification-before-completion`
- `using-git-worktrees`
- `requesting-code-review`
- `receiving-code-review`
- `finishing-a-development-branch`
- `writing-skills`

Adapt rather than copy orchestration:
- `subagent-driven-development` because local Attempt/Kernel protocol should own dispatch/publication.

## Matt Pocock skills — selective
Potentially vendor or fork:
- `grilling` / `grill-with-docs`
- `domain-modeling`
- `codebase-design`
- `diagnosing-bugs`
- `code-review`
- `writing-great-skills`
- `resolving-merge-conflicts`

Adapt strongly:
- `to-spec` and `to-tickets` because tracker publishing and local Request/Workflow contracts differ.

## ECC
Prefer concept/pack extraction rather than wholesale copy:
- context-budget / onboarding / security / skill-authoring patterns
- selected stack-specific skills only when a concrete project profile needs them

## GSD
Prefer adaptation, not direct copying:
- Plan Checker
- thin orchestrator
- namespace routing
- fresh-context/wave execution
GSD agents/workflows are tightly coupled to its `.planning` and command runtime.
