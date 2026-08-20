# Handoff

## Completed in this slice (M2 planning)

- M2 — One-task protocol E2E (Attempt/Result/Verification/Receipt) implementation plan
  written and merged: [`docs/plans/active/m2-one-task-protocol-e2e.md`](docs/plans/active/m2-one-task-protocol-e2e.md),
  PR #42.
- Grilled the design with the user (design tree, 4 rounds) after a codex (`gpt-5.6-luna
  max`, via `orca terminal`) research pass over the M2-relevant specs/ADRs/roadmap and the
  current M1 kernel implementation. Key decisions locked into the plan doc:
  - 4 new `ContractKind`s (`attempt_packet`, `result`, `verification`, `receipt`), each
    independently published/fenced through M1's existing `publish()`/`lineage_store.py`
    mechanism — Runtime Observation is embedded in `result`'s payload, not a 5th kind.
  - `publish.py`'s hardcoded 2-step state check generalizes to a linear
    `head-kind -> next-kind` transition table (request→workflow_revision→attempt_packet→
    result→verification→receipt), each kind one-per-run, no branching/retry.
  - Verification `verdict` is a **total function** of `coverage`
    (PASS iff all SATISFIED > BLOCKED iff any BLOCKED > else FAIL), reader-enforced.
  - Each `SATISFIED` coverage entry carries an `evidence_digest` bound to the Result's
    `output_snapshot_digest`, checked at the (lineage-aware) publish boundary — closes a
    "PASS from assertion alone" gap a reviewer found.
  - `coverage`-vs-`acceptance_criteria` and Result/Attempt/Verification cross-record
    bindings are publish-level checks; payload-local self-consistency (e.g.
    `result.observation` digest match) is reader-level — this reader/publish split was a
    real defect in the first draft (two independent reviewers caught it) and is now
    explicit in the plan.
  - `ReceiptV1` carries `receipt_type: "terminal"` (spec 03's checkpoint/terminal
    discriminator) instead of inferring terminality from record presence.
  - stub Host lives in `product/src/execution/` (already scaffolded), stub Verifier in
    `product/src/verification/` (already scaffolded) — no new top-level module.
  - **Deliberately deferred, not a gap**: self-verification is closed by plain
    `verifier_identity != implementer_identity` string inequality, not real
    execution-provenance-independent identity — that's issue #34's M5 bullet
    ("execution-provenance independence"), documented in the plan as an explicit
    non-goal so it doesn't read as an oversight later.
  - Plan doc §8 breaks implementation into 5 independently-reviewable PRs (protocol
    readers → publish state machine → replay extension → stub Host/Verifier →
    end-to-end integration); §9 has the full exit gate.
- Adversarial review (user's own pass + automated codex review) on the first plan draft
  found 3 P1s (unconstructible stub APIs, reader doing a lineage-aware check it can't
  perform, undefined verdict totality) + evidence-binding and receipt-typing gaps; all
  fixed in the plan before merge (see PR #42 commit history for the full before/after).

## Completed earlier (M1)

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
- Merged as PR #41. An adversarial review pass on the PR raised 7 findings; 6 judged real
  defects and fixed before merge, 1 judged out of M1 scope:
  1. `publish()` no longer trusts `_head.json` blindly — the authoritative head is
     re-derived from a scan of committed records on every call, inside the lock, and a
     missing/corrupt/stale projection is repaired before any admission decision.
  2. `publish()` now enforces the state machine: genesis accepts only a Request candidate,
     non-genesis accepts only a WorkflowRevision, and a WorkflowRevision's embedded
     `request` binding is verified against the run's actual genesis Request via
     `protocol.verify_binding`, not merely structural validity. New
     `PublishRejectionCode.INVALID_CANDIDATE_KIND_FOR_RUN_STATE` /
     `.GENESIS_REQUEST_BINDING_MISMATCH`.
  3. Genesis idempotency now recovers across a lost-response crash window: before minting
     a new run_id, `publish()` peeks at each existing run's sequence-1 record for the
     idempotency_key, so a retry with `run_id=None` after a commit-but-unreturned genesis
     publish finds the original run.
  4. `replay()` recomputes each committed record's content digest and cross-checks
     `record_id`/`run_id`/`sequence` against the deterministic scheme, and enforces
     sequence contiguity — fails closed on any mismatch instead of trusting envelope
     metadata. `publish()`'s committed-record scan no longer silently skips
     unreadable/malformed records; it raises.
  5. Caller-supplied `run_id` is validated against the exact 32-hex-char `uuid4().hex`
     format `publish()` itself generates, before any filesystem access — closes a
     path-traversal opening.
  7. `lineage_store.RunHandle.lock()` gained a poll-acquire `timeout`; `publish()` now
     actually returns `LOCK_CONTENTION_TIMEOUT` instead of declaring an unreachable code.
  - **Not fixed, deliberately**: directory-fsync-after-rename durability (real power-loss
    crash consistency). M1's fault injection proves commit-before-projection *ordering*
    via the `commit_barrier` seam, not real OS/power-crash durability — that's explicit
    M7 scope per the plan doc; revisit there if a concrete need appears sooner.

## Validation (M1, post-hardening)

- `PYTHONPATH=product/src python3.12 -m unittest discover -s product/tests/kernel -p 'test_*.py' -v` — 56 passed.
- `PYTHONPATH=product/src python3.12 -m unittest discover -s product/tests/contracts -p 'test_*.py' -v` — 78 passed.
- `python3.12 -m compileall -q product/src product/tests` — passed.
- Note: system `python3` on this machine is 3.9 and lacks `StrEnum` (used by
  `protocol.py`/`admission.py`/`publish.py`); use `python3.12`+ for this repo.

## Next session — fixed scope

**Implement M2** per the merged plan doc:
[`docs/plans/active/m2-one-task-protocol-e2e.md`](docs/plans/active/m2-one-task-protocol-e2e.md)
(PR #42). The design is closed — do not re-derive schemas/state-machine/rejection codes
from the specs again; read the plan doc first, it already answers those questions and
records why. Only reopen it if implementation surfaces a real contradiction with the
governing specs/ADRs (update the plan doc, or escalate to the specs, before coding around
it).

Follow the plan's §8 order, 5 independently-reviewable PRs:

1. Protocol extension — `protocol.py` new `ContractKind`s, `protocol_v1.py`
   `AttemptPacketV1`/`ResultV1`/`VerificationV1`/`ReceiptV1` readers. Golden + negative
   reader tests only.
2. Kernel publish state-machine generalization — `publish.py` transition table, new
   `PublishRejectionCode`s (`RUN_ALREADY_TERMINAL`, `ATTEMPT_TASK_BINDING_MISMATCH`,
   `RESULT_ATTEMPT_BINDING_MISMATCH`, `VERIFICATION_RESULT_BINDING_MISMATCH`,
   `VERIFICATION_COVERAGE_MISMATCH`, `SELF_VERIFICATION_REJECTED`,
   `RECEIPT_VERIFICATION_NOT_PASSED`), per-kind binding checks, verdict-gated Receipt
   admission.
3. Replay extension — `replay.py` six-field `RunState`, `terminal` property keyed off
   `receipt_type == "terminal"`.
4. Stub Host + stub Verifier — `product/src/execution/attempt.py` +
   `product/src/execution/stub_host.py`, `product/src/verification/stub_verifier.py`.
   Builder signatures take the published `RecordRef` from `publish()`, not payload objects
   (see plan §6 — this was a real defect caught in review, don't reintroduce it).
5. End-to-end integration — wire stub Host/Verifier through `publish()`;
   `test_m2_integration.py` golden PASS and FAIL fixtures.

M1 is a closed prerequisite: do not reopen `lineage_store.py`'s or `replay.py`'s M1-proven
invariants (atomic append, predecessor fencing, idempotency, commit-before-projection
ordering). `publish.py`'s state-machine check is the one M1 piece M2 *does* extend, per
plan §4 — that's expected, not a regression risk, as long as the M1 exit-gate behaviors
(genesis/Request-only, WorkflowRevision binding, idempotency, fault-injection ordering)
stay intact under the new transition table.

Exit gate for checking M2 in Issue #34: plan doc §9 (full chain golden fixture,
stale-binding/self-verification/missing-evidence/duplicate-terminal all fail closed,
FAIL/BLOCKED Verification publishes but produces no Receipt, all M0/M1 suites green, no
M3+ scope creep).

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
