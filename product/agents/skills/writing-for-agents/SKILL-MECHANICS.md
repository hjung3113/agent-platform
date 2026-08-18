# Skill Mechanics

Skill-specific guidance for [writing-for-agents](SKILL.md).

## Invocation

Choose between:

- **Model-invoked** — discoverable from a compact trigger description when the platform/runtime permits automatic invocation.
- **User-invoked** — selected explicitly by the human when automatic reach would add unnecessary context or authority ambiguity.

The canonical project skill should express the intended invocation semantics without granting capabilities. Runtime-specific invocation files are derived deployment output and are not vendored here.

## Splitting by invocation

Split a skill only when a distinct workflow needs independent discovery or when another skill must compose it. Every new model-visible trigger spends context load.

## Router skills

A router may reduce human cognitive load when user-invoked skills multiply, but it only selects/recommends workflows. It does not acquire the capabilities or authority of the routed skill and must not become a workflow-state authority.
