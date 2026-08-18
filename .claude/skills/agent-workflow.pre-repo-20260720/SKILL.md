---
name: agent-workflow
description: "Run a coding task through the multi-agent dev workflow (cmux × Claude × Codex). Enforces sandboxed codex implementation, evidence-gated verification, and artifact-based state. Trigger: /agent-workflow"
trigger: /agent-workflow
---

# /agent-workflow

Execute a coding task through the **multi-agent development workflow**: a disciplined loop where Codex implements inside a sandbox, a VERIFIER proves green OUTSIDE the sandbox, and nothing is "done" without a machine-checkable evidence artifact. This skill makes the workflow **mandatory**, not optional — it runs the actual scripts and refuses prose-only "it works" claims.

## Usage

```
/agent-workflow <task or issue description>
/agent-workflow #<issue-number>                 # pull the issue, then run
/agent-workflow <task> --target <repo-path>      # target project (default: cwd)
/agent-workflow <task> --tier trivial|standard|full   # override risk tier
```

## Where the toolkit lives

The workflow scripts live in a dedicated repo. Resolve `WF_HOME` in this order:
1. `$WF_HOME` env var if set.
2. `~/Desktop/2026/feedbackops-workflow` (default).
3. If neither exists, STOP and tell the user where the workflow repo is.

Set once at the start of a run: `WF="${WF_HOME:-$HOME/Desktop/2026/feedbackops-workflow}"`. The **target** is the project being changed (`--target` or cwd) — never `$WF` unless you are improving the toolkit itself.

## Model allocation — READ THE PLAYBOOK, DO NOT GUESS

The model ladder, the role × model map, per-tier selection, and the review-depth scaling rules are **owned by `$WF/docs/agents/multi-agent-workflow.md` §"Model Allocation"**. They change as models come and go, so this file does not restate them — a copy here drifts and has drifted before.

**Before your first dispatch, read `$WF/docs/agents/multi-agent-workflow.md`.** If it is unreadable or `$WF` does not resolve, **STOP and tell the user** — do not proceed from memory or from a model name you recall. That file plus the role prompts (`$WF/docs/agents/conductor-persona.md`, `$WF/docs/agents/visual-reviewer-persona.md`) are the authority whenever this skill is ambiguous.

Two invariants that gate every dispatch (the playbook holds the detail):
- The review model is at least one tier **above** the implementation model — never the same or lower.
- **Pin the model explicitly on every dispatch** (`--model <X> --effort medium`). Omitting it silently takes the config default, which is not the tier you chose.

## Non-negotiable rules (the whole point of this skill)

1. **Codex only via the wrapper.** Every implementation dispatch goes through `$WF/scripts/codex-safe.sh` (pins `--sandbox workspace-write` + `--cd`). NEVER call `codex exec` directly — that would drop containment.
2. **The sandbox has no network.** `workspace-write` blocks ALL egress incl. loopback (proven: EPERM on TCP and AF_UNIX). So Codex CANNOT reach the DB. DB-backed verification runs OUTSIDE the sandbox, by you, as VERIFIER.
3. **Evidence or it didn't happen.** A task is complete only when the canonical verifier artifact (`.review/ISSUE-<N>-VERIFY.json`, `producer_role: "VERIFIER"`, `classifier: "PASS"`, `verdict.exit_code: 0`, `verdict.failed: 0`, `verdict.passed >= 1`, matching issue/branch, and `head_sha` equal to the live worktree HEAD) exists for the current head. `pr_draft.verify_result` is deprecated and ignored. In `VERIFY_ISSUE` mode, a green run that cannot write a valid VERIFY artifact is not done (`verify.sh` exits 5). "Tests pass" in prose ≠ done.
4. **Implementation, review, and verification are separate.** The same agent/session must not implement and then approve or verify its own work. Re-review uses a new clean context.
5. **Doc-sync discipline.** Any script/schema/contract change updates the relevant doc (playbook / README / STATUS) in the SAME commit.
6. **Don't merge to main/develop or push without explicit user approval.** You are the orchestrator, the human is Release Captain.
7. **CONDUCTOR is READ-ONLY on product code.** You (the main session) NEVER edit source files — not a typo, not a one-line patch, not "just this once." Any source edit by the conductor is **role bleed — a defect** (`conductor-persona.md` §2). You dispatch; the workers touch code. If a fix is needed, re-dispatch CODEX with a scoped follow-up prompt.
8. **Worker roles run IN their cmux panes — never inline in the conductor.** This is a **cmux 4-pane** workflow (ARCHITECT / CODEX / REVIEWER / VERIFIER, +VISUAL in its own pane) so the human can WATCH each role work. The conductor dispatches a command into the role's pane (e.g. send `verify.sh ...` to the VERIFIER pane, a review task to the REVIEWER pane) — it does NOT run review/verify in its own session. The conductor stays lean by reading **`.review/*.json` artifacts** (via `conductor-rebuild.sh`), **never pane scrollback, never raw diffs/test logs** (persona §3/§4). That artifact-only read — not moving work out of the panes — is what keeps the conductor's context small. Do NOT replace panes with invisible `Agent` subagents: that defeats the watch-the-work purpose of cmux.
9. **Do not run two workspace-write Codex jobs in the same repo at the same time.** `codex-safe.sh` stashes partial work on failure; concurrent jobs in one checkout can race on stash state. Parallel implementation requires separate prepared worktrees.
10. **Clear `NODE_OPTIONS=` before codex/node dispatch and verification.** cmux or shell preloads can leak `--require` instrumentation into codex/vitest children.
11. **Close finished cmux workspaces.** When a chunk is merged (or abandoned), close its cmux workspace so the workspace list doesn't accumulate. See Step 8.

## Procedure

### 0. Setup
- `WF=...` (above). Verify `$WF/scripts/verify.sh` exists; if not, stop.
- Identify the target repo and the task. If `#<n>`, fetch via `gh issue view <n>`.

### 1. Risk-tier routing
Pick the agent set by tier (full table in the playbook):
- **Trivial** — single file, no API/domain/UI/contract change → CODEX + VERIFIER.
- **Standard** — single-module behavior change → CODEX + REVIEWER + VERIFIER.
- **Full Cluster** — migration / auth / permissions / shared UI / `packages/shared` / cross-module contract / prod data path → ARCHITECT + CODEX + REVIEWER + VERIFIER (+ VISUAL if UI).

Before assigning **Trivial**, run the probe over the touched files — a non-zero exit FORBIDS trivial:
```
$WF/scripts/tier-probe.sh <touched-file> [...]
```
File count is NOT the tier: an exported-contract change is non-trivial no matter how few files.

### 2. Prepare an isolated worktree (host side, OUTSIDE sandbox)
A fresh worktree has no deps/env and the sandbox can't self-provision (no network). Provision on the host first:
```
$WF/scripts/prepare-worktree.sh <worktree-path> [--env-profile <env-file>]
```
For parallel clusters: each cluster needs its OWN throwaway DB (schema/workspace isolation is insufficient — fixed schemas + instance-global `pg_locks`). Give the 2nd+ worktree `--env-profile` (shared env corrupts parallel runs). `cmux-cluster.sh` refuses to launch a worktree missing `node_modules`/`.env`.

### 3. Write the dispatch prompt → `.review/ISSUE-<N>-PROMPT.txt`
Scope it tightly: the exact files allowed, the contract, the test to satisfy. Tell Codex to **abort with a `blocker` artifact** (`reason_code` + real `blocking_fact`, never the prompt's example phrasing) if the touch set escapes scope (e.g. hits `packages/shared`, a migration, a shared type).

### 4. Dispatch CODEX (sandbox)
```
$WF/scripts/cmux-dispatch.sh --issue <N> --worktree <worktree-path> --model <tier-model> --effort medium
```
`--model`/`--effort` are forwarded to `codex-safe.sh`. **Always pass them** — omitted, the dispatch silently runs the config default instead of the tier you selected in step 1.
- **`cmux-dispatch.sh` is the mandated dispatch path** — do NOT hand-roll `cmux workspace create` + watchdog. It validates the worktree and prompt file (default `<worktree>/.review/ISSUE-<N>-PROMPT.txt`), absolutizes paths, always passes `--cwd` to BOTH the cmux workspace and the watchdog, then polls up to 300s for RUN.json/BLOCKER.json and exits non-zero if the watchdog never started. (Incident 2026-07-13: a hand-rolled dispatch missing cmux `--cwd` + a relative prompt path died silently with zero artifacts.)
- The watchdog calls `codex-safe.sh` by absolute path, preserving the sandbox and stash contract.
- Liveness is process + filesystem progress, never stdout first-token output. It writes `<worktree>/.review/ISSUE-<N>-RUN.json`.
- **RUN.json terminal-state contract:** `status:"running"` while alive; terminal is `status:"exited"` + `exit_code` (there is NO `"completed"`/`"failed"` status — do not poll for those). `exit_code: 0` means the codex process finished; task success is still judged by commits + the VERIFY artifact, never by exit code alone. A `.review/ISSUE-<N>-BLOCKER.json` is a scoped abort.
- 4xx/model refusal exits fail-fast; stalls are killed and retried. On non-zero `codex-safe.sh` exit, partial work is still preserved via `workflow-stash.sh`.

### 5. REVIEW (Standard/Full) — in the REVIEWER pane
Do NOT review inline in the conductor (that loads the diff into the conductor's context = the thing we're avoiding). The REVIEWER must be a different agent/session from the implementer. Re-review uses a clean context. Drive the **REVIEWER cmux pane**: launch a reviewer there (a Claude instance, or `codex exec --sandbox read-only` for an adversarial read) scoped to ONE chunk — worktree path, brief, contract/scope to check. It reads the actual diff (not Codex's summary), checks design fit / contract adherence / scope / role-bleed, and writes its verdict to the `review` artifact. The conductor reads the artifact, not the pane scrollback.

**Polling a read-only codex reviewer — do NOT declare death on a missing output file (incident 2026-07-15).** A `gpt-5.6-sol` review at `medium` effort routinely takes **4–5 minutes and ~60k tokens** before it writes `--output-last-message`. A hand-rolled poller that checks once after a short `sleep` (or times out early) and sees no output file will FALSELY report "died" — the codex process is still running. Two r4 re-reviews were misjudged this way; a direct re-run of the identical prompt finished fine at 4 min. Rules: (a) **liveness = process alive (`pgrep -f "codex exec"`) OR output-file present — never "output absent" alone**; only conclude death when the process is GONE and no output landed. (b) Budget ≥ 8 min for a sol/medium reviewer before any timeout. (c) When a hand-rolled cmux `--command` reviewer looks stuck, prefer re-running the codex directly in a Bash call with `2>/tmp/rev-stderr.log` so you can SEE the real error instead of guessing — inline-vs-`$(cat file)` prompt form is NOT the cause (both work; verified). For anything non-trivial, pass the prompt via a file + `$(cat …)` anyway to avoid shell-escaping fragility, but that is ergonomics, not the liveness fix.

### 6. VERIFY (OUTSIDE the sandbox) — in the VERIFIER pane
This is the evidence gate. The VERIFIER must be a different agent/session from the implementer. The implementer's own test claim is not verification. Drive the **VERIFIER cmux pane** (visible to the human) to run, from the worktree root:
```
cd <worktree-path>
VERIFY_ISSUE=<N> VERIFY_DATABASE_URL=<low-priv-local-url-to-throwaway-db> \
  $WF/scripts/verify.sh <vitest-name-filter>
$WF/scripts/verify.sh --typecheck     # baseline-aware: only NEW errors fail
```
- `<filter>` is a **vitest name/path filter scoped to the backend package**, NOT a package selector. A fully-skipped suite, a failed suite, a non-zero vitest exit, or a missing/unparseable report all = FAIL (false-green-proof). A bare `pnpm test` is forbidden as a green signal.
- `verify.sh` refuses (`exit 3`) a non-local `DATABASE_URL` host, warns if running as superuser `postgres`, and runs vitest under a scrubbed `env -i` allowlist (add vars via `VERIFY_ENV_ALLOW`).
- **`VERIFY_DATABASE_URL` must be explicitly set — `verify.sh` now exits 4 rather than fall back to `.env`.** (Incident 2026-07-13: an empty upstream `eval` left it unset and the suite ran against the shared dev DB, producing a garbage FAIL artifact.) Provision the throwaway DB with `$WF/scripts/prepare-verify-db.sh` using an admin URL that actually has CREATEDB (e.g. `PGADMIN_URL=postgres://postgres:...@localhost:5434/postgres`; `fops_migrate` cannot create DBs) — it is fail-closed since toolkit `68716ae` (no `VERIFY_DATABASE_URL=` line printed on any failure), but still check its exit code before consuming the line.
- **Integration suites often need more than the app URL:** pass `VERIFY_DATABASE_URL_MIGRATE` (fixture setup/cleanup runs as the migrate role) and allowlist app-required env like `WORKSPACE_ID` via `VERIFY_ENV_ALLOW`. A fresh DB also needs migrations AND `db:seed` (seed requires `WORKSPACE_ID`) — symptoms of a missing piece: tests `pending` (setup died: no seed / wrong role), not `failed`.
- **`VERIFY_DATABASE_URL` (the app handle) MUST be a low-priv role (`fops_app`), NOT the `postgres` superuser (incident 2026-07-15).** A broad module filter (e.g. `verify.sh voc`) pulls in **role-grants assertion tests** — tests that assert `fops_app CANNOT UPDATE/DELETE` a table. Run the app handle as `postgres` and those tests FALSE-FAIL (superuser bypasses every grant), looking like a real regression on code that never touched grants. `verify.sh` prints `WARN: verifier running as superuser role 'postgres' — prefer a low-privilege role` — heed it. Fix: pass the app URL with the `fops_app` role (`sed 's|postgres://postgres:postgres@|postgres://fops_app:fops_app@|'` on the URL `prepare-verify-db.sh` emits), keep the **migrate** handle as the superuser/`fops_migrate` URL for fixture setup/cleanup. Narrow filters (a single test file, e.g. `patch-task-status`) dodge this because they never load the grant suite — which is why it only bites on broad filters.
- Success writes `.review/ISSUE-<N>-VERIFY.json` — the canonical readiness signal. The conductor reads THIS ARTIFACT (`classifier` + failing test names) — it does NOT run `verify.sh` in its own shell and does NOT read the pane scrollback (keep its context clean; trust the artifact, not prose).
- **Non-vitest targets:** if the project has no vitest backend (e.g. a scripts/bash repo), the VERIFIER step is the project's own test command (e.g. its smoke suite). Still gate on a real pass, and still record evidence.

### 7. Reconstruct state & decide (CONDUCTOR / Release Captain)
```
$WF/scripts/conductor-rebuild.sh <worktree>/.review
```
A draft is **verified** only when `status: ready_for_review` and the deterministic `.review/ISSUE-<N>-VERIFY.json` satisfies: `producer_role: "VERIFIER"`, `classifier: "PASS"`, `verdict.failed == 0`, `verdict.passed >= 1`, `verdict.exit_code == 0`, internal issue matches the draft issue, branch matches the draft branch, and `head_sha` equals the worktree's live HEAD. `pr_draft.verify_result` is deprecated and ignored. Stale verify (work landed after), missing VERIFY artifact, identity mismatch, or unresolved HEAD → NOT verified. Present the evidence to the user (Release Captain) for the merge decision. Do not merge/push without approval.

### 8. Close out
- Commit with doc-sync (code + affected docs together). Scope messages to the project's convention.
- **Close the GitHub issue** (with a comment citing the commit + verify evidence) so the milestone closed-count reflects reality — track progress by milestone, not prose.
- **Close the chunk's cmux workspace.** Once merged/abandoned, free the workspace so the list doesn't pile up: `cmux list-workspaces` to find it, then `cmux close-workspace --workspace <id>` (or the app's close). Leaving dozens of dead workspaces open is clutter — clean as you go.
- Archive merged-issue artifacts: `$WF/scripts/review-archive.sh`.
- When the integration branch advances, rebase in-flight worktrees: `$WF/scripts/rebase-inflight.sh --onto <branch>` (dirty-safe, conflict-aborting).

## Co-design with Codex (recommended for non-trivial design)
Before/after implementing, run an adversarial design pass with a read-only Codex:
```
codex exec --sandbox read-only -c model_reasoning_effort=low --cd <repo> "<design question>"
```
(`read-only` design discussion is the one place a bare `codex exec` is fine — it writes nothing. Implementation still goes through `codex-safe.sh`.) Use it to attack your own plan; you own the design review, Codex implements.

## Self-check before declaring done
- [ ] Every implementation dispatch went through `codex-safe.sh` (no bare `codex exec` for writes).
- [ ] A VERIFY artifact exists with `classifier: PASS` for the current head sha.
- [ ] Diff reviewed against the actual files, scope respected (or a blocker was raised).
- [ ] Docs synced in the same commit as code.
- [ ] No merge/push without the user's approval.
