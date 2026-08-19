# M1 — Kernel Authoritative Publication and Replay Spine Implementation Plan

Status: **Active**
Tracker: [Issue #34](https://github.com/hjung3113/agent-platform/issues/34)
Milestone: **M1 only**

This document is the execution plan for M1 of the MVP roadmap. It builds the append-only
authoritative lineage store and Kernel publication boundary on top of the M0 protocol
primitives, without pre-building M2's Attempt/Result/Verification/Receipt path.

Normative semantics remain owned by the specs/ADRs. If implementation reveals a
contradiction with those authorities, update the governing design first rather than
encoding a local interpretation here.

## 1. Sources and current baseline

Primary design sources:

- [`mvp-implementation-roadmap.md`](./mvp-implementation-roadmap.md) — M1 section
- [`m0-minimum-protocol-foundation.md`](./m0-minimum-protocol-foundation.md)
- [ADR-0007](../../adr/0007-authoritative-event-lineage.md) (superseded, historical context)
- [ADR-0008](../../adr/0008-run-state-authority.md)
- [`03-contracts-protocol-state.md`](../../specs/03-contracts-protocol-state.md)

Issue evidence:

- [#1 Authority / Trust Boundary](https://github.com/hjung3113/agent-platform/issues/1)
- [#2 Protocol / State Correctness](https://github.com/hjung3113/agent-platform/issues/2)
- [#3 End-to-End Handoff Integrity](https://github.com/hjung3113/agent-platform/issues/3)

Already implemented on `main` and to be reused, unchanged:

- `product/src/kernel/canonical.py` — canonical JSON + content digest.
- `product/src/kernel/protocol.py` — `ContractKind`, `RecordRef`, `ProtocolRejectionCode`,
  exact `(contract_kind, protocol_version, schema_version)` reader dispatch.
- `product/src/kernel/protocol_v1.py` — `RequestV1`, `TaskV1`, `WorkflowRevisionV1` strict
  readers.
- `product/src/kernel/admission.py` — Attempt/runtime policy admission; unrelated to this
  slice, not to be generalized or merged with the new publish boundary.

M1 does not modify M0 protocol modules. It adds a store + publish boundary that consumes
their typed values.

## 2. M1 scope decision

M1 proves only this chain:

```text
validated candidate value (from M0 reader)
  + expected predecessor RecordRef
  + idempotency key
  -> Kernel admission (fencing check)
  -> atomic authoritative commit (durable, outside checkout)
  -> derived run-head projection update
  -> deterministic replay/reducer from the committed lineage
```

It does **not** prove:

```text
Request -> Workflow -> Attempt -> Result -> Verification -> Receipt
```

That is M2. M1 publishes only `request` and `workflow_revision` records.

**Non-goals:** distributed consensus, database-backed event store, leases across multiple
machines, production HA, cross-platform crash-consistency validation (M7), a generic
storage-backend abstraction (introduced only if a second real backend appears), a separate
idempotency index (record volume in M1 is small enough that a directory scan suffices).

## 3. Lineage scoping

One **run** = one Request. A run is the unit of fencing, replay, and projection.

```text
{state_dir}/runs/{run_id}/
  0000000001.json   # first committed record (request)
  0000000002.json   # next committed record (workflow_revision)
  _head.json         # derived projection, rebuildable
  _lock              # advisory fcntl lock for sequence assignment
```

`run_id` is Kernel-assigned when the genesis `request` record is admitted for a run that
does not yet exist. `state_dir` comes from the required `AGENT_PLATFORM_STATE_DIR`
environment variable; there is no default, and startup fails closed if it is unset or not
writable.

A global cross-run stream is explicitly rejected: unrelated runs must never block or fence
against each other's sequence assignment.

## 4. Proposed implementation layout

```text
product/src/kernel/lineage_store.py
product/src/kernel/publish.py
product/src/kernel/replay.py

product/tests/kernel/test_lineage_store.py
product/tests/kernel/test_publish.py
product/tests/kernel/test_replay.py
product/tests/kernel/test_fault_injection.py
```

### `lineage_store.py`

Filesystem primitive only. No knowledge of contract kinds or protocol semantics.

- `open_run(state_dir, run_id) -> RunHandle`
- `RunHandle.append(seq, record_bytes) -> None` — temp-file-in-run-dir + `os.rename`
  atomic create; rejects if `seq` file already exists (stale/conflicting writer).
- `RunHandle.read_head() -> HeadProjection | None`
- `RunHandle.write_head(HeadProjection) -> None`
- `RunHandle.rebuild_head_from_scan() -> HeadProjection` — used when `_head.json` is
  missing/corrupt; scans `NNNNNNNNNN.json` files, deterministic by sequence order.
- `RunHandle.lock()` context manager — `fcntl.flock` exclusive lock on `_lock`, scoped to
  the sequence-assignment + commit + projection-update critical section.

### `publish.py`

The Kernel publication boundary. Only production writer of authoritative records.

```python
def publish(
    state_dir: str,
    run_id: str | None,           # None only for a genesis `request`
    candidate: ReaderOutcome,      # from protocol.py dispatch, already M0-validated
    expected_predecessor: RecordRef | None,
    idempotency_key: str,
    commit_barrier: Callable[[], None] | None = None,  # test-only fault-injection seam
) -> PublishResult
```

`PublishResult` is `Published(record_ref, run_id) | Rejected(PublishRejectionCode)`.

Rejection codes required, distinct from M0's `ProtocolRejectionCode`:

- `RUN_NOT_FOUND` (non-genesis publish against unknown run)
- `PREDECESSOR_MISMATCH` (stale or conflicting fencing reference)
- `IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_CONTENT`
- `LOCK_CONTENTION_TIMEOUT`

`publish()` sequence:

1. Acquire run lock.
2. Compute current head (read `_head.json`, or rebuild-from-scan if missing/corrupt).
3. Scan existing records in the run for `idempotency_key`: if found with matching content
   digest, return the existing `Published` result (idempotent replay of the same logical
   operation); if found with a different digest, reject.
4. Compare `expected_predecessor` against actual head; mismatch rejects.
5. Assign next sequence number, write record file atomically (this is the commit point).
6. Invoke `commit_barrier()` if provided (test seam only — production callers never pass
   one).
7. Update `_head.json` from the just-committed record.
8. Release lock.

Step 6 sits deliberately between the durable commit (step 5) and the projection update
(step 7) so a fault injected there proves the projection-loss invariant without a real
process kill.

### `replay.py`

Pure reducer over a run's committed records, independent of `_head.json`.

```python
@dataclass(frozen=True)
class RunState:
    request: RequestV1 | None
    workflow_revision: WorkflowRevisionV1 | None
    last_sequence: int
    last_record_id: RecordRef | None

def replay(state_dir: str, run_id: str) -> RunState
```

Reads records in sequence order directly from disk (not from `_head.json`), re-parses each
through the M0 `protocol.py` dispatch table, and folds into `RunState`. Used both by tests
asserting replay determinism and by `rebuild_head_from_scan`.

## 5. Test plan

### Store primitive

- append is atomic: partial temp file never observable under the final sequence name
- appending an already-used sequence number rejects (no silent overwrite)
- `_head.json` missing/corrupt: `rebuild_head_from_scan` reproduces the same projection a
  clean run would have produced
- lock prevents two concurrent `append` calls (same process, two threads/handles) from
  assigning the same sequence number

### Publish boundary

- genesis `request` publish with no `expected_predecessor` succeeds and creates `run_id`
- `workflow_revision` publish with correct `expected_predecessor` succeeds
- stale `expected_predecessor` (older head) rejects with `PREDECESSOR_MISMATCH`
- conflicting `expected_predecessor` (right sequence, wrong digest) rejects
- same `idempotency_key` + same content digest returns the original `Published` result,
  does not create a second record
- same `idempotency_key` + different content digest rejects with
  `IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_CONTENT`
- publish against unknown `run_id` rejects with `RUN_NOT_FOUND`
- a schema-valid M0 candidate that has not gone through `publish()` has no authoritative
  effect (regression carried from M0)

### Replay / fault injection

- replay of an accepted two-record run yields the same `RunState` on repeated calls
- `commit_barrier` raising after record commit but before `_head.json` write: subsequent
  `rebuild_head_from_scan` / `replay` still produce the correct state — proves crash
  between commit and projection cannot lose or corrupt authority
- corrupting/deleting `_head.json` after a successful multi-record publish sequence does
  not change what `replay` returns
- no test or fixture path writes directly into a run directory outside `publish()` /
  `lineage_store` primitives — production code must not have a second writer

### Regression

```bash
PYTHONPATH=product/src python -m unittest discover -s product/tests/contracts -p 'test_*.py' -v
PYTHONPATH=product/src python -m unittest discover -s product/tests/kernel -p 'test_*.py' -v
python -m compileall -q product/src product/tests
```

Existing M0 protocol, canonical, runtime-capability, and admission tests must remain green
and unmodified.

## 6. Implementation order

Four PRs, each independently reviewable:

1. **Store primitive + fencing** — `lineage_store.py`, atomic append, lock, head
   read/write/rebuild-from-scan. Negative tests: duplicate sequence, concurrent-append,
   corrupt-head rebuild.
2. **Kernel publish/admission boundary** — `publish.py`, `PublishRejectionCode`,
   idempotency scan, predecessor fencing. Negative tests: stale/conflicting predecessor,
   idempotency reuse/conflict, unknown run.
3. **Replay/reducer + fault injection** — `replay.py`, `commit_barrier` seam, the
   crash-between-commit-and-projection test suite.
4. **Request/WorkflowRevision integration** — wire M0's `protocol.py` dispatch output
   through `publish()` end to end; golden fixtures for a full genesis-then-child publish
   sequence.

## 7. M1 exit gate

M1 may be checked in Issue #34 only when all are true:

- Same idempotency key + same content returns the existing authoritative publication.
- Same idempotency key + conflicting content fails closed.
- Stale predecessor / conflicting successor fails closed.
- Simulated fault after authoritative commit but before projection update: replay/rebuild
  produces the same projection a clean run would have produced.
- Projection loss/corruption cannot change authority (replay from raw records matches).
- No non-`publish()` production path can write into a run directory.
- Existing M0 and earlier contract/kernel regression suites remain green.
- No database, distributed lock service, generic storage-backend abstraction, or
  multi-task/DAG machinery was introduced.

After merge, attach the PR(s) and test evidence to Issue #34 before checking M1.

## 8. Explicit deferrals / next handoff

### M2 only after M1

- Attempt Packet, stub Host, Result
- minimal Evidence/Verification representation
- independent Verifier execution identity
- terminal Receipt
- one-task protocol E2E

### M7 / real cross-version edge or platform validation

- cross-platform (Windows/Linux) crash-consistency validation of the store
- compatibility registry, migration rule provenance
- retained old-lineage replay conformance

### Later, only if a concrete need appears

- separate idempotency index (if per-run record volume grows beyond what a directory scan
  can serve deterministically)
- storage-backend abstraction (if a second real backend, e.g. for a hosted deployment,
  is actually required)
- cross-machine locking/leases (M6+ orchestration expansion, if concurrent multi-process
  publication across machines becomes a real scenario)

This boundary is deliberate: M1 should make M2 possible, not partially implement M2 or
simulate a real distributed store.
