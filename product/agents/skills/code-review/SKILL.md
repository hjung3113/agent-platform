---
name: code-review
description: Review changes since a fixed point along two independent axes: repository standards/invariants and originating spec/issue fidelity. Use for branches, PRs, WIP changes, or review-since-X requests.
---

# Code Review

Review the diff between `HEAD` (or the requested PR head) and a fixed point along two independent axes:

- **Standards** — does the change conform to this repository's documented rules, architecture, authority/security invariants, and applicable smell baseline?
- **Spec** — does it faithfully implement the originating issue/spec without omissions, wrong behaviour, or scope creep?

Use independent parallel review agents when the runtime supports them. Otherwise perform two separated passes and preserve the axes independently so findings from one do not bias away the other.

## 1. Pin the fixed point

Resolve the comparison point from the user's PR/branch/commit context. For a PR, use its base/merge-base; for a branch review, use the stated base. Ask only when it cannot be derived safely. Validate the ref and ensure the intended diff is non-empty.

## 2. Identify the spec source

Use the repository's actual sources, in order:

1. Issue/PR references and linked GitHub issues.
2. A spec/plan path provided by the user.
3. Governing docs under `docs/specs`, `docs/architecture`, `docs/adr`, or the active plan linked by the work.
4. If there is genuinely no spec, report that the Spec axis is ungrounded rather than inventing requirements.

Do not require or create Matt Pocock's upstream `docs/agents/issue-tracker.md`; this project already uses its own GitHub/Request/Workflow conventions.

## 3. Identify standards sources

Always include `AGENTS.md`, relevant `CONTEXT.md`, applicable specs/ADRs, and any repository coding/testing rules. Apply these project rules before generic heuristics.

Use the following smell baseline as judgement-call prompts, not hard violations: Mysterious Name, Duplicated Code, Feature Envy, Data Clumps, Primitive Obsession, Repeated Switches, Shotgun Surgery, Divergent Change, Speculative Generality, Message Chains, Middle Man, Refused Bequest.

Repository rules override generic smells. Skip issues already deterministically enforced by tooling unless the enforcement itself is broken.

## 4. Standards pass

For every material finding, identify the file/hunk and cite the governing repository rule or name the smell/heuristic. Distinguish hard invariant violations from judgement calls. In agent-platform, explicitly look for authority bypass, stale/mismatched identity/digest bindings, silent fallback, non-determinism, YAGNI violations, and runtime-specific semantics leaking into canonical contracts when relevant to the diff.

## 5. Spec pass

Report:

- requested requirements missing or partial;
- behaviour added without a requirement;
- requirements that appear implemented but are implemented incorrectly;
- negative/fail-closed acceptance evidence the spec requires but the change lacks.

Ground each finding in the issue/spec rather than reviewer preference.

## 6. Aggregate

Present `## Standards` and `## Spec` separately. Do not let one axis erase the other. Summarize the number and highest severity of findings within each axis. If the user requested an adversarial review, prioritize concrete failure scenarios and reproducible evidence over stylistic commentary.
