# Handoff

## Completed in this slice (M6 — verification/evidence hardening, PR open)

M6 implemented per [`docs/plans/active/m6-verification-evidence-hardening.md`](docs/plans/active/m6-verification-evidence-hardening.md),
tracking [Issue #5](https://github.com/hjung3113/agent-platform/issues/5). **PR not yet
merged**: [PR #48](https://github.com/hjung3113/agent-platform/pull/48).

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
- **Not yet done**: PR review/merge. No second adversarial review round happened this slice
  (M3/M4 both had two rounds — draft-review and post-implementation-review; M6 only had the
  pre-implementation round so far). Next session should do a post-implementation review pass
  on PR #48 before merging, mirroring M3 §14/M4 §14's precedent, not skip straight to merge.

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

## Next session — fixed scope: review and merge PR #48 (M6)

M6 is designed and implemented (see above); [PR #48](https://github.com/hjung3113/agent-platform/pull/48)
is open, not merged, and has not had a post-implementation adversarial review round yet — M3
and M4 both had two review rounds (pre-implementation plan review, then a second pass against
the real committed diff), and M6 has only had the first so far. **First action next session**:
run a second review round against PR #48's actual diff (not the plan doc) — same process as
M3 §14/M4 §14 — before merging, and fold any findings into the plan doc's §14 (create it,
mirroring M4's §14 stub) and fix them in the PR. Once merged, next scope is M7 (orchestration
expansion — retry/repair/replan, fan-in, safe parallelism, multi-task DAG, Reviewer/Verifier
split per ADR-0009), which several of M6's explicit scope limits (plan §11 — genuine
verifier-environment independence, cross-run Finding lifecycle, stale/flaky/retry evidence)
are deferred to.

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

- #5 verification/evidence soundness after authoritative lineage/snapshot bindings exist
  (M6 — hardened criterion/evidence policy, execution-provenance independence,
  self-verification closed by real distinct identity rather than M2's string inequality).
  M3's real Result/Runtime Observation binding and M4's real Context Pack make this possible
  but do not implement it. M5's failure-mode ledger is done; next session starts M6.
- #4 deterministic orchestration after replay/authoritative state is stable (M7 — retry/
  repair/replan, fan-in, safe parallelism, multi-task DAG, Reviewer/Verifier split per
  ADR-0009; also where M3's per-task capability-requirement gap above likely gets closed;
  M4's `lineage`/`observed` source classes stay structurally empty until M7 gives them real
  predecessors/tool output).
- #24 skill supply-chain (M10) after core Kernel/runtime boundaries are executable.
- #9/#25 compatibility registry, historical cross-version rule provenance, retained-lineage
  replay, and reader/rule retirement reachability remain M8/real-cross-version-edge work.
- additional runtime adapters (M9) built against M3's `RuntimeCapabilityProfile`/
  containment/redaction primitives — cross-runtime canonical-action conformance matrix.
