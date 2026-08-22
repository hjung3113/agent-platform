# Handoff

## Completed in this slice (M4 — deterministic Context Compiler, merged)

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

## Next session — fixed scope: M5, cross-project failure-mode ledger

Per [`mvp-implementation-roadmap.md`](docs/plans/active/mvp-implementation-roadmap.md)'s M5
section, tracking [Issue #46](https://github.com/hjung3113/agent-platform/issues/46). This
milestone is **research/documentation, not code** — no plan doc, no adversarial review round,
no implementation DAG. Goal: mine sibling repositories' own git history/issues/PRs for
concrete failure/regression/bug records (not design-pattern adoption, which
`docs/research/adoption-ledger.md` already covers) so M6's adversarial review starts from
real prior failures instead of rediscovering them from scratch.

**Method** (per roadmap, follow exactly, do not gold-plate):

1. Scan git log/issues/PRs per repo for failure/regression/bug records first — titles/commit
   messages/labels only, cheap pass.
2. For flagged items only, read the actual PR body/diff to extract root cause and the actual
   fix/improvement applied.
3. Record: source repo + commit/PR reference, failure mode, their fix, applicability to
   agent-platform (which module/future milestone), status.

**Scope:**

- Full failure-mode mining: `opencode-orchestrated-agent-workflow`,
  `agent-migration-pipeline`, `general-low-reasoning-agent-harness`, `thin-agent-harness`.
- Applicability-only scan (conceptual repo, not a failure-mining target):
  `meta-prompting-skill` — record current-project applicability only, not failure modes.

**Deliverable:** new `docs/research/failure-mode-ledger.md`, separate from
`adoption-ledger.md`.

**Exit evidence:**

- each of the 4 mining-scope repos shows scan evidence (git log/issue/PR pass completed)
- `meta-prompting-skill` applicability note recorded
- findings folded into M6's adversarial review checklist before M6 design starts

M5 gates M6 — do not start M6 (verification hardening, primary issue #5) design until this
ledger exists and its findings are folded into M6's adversarial review checklist.

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
  but do not implement it. M5 (next session) gates M6's design.
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
