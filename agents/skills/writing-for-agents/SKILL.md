---
name: writing-for-agents
description: Writing documents for agents. Use when creating or editing skills, AGENTS.md/CLAUDE.md, or documents reached by agent context pointers.
---

# Writing For Agents

Reference for writing any document an agent consumes: a skill, `AGENTS.md`, runtime instructions, or a document reached by a pointer. The goal is predictable process, not identical output.

When writing a skill, also read [SKILL-MECHANICS.md](SKILL-MECHANICS.md).

## Context pointers

A **context pointer** names out-of-context material and encodes the condition for reaching it. The pointer wording decides when an agent discovers the material. Front-load the trigger, keep one trigger per genuinely distinct branch, and remove identity text the target already carries.

## The two loads

- **Context load** — always-loaded tokens/attention.
- **Cognitive load** — what the human must remember exists and when to invoke it.

Spend context load only where automatic discovery is valuable; spend cognitive load where human judgement should select the workflow.

## Information hierarchy

1. **In-file step** — ordered actions the agent must perform.
2. **In-file reference** — rules/facts needed by most branches.
3. **Disclosed reference** — branch-specific material behind a pointer.

Use progressive disclosure to keep the top-level process legible. Co-locate definitions, rules, and caveats for one concept. Split only when the cut meaningfully reduces context or premature-completion pressure.

## Steps and completion criteria

Every step needs a completion criterion that is checkable and demanding enough to prevent plausible-looking premature completion. Prefer observable criteria and exhaustive bounds over vague states like "understood" or "looks good".

## Leading words

Use compact, well-known concepts as repeated anchors when they meaningfully sharpen behaviour: for example **tight** feedback loop, **red** regression signal, **frontier** of currently answerable decisions. Prefer positive target behaviour; reserve prohibitions for hard guardrails.

## Pruning

- Keep each meaning in one source of truth.
- Treat environment/config as source of truth; avoid caching easy lookups in prose.
- Remove stale, irrelevant, or default/no-op instructions.
- Prefer small composable skills over a monolithic process owner.
- In agent-platform, skill text never grants publication, filesystem, network, secret, or external-effect authority; those remain admitted by the platform's governing contracts.
