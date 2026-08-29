# Handoff

## Completed this milestone (M7 — orchestration expansion, slice 2: DAG dependency validation, merged)

M7 slice 2 designed, reviewed, implemented, fixed, re-reviewed, and merged: [PR #50](https://github.com/hjung3113/agent-platform/pull/50)
(squash-merged to `main` as `eadc857`). Tracking [Issue #4](https://github.com/hjung3113/agent-platform/issues/4), roadmap
expansion-order step 2 only (not step 3, resource claims).

- **Toolkit adopted this session**: [`feedbackops-workflow`](https://github.com/hjung3113/feedbackops-workflow)
  (a separate personal repo — reusable multi-agent dispatch/review/verify toolkit) installed into this repo via
  `scripts/install-into.sh` into the four managed leaves (`.agent-workflow/{scripts,schemas,docs/agents}`,
  `.claude/skills/agent-workflow`) plus an `AGENTS.md` managed-marker pointer block. Project-owned files created:
  `.agent-workflow/workflow-config.json` (orchestrator=cmux default, override per-dispatch),
  `.agent-workflow/target-profile.json` (this repo's 4 unittest groups + compileall, `python3.12`, no setup step —
  see file for exact argv). **Upgrade path**: `git pull` the toolkit repo, re-run `install-into.sh --upgrade` (preserves
  `model-alloc.json`/`workflow-config.json`/`target-profile.json`, backs up prior managed-leaf content under
  `.review/agent-workflow-install-backups/`). Already upgraded once this session (223 commits) with no issues.
- **Working model-routing note (real gotcha hit twice this session)**: `opencode`'s `zai/glm-5.3` (pay-per-token)
  returns `Insufficient balance or no resource package` — same account-balance issue HANDOFF already flagged as
  possibly-live. **Fix: use `zai-coding-plan/glm-5.3` instead** (the coding-plan/subscription model alias) — this
  one has balance and works. Use this alias for any future `glm-5.3` dispatch via opencode.
- **Toolkit dispatch gotchas hit and worked around this session** (useful for the next reviewer/implementer dispatch
  via `agent-workflow.sh dispatch`):
  - `--orchestrator orca` defaults to `execution-mode live-tui`; a read-only role (e.g. `reviewer`) must pass
    `--execution-mode headless` explicitly or it's refused (`live_tui_requires_implementation_write`).
  - `--orchestrator cmux` requires being invoked from inside an actual cmux session (`Access denied - only
    processes started inside cmux can connect`) — not usable from a plain shell; `orca` worked fine instead.
  - **Always pass `--prompt-file` explicitly for `--role reviewer --produce-review`.** With no `--prompt-file`,
    `dispatch-core.sh` defaults to `.review/ISSUE-N-PROMPT.md`/`.txt` — if a prior session (e.g. an
    implementer's own internal self-review loop) left one there, the reviewer gets that stale prompt and
    returns unparseable prose (`refused: unparseable_output`), not a real review of what you actually wanted
    reviewed. Build the prompt with the review task plus
    `"$PRODUCT_HOME/scripts/output-contract.sh" render --role reviewer` appended (the exact JSON schema block the
    runtime must return), and pass it explicitly.
  - **`target-verify.sh`'s content-hash check breaks if the worktree has no `.gitignore`** — it hashes
    `git ls-files --cached --others --exclude-standard`, so `__pycache__/*.pyc` written mid-run by
    `compileall`/`unittest` (untracked, not excluded without a gitignore) changes the before/after snapshot and
    fails closed with `worktree changed during verification`. This repo's own `.gitignore` (added this session,
    `744a17d`) fixes it for `main`/future worktrees branched after that commit; a worktree branched from a commit
    before it needs a local (even uncommitted) `.gitignore` copied in for `target-verify.sh` to work.
- **Plan**: [`docs/plans/active/m7-orchestration-expansion.md`](docs/plans/active/m7-orchestration-expansion.md),
  new "M7 — Slice 2" section (S1–S13 pre-implementation, S14 folded post-implementation-review fixes) appended
  after slice 1's untouched §1–§14. `TaskV1.depends_on: tuple[str, ...]` (required), `WORKFLOW_REVISION_SCHEMA_VERSION`
  2→3 with legacy-reader retention, DAG admission at reader+publish (unknown ref/self-dep/duplicate-edge/cycle,
  iterative Kahn's), `WorkflowEligibility.eligible_tasks` real ready-set with in-flight-resume inclusion, driver
  rewritten to materialize by `task_id` not index range.
- **Round-1 plan review**: `zai-coding-plan/glm-5.3` (effort `high`, via `opencode`, `--auto`) against the plan
  draft + real code: **0 BLOCKER, 3 HIGH, 3 MEDIUM, 3 LOW** — all folded into the plan (§13) before dispatch. The
  3 HIGH findings were real: (1) the eligible-set definition silently dropped slice 1's in-flight-resume rule,
  contradicting a live test; (2) the driver sketch returned immediately on `WORKFLOW_COMPLETE`/`WORKFLOW_BLOCKED`
  without materializing anything, breaking idempotent re-invocation; (3) adding `depends_on` to
  `to_canonical_value()` silently orphans every pre-slice-2 workflow's idempotency keys across the schema
  upgrade — accepted explicitly and tested, not silently absorbed.
- **Implementation**: dispatched to `codex --model gpt-5.6-luna -c model_reasoning_effort=max` (non-interactive
  `codex exec`, Orca-managed worktree `m7-orchestration-expansion-slice2`) — hit one real plan contradiction
  before writing code (blanket `depends_on=()` migration for two existing regression tests would have made their
  `TASK_ORDER_VIOLATION` assertions meaningless under pure dependency-based ordering; fixed in-plan: those two
  tests declare an explicit `task-2.depends_on=("task-1",)` edge instead), redispatched, then ran **its own internal
  review→fix→recheck loop autonomously** (picked up on the installed toolkit's `AGENTS.md` model-routing pointer
  block and self-orchestrated using `.agent-workflow` conventions — `ISSUE-4-ROUND-STATE.json`,
  `ISSUE-4-IMPL-REVIEW.md`, a self-review round finding 4 LOW findings all fixed in `ad3ac1a`, `ISSUE-4-FIX-RECHECK.md`
  verdict CLEAN) — landed 3 commits (`456b851`/`ad3ac1a`/`3ac5862`), 426 tests green (contracts 162, kernel 143,
  execution 113, verification 8, up from 395), pushed and opened PR #50 on its own.
- **Independent post-hoc review** (separate orchestrator session, outside the implementer's own loop): toolkit-native
  `agent-workflow.sh dispatch --orchestrator orca --runtime opencode --role reviewer --produce-review --model
  zai-coding-plan/glm-5.3 --effort high --execution-mode headless` against `3ac5862`. Canonical `ISSUE-4-REVIEW.json`
  published: **status pass**, 7/8 checklist items independently confirmed, 1 nit (private-symbol import), no
  BLOCKER/HIGH. **Independent VERIFY** via `target-verify.sh`: **PASS 5/5**.
- **Real HIGH finding from a human adversarial pass on the PR** (not caught by either automated review round):
  `read_legacy_workflow_revision_v1_v2()` reused the v3 `WorkflowRevisionV1` type, whose `to_canonical_value()`
  unconditionally serialized every task with `depends_on` — so a v2-read revision's typed canonicalization
  silently diverged from its own `ReaderOutcome.canonical_payload` (an invariant every other reader in the module
  keeps by construction). **Fixed** (`deea8cd`): added `schema_version: int = 3` field to `WorkflowRevisionV1` so
  `to_canonical_value()` reproduces the shape it was actually read from; v2 legacy reader tags `schema_version=2`.
  Verified this does NOT regress the already-accepted HIGH-3 idempotency-orphaning behavior — the digest functions
  that must stay schema-agnostic (`workflow_task_sequence_digest`, `_validate_revision_copies`) iterate
  `TaskV1.to_canonical_value()` directly, untouched by this fix. Added the requested regression test. 427 tests
  green, independently re-verified (`target-verify.sh` PASS at `deea8cd`), pushed, PR comment posted, merged.
- **Merged**: PR #50 squash-merged to `main` as `eadc857` after the fix above; worktree and local branch cleaned up.

## Completed earlier this milestone (M7 — orchestration expansion, slice 1: linear multiple tasks, merged)

M7 slice 1 designed, reviewed twice, implemented, fixed, and merged:
[PR #49](https://github.com/hjung3113/agent-platform/pull/49) (squash-merged to `main` as
`062c580`). Tracking [Issue #4](https://github.com/hjung3113/agent-platform/issues/4), per the
[roadmap's M7 section](docs/plans/active/mvp-implementation-roadmap.md) (9-step expansion
order; slice 1 covers only step 1, "linear multiple tasks").

- **Plan**: [`docs/plans/active/m7-orchestration-expansion.md`](docs/plans/active/m7-orchestration-expansion.md),
  drafted grounded in the real committed code (`kernel/protocol_v1.py`, `publish.py`,
  `replay.py`, `execution/attempt.py`/`host.py`/`run_one_task.py`), not the roadmap's general
  vocabulary. Explicit scope decision (§2): only expansion-order step 1, not steps 1–3
  together — even step 1 alone requires a real schema-version bump (`WorkflowRevisionV1`
  single `task` field → `tasks` tuple) and a structural choice about how a multi-task
  Workflow Revision maps onto the existing one-task `lineage_store` run primitive. That
  structural choice (§3) was escalated to the user rather than decided unilaterally: **Option
  A** (keep the run primitive at one task unchanged; add a new outer pure-projection
  eligibility function sequencing per-task runs sharing one admitted `tasks` sequence) vs.
  Option B (change per-kind cardinality to `(kind, task_id)` inside one run, larger blast
  radius across `publish.py`). User chose **Option A** — smallest blast radius, reuses M1's
  run/lock/replay primitives completely unchanged.
- **Review round 1** (pre-implementation, plan-doc review): `glm-5.3` (effort `high`, via
  `opencode`, `--auto`) against the plan draft and the real committed code found **3 BLOCKER,
  3 HIGH, 4 MEDIUM, 5 LOW** — every citation in the draft's baseline section verified accurate;
  the findings were omissions in the change inventory, not fabricated claims. The three
  BLOCKERs were the same class: the plan's inventory of code reading the old `revision.task`
  field was incomplete — missed the `publish.py` VERIFICATION branch (crashes every v2
  Verification publish), missed `execution/attempt.py` and `execution/host.py` (both also
  read `revision.task`, and the draft falsely claimed `host.py` was "completely unchanged"),
  and missed that `kernel/replay.py`'s fold had no branch for the retained legacy
  single-`task` shape (pre-M7 history would silently replay to `workflow_revision=None`
  instead of raising or preserving the value). All 15 findings were folded directly into the
  plan's design sections (not just logged) — see the plan's §13 "Adversarial review log."
- **Implementation dispatch, attempt 1 — blocked on a missing file, not a design issue:**
  dispatched to `codex --model gpt-5.6-luna -c model_reasoning_effort="max"` (via `codex exec`,
  non-interactive — the Orca-managed interactive TUI hit an unrelated `codex-update-prompt`
  guard that blocks programmatic `terminal send` into that specific prompt) in a fresh Orca
  worktree (`hjung3113/m7-orchestration-expansion-slice1`). Failed immediately: the plan doc
  was uncommitted in the main checkout, so the fresh worktree (branched from `main`) never saw
  it. Fixed by copying the plan file into the worktree checkout directly (still uncommitted —
  this repo's rule is one Kernel/authoritative-publication writer, not a rule against
  uncommitted planning docs, but the fix here was mechanical file placement, not a design
  question).
- **Implementation dispatch, attempt 2 — a real design contradiction the review missed,
  caught by the implementing agent, not guessed around:** `luna` correctly stopped before
  writing any code and reported: the plan's post-BLOCKER-fix §4.4 claimed every per-task run
  commits an *identical* `WorkflowRevisionV1` record (byte-for-byte) across the whole
  workflow — but `_kind_binding_rejection`'s `WORKFLOW_REVISION` branch
  (`publish.py:322–328`, unchanged, already spot-checked accurate by round 1's review)
  requires each candidate's `request` field to bind to *that run's own* genesis Request. Since
  every per-task run has a distinct genesis Request (distinct `record_id`), an identical
  record could never actually publish into more than one run — `GENESIS_REQUEST_BINDING_MISMATCH`
  on the second run, every time. Not escalated to the user as an architecture decision (unlike
  M6 round 2's spec-retraction question) because there was no real tradeoff: fixed directly in
  the plan (§4.2–§4.4, addendum in §13) — what's shared identically across per-task runs is
  the `tasks` sequence and a `tasks`-only sub-digest, not the whole record; each run binds its
  own genesis Request as it always would. `run_one_task`'s new parameter renamed
  `admitted_tasks: tuple[TaskV1, ...] | None` (a bare tasks tuple, not a full revision record)
  to make this structurally obvious rather than re-inviting the same mistake.
- **Implementation dispatch, attempt 3 — landed clean:** same `luna` max dispatch, corrected
  plan copied into the worktree. Commit `a4f6121` (worktree
  `m7-orchestration-expansion-slice1`, based on `a07e56a`), one commit, 30 files changed. **386
  tests green** (contracts 152, kernel 125, execution 102, verification 7 — up from 357
  pre-M7) + `compileall`, independently re-run outside the implementation session by the
  orchestrator, matching every prior milestone's discipline. Spot-checked the critical fix
  (`run_one_task.py`'s `admitted_tasks` parameter, not a shared revision record) against the
  corrected plan text — matches exactly.
- **Round 2 (post-implementation review, PR #49):** opened PR #49 for `a4f6121`. Dispatching a
  manual `glm-5.3`-via-`opencode` review round hit an account-balance error (`Insufficient
  balance or no resource package`) before it could run — no findings from that path. Instead,
  GitHub's `chatgpt-codex-connector` auto-review (2 inline P1/P2 findings) plus a manual
  adversarial pass by the repo owner directly on the PR (4 more findings, all P1 except one P2)
  found **6 real defects, all against this slice's own core guarantee** ("strict ordered
  multi-task execution," not later-slice behavior) — none required a protocol/contract schema
  change: (1) eligibility trusted the caller-supplied `task_runs` mapping key instead of
  checking a run's own committed `attempt_packet.task_id`, letting a swapped run silently pass
  as the wrong task's completion; (2) eligibility never checked for out-of-order committed
  work, silently normalizing a later task's completion before an earlier one; (3) the
  fail-closed eligibility/divergence projection existed but was never called from
  `run_workflow()`'s real execution path — it just looped tasks unconditionally; (4)
  `run_workflow()` reused one `expected_output_digest` across every task, so no real
  (non-`noop`) multi-task workflow could verify correctly; (5, codex) crash-resume rebuilt and
  republished the Attempt Packet from a possibly-mutated workspace before checking for an
  already-committed one, guaranteeing `IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_CONTENT` on resume
  after a Result-stage crash; (6, codex) the per-task idempotency key omitted the Request's own
  identity, so two distinct Requests decomposing into an identical task sequence would collide.
  All 6 folded into the plan doc's new §14, with fix directives, before dispatching
  implementation — same discipline as every prior milestone's review round.
- **Implementation dispatch, attempt 1 — a real contradiction in the fix directive itself,
  caught by the implementing agent, not guessed around:** `codex --model gpt-5.6-luna -c
  model_reasoning_effort="max"` stopped before writing any code and reported that §14.3's
  required regression test ("re-invoking `run_workflow` with task 1's content changed must raise
  `WORKFLOW_REVISION_DIGEST_DIVERGENCE`") could never pass under the very lookup mechanism that
  same fix specifies: the per-task idempotency key is itself derived from the tasks-sequence
  content digest, so changing task 1's content changes every downstream key — the lookup
  correctly finds nothing, because a changed sequence is a different workflow by this slice's
  own content-addressed design, not a divergent copy of the same one. This was an error in the
  review directive's own drafting (an over-specified test), not a real implementation gap.
  Corrected directly in the plan (§14.3), same "no real tradeoff, fix in place" precedent as the
  first implementation round's §4.4 addendum: kept the real ordering/identity guarantees
  (§14.1/§14.2), retracted only the unsatisfiable divergence-on-changed-content test, and noted
  the underlying cross-run digest-agreement check is now structurally unreachable from
  `run_workflow()`'s own call path — same class of documented, deliberately-kept dead scaffold
  as M4's `OmissionRecord` (see "Explicit scope limits" below).
- **Implementation dispatch, attempt 2 — landed clean:** same `luna` max dispatch, corrected
  plan re-read mid-run per an explicit note in the redispatch prompt. Commit `2b8f2f9`, 6 files
  changed. **395 tests green** (contracts 152, kernel 130, execution 106, verification 7, up
  from 386) + `compileall`, independently re-run outside the implementation session. Diff
  spot-checked against all 6 fixes (§14.1–§14.6) before committing — matches exactly. Pushed to
  PR #49; PR comment posted explaining the round-2 fix and the §14.3 correction.
- **Merged**: PR #49 squash-merged to `main` as `062c580` after user confirmation (repo has no
  CI configured to wait on). Worktree (`m7-orchestration-expansion-slice1`) and local feature
  branch cleaned up (force-removed/force-deleted — squash-merge history isn't fast-forward-
  detectable by git, content confirmed present in `main` first). One stale untracked copy of
  the plan doc in the main checkout (predating this session, never committed) was removed
  before pulling — the merged, final §14-inclusive version is now the tracked one.

## Completed earlier this milestone (M6 — verification/evidence hardening, merged)

M6 implemented and merged: [PR #48](https://github.com/hjung3113/agent-platform/pull/48)
(squash-merged to `main`), per
[`docs/plans/active/m6-verification-evidence-hardening.md`](docs/plans/active/m6-verification-evidence-hardening.md),
tracking [Issue #5](https://github.com/hjung3113/agent-platform/issues/5).

- **Plan**: drafted grounded in the real M2–M4 code (not the roadmap's general vocabulary),
  folding in the 8 M6-tagged findings from the M5 ledger (issue #5 comment 5386949987, worked
  through individually in the plan's §1.1). Reviewed by `glm-5.3` (effort `high`, via
  `opencode`, `--auto` — the default sandbox denies writes outside the repo, needed for the
  reviewer's findings-file output) before any implementation: **2 BLOCKER, 6 HIGH, 4 MEDIUM,
  3 LOW**, all addressed in the plan (§13) before dispatching implementation — both BLOCKERs
  were the same class (a check unsatisfiable by any real producer path: the env-binding
  comparison used two differently-derived identity fields that never agree; the
  self-verification distinctness check would reject every honest run in this single-runtime,
  in-process-verifier deployment). The second is now an explicit scope limit (plan §6/§11),
  not a false guarantee.
- **Implementation**: dispatched to `codex --model gpt-5.6-luna -c
  model_reasoning_effort="max"` in an Orca worktree (`hjung3113/m6-verification-evidence-
  hardening`), ~32 min, one commit (`93acbab`), 19 files, 338 tests green (contracts 140,
  kernel 102, execution 91, verification 5) + `compileall`, independently re-run outside the
  implementation worktree before opening the PR. Diff spot-checked against the plan's two
  BLOCKER fixes (`host.py`'s `runtime_identity=profile.identity`; `publish.py`'s
  bidirectional Finding-count rule) — matches exactly.
- **Round 2 (post-implementation review, this same slice — the M3/M4-style second round did
  happen, just automated rather than manual):** GitHub's `chatgpt-codex-connector` auto-review
  on PR #48 found a real P1: round 1's plan §6 had retracted the self-verification
  execution-distinctness check as unsatisfiable-by-the-honest-path, but
  `docs/specs/06-review-verification-evidence.md:15` **normatively requires** it — retracting
  a real spec requirement is a defect, not a legitimate scope limit. Escalated to the user
  (architecture decision, not unilaterally resolved) — user chose "implement real separation."
  Corrected design: the verifier now runs as a genuinely separate OS process
  (`verification/stub_verifier_cli.py`, subprocess-spawned) with a real random per-invocation
  execution nonce, checked at publish time against a matching real per-spawn nonce now on the
  Result (`RuntimeObservationV1.execution_identity`, generated around `host.py`'s existing real
  `subprocess.run` spawn of OpenCode). `ResultV1` bumped to schema v2 with the same
  legacy-reader-retention pattern round 1 built for `VERIFICATION`. Implementation hit one real
  mid-build blocker the agent correctly stopped on instead of silently deviating (the nonce
  payload hashed a raw `time.time_ns()` int, which this repo's canonicalizer rejects outside
  ±2⁵³) — plan corrected (stringify timestamp, drop an unneeded PID field), agent resumed.
  Landed as `bab23bb`, 351 tests green (contracts 143, kernel 109, execution 92, verification
  7) + `compileall`, independently re-verified outside the worktree, diff spot-checked against
  the corrected design. Pushed to PR #48; PR comment posted explaining the round-2 fix.
- **Round 3 (manual second-pass review against the final `bab23bb` diff, this same slice):**
  ran the M3/M4-style manual second review round — `glm-5.3` (effort `high`, via `opencode`,
  `--auto`) against `git diff main...bab23bb`, the governing spec, and the plan doc, with 4
  adversarial probes run directly against the real publish boundary. Found **0 BLOCKER, 2
  HIGH, 3 MEDIUM, 4 LOW**: HIGH 1 — publishing a schema-1 candidate crashed the Kernel
  boundary with an unhandled `AttributeError` instead of a typed `Rejected` (reproduced);
  fixed with a schema-freshness gate in `publish.py` (new
  `PublishRejectionCode.STALE_SCHEMA_VERSION`). HIGH 2 — round-1-committed schema-2
  Verifications became unreplayable after round 2 reused their dispatch key (reproduced:
  `malformed_payload: verification_payload_keys_missing=['verifier_execution_identity']`);
  fixed by bumping `VERIFICATION_SCHEMA_VERSION` to 3 and retaining the round-1 shape as a
  legacy reader at the freed `(VERIFICATION, 1, 2)` slot. MEDIUM 1 closed by the HIGH 1 fix
  (same root cause — a v1 RESULT candidate previously committed a dead-end record). MEDIUM
  2/3 and the 4 LOWs were plan-doc overclaim corrections (the execution-identity nonce's
  actual evidentiary strength) and verifier-subprocess robustness (`PYTHONPATH` resolution,
  stderr capture) — full detail in the plan doc's §14 "Round 2 manual review" subsection.
  Dispatched fix implementation to `codex --model gpt-5.6-luna -c
  model_reasoning_effort="max"` in the same worktree; landed as `36e6bc7`, 357 tests green
  (contracts 146, kernel 111, execution 93, verification 7, up from 351) + `compileall`,
  independently re-verified outside the worktree, diff spot-checked against both HIGH fixes
  — matches exactly. Pushed to PR #48; PR comment posted explaining round 3.
- **Merged**: PR #48 squash-merged to `main` after user confirmation (repo has no CI configured
  to wait on — `gh pr checks` reports none). Worktree and local feature branch cleaned up.

## Completed earlier (M5 — cross-project failure-mode ledger, research/docs only)

M5 done per [`mvp-implementation-roadmap.md`](docs/plans/active/mvp-implementation-roadmap.md)'s
M5 section, tracking [Issue #46](https://github.com/hjung3113/agent-platform/issues/46).
Research/documentation only — no plan doc, no adversarial review round, no code.

- **Method**: dispatched `codex --model gpt-5.6-luna -c model_reasoning_effort="xhigh"
  --sandbox read-only` in 5 parallel Orca worktrees (one per sibling repo), each doing a
  cheap `git log --all` keyword pass first (fix/bug/regression/revert/hotfix/crash/race/
  leak/deadlock/security/incident/broke/failed), then deep-reading only flagged commit
  diffs/PR bodies for real root cause + actual fix. Orchestrator (main session) polled via
  Monitor until all 5 confirmed idle, read back full scrollback per terminal, then removed
  all 5 scratch worktrees (verified clean, no changes) after extraction.
- **Deliverable**: new [`docs/research/failure-mode-ledger.md`](docs/research/failure-mode-ledger.md),
  separate from `adoption-ledger.md` (design-pattern adoption, not failure records).
- **Coverage**: all 4 mining-scope repos scanned — `opencode-orchestrated-agent-workflow`
  (147 commits, 17 records), `agent-migration-pipeline` (175 commits, 5 records),
  `general-low-reasoning-agent-harness` (746 commits, 30 records), `thin-agent-harness`
  (8 commits, 2 records) — plus `meta-prompting-skill` applicability-only paragraph (per
  roadmap, conceptual repo not a failure-mining target). GitHub issue/PR API was unavailable
  in the sandboxed recon environment for 3 of 4 repos; local PR refs/commit bodies used
  instead where flagged.
- **M6-relevant findings folded into M6's adversarial review checklist**: posted as
  [issue #5 comment](https://github.com/hjung3113/agent-platform/issues/5#issuecomment-5386949987) —
  all 8 records tagged "directly relevant to M6" in the ledger, each restated as a concrete
  adversarial question with source record and their fix: semantically-forged-but-digest-valid
  provenance (`opencode-orchestrated-agent-workflow` 3f77019 et al.), dangling-reference/
  stale-concurrent-write acceptance (`agent-migration-pipeline` PR #57), racy admission-proof
  idempotency + unsigned nonce evidence (`general-low-reasoning-agent-harness`
  8f1e465/dc8cf31), fail-closed checks wrongly rejecting legitimate rotated/lagged evidence
  (`ed08df9`/`d2e6159`), absent/empty/telemetry-only evidence accepted as fresh state
  (`c8f4789`), verification wired into tests but not the production path (`d671ba9`),
  mismatched-field false rejection masking a real integrity check (`f7d1081`), circular
  approval-digest self-reference and ambiguous record ownership (`thin-agent-harness`
  `b9b9460`/PR #2). **M5→M6 gate now fully satisfied** — this was the last precondition
  before M6 design.

## Completed earlier (M4 — deterministic Context Compiler, merged)

M4 implemented, reviewed twice, and merged: [PR #47](https://github.com/hjung3113/agent-platform/pull/47)
(squash-merged to `main` as `907c007`), per
[`docs/plans/active/m4-deterministic-context-compiler.md`](docs/plans/active/m4-deterministic-context-compiler.md).
`AttemptPacketV1.context_digest` is now a real compiled Context Pack digest, not M2's
`_fixture_digest` (deleted).

- **Implementation** dispatched as a dependency-ordered task DAG (`gpt-5.6-luna` max,
  `glm-5.3` high/low via opencode); orchestrator (main session, in-process) verified/
  integrated between steps and caught one real cross-task bug before it shipped:
  compile-time placeholder `reserved_cost` vs execute-time real value would have made every
  `execute()` call raise `StaleContextPackError` — fixed by hoisting the shared constant/
  helper into `context_compiler.py` so both sides compute identically.
- **First review round** (`chatgpt-codex-connector` automated PR review + repo owner
  adversarial review, both against the real committed code) found and fixed 4 P1s + 3 P2s:
  unverified `contract_refs` accepted with zero authority check (now fail-closed rejected at
  both real entry points — `UnverifiedContractRefError`); contract-ref dedup grouped by
  `record_id` alone (now `(contract_kind, record_id)`); budget accounting undercounted the
  real rendered-message overhead (now computed from the actual `render_context_pack` output,
  single source of truth shared with the real spawn rendering; `CONTEXT_BUDGET_MAX` lowered
  128 KiB → ~117 KiB); evidence-file writing was an unguarded hard dependency of execution
  (now `try/except OSError`, non-fatal, matching its own documented non-authoritative
  status); evidence temp-file race; `build_attempt_packet` missing an explicit `task_id`
  check; this file's stale "M4 is future work" framing.
- **Second review round** (plan §14 — `glm-5.3` effort high via opencode, against the
  post-first-round-fix code) found 0 BLOCKER/HIGH, 3 MEDIUM + 4 LOW, all fixed:
  `kernel.publish.read_committed_contract` passed an unvalidated caller `run_id` straight to
  `open_run`, which creates the run directory as a side effect (a typo or `"../elsewhere"`
  could silently create a stray directory or escape `runs/` entirely) — now validates format
  + existence first, raising a new typed `UnknownRunError`; `reserved_cost` only reflected
  rendered-message *length*, so a length-preserving render-template edit was invisible to
  `context_digest` — `ContextPack` gained a `rendered_digest` field (a real digest of the
  actual rendered bytes) closing that gap structurally; the PR #47 `except OSError: pass`
  evidence guard shipped with no negative test (added); a docstring implied an
  omission-selection mechanism that doesn't exist in code (corrected); a bare `assert`
  guarding a real invariant in `run_one_task.py` (vanishes under `python -O`, replaced with
  a real check); evidence files landed at mode 0600 via `tempfile.mkstemp` regardless of
  umask, inconsistent with the lineage store's 0644 (chmod'd to match). One LOW
  (`publish()` doesn't itself validate `context_digest` against a compilable pack) left as
  an explicit documented deferral — same "trust boundary is execution, not publication"
  property M2/M3 already had for `context_digest` generally, not a new gap M4 introduced.
- **314 tests total, all green** (up from 283 pre-M4): `test_context_compiler.py`,
  `test_context_evidence.py`, `test_m4_integration.py` are new; `test_attempt.py`/
  `test_attempt_and_host.py`/`test_host.py`/`test_publish.py` extended; full validation
  command block below.
- Optional/omission machinery (`OmissionRecord`, `omitted` field) remains real but
  structurally unreachable — no code path ever constructs an optional `ContextUnit`, flagged
  by the owner review as dead scaffold both rounds — **deliberately not removed**: an
  explicit settled decision from M4 design-grilling round 2 (forward-compatible shape, same
  precedent as M3's `M3_REQUIRED_CAPABILITIES = ()`). Revisit only if a concrete milestone
  need makes optional candidates real (see "Explicit scope limits" below).

## Validation (M4, post-merge)

```
PYTHONPATH=product/src python3.12 -m unittest discover -s product/tests/contracts -p 'test_*.py'   # 133 passed
PYTHONPATH=product/src python3.12 -m unittest discover -s product/tests/kernel -p 'test_*.py'       # 85 passed
PYTHONPATH=product/src python3.12 -m unittest discover -s product/tests/execution -p 'test_*.py'    # 91 passed
PYTHONPATH=product/src python3.12 -m unittest discover -s product/tests/verification -p 'test_*.py' # 5 passed
python3.12 -m compileall -q product/src product/tests                                               # passed
```

314 tests total, all green.

## Completed earlier (M3)

- M3 — Real Host/security boundary and first runtime adapter (OpenCode), PR #44 (plan) + #45
  (impl). See prior handoff commits for full detail if needed — not reproduced here to keep
  this file current rather than cumulative. `execution/host.py`'s deny-first execution,
  `execution/workspace_snapshot.py`'s Workspace Snapshot identity, and
  `kernel/runtime_capability.py`'s `RuntimeCapabilityProfile` are the primitives M4 reused
  unchanged.

## Completed earlier (M2)

- M2 — Attempt/Result/Verification/Receipt one-task protocol E2E, PR #43. See prior handoff
  commits for full detail if needed.

## Completed earlier (M1)

- M1 — Kernel authoritative publication and replay spine, PR #41. See prior handoff commits
  for full detail if needed.

## Next session — start M7 slice 3 (roadmap expansion-order step 3: logical Resource Claims)

M7 slice 2 is fully landed on `main` (`eadc857`) — see "Completed this milestone" above. Next
session should start the next expansion-order slice per the roadmap's 9-step M7 plan: step 3,
logical Resource Claims with read/write conflict semantics. Same discipline as slices 1/2: a
plan doc grounded in the real committed code (not roadmap vocabulary — read `TaskV1`/
`WorkflowRevisionV1` post-slice-2, `workflow_eligibility.py`'s `eligible_tasks`, and
`run_one_task.py`'s driver as they now exist, with `depends_on` and real DAG scheduling already
in place), a pre-implementation adversarial review round, then implementation, then a
post-implementation review round before merge — do not batch step 3 with step 4 (retry) or
later steps, per the roadmap's own rule, which both prior slices' review rounds have repeatedly
found real value in enforcing narrowly.

**Use the now-installed `feedbackops-workflow` toolkit's actual dispatch pipeline this time**,
not raw `codex exec`/`opencode run` calls — see "Toolkit adopted this session" above for the
exact gotchas (glm-5.3 model alias, orca execution-mode, cmux session requirement, `--prompt-file`
requirement for reviewer dispatch, `.gitignore` requirement for `target-verify.sh`). This
session's own review-dispatch mistakes (defaulting to a stale prompt file, forgetting
`--execution-mode headless`) are exactly what to avoid repeating. Implementation model routing
this session was `codex --model gpt-5.6-luna -c model_reasoning_effort=max`; review was
`zai-coding-plan/glm-5.3` effort `high` via `opencode` — confirm with the user whether the same
routing applies before assuming it's fixed policy.

**Also worth noting**: this session's implementer (`luna` max) autonomously ran its own internal
review→fix→recheck loop using the installed toolkit's conventions before the orchestrating
session ever dispatched an independent review — this happened because the toolkit's
`AGENTS.md` managed-marker block explicitly tells any dispatched agent to read
`model-alloc.json`/`conductor-persona.md` before acting. This is a real behavior change from
slice 1 (which had no such self-directed loop) worth expecting again, not a bug — but it means
checking `git log`/`.review/ISSUE-N-*` state on the worktree *before* assuming a fresh dispatch
is starting from nothing.

**A human adversarial pass on the PR caught a real HIGH finding that neither automated review
round did** (the schema-v2 canonical-shape divergence in `WorkflowRevisionV1.to_canonical_value()`,
fixed in `deea8cd`) — a reminder that automated review rounds (even at effort `high`) are not a
substitute for a manual pass on the final diff before merge, same lesson M4's and M7-slice-1's
own review rounds already recorded.

Also still pending, named explicitly in the M7 slice 1/2 plans as deferred rather than dropped:
ADR-0009's Reviewer/Verifier split (blocked on risk-tier/Plan-Check machinery that doesn't exist
anywhere yet) and M3's per-task capability-requirement gap (below) — both "likely" M7 territory
per the roadmap, not committed to any specific future slice yet.

## Explicit scope limits carried forward from M3/M4 (not gaps to silently close later)

Per AGENTS.md rule 9 (YAGNI) and M3/M4's own explicit-deferrals precedent — revisit only
when a concrete milestone need makes one of these load-bearing:

- **Per-task capability-requirement differentiation.** M3's admission policy
  (`execution/policy.py`) is one fixed global table; it cannot express "this specific task
  requires network/filesystem/process isolation as a guarantee." Checked at M4 design start
  per the prior handoff's note — M4's Context Compiler is not the right place either (it
  compiles disclosure, not admission policy). Still open, still deferred to M7's real
  orchestration layer or a dedicated contract change.
- **OpenCode global-config provenance.** `execution/opencode_adapter.py` probes and digests
  merged config layers, and `execution/host.py` pins the *project*-layer config by launching
  OpenCode with `cwd` at the exact resolved workspace root — but OpenCode's CLI has no flag
  to pin a spawned process to exactly the probed configuration or to prove it didn't
  additionally discover an unprobed global/default layer. Same enforceability class as
  network denial (below); would need a concrete OpenCode-side mechanism, not a Kernel-side
  one, to close.
- **Network and filesystem/process-interception-beyond-declared-scope remain unenforced**,
  by original M3 design (plan §2/§6) — profiled `PARTIAL`/`UNKNOWN`, `require()` fails closed
  for any Attempt that actually needs them. A real per-OS sandbox (macOS `sandbox-exec`/
  Seatbelt, Linux seccomp-bpf/network namespace) is not assigned to any milestone yet; raise
  it as an explicit roadmap amendment before any workflow's task genuinely requires these as
  `SUPPORTED` rather than `PARTIAL`.
- **External-effect denial is declarative admission rejection only**, not a process-boundary
  control — same document/enforcement-honesty class as network. `permission_envelope.
  external_effects` stays empty for every M3/M4 path; real release/external-effect
  authorization is M10 scope per the roadmap, unchanged.
- **M4's optional/omission machinery is structurally unreachable.** `OmissionRecord` and
  optional-cost accounting are real code but no path ever constructs an optional
  `ContextUnit` — flagged twice by review as dead scaffold, kept deliberately (M4 design-
  grilling round 2 decision). Revisit only if a later milestone gives M4 a real optional
  candidate to omit under budget pressure.
- **`kernel.publish()` does not itself validate `context_digest`** against any compilable
  Context Pack — the M4 unverified-`contract_refs` gate lives at the execution trust boundary
  (`build_attempt_packet`, `host.execute`), not at publication. A hand-built
  `AttemptPacketV1` with a refs-influenced digest could theoretically be published (never
  executed — both real entry points always reject it), same class of property M2/M3 already
  had for `context_digest` generally. Documented deferral, not a regression M4 introduced.

## Deferred until the corresponding gate

### M8 / real cross-version edge or platform validation

- cross-platform (Windows/Linux) crash-consistency validation of the M1 store
- compatibility registry, historical cross-version rule provenance, retained-lineage replay
- reader/rule retirement reachability

### Only if a concrete need appears later

- separate idempotency index (current directory-scan dedupe is bounded by M1's small
  per-run record count)
- storage-backend abstraction beyond the concrete filesystem implementation
- cross-machine locking/leases for multi-process publication across machines

### Later milestones (unchanged from M0/M1/M2/M3 handoff)

- #5 verification/evidence soundness — **done, M6 merged** (hardened criterion/evidence
  policy, execution-provenance independence, self-verification closed by real distinct
  process identity rather than M2's string inequality).
- #4 deterministic orchestration after replay/authoritative state is stable (M7 — **slice 1
  (linear multiple tasks) done, merged PR #49; slice 2 (DAG dependency validation) done, merged
  PR #50**; remaining: resource claims, retry/repair/replan, fan-in, safe parallelism,
  Reviewer/Verifier split per ADR-0009;
  also where M3's per-task capability-requirement gap above likely gets closed; M4's
  `lineage`/`observed` source classes stay structurally empty until M7 gives them real
  predecessors/tool output).
- #24 skill supply-chain (M10) after core Kernel/runtime boundaries are executable.
- #9/#25 compatibility registry, historical cross-version rule provenance, retained-lineage
  replay, and reader/rule retirement reachability remain M8/real-cross-version-edge work.
- additional runtime adapters (M9) built against M3's `RuntimeCapabilityProfile`/
  containment/redaction primitives — cross-runtime canonical-action conformance matrix.
