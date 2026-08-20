# M2 — One-Task Protocol E2E Implementation Plan

Status: **Active**
Tracker: [Issue #34](https://github.com/hjung3113/agent-platform/issues/34)
Milestone: **M2 only**

This document is the execution plan for M2 of the MVP roadmap. It extends the M1 Kernel
publication/replay spine with the Attempt Packet / Result / Verification / terminal Receipt
chain for exactly one task, proving protocol wiring only — not real Host/runtime security,
real context compilation, real evidence judgement, or orchestration (DAG/retry/repair/
replan/parallelism), all of which remain later milestones.

Normative semantics remain owned by the specs/ADRs. If implementation reveals a
contradiction with those authorities, update the governing design first rather than
encoding a local interpretation here.

## 1. Sources and current baseline

Primary design sources:

- [`mvp-implementation-roadmap.md`](./mvp-implementation-roadmap.md) — M2 section
- [`m1-kernel-authoritative-publication.md`](./m1-kernel-authoritative-publication.md) — style/precedent
- [`end-to-end-wiring.md`](../../architecture/end-to-end-wiring.md)
- [`03-contracts-protocol-state.md`](../../specs/03-contracts-protocol-state.md)
- [`04-workflow-orchestration.md`](../../specs/04-workflow-orchestration.md)
- [`05-runtime-execution.md`](../../specs/05-runtime-execution.md)
- [`06-review-verification-evidence.md`](../../specs/06-review-verification-evidence.md)
- [ADR-0007](../../adr/0007-authoritative-event-lineage.md) (superseded, historical context)
- [ADR-0008](../../adr/0008-run-state-authority.md)
- [ADR-0009](../../adr/0009-reviewer-verifier-split-trigger.md)

Issue evidence: #1 #3 #5 #10

Already implemented on `main` and to be reused, unchanged in semantics:

- `product/src/kernel/canonical.py` — canonical JSON + content digest.
- `product/src/kernel/protocol.py` — `ContractKind`, `RecordRef`, `ProtocolRejectionCode`,
  exact reader dispatch, `verify_binding`.
- `product/src/kernel/protocol_v1.py` — `RequestV1`, `TaskV1`, `WorkflowRevisionV1` strict
  readers.
- `product/src/kernel/lineage_store.py` — append-only run-scoped filesystem primitive.
- `product/src/kernel/publish.py` — sole production writer; M1 hardening (fail-closed head
  re-derivation, state-machine enforcement, genesis idempotency recovery, run_id format
  validation, lock timeout) stays intact.
- `product/src/kernel/replay.py` — pure reducer over raw committed records.
- `product/src/kernel/admission.py` — pure Attempt policy admission (`admit_attempt`),
  unrelated to the Kernel publish boundary; M2's stub Host may call it but M2 does not
  generalize or merge it with `publish.py`.

Already scaffolded, to be filled in this slice:

- `product/src/execution/README.md` — attempt packet creation, capability admission,
  runtime dispatch, host-observed runtime facts live here.
- `product/src/verification/README.md` — evidence normalization, independent
  review/verify publication, acceptance coverage live here.
- `product/agents/roles/implementer.md`, `product/agents/roles/verifier.md` — existing role
  prompts describing the real (non-stub) Implementer/Verifier; M2's stub Host and stub
  Verifier are deterministic placeholders for these roles, not replacements.

M2 does not modify M0 protocol module semantics and does not reopen
`lineage_store.py`/`replay.py`'s M1-proven invariants (atomic append, predecessor fencing,
idempotency, commit-before-projection ordering). It extends `publish.py`'s state machine
and `protocol_v1.py`'s reader set.

## 2. M2 scope decision

M2 proves this chain, one record of each kind per run, no branching:

```text
Request -> Workflow Revision -> Attempt Packet -> Result -> Verification -> [Receipt]
```

Receipt is admitted only when Verification's verdict is `PASS`. A `FAIL`/`BLOCKED`
Verification still publishes as an authoritative record (real information — a Kernel
rejection would hide it) but produces no Receipt; the run ends unterminated. Retry, repair,
replan, and any second Attempt are explicitly out of scope — closing that gap is M6.

**Non-goals:** real Host process/network/filesystem/credential isolation (M3), real
Workspace Snapshot / runtime adapter / redaction (M3), Context Compiler and budgeting (M4),
durable Finding lifecycle and hardened evidence policy (M5), DAG/dependency graphs/resource
claims beyond the existing single `TaskV1`, safe parallelism, fan-in (M6), compatibility
registry and cross-version replay (M7), multi-runtime portability (M8), release
authorization and skill supply chain (M9). The Reviewer/Verifier split (ADR-0009) is not
implemented in M2: the one task is treated as explicitly low-risk, so only the Verifier
runs; the risk-tier computation itself stays a fixed low-risk stub, not a real Plan Check
scorer.

## 3. New contract kinds and payload shapes

Four new `ContractKind` values in `protocol.py`: `attempt_packet`, `result`,
`verification`, `receipt`. Each is an independently published, independently fenced record
in the run lineage — same mechanism M1 proved for `request`/`workflow_revision`. Runtime
Observation is **not** a fifth kind; it is embedded in `result`'s payload.

All four readers live in `protocol_v1.py` (protocol/schema version 1, same file as
`RequestV1`/`WorkflowRevisionV1` — one dispatch-key registration point, split out only if a
later milestone makes the file unwieldy).

### `AttemptPacketV1`

```text
workflow_revision: RecordRef      # binds to this run's published Workflow Revision
task_id: str                      # must equal workflow_revision's task.task_id
implementer_identity: str         # opaque identity of who is attempting; self-verification anchor
context_digest: str                # opaque fixture identity; no real Context Compiler yet
workspace_snapshot_digest: str      # opaque fixture identity; no real Host snapshot yet
runtime_capability_profile_identity: str  # opaque fixture identity
```

### `ResultV1`

```text
attempt: RecordRef                # binds to this run's published Attempt Packet
output_snapshot_digest: str       # opaque fixture identity of the produced output
observation:                      # embedded Runtime Observation, not a separate record
  runtime_identity: str
  output_snapshot_digest: str      # must equal the sibling field above (Result/Observation binding)
```

### `VerificationV1`

```text
result: RecordRef                 # binds to this run's published Result
verifier_identity: str            # must differ from the Attempt's implementer_identity
coverage:                          # one entry per Workflow Revision task.acceptance_criteria item, same order
  - criterion: str
    status: "SATISFIED" | "UNSATISFIED" | "BLOCKED" | "UNPROVEN"
verdict: "PASS" | "FAIL" | "BLOCKED"   # PASS iff every coverage entry is SATISFIED
findings: tuple[str, ...]          # free-text reasons; non-empty only when verdict != PASS
```

`coverage` length/criterion-text mismatch against the bound Workflow Revision's
`task.acceptance_criteria` is a reader-level `MALFORMED_PAYLOAD` rejection — this is where
"missing evidence fails closed" is enforced, not a publish-level check.

### `ReceiptV1`

```text
verification: RecordRef           # binds to this run's published Verification; must be PASS
```

## 4. `publish.py` state machine generalization

Replace the current hardcoded `is_genesis -> REQUEST, else -> WORKFLOW_REVISION` check with
a linear transition table keyed by the current head's `contract_kind`:

```python
_NEXT_KIND = {
    None: ContractKind.REQUEST,                       # genesis
    ContractKind.REQUEST: ContractKind.WORKFLOW_REVISION,
    ContractKind.WORKFLOW_REVISION: ContractKind.ATTEMPT_PACKET,
    ContractKind.ATTEMPT_PACKET: ContractKind.RESULT,
    ContractKind.RESULT: ContractKind.VERIFICATION,
    ContractKind.VERIFICATION: ContractKind.RECEIPT,
}
```

A run's head kind is `ContractKind.RECEIPT` only when that Receipt was actually published
(never for a `FAIL`/`BLOCKED` Verification — no Receipt exists yet, so the head stays at
`VERIFICATION` and the run is simply unterminated, not blocked from a correct next step
that never comes). Once a Receipt is published, the run is terminal: any further
non-idempotent-retry publish rejects `RUN_ALREADY_TERMINAL` before any other check.

Each new kind gets the same defense-in-depth explicit binding check M1's hardening pass
added for `workflow_revision.request` — predecessor-equals-head fencing already pins
position, but each payload's own reference (`attempt_packet.workflow_revision`,
`result.attempt`, `verification.result`, `receipt.verification`) is independently verified
via `verify_binding` against the actual prior record.

New `PublishRejectionCode` entries:

- `RUN_ALREADY_TERMINAL` — any publish attempted against a run whose head is a Receipt.
- `ATTEMPT_TASK_BINDING_MISMATCH` — `attempt_packet.task_id` != the run's Workflow
  Revision `task.task_id`, or `attempt_packet.workflow_revision` fails `verify_binding`.
- `RESULT_ATTEMPT_BINDING_MISMATCH` — `result.attempt` fails `verify_binding`, or
  `result.observation.output_snapshot_digest` != `result.output_snapshot_digest`.
- `VERIFICATION_RESULT_BINDING_MISMATCH` — `verification.result` fails `verify_binding`.
- `SELF_VERIFICATION_REJECTED` — `verification.verifier_identity` ==
  the run's Attempt Packet `implementer_identity`.
- `RECEIPT_VERIFICATION_NOT_PASSED` — a Receipt candidate is published while the run's
  Verification `verdict` != `PASS`, or `receipt.verification` fails `verify_binding`.

Existing codes (`RUN_NOT_FOUND`, `PREDECESSOR_MISMATCH`,
`INVALID_CANDIDATE_KIND_FOR_RUN_STATE`, `GENESIS_REQUEST_BINDING_MISMATCH`,
`IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_CONTENT`, `LOCK_CONTENTION_TIMEOUT`) are unchanged
and still reachable at their existing steps (genesis stays Request-only;
`GENESIS_REQUEST_BINDING_MISMATCH` stays specific to the Workflow Revision step).

Idempotency: unchanged mechanism from M1 (scan for `idempotency_key`, matching digest
returns the existing `Published`, differing digest rejects) applies uniformly to all six
kinds, including a duplicate terminal Receipt retry.

## 5. `replay.py` extension

Extend `RunState` to carry all six optional fields plus `last_sequence`/`last_record_id`,
same reduction pattern as M1 (fold committed records in sequence order, independent of
`_head.json`). Add a `terminal: bool` derived property (`receipt is not None`). No change
to the fault-injection proof shape — `commit_barrier` behavior is orthogonal to which kind
is being committed.

## 6. Stub Host and stub Verifier

### `product/src/execution/attempt.py`

`build_attempt_packet(workflow_revision, implementer_identity) -> AttemptPacketV1` —
constructs the fixture-level identity fields deterministically (e.g. digests of fixed
constants scoped by `workflow_revision`'s task_id); no real context compilation or
workspace inspection.

### `product/src/execution/stub_host.py`

`stub_execute(attempt) -> ResultV1` — deterministically derives an output snapshot digest
from the Attempt (no process/subprocess/network execution); this is the explicit fake Host
identity the M2 gate requires. May call `kernel.admission.admit_attempt` for its pure
policy check as a demonstration of the seam, but M2 does not require real enforcement at
this boundary — that is M3.

### `product/src/verification/stub_verifier.py`

`stub_verify(result, workflow_revision, verifier_identity, expected_output_digest) ->
VerificationV1` — builds the `coverage` array by comparing `result.output_snapshot_digest`
against `expected_output_digest` (a test-fixture constant) via plain string equality for
every `task.acceptance_criteria` entry; no semantic judgement. `verdict` is the pure
function of `coverage` (`PASS` iff all `SATISFIED`).

## 7. Test plan

### Protocol readers (`product/tests/contracts/`)

- golden `AttemptPacketV1`/`ResultV1`/`VerificationV1`/`ReceiptV1` round-trip + canonical
  digest determinism, mirroring existing `test_protocol_v1.py`/`test_protocol_golden.py`
  patterns.
- negative: malformed payload keys, `coverage` length/criterion mismatch against a fixture
  Workflow Revision, `verdict` inconsistent with `coverage` (reader must reject, not trust
  caller-declared verdict against computed coverage).

### Publish boundary (`product/tests/kernel/`)

- each of the six kinds publishes in order with correct binding/fencing; out-of-order kind
  at any step rejects `INVALID_CANDIDATE_KIND_FOR_RUN_STATE`.
- stale/conflicting predecessor at each of the four new steps rejects `PREDECESSOR_MISMATCH`
  (carrying forward the M1 pattern, not a new mechanism).
- `attempt_packet.task_id` mismatch rejects `ATTEMPT_TASK_BINDING_MISMATCH`.
- `result.attempt` binding mismatch and `result`/`observation` digest mismatch reject
  `RESULT_ATTEMPT_BINDING_MISMATCH`.
- `verification.result` binding mismatch rejects `VERIFICATION_RESULT_BINDING_MISMATCH`.
- `verification.verifier_identity == attempt.implementer_identity` rejects
  `SELF_VERIFICATION_REJECTED`.
- Receipt publish while Verification `verdict` != `PASS` rejects
  `RECEIPT_VERIFICATION_NOT_PASSED`.
- FAIL/BLOCKED Verification publishes successfully (authoritative record exists) and the
  run stays non-terminal; no Receipt is created implicitly.
- duplicate terminal Receipt: same idempotency key + same content returns the existing
  `Published`; differing content rejects
  `IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_CONTENT`; any other publish against a terminal run
  rejects `RUN_ALREADY_TERMINAL`.

### Replay (`product/tests/kernel/`)

- replay of a full six-record run reproduces identical `RunState` on repeated calls.
- replay of a five-record (FAIL-terminated, no Receipt) run correctly reports
  `terminal=False`.
- existing M1 fault-injection suite (`commit_barrier` between commit and head write)
  re-run against an Attempt/Result/Verification/Receipt commit point, not just
  Request/WorkflowRevision — proves the ordering invariant generalizes.

### Stub Host / stub Verifier (`product/tests/execution/`, `product/tests/verification/`)

- `stub_execute` is deterministic: same Attempt Packet content produces the same
  `ResultV1` content digest across calls.
- `stub_verify` produces `PASS` when digests match, `FAIL` with populated `findings` and
  `UNSATISFIED` coverage entries when they don't.

### End-to-end golden (`product/tests/kernel/test_m2_integration.py`)

- full Request -> Workflow Revision -> Attempt Packet -> Result -> Verification -> Receipt
  chain through the real `publish()` boundary, PASS path, one task.
- same fixture run through the FAIL path: chain stops at Verification, no Receipt, replay
  confirms non-terminal state.

### Regression

```bash
PYTHONPATH=product/src python3.12 -m unittest discover -s product/tests/contracts -p 'test_*.py' -v
PYTHONPATH=product/src python3.12 -m unittest discover -s product/tests/kernel -p 'test_*.py' -v
PYTHONPATH=product/src python3.12 -m unittest discover -s product/tests/execution -p 'test_*.py' -v
PYTHONPATH=product/src python3.12 -m unittest discover -s product/tests/verification -p 'test_*.py' -v
python3.12 -m compileall -q product/src product/tests
```

All M0/M1 suites must remain green and unmodified in semantics (new test files/cases are
additive).

## 8. Implementation order

Five PRs, each independently reviewable:

1. **Protocol extension** — `protocol.py` new `ContractKind` values, `protocol_v1.py`
   `AttemptPacketV1`/`ResultV1`/`VerificationV1`/`ReceiptV1` readers + canonical digest
   helpers. Golden + negative reader tests only; no publish/replay changes yet.
2. **Kernel publish state-machine generalization** — `publish.py` transition table, new
   `PublishRejectionCode` entries, per-kind explicit binding checks, verdict-gated Receipt
   admission, `RUN_ALREADY_TERMINAL`. Negative tests per new rejection code.
3. **Replay extension** — `replay.py` six-field `RunState`, `terminal` property; extend the
   M1 fault-injection suite to a later commit point in the new chain.
4. **Stub Host + stub Verifier** — `product/src/execution/attempt.py` +
   `product/src/execution/stub_host.py`, `product/src/verification/stub_verifier.py`.
   Determinism tests only; no Kernel wiring yet.
5. **End-to-end integration** — wire stub Host/Verifier output through `publish()`;
   `test_m2_integration.py` golden PASS and FAIL fixtures.

## 9. M2 exit gate

M2 may be checked in Issue #34 only when all are true:

- Golden fixture: `Request -> Workflow Revision -> Attempt Packet -> Result -> Verification
  -> Receipt` passes end to end through the real `publish()` boundary for one task.
- Stale/conflicting predecessor at any of the six steps fails closed.
- Self-verification (`verifier_identity == implementer_identity`) fails closed.
- Missing/malformed evidence (`coverage` shape mismatch against acceptance criteria) fails
  closed at the reader boundary.
- Duplicate terminal Receipt publication is idempotent on matching content, rejects on
  conflicting content, and any further publish against a terminal run rejects
  `RUN_ALREADY_TERMINAL`.
- A `FAIL`/`BLOCKED` Verification publishes as an authoritative record but produces no
  Receipt, and a Receipt candidate against a non-PASS Verification rejects
  `RECEIPT_VERIFICATION_NOT_PASSED`.
- All M0/M1 regression suites remain green.
- No real Host isolation, real Workspace Snapshot, Context Compiler, DAG/retry/repair/
  replan/parallelism, durable Finding lifecycle, or Reviewer/Verifier split was introduced.

After merge, attach the PR(s) and test evidence to Issue #34 before checking M2.

## 10. Explicit deferrals / next handoff

### M3 only after M2

- real Host process/network/filesystem/credential isolation and adapter-reported effective
  profiles
- real effective Workspace Snapshot, runtime adapter behavior, pre-retention redaction
- first real runtime adapter target (OpenCode)

### M4

- deterministic Context Compiler: structured trust/authority/source/digest bindings,
  deterministic ordering/dedupe, versioned selection/budget policy, replacing M2's opaque
  `context_digest` fixture field

### M5

- durable Finding identity/lineage/resolution, replacing M2's plain `findings: tuple[str,
  ...]` field
- hardened criterion/evidence policy, execution-provenance independence, self-test
  mutation coverage

### M6

- retry/repair/replan, fan-in, safe parallelism, multi-task DAG eligibility (replacing
  M2's trivial single-task binding check), Reviewer/Verifier split enforcement per
  ADR-0009's real risk-tier computation

### Later, unchanged from M1 handoff

- M7 cross-platform crash-consistency, compatibility registry, retained-lineage replay
- M8 multi-runtime portability
- M9 release authorization, skill supply chain

This boundary is deliberate: M2 should make M3–M6 possible, not partially implement them or
simulate real Host security, real context assembly, or real evidence judgement.
