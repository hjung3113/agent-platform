# Upstream Direct-Reuse Candidates

All listed upstreams are MIT-licensed as of their recorded research/import review date.
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

## Matt Pocock skills — selective import completed
Imported/adapted at revision `9c9f36ccd3995266cd675468af71639c8dde1ec5`:
- `grilling` / `grill-with-docs`
- `domain-modeling`
- `codebase-design`
- `diagnosing-bugs`
- `code-review`
- `writing-for-agents` (current successor to the previously researched `writing-great-skills` concept)
- `resolving-merge-conflicts`

Selection and local-delta evidence: [`mattpocock-skill-import-2026-08-18.md`](./mattpocock-skill-import-2026-08-18.md).

Deliberately not imported unchanged:
- `to-spec`, `to-tickets`, `triage`, `wayfinder`, `setup-matt-pocock-skills`: tracker/workflow ownership conflicts with local Request/Workflow/Kernel design.
- `ask-matt`: routes the full upstream catalog rather than this project's admitted subset.
- HTML/UI-oriented skills such as `prototype` and `improve-codebase-architecture`.
- overlapping/general workflow skills where this project already has or plans a stronger canonical owner.

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
