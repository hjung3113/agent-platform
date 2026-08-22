# Handoff

## Completed in this slice (M3 implementation)

- M3 — Real Host/security boundary and first runtime adapter (OpenCode) implemented and
  merged per [`docs/plans/active/m3-real-host-security-boundary.md`](docs/plans/active/m3-real-host-security-boundary.md),
  plan PR #44, implementation PR #45. Evidence attached to tracking
  [Issue #34](https://github.com/hjung3113/agent-platform/issues/34).
- Plan drafted, adversarial-reviewed by `glm-5.3` (effort high, via opencode) against the
  roadmap's five lenses plus targeted attacks on the deny-first enforcement claims and TOCTOU
  behavior, then hardened (plan §13) before implementation started — found and fixed one
  BLOCKER (network deny-first overclaimed as real process enforcement) and multiple HIGH
  findings (unbound admission-policy inputs, an unclosed admission-to-spawn TOCTOU window,
  filesystem/process "enforcement" overclaiming interception it can't deliver).
- Implementation dispatched via `orca`/`opencode`/`codex exec` as an 18-task DAG: `gpt-5.6-luna`
  (effort max) for straightforward implementation, `glm-5.3` (effort high, via opencode) for
  the two security/design-critical pieces (OpenCode adapter probe, deny-first Host), `glm-5.3`
  (effort low) for containment test fixtures. 11 commits on `product/m3-real-host-boundary`,
  each independently reviewable: Workspace Snapshot identity → containment fixtures → policy
  table + adapter probe → deny-first Host → redaction gate → attempt-packet real identities →
  reference driver/E2E integration → stub retirement.
- Real design defect caught mid-implementation, not just at review: PR4's implementer
  (`glm-5.3` high) surfaced rather than silently patched a contradiction between the fixed M3
  policy table (which named `read_workspace`/`write_workspace` as required capabilities) and
  the honest OpenCode adapter (which can only ever mark those `PARTIAL`, never `SUPPORTED`
  per the plan's own honesty rule) — the unpatched combination made every M3 execution
  permanently fail closed at admission. Resolved by making `M3_REQUIRED_CAPABILITIES` empty
  by design: M3's real enforcement is `PermissionEnvelope` + containment + credentials
  allow-list, not the `require()`/`SUPPORTED`-capability mechanism.
- A second, larger review round after both PRs were opened: the repo owner and
  `chatgpt-codex-connector` (automated PR review) found 14 further real defects across the
  plan and the implementation — verified individually against the actual committed code
  (not assumed correct) before fixing. All P1s fixed except two, which were investigated and
  then explicitly, honestly downgraded to documented scope limits rather than silently left
  implicit (see "Explicit deferrals" below). Fixed in 5 follow-up commits (also merged in
  PR #45), full detail in the plan doc's §14:
  - `generated_digest` hashed only declared path *names*; a Git-ignored generated artifact's
    actual content could change with zero digest change. Now hashes each path's own
    file/symlink/absent state.
  - Nested-repository identity bound only path + HEAD commit; uncommitted changes inside a
    nested worktree never changed the outer Workspace Snapshot. Now recurses through the
    nested repo's own full `snapshot_identity`.
  - `RuntimeCapabilityProfile.runtime` bound only a reported `--version` string; a binary
    substituted in place with different code reporting the same version would pass the
    Host's no-silent-substitution recheck unnoticed. Now folds a content digest of the
    executable's actual bytes into `runtime`.
  - `host.execute()` spawned OpenCode with **zero task information** — no objective, no
    acceptance criteria — so the runtime succeeded independently of what was actually
    admitted; the E2E chain proved protocol wiring only. `execute()` now takes the
    authoritative `TaskV1` and renders it as the runtime's `run` message.
  - A nonzero runtime exit code was silently discarded (`subprocess.run(check=False)`) and
    still produced a successful Result. Now raises `RuntimeExecutionFailedError` before any
    Result is built — "exit code alone doesn't establish completion" always meant zero-exit
    isn't *trusted*, never that a crash should be *discarded*.
  - `capture_output=True, text=True` decoded subprocess output before the redaction scanner
    ever ran, so invalid UTF-8 raised `UnicodeDecodeError` instead of degrading to
    `"unknown"`. Output is now captured as bytes and decoded under Host control.
  - External-effect denial was documented/claimed as "real process-boundary + policy
    enforcement," but the spawned OpenCode process/shell was never actually prevented from
    calling `git push`/`gh`/`curl` directly, and `requested_effects` wasn't even reachable
    from `execute()` in the first shipped draft. Relabeled to match what's actually
    enforced (declarative admission rejection only, same class as network denial) and wired
    `requested_effects` through as a real `execute()` parameter.
  - The plan documented an inverted OpenCode config-merge precedence ("pass specific first,
    inherited/global last" combined with "later overrides earlier" — backwards). Corrected
    the calling convention; no merge-code change was needed.
  - The redaction gate's design implied reusing `admission.admit_attempt`'s pre-spawn
    `retain_evidence` check for post-spawn stdout/stderr — impossible, since output doesn't
    exist until after the subprocess returns. Clarified as two genuinely separate gates
    (the implementation already had this right; only the plan text was wrong).
  - Symlink-loop containment hardened with an explicit, Python-version-independent bounded
    chain walk, as defense-in-depth (the cited failing case already passed on this
    platform/Python version — could not reproduce the reviewer's exact failure).

## Validation (M3, post-merge)

```
PYTHONPATH=product/src python3.12 -m unittest discover -s product/tests/contracts -p 'test_*.py' -v   # 133 passed
PYTHONPATH=product/src python3.12 -m unittest discover -s product/tests/kernel -p 'test_*.py' -v       # 78 passed
PYTHONPATH=product/src python3.12 -m unittest discover -s product/tests/execution -p 'test_*.py' -v    # 67 passed
PYTHONPATH=product/src python3.12 -m unittest discover -s product/tests/verification -p 'test_*.py' -v # 5 passed
python3.12 -m compileall -q product/src product/tests                                                  # passed
```

283 tests total, all green. M0/M1/M2 suites: `test_m2_integration.py` was deliberately
**deleted**, not just left green — `test_m3_integration.py` proves the identical Kernel
publish/replay/PASS/FAIL invariants through the real Host instead of the retired stub, so no
coverage was lost by retiring the stub-era duplicate (see PR7b in the plan's §10).

## Completed earlier (M2)

- M2 — Attempt/Result/Verification/Receipt one-task protocol E2E, PR #43. See prior handoff
  commits for full detail if needed — not reproduced here to keep this file current rather
  than cumulative.

## Completed earlier (M1)

- M1 — Kernel authoritative publication and replay spine, PR #41. See prior handoff commits
  for full detail if needed.

## Next session — fixed scope

**Plan M4** per [`mvp-implementation-roadmap.md`](docs/plans/active/mvp-implementation-roadmap.md)
line 237 ("M4 — Deterministic Context Compiler"), then implement it. No M4 plan doc exists
yet — start there, following the same process M1/M2/M3 used: design doc, adversarial review
(consider a **second** review round after implementation too, not only before — this
session's second round caught 14 real defects a single pre-implementation review missed),
then dispatch implementation.

This session's design grilling (before any M4 code) settled the following scope decisions —
follow them rather than re-deriving:

- source-class taxonomy (control/lineage/observed/derived) implemented structurally now even
  though the lineage class stays empty until M7's real orchestration gives it predecessors —
  forward-compatible shape, no behavior yet
- candidate set stays limited to what's already real: Task objective/AC, admitted decision/
  contract refs, `WorkspaceSnapshot` identity, `RuntimeCapabilityProfile` identity — no new
  repository-file discovery/selection subsystem (YAGNI per AGENTS.md rule 9, mirrors M3's
  empty `M3_REQUIRED_CAPABILITIES` precedent); shuffle-order/determinism exit evidence is
  proven over this finite set (reuse `runtime_capability.py`'s `_utf16_sort_key` pattern), not
  over filesystem/API enumeration that doesn't exist in scope
- Context Pack follows M3's pattern: a computed value, identity embedded into (repurposed)
  `AttemptPacketV1.context_digest`, full structured pack kept as evidence alongside — no new
  Kernel-published record type
- token/cost estimator is a deterministic placeholder (byte-length based), versioned
  (`estimator_name@revision`) like everything else here — a real tokenizer is a runtime/model
  decision outside M4's boundary; only the identity binding needs to be real now
- `host.execute()`'s OpenCode `run`-message rendering gets wired to the real Context Pack (not
  left as an unused struct) — labeled sections per source class so the authority/data boundary
  survives rendering, per issue #6's "renderer must preserve a hard boundary" finding
- `CONTEXT_BUDGET_EXCEEDED` is a new exception type mirroring `CapabilityAdmissionError`
  (`kernel/runtime_capability.py`), raised during compile before packet construction — blocks
  packet creation entirely, no runnable partial packet
- runtime disclosure-profile identity/reserved-cost is a separate lightweight identity computed
  in the M4 module, not a new `RuntimeCapabilityProfile` field (avoids M3 schema churn), but
  re-verified at `execute()` time the same way M3 re-verifies profile identity on drift
- evaluated and declined migrating `opencode-orchestrated-agent-workflow`'s runtime/
  adapter/transport code directly: different language (Node.js vs this repo's Python kernel),
  different protocol shape (its own Task Packet/bootstrap envelope vs this repo's
  `AttemptPacketV1`/`RecordRef`), and its own research note already flags a core state-model
  conflict (mutable `run.json` vs this repo's event-authority Kernel-publish model). Interface-
  level reference only, same as the existing `docs/research/` adoption process — no code/
  runtime dependency on that sibling repo.

M4 replaces M2's opaque `AttemptPacketV1.context_digest` fixture field with a real,
structured Context Pack, compiled deterministically over exactly the admitted task/lineage/
source identities:

- structured Context Unit with trust/authority class, source identity/digest, scope,
  inclusion reason, required/optional class, and content/range
- deterministic ordering and deduplication
- frozen candidate identities for one compilation
- versioned selection policy and token/cost estimator identity
- provenance-closure freshness checks for derived context — M3's now-real Workspace
  Snapshot identity (`execution/workspace_snapshot.py`) is one of the freshness-check inputs
  this milestone gets to build on, not invent
- required/optional budget accounting across actual platform-controlled disclosure
- typed `CONTEXT_BUDGET_EXCEEDED`
- deterministic optional omission/truncation record
- runtime disclosure profile identity/reserved-cost binding

Start in-process. Do not create a Context service.

**Non-goals for M4:** all runtimes beyond OpenCode (M9), release automation, hardened
criterion/evidence policy (M6), orchestration expansion (M7). Reuse M3's real
`RuntimeCapabilityProfile`/`workspace_snapshot` primitives rather than inventing parallel
freshness/identity machinery.

**Exit evidence to design toward:** shuffled filesystem/API/input order produces the same
selected order and digest; malicious repository/issue/external/runtime text cannot add
capabilities, mandatory sources, approval, PASS, or policy; stale derived context fails
after any bound authoritative dependency changes; undersized required-context budget
produces no runnable Attempt; disclosure drift after compilation rejects or recompiles
rather than silently expanding context.

Primary issue: #6, with security overlap in #8.

**New milestone inserted after M4, before verification hardening**: this session added
[`M5 — Cross-project failure-mode ledger`](docs/plans/active/mvp-implementation-roadmap.md)
(tracking [Issue #46](https://github.com/hjung3113/agent-platform/issues/46)), so the old
M5-M9 became M6-M10 — a genuine renumber, not a new milestone silently taking an old number.
It mines sibling repos' own git history/issues/PRs (git-log/issue/PR failure-mode pass first,
then PR body/diff on flagged items only) for concrete failure/regression/bug records — not
design-pattern adoption, which `docs/research/adoption-ledger.md` already covers — producing
a new `docs/research/failure-mode-ledger.md` that feeds M6's adversarial review before M6
design starts. Full mining scope: `opencode-orchestrated-agent-workflow`,
`agent-migration-pipeline`, `general-low-reasoning-agent-harness`, `thin-agent-harness`.
`meta-prompting-skill` gets an applicability-only scan (conceptual repo, not a failure-mining
target), not failure mining. Do M4 first, M5 gates M6.

**Renumbering caveat**: only `mvp-implementation-roadmap.md` and this file were renumbered.
The already-merged `docs/plans/active/m0`–`m3` plan docs still say "M5"/"M6"/etc. in their own
historical rationale prose (dozens of occurrences, mostly embedded in analysis sentences, not
headers) — deliberately left untouched as historical record rather than risking a wide,
error-prone edit across merged docs. When reading those older plan docs, their M5–M9 mentions
refer to the **old** numbering, one lower than the current roadmap for M6 onward.

`AttemptPacketV1.context_digest` (currently `execution/attempt.py`'s M2-era
`_fixture_digest("context", task_id)`, deliberately left untouched through M3) is M4's
replacement target — decide how much of the fixture's shape (a single opaque digest field on
the packet) survives versus needs a real structured Context Pack reference.

## Explicit scope limits carried forward from M3 (not gaps to silently close in M4)

These were investigated during M3's second review round and deliberately downgraded to
documented, accepted scope limits rather than fixed — revisit only if a concrete milestone
need makes them load-bearing, per AGENTS.md rule 9 (YAGNI):

- **Per-task capability-requirement differentiation.** M3's admission policy
  (`execution/policy.py`) is one fixed global table; it cannot express "this specific task
  requires network/filesystem/process isolation as a guarantee." Real per-task/per-role
  requirement binding needs either a contract change or M7's real orchestration layer, where
  task variability first becomes real — M4's Context Compiler is not obviously the right
  place either, but check when M4 design starts.
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
  external_effects` stays empty for every M3 path; real release/external-effect authorization
  is M10 scope per the roadmap, unchanged.

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

### Later milestones (unchanged from M0/M1/M2 handoff)

- #5 verification/evidence soundness after authoritative lineage/snapshot bindings exist
  (M6 — hardened criterion/evidence policy, execution-provenance independence,
  self-verification closed by real distinct identity rather than M2's string inequality).
  M3's real Result/Runtime Observation binding makes this possible but does not implement it.
- #4 deterministic orchestration after replay/authoritative state is stable (M7 — retry/
  repair/replan, fan-in, safe parallelism, multi-task DAG, Reviewer/Verifier split per
  ADR-0009; also where M3's per-task capability-requirement gap above likely gets closed).
- #24 skill supply-chain (M10) after core Kernel/runtime boundaries are executable.
- #9/#25 compatibility registry, historical cross-version rule provenance, retained-lineage
  replay, and reader/rule retirement reachability remain M8/real-cross-version-edge work.
- additional runtime adapters (M9) built against M3's `RuntimeCapabilityProfile`/
  containment/redaction primitives — cross-runtime canonical-action conformance matrix.
