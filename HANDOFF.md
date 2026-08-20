# Handoff

## Completed in this slice (M2 implementation)

- M2 — Attempt/Result/Verification/Receipt one-task protocol E2E implemented and merged
  per [`docs/plans/active/m2-one-task-protocol-e2e.md`](docs/plans/active/m2-one-task-protocol-e2e.md),
  PR #43. 5 commits (protocol readers → publish state machine → replay extension → stub
  Host/Verifier → e2e integration), each independently reviewable, plus one post-review
  fix commit.
- Implementation dispatched via `orca` worktrees to `opencode`/`zai-coding-plan/glm-5.3`
  (effort `high` for protocol readers, publish state machine, and e2e integration; effort
  `low` for replay extension and stub Host/Verifier), tracked as an `orca orchestration`
  task DAG (`run_30bc5e66c6a0`). PR4 (stub Host/Verifier) ran in a separate parallel
  worktree since it only depends on PR1, then was cherry-picked into the integration
  branch once PR1 landed.
- Real design defect caught and fixed mid-implementation, not just at PR review: PR2's
  first pass special-cased a second Workflow Revision publishing at a Workflow Revision
  head, to avoid touching 3 pre-existing M1 tests that happened to use a second Workflow
  Revision as chain filler. That directly violated plan §2's "one record of each kind per
  run, no branching." Rejected on review; fixed by updating the affected M1 tests
  (`test_publish.py`, `test_replay.py`, `test_fault_injection.py`, `test_m1_integration.py`)
  to fill the same chain slots with an Attempt Packet — the actual valid next kind — instead
  of weakening the state machine. `publish.py`'s `_NEXT_KIND` table has no self-loop on any
  kind.
- Two more real defects caught by GitHub PR review (Codex + human adversarial pass) after
  merge-readiness, fixed in a follow-up commit before merging:
  1. `read_verification_v1` accepted a `PASS` verdict with non-empty `findings`, letting a
     self-contradictory authoritative Verification (and a terminal Receipt built on it)
     exist. Plan §3 defines findings as "non-empty only when verdict != PASS"; the reader
     recomputed verdict from coverage but never checked this side of the invariant. Now
     rejects `MALFORMED_PAYLOAD`.
  2. `Result.output_snapshot_digest` (and the embedded Observation's copy) was validated as
     merely a non-empty string, not content-digest-shaped, while Verification's `SATISFIED`
     `evidence_digest` is required to be both content-digest-shaped *and* equal to it. A
     Result with a non-digest-shaped identity could publish successfully but could never
     receive a `PASS` Verification — an authoritative dead-end reachable at the protocol
     layer alone. Both fields now require `is_content_digest()`.
  - A third PR-review finding (an M1 run with multiple Workflow Revisions crashing instead
    of migrating cleanly on `publish.py`'s stricter lookup) was **not** actioned: M2 has no
    persisted production state to migrate. Compatibility registry / historical
    cross-version rule provenance is explicit M7 scope per the plan doc's own deferred
    section (§10). Revisit only if a concrete cross-version migration need appears before
    M7.
- Design decisions from the M2 plan doc held without needing rework during implementation:
  4 new `ContractKind`s each independently published/fenced through M1's `publish()`
  mechanism; `verdict` as a reader-enforced total function of `coverage`; the
  reader/publish split for payload-local vs. lineage-aware checks; evidence binding via
  `evidence_digest == Result.output_snapshot_digest`; `ReceiptV1.receipt_type == "terminal"`
  literal; every stub builder taking the published `RecordRef`, never the candidate payload
  object (plan §6's explicitly-called-out defect, correctly avoided by the implementer on
  the first pass).

## Validation (M2, post-merge)

```
PYTHONPATH=product/src python3.12 -m unittest discover -s product/tests/contracts -p 'test_*.py' -v   # 133 passed
PYTHONPATH=product/src python3.12 -m unittest discover -s product/tests/kernel -p 'test_*.py' -v       # 78 passed
PYTHONPATH=product/src python3.12 -m unittest discover -s product/tests/execution -p 'test_*.py' -v    # 11 passed
PYTHONPATH=product/src python3.12 -m unittest discover -s product/tests/verification -p 'test_*.py' -v # 5 passed
python3.12 -m compileall -q product/src product/tests                                                  # passed
```

227 tests total, all green. M0/M1 suites unmodified in semantics (only the 4 test files
noted above changed, to swap a filler Workflow Revision for a filler Attempt Packet).

M2 exit gate (plan doc §9) self-checked bullet-by-bullet against the combined PR1-PR5 test
suites during PR5's implementation; see PR #43 description for the per-bullet test mapping.

## Completed earlier (M1)

- M1 — Kernel authoritative publication and replay spine, 4 PRs per
  [`docs/plans/active/m1-kernel-authoritative-publication.md`](docs/plans/active/m1-kernel-authoritative-publication.md).
  Merged as PR #41; adversarial review pass fixed 6 findings before merge (fail-closed head
  re-derivation, state-machine enforcement, genesis idempotency recovery across crash,
  fault-closed replay integrity checks, run_id format validation, lock timeout). See prior
  handoff commits for full detail if needed — not reproduced here to keep this file current
  rather than cumulative.

## Next session — fixed scope

**Plan M3** per [`mvp-implementation-roadmap.md`](docs/plans/active/mvp-implementation-roadmap.md)
line 204 ("M3 — Real Host/security boundary and first runtime adapter"), then implement it.
No M3 plan doc exists yet — start there, following the same process M1/M2 used (design
review with the user, adversarial pass on the plan draft before locking it, then dispatch
implementation).

M3 replaces the fake execution boundary M2 proved wiring for with one real enforceable
runtime path, without generalizing portability yet:

- effective Workspace Snapshot identity (tracked/staged/unstaged/untracked/generated/nested
  state as outcome-relevant)
- resolved workspace containment and escape rejection (traversal/symlink/equivalent)
- Runtime Capability Profile bound to Attempt admission and execution, not just admission
- effective permission-envelope comparison after native/default/inherited config resolution
  — inherited/default permissions must not widen the admitted envelope
- deny-first filesystem/network/process/credential/external-effect enforcement where the
  runtime can enforce it; no silent runtime/transport/tool fallback
- real Runtime Observation and exact output snapshot provenance (replacing M2's
  `stub_execute`, which derives `output_snapshot_digest` as a pure function of the Attempt
  Packet's digest — no real execution)
- pre-retention redaction/sensitivity gate sufficient for retained runtime output/evidence
- deterministic adapter conformance fixtures independent of model/network availability;
  live runtime smoke tests supplemental only

**Default first runtime: OpenCode.** Additional runtimes stay deferred to M8.

**Non-goals for M3:** all runtimes, general plugin system, release automation,
sophisticated secret-classification taxonomy, real evidence policy (M5), Context Compiler
(M4), DAG/retry/repair/replan (M6).

**Exit evidence to design toward:** traversal/symlink/equivalent escape cases fail closed;
unsupported/partial/unknown required capability cannot execute without an explicitly
admitted degraded mode; runtime/config/tool-mapping drift changes profile identity and
invalidates stale admission; inherited/default permissions cannot widen the admitted
envelope; runtime exit/stdout cannot directly establish completion; retained canary secret
fixtures do not persist raw secret material.

Primary issues: #7, #8.

M2's stub Host/Verifier (`product/src/execution/stub_host.py`,
`product/src/verification/stub_verifier.py`) are M3's replacement targets, not code to
extend in place — M3 should design the real Host boundary against
`product/agents/roles/implementer.md`'s actual requirements, then decide how much of the
stub's shape (function signatures, RecordRef-in/typed-payload-out pattern) survives versus
gets replaced outright.

## Deferred until the corresponding gate

### M7 / real cross-version edge or platform validation

- cross-platform (Windows/Linux) crash-consistency validation of the M1 store
- compatibility registry, historical cross-version rule provenance, retained-lineage replay
  (includes the M2-PR-review finding about multi-Workflow-Revision legacy runs — no action
  needed until this gate is concrete)
- reader/rule retirement reachability

### Only if a concrete need appears later

- separate idempotency index (current directory-scan dedupe is bounded by M1's small
  per-run record count)
- storage-backend abstraction beyond the concrete filesystem implementation
- cross-machine locking/leases for multi-process publication across machines

### Later milestones (unchanged from M0/M1 handoff)

- #5 verification/evidence soundness after authoritative lineage/snapshot bindings exist
  (M5 — hardened criterion/evidence policy, execution-provenance independence,
  self-verification closed by real distinct identity rather than M2's string inequality).
- #4 deterministic orchestration after replay/authoritative state is stable (M6 — retry/
  repair/replan, fan-in, safe parallelism, multi-task DAG, Reviewer/Verifier split per
  ADR-0009).
- #6 context compilation (M4) and #24 skill supply-chain (M9) after core Kernel/runtime
  boundaries are executable.
- #9/#25 compatibility registry, historical cross-version rule provenance, retained-lineage
  replay, and reader/rule retirement reachability remain M7/real-cross-version-edge work.
