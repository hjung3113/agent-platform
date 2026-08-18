---
name: model-routing
description: Routes work to the right model and the right dispatch mechanism — Opus stays on whole-session orchestration and every judgement role (review, verify, audit); all other work goes to codex gpt-5.6-sol/terra/luna spawned through orca worktrees and terminals. Use before spawning any subagent or delegating implementation, planning, docs, or recon work, and whenever deciding "which model should do this".
---

# Model routing

Two model families, two **different dispatch mechanisms**. The mechanism is the hard part —
the Claude Code `Agent` tool can only spawn Claude models, so codex tiers are not a config
switch, they are a different execution path.

## The rule

**Opus is reserved.** It runs exactly two kinds of work:

1. **Whole-session orchestration** — the main conversation: decomposing the request, choosing
   routes, holding the thread, deciding what happens next.
2. **Judgement roles** — anything whose output is a *verdict* rather than an artifact:
   review, verification, audit, plan-checking, integration-checking.

Everything else — planning, implementation, fixing, documentation, reconnaissance — runs on
codex.

Rationale for keeping judgement on Opus: adversarial review repeatedly catches critical
defects that phase verification passed over. Downgrading the role that issues verdicts
removes the only step that disagrees with the work.

## Model tiers

| Model | Tier | Catalog description | Use for |
|---|---|---|---|
| `gpt-5.6-sol` | frontier | "Latest frontier agentic coding model" | planning, roadmapping, research, hard design work |
| `gpt-5.6-terra` | balanced | "Balanced agentic coding model for everyday work" (codex default) | implementation, fixes, docs, ordinary engineering |
| `gpt-5.6-luna` | fast | "Fast and affordable agentic coding model" | recon, mechanical scans, derived-artifact regeneration |

Reasoning effort is **not** baked into the slug. Set it separately:
`-c model_reasoning_effort="low|medium|high|xhigh"`.

## Role map

| Role | Model | Dispatch |
|---|---|---|
| main session / orchestration | Opus | in-process |
| `code-reviewer`, `gsd-code-reviewer` | Opus | `Agent` |
| `gsd-verifier`, `gsd-plan-checker`, `gsd-doc-verifier`, `gsd-integration-checker` | Opus | `Agent` |
| `gsd-nyquist-auditor`, `gsd-security-auditor`, `gsd-eval-auditor`, `gsd-ui-auditor` | Opus | `Agent` |
| `gsd-planner`, `gsd-roadmapper`, `gsd-phase-researcher`, `gsd-project-researcher` | **sol** | orca + codex |
| `gsd-executor`, `gsd-code-fixer`, `gsd-doc-writer`, `python-engineer` | **terra** | orca + codex |
| `explorer`, `gsd-intel-updater`, `curator`, broad greps | **luna** | orca + codex |

A role **absent from a project's `model_overrides`** is not "default Claude" — it is
codex-routed. Only the roles that stay on Claude are listed there.

## Dispatching to codex

Two mechanisms. Pick by whether the work is short and synchronous or long and isolated.

### Synchronous — `codex exec` (default; prefer this)

Returns the output directly to the caller. No worktree, no terminal handle, no polling.

```bash
codex exec --model gpt-5.6-terra --sandbox read-only "<task brief>"
codex exec --model gpt-5.6-sol -c model_reasoning_effort="high" --sandbox workspace-write "<task brief>"
```

- `--sandbox read-only` for recon and analysis; `workspace-write` when it must edit files.
- Must run inside a trusted directory (a git repo), or it refuses with
  *"Not inside a trusted directory and --skip-git-repo-check was not specified"* — cd into the
  repo rather than passing the skip flag.
- Reads stdin: pipe `""` in from a non-interactive caller (`echo "" | codex exec ...`) or it
  blocks on *"Reading additional input from stdin..."*.

Verified live: all three slugs resolve and respond. Same trivial prompt cost ~25k tokens on
sol vs ~11k on terra and luna — the tier choice is a real cost decision, not a label.

### Asynchronous / isolated — orca worktree

Use when the work is long-running, must not touch the current checkout, or the user wants it
visible as a workspace card.

Resolve the orca executable once per session (`ORCA_CLI_COMMAND` → `orca-dev` in a dev
checkout → `orca-ide` on Linux outside Orca → otherwise `orca`), then reuse it. Load the
version-matched guide with `<orca> skills get orca-cli` before using flags not shown here.

**Isolated worker** (own checkout — use when the work writes files and must not disturb the
current tree):

```text
<orca> worktree create --name <task> --no-parent --json
<orca> terminal create --worktree id:<repoId>::<path> --title <task> \
  --command 'codex --model gpt-5.6-terra -c model_reasoning_effort="medium"' --json
<orca> terminal wait --terminal <handle> --for tui-idle --timeout-ms 60000 --json
<orca> terminal send --terminal <handle> --text "<task brief>" --enter --json
```

`worktree create --agent codex` launches codex in the first terminal but does **not** accept
`--model` / `-c`, so any non-default tier needs the two-step form above.

**In the current checkout** (no new worktree):

```text
<orca> terminal create --worktree active --command 'codex --model gpt-5.6-luna' --json
```

**Collecting results** — codex dispatch is asynchronous. Read back rather than assuming:

```text
<orca> terminal wait --terminal <handle> --for tui-idle --timeout-ms 300000 --json
<orca> terminal read --terminal <handle> --json
```

If a handle returns `terminal_handle_stale`, re-list it with `terminal list`; never send to
both the old and the replacement handle.

## Choosing between the two paths

Dispatch to codex when the work produces an **artifact** — code, a plan, a document, a file
listing. Keep it on Opus when the work produces a **verdict**, or when it is the session's
own orchestration.

Do not route a judgement role to codex to save budget. Do not route bulk implementation to
Opus for convenience.

When work must both produce an artifact and be judged: codex writes it, Opus reviews it.
Those are two steps, not one — never let the writer grade its own output.
