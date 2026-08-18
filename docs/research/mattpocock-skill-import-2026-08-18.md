# Matt Pocock Skill Import Review — 2026-08-18

Status: **Accepted project-level import**

## Source

- Repository: `mattpocock/skills`
- Pinned revision: `9c9f36ccd3995266cd675468af71639c8dde1ec5`
- License: MIT, copyright Matt Pocock (2026)
- License notice retained at `vendor/licenses/mattpocock-skills-LICENSE`
- Canonical destination: `agents/skills/`

The upstream revision was reviewed rather than installing the entire catalog. Only skills with a direct fit to agent-platform's engineering/domain/review workflows were admitted.

## Imported subset

| Skill | Why it belongs here | Local adaptation |
|---|---|---|
| `grilling` | adversarial design/decision clarification | fact lookup uses available tools directly; Human/Kernel authority preserved |
| `grill-with-docs` | composes design grilling with domain documentation | composition made runtime-neutral; writing docs does not confer authority |
| `domain-modeling` | directly fits `CONTEXT.md` and ADR work | existing project context/ADR structure overrides upstream fallback; material ADR acceptance is not automatic |
| `codebase-design` | useful for Kernel/Host/adapter/module seams and YAGNI | explicitly preserves deliberate authority/security boundaries; parallel design pass is capability-conditional |
| `diagnosing-bugs` | debugging/performance regression discipline | UI/browser examples demoted to boundary-specific option; HITL template generalized; secret retention guard retained |
| `code-review` | matches the project's repeated adversarial PR/spec review workflow | removes dependency on upstream setup docs; uses local GitHub/issues/specs/AGENTS/ADR authority and local invariant checks |
| `writing-for-agents` | skill/AGENTS/pointer authoring is core platform work | shortened to runtime-neutral canonical guidance; explicit no-authority rule |
| `resolving-merge-conflicts` | directly relevant to Git delivery | preserves intent/source tracing but allows stopping when the merge target itself is invalid; external effects remain separately authorized |

`writing-for-agents` is the current upstream successor to the previously recorded `writing-great-skills` candidate.

## Excluded subset

Excluded because the user requested no web/UI-only or unrelated skills, and because wholesale import would violate YAGNI:

- `prototype`, `improve-codebase-architecture`: their normal workflow is centered on shareable HTML/UI output; not needed for the current platform core.
- `ask-matt`: router over the complete upstream catalog, which would expose skills this project intentionally did not admit.
- `setup-matt-pocock-skills`, `to-spec`, `to-tickets`, `triage`, `wayfinder`: encode an upstream tracker/domain workflow that overlaps or conflicts with agent-platform's Request/Workflow/Kernel authority model; concepts may be adapted later, not vendored unchanged.
- `implement`: broad process owner that commits work directly and assumes its own `/tdd`→`/code-review` flow; local execution protocol should own implementation sequencing.
- upstream `tdd`: relevant, but not imported here to avoid two competing TDD semantics while Superpowers TDD remains the project's preferred direct-reuse candidate.
- `research`: useful conceptually, but its hard-coded background-agent assumption is runtime capability-specific; local research roles/workflows should own delegation.
- productivity `handoff`: writes to OS temp and assumes upstream skill invocation; this repository already owns a root `HANDOFF.md` convention.
- remaining teaching/questionnaire/misc/in-progress skills: no current concrete agent-platform need.

## Runtime-neutral import policy

Upstream `agents/openai.yaml` files were not imported. The project stores runtime-neutral canonical skill sources and treats runtime-specific invocation/configuration as generated/adapter-owned output. This avoids making Codex/Claude-specific metadata an independent source of truth.

## Local delta identity

`agent-platform-mattpocock-adapt-v1` denotes the reviewed adaptation from the pinned upstream trees to the local content trees recorded in `vendor/upstream-skills.lock.yaml`.

Material adaptation rules:

1. Project `AGENTS.md`, specs, ADRs, and Human/Kernel authority always win.
2. No imported skill can publish authoritative run state or grant filesystem/network/secret/external-effect capability.
3. Sub-agent/parallel behavior is conditional on runtime capability; canonical semantics do not require one transport/runtime.
4. Upstream setup/tracker assumptions are removed when they would create a second workflow authority.
5. UI/browser-specific techniques remain only where they are legitimate debugging boundary choices, not default platform behavior.
6. Supporting reference files are copied/adapted only when an imported `SKILL.md` actually points to them.

## Conformance eval — `mattpocock-import-conformance-v1`

Type: manual static workflow conformance. Result: **PASS**.

Checks performed:

- **Project relevance:** each admitted skill maps to an existing project skill bucket or repeatedly used engineering workflow.
- **Exclusion gate:** web/UI-centric and unrelated catalog entries are absent.
- **Authority gate:** reviewed local skill text contains no path that upgrades prose, role output, review PASS, or runtime observation into Kernel authority.
- **External-effect gate:** Git push/merge/release is not implicitly authorized by skill success.
- **Runtime-neutral gate:** no upstream `agents/openai.yaml` or equivalent runtime-specific canonical source was imported.
- **Reference closure:** every relative file reference in the admitted canonical skill set has a local destination, or the reference was removed during adaptation.
- **Provenance gate:** exact upstream revision, upstream tree identities, local tree identities, license, local-delta identity, and update policy are recorded.
- **YAGNI gate:** no router/setup/plugin/catalog machinery was copied solely to support hypothetical future use.

This is an import/adaptation conformance gate, not proof that every future runtime can execute every skill. Runtime capability enforcement and cross-runtime generated-output drift remain governed by the platform roadmap. Future upstream updates must review both upstream diff and local delta, rerun the applicable evals, and retain the previously admitted revision as rollback target.
