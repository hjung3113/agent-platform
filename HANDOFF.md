# Handoff

## Completed in this slice

- M1 — Kernel authoritative publication and replay spine, 4 PRs per
  [`docs/plans/active/m1-kernel-authoritative-publication.md`](docs/plans/active/m1-kernel-authoritative-publication.md):
  1. `product/src/kernel/lineage_store.py` — run-scoped append-only filesystem primitive:
     atomic temp-file+rename commit, duplicate-sequence rejection, `fcntl`-locked run
     critical section, `_head.json` projection with scan-based rebuild.
  2. `product/src/kernel/publish.py` — single production writer boundary. Idempotency scan
     (same key+digest short-circuits to the prior `Published`; differing digest rejects)
     runs before predecessor fencing, so a retry survives the head advancing underneath it.
     Typed `PublishRejectionCode` distinct from M0's `ProtocolRejectionCode`.
  3. `product/src/kernel/replay.py` — pure reducer over raw committed records (never
     `_head.json`), re-dispatched through M0's real `read_candidate`. Fault-injection tests
     use `publish()`'s `commit_barrier` seam to prove the commit-before-projection-update
     ordering invariant: a crash between durable commit and head write leaves the record
     recoverable via `replay()` / `rebuild_head_from_scan()`.
  4. `product/tests/kernel/test_m1_integration.py` — end-to-end golden fixtures: genesis
     Request → child WorkflowRevision through the real dispatch → publish → replay chain,
     golden envelope shape, content-digest determinism, stale-predecessor rejection.
- M1 exit gate satisfied: idempotency replay/conflict, stale/conflicting predecessor
  fencing, commit-before-projection fault recovery, projection loss/corruption cannot
  change authority, `publish()` is the only writer, all M0 regression suites remain green.
- Implementation dispatched to `zai-coding-plan/glm-5.3` (low effort for PR1/PR4, high
  effort for PR2/PR3); each PR independently reviewed and test-verified before commit.

## Validation (M1)

- `PYTHONPATH=product/src python3.12 -m unittest discover -s product/tests/kernel -p 'test_*.py' -v` — 41 passed.
- `PYTHONPATH=product/src python3.12 -m unittest discover -s product/tests/contracts -p 'test_*.py' -v` — 78 passed.
- `python3.12 -m compileall -q product/src product/tests` — passed.
- Note: system `python3` on this machine is 3.9 and lacks `StrEnum` (used by
  `protocol.py`/`admission.py`/`publish.py`); use `python3.12`+ for this repo.

## Next session — fixed scope

Follow Issue #34's milestone order. Implement **M2 — Attempt/Result/Verification/Receipt**
next. M1 is a closed prerequisite: do not reopen `lineage_store.py` / `publish.py` /
`replay.py` semantics without a design-doc update first.

Required M2 scope (per HANDOFF's prior deferral list, to be detailed in a new
`docs/plans/active/m2-*.md` before implementation):

1. Attempt Packet representation and admission wiring onto the M1 publish boundary.
2. Explicit stub Host boundary (no real process/network/secret isolation yet — that is
   #7/#8, later).
3. Result / minimal Evidence / Verification representation.
4. Independent Verifier execution identity.
5. Terminal Receipt.
6. One-task protocol E2E through the full Request → WorkflowRevision → Attempt → Result →
   Verification → Receipt chain.

## Deferred until the corresponding gate

### M7 / real cross-version edge or platform validation

- cross-platform (Windows/Linux) crash-consistency validation of the M1 store
- compatibility registry, historical cross-version rule provenance, retained-lineage replay
- reader/rule retirement reachability

### Only if a concrete need appears later

- separate idempotency index (current directory-scan dedupe is bounded by M1's small
  per-run record count)
- storage-backend abstraction beyond the concrete filesystem implementation
- cross-machine locking/leases for multi-process publication across machines

### Later milestones (unchanged from M0 handoff)

- #7/#8 Host/runtime enforcement: actual process/network/secret isolation, adapter-reported
  effective profiles, drift-triggered re-admission, admission-to-use path race closure.
- #5 verification/evidence soundness after authoritative lineage/snapshot bindings exist.
- #4 deterministic orchestration after replay/authoritative state is stable.
- #6 context compilation and #24 skill supply-chain after core Kernel/runtime boundaries
  are executable.
- #9/#25 compatibility registry, historical cross-version rule provenance, retained-lineage
  replay, and reader/rule retirement reachability remain M7/real-cross-version-edge work.
