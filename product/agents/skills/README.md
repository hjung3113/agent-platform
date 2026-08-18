# Skills

Skills are the canonical reusable agent-side unit.

Recommended buckets:
- intake-alignment
- repository-recon
- domain-modeling
- planning
- plan-checking
- implementation
- tdd
- debugging
- review
- verification
- handoff
- git-delivery
- documentation
- skill-authoring

Prefer small composable skills over a monolithic process owner.
Use progressive disclosure and keep trigger descriptions compact.

## Skill contract
Every managed skill has enough metadata to make routing, portability, context cost, provenance, and regression behavior explicit:
- stable skill identity and version
- invocation mode: user-invoked, model-invoked, or internal composition only
- compact trigger/selection description
- required canonical actions and capability requirements
- runtime-neutral behavior plus any explicit runtime-extension dependency
- model-visible disclosure/context cost used by context budgeting
- declared skill dependencies when composition is required
- behavior/eval references and last accepted eval identity for managed/upstream skills
- upstream provenance, pinned revision/content identity, license, and local delta identity when vendored or imported

Skill metadata supports routing and validation but never grants publication, external-effect, filesystem, network, or secret authority by itself. Those capabilities remain admitted per Attempt/Host policy.

Upstream candidates are recorded in `../../../dev-env/docs/research/direct-reuse-candidates.md`
and `vendor/upstream-skills.lock.yaml`.

## Installed Matt Pocock engineering skills

The following project-level canonical skills are adapted from `mattpocock/skills` and pinned in `vendor/upstream-skills.lock.yaml`:

- `grilling`
- `grill-with-docs`
- `domain-modeling`
- `codebase-design`
- `diagnosing-bugs`
- `code-review`
- `writing-for-agents`
- `resolving-merge-conflicts`

These are canonical runtime-neutral sources. Upstream runtime-specific files such as `agents/openai.yaml` are intentionally not imported; runtime emits must be generated/validated through this project's adapter/profile machinery. Project `AGENTS.md`, specs, ADRs, and authority/security contracts override any conflicting upstream workflow instruction.

Import selection, exclusions, local adaptations, and conformance evidence are recorded in `../../../dev-env/docs/research/mattpocock-skill-import-2026-08-18.md`.
