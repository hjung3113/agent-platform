# M0 — Minimum Protocol Foundation Implementation Plan

Status: **Active**  
Tracker: [Issue #34](https://github.com/hjung3113/agent-platform/issues/34)  
Milestone: **M0 only**

This document is the execution plan for M0 of the MVP roadmap. It narrows the first implementation slice to the smallest protocol foundation that can support M1 authoritative publication without pre-building M1/M2 behavior.

Normative semantics remain owned by the specs/ADRs. If implementation reveals a contradiction with those authorities, update the governing design first rather than encoding a local interpretation here.

## 1. Sources and current baseline

Primary design sources:

- [`mvp-implementation-roadmap.md`](./mvp-implementation-roadmap.md)
- [`end-to-end-wiring.md`](../../architecture/end-to-end-wiring.md)
- [`03-contracts-protocol-state.md`](../../specs/03-contracts-protocol-state.md)
- [`versioning-and-migrations.md`](../../architecture/versioning-and-migrations.md)
- [`contracts/catalog.md`](../../../contracts/catalog.md)
- [`AGENTS.md`](../../../AGENTS.md)

Issue evidence:

- [#1 Authority / Trust Boundary](https://github.com/hjung3113/agent-platform/issues/1)
- [#3 End-to-End Handoff Integrity](https://github.com/hjung3113/agent-platform/issues/3)
- [#9 Contract Evolution / Compatibility](https://github.com/hjung3113/agent-platform/issues/9)
- [#10 Complexity / Minimum Viable Kernel](https://github.com/hjung3113/agent-platform/issues/10)
- [#25 Protocol golden/replay conformance](https://github.com/hjung3113/agent-platform/issues/25)

Already implemented on `main` and to be reused:

- `src/kernel/canonical.py`: deterministic canonical JSON and format-bound SHA-256 content digest.
- `tests/contracts/test_canonical.py`: canonical golden and fail-closed vectors.
- `src/kernel/runtime_capability.py`: runtime capability primitives; not an M0 protocol-reader dependency.
- `src/kernel/admission.py`: Attempt/runtime policy admission seam; do not generalize or refactor it into the M0 protocol validator.

Repository research was inspected under `docs/research/`. The recorded direct-reuse candidates primarily cover coding/review/orchestration skills rather than this protocol record boundary, so M0 should reuse the existing in-repository canonical primitive and normative contracts rather than add a new upstream framework or dependency.

## 2. Adversarial review findings

### BLOCKER — the existing handoff scope jumps across milestone gates

The current `HANDOFF.md` asks the next session to implement atomic publication, idempotency/CAS, replay, and a one-task E2E skeleton together. Those are M1 and M2 responsibilities, while Issue #34 now makes M0 -> M1 -> M2 ordering normative.

**Failure mode:** M0 protocol shapes get designed around a storage/replay/E2E implementation before their own version/binding invariants are closed, or the session declares progress using mocked E2E evidence while exact protocol dispatch is still incomplete.

**Correction:** the next implementation session is M0 only. M1 publication/replay and M2 Attempt/Result/Verification/Receipt remain blocked until the M0 exit gate passes.

### HIGH — a `PublishedEnvelope` type can accidentally become an authority token

Spec 03 distinguishes candidate, admitted, published, and derived authority states. A Python object named `PublishedEnvelope`, a canonical path, a valid digest, or serialized `published=true` metadata must not itself confer authority.

**Failure mode:** downstream code accepts a structurally valid published-looking object and skips the future Kernel publication boundary.

**Correction:** M0 may define the wire/storage shape needed to parse a published record, but parsing/constructing that value is not an authority decision. There is no M0 production `publish()` API, no writable authoritative store, and no boolean/field that upgrades a candidate to authority. Kernel authority is introduced only in M1.

Candidate readers must reject publication-only fields rather than silently ignore them.

### HIGH — version dispatch can be under-keyed

Dispatching only on schema version, or only on protocol version, leaves room for the wrong contract reader to interpret bytes successfully.

**Failure mode:** a `workflow_revision` payload is interpreted by a `request` v1 reader because both happen to use schema version `1`, or an unsupported version falls through to a current/latest reader.

**Correction:** exact dispatch key is:

```text
(contract_kind, protocol_version, schema_version)
```

There is no latest-reader fallback, semantic-version inference, runtime/adapter-based reader selection, or compatibility coercion.

### HIGH — generic parent lists weaken handoff semantics

A generic `parents: [...]` list makes it easy to lose the meaning of a relationship and accept the right digest in the wrong role.

**Failure mode:** a Workflow Revision binds a valid record digest that is not the exact Request it claims to derive from, or parent ordering/role becomes implicit convention.

**Correction:** use a small reusable record-reference value object, but place it in relation-specific schema fields such as `request`. The reference binds at least:

```text
contract_kind
record_id
content_digest
```

The child reader validates the expected parent kind. M1 will additionally resolve that exact reference against authoritative lineage.

Do not introduce a generic graph/edge framework in M0.

### HIGH — candidate digest and publication metadata can become circular or unstable

If Kernel-assigned publication identity, write timestamp, storage path, or other publication metadata participates in candidate content identity, the candidate cannot be stably checked before publication.

**Failure mode:** the content digest changes merely because the Kernel publishes the same candidate, invalidating pre-publication semantic checks or idempotency inputs.

**Correction:** the protocol content digest is computed over the versioned contract content:

```text
contract_kind + protocol_version + schema_version + payload/bindings
```

Kernel-assigned publication identity and storage/projection metadata are excluded from that content digest. A published record stores/binds the resulting content digest rather than redefining it.

The existing canonical algorithm and digest domain are unchanged in M0.

### HIGH — permissive parsing can hide forged authority metadata or schema drift

Dataclass construction or ad-hoc dictionary reads that ignore unknown keys make malformed/future records look valid.

**Failure mode:** a candidate supplies `record_id`, `published`, `authoritative`, or an unknown future field; the v1 reader ignores it and accepts a meaning the sender did not actually sign/digest under the intended schema.

**Correction:** v1 readers use exact allowed-key validation at every correctness-relevant object boundary. Unknown fields fail closed. Required fields are explicit; correctness-relevant defaults are not silently injected during parsing.

If normalization is needed, it happens before content identity is fixed. No admission-time transformation may silently mutate already-digested content.

### MEDIUM — protocol rejection semantics can be conflated with Attempt admission

`src/kernel/admission.py` already exposes `AdmissionStatus` and string reasons for runtime/permission policy. Reusing those names/types for protocol parsing would collapse two different boundaries.

**Failure mode:** callers treat “protocol parsed successfully” as “Attempt admitted” or vice versa.

**Correction:** M0 introduces protocol-specific typed rejection codes/results. Do not rename or refactor the existing Attempt admission API in this slice.

### MEDIUM — M0 can accidentally pre-build the compatibility registry from #9/#25

Issue #9 requires exact readers now but directional compatibility rules only when real cross-version relationships exist. Issue #25 spans M0, M1, and M7 evidence.

**Failure mode:** a speculative v1/v2 compatibility abstraction is frozen before v2 exists, or M0 expands into replay/reader-retirement machinery.

**Correction:** M0 implements exact v1 dispatch and rejection of every unsupported combination. Compatibility registry, migration-rule provenance, old-lineage replay, and reader-retirement reachability are deferred to M7 or to the first real cross-version edge.

### MEDIUM — test fixtures can become an unofficial authoritative state path

Hand-built “published” JSON fixtures are useful for binding tests but can later be imported by production code as if they were admitted facts.

**Correction:** M0 fixtures are protocol/golden inputs only. Production code must not load fixture paths as authority. M1 introduces the real authoritative lineage boundary. Historical authoritative fixture helpers, if later needed for replay tests, must remain test-only and clearly separated from production publication APIs.

## 3. M0 scope decision

M0 proves only this chain:

```text
raw candidate bytes/value
  -> exact contract/version dispatch
  -> strict v1 shape validation
  -> typed Request or one-task Workflow Revision value
  -> canonical content identity / exact Request binding checks
```

It does **not** prove:

```text
candidate -> Kernel publication -> authoritative lineage -> replay
```

That is M1.

It also does not prove:

```text
Request -> Workflow -> Attempt -> Result -> Verification -> Receipt
```

That is M2.

## 4. Proposed implementation layout

Prefer two small modules. Collapse them only if the implementation becomes materially simpler without weakening exact-reader retention.

```text
src/kernel/protocol.py
src/kernel/protocol_v1.py

tests/contracts/test_protocol.py
tests/contracts/test_protocol_v1.py

tests/fixtures/protocol/v1/
  request.json
  workflow-revision.json
  golden-digests.json
```

### `src/kernel/protocol.py`

Own only version-independent protocol primitives:

- `ContractKind`
- candidate/published wire envelope value shapes
- `RecordRef` / exact identity+digest binding primitive
- `ProtocolRejectionCode`
- validation/read result type
- exact reader dispatch keyed by `(contract_kind, protocol_version, schema_version)`
- content-digest shape validation if needed

No store, publisher, CAS, replay reducer, compatibility registry, plugin system, service boundary, or dynamic reader discovery.

### `src/kernel/protocol_v1.py`

Own only retained v1 contract semantics needed by M0:

- `RequestV1`
- `TaskV1`
- `WorkflowRevisionV1`
- strict v1 readers/validators
- canonical-value conversion used by the shared `content_digest()` primitive

Keeping v1 semantics in a version-specific module directly supports Issue #9's exact-reader requirement without building a general migration framework.

## 5. Minimum wire shapes

Exact field names may be adjusted during implementation only if required by a governing spec. Any such change must remain within this semantic minimum.

### Candidate envelope

```json
{
  "contract_kind": "request",
  "protocol_version": 1,
  "schema_version": 1,
  "payload": {}
}
```

Candidate envelope invariants:

- no Kernel-assigned `record_id`
- no authoritative/published flag
- no storage path/timestamp/projection metadata
- exact known key set
- supported exact reader must exist before payload interpretation

### Published record shape

M0 may define the data shape needed for future reading/binding:

```json
{
  "record_id": "...",
  "content_digest": "sha256:agent-platform-json-v1:...",
  "contract_kind": "request",
  "protocol_version": 1,
  "schema_version": 1,
  "payload": {}
}
```

Important: this shape is **not** a publication mechanism and is not an authority token. A structurally valid instance created by arbitrary code remains untrusted until M1's Kernel publication/store boundary establishes it in authoritative lineage.

A published-record reader must recompute the content digest from the versioned contract content and reject a declared digest mismatch.

### Exact record reference

```json
{
  "contract_kind": "request",
  "record_id": "...",
  "content_digest": "sha256:agent-platform-json-v1:..."
}
```

The Workflow Revision schema uses this in a named `request` field rather than a generic untyped parent list.

## 6. Minimal Request v1

Required semantic fields:

```text
objective
scope
acceptance_criteria
```

Recommended minimum validation:

- `objective`: non-empty string
- `scope`: ordered array/tuple of non-empty strings
- `acceptance_criteria`: non-empty ordered array/tuple of non-empty strings
- no unknown fields

Do not add Decision Proposal, Plan Check, approval workflow, runtime profile, context, release authorization, or orchestration state.

A direct human request may become a Request candidate without inventing a standalone Human Approval Record unless current policy identifies a material decision requiring one.

## 7. Minimal one-task Workflow Revision v1

Required semantic fields:

```text
request: exact RecordRef to Request
task: one TaskV1
```

`TaskV1` should contain only fields needed to preserve the one-task objective and acceptance boundary, for example:

```text
task_id
objective
acceptance_criteria
```

Required validation:

- `request.contract_kind == request`
- request reference fields are non-empty and digest-shaped
- exactly one task exists by construction; do not introduce DAG arrays or dependency graphs
- task ID/objective/criteria are explicit and non-empty
- no unknown fields

Do not add retry, repair, replan, resources, fan-in, concurrency, context budget, runtime selection, evidence policy, or release state.

## 8. Exact reader dispatch

Required behavior:

```text
(request, 1, 1)           -> Request v1 reader
(workflow_revision, 1, 1) -> Workflow Revision v1 reader
anything else             -> typed rejection
```

Required rejection classes/codes should distinguish at least:

- unknown contract kind
- unsupported protocol version
- unsupported schema version / unsupported exact reader combination
- malformed envelope
- malformed payload
- malformed record reference
- content digest mismatch
- parent/source binding mismatch

Exact naming can follow repository style, but callers must not have to parse free-form exception text to determine the rejection class.

No fallback order exists. In particular:

- no “latest supported reader”
- no “same major version” inference
- no runtime/adapter selected reader
- no coercion from unsupported known versions
- no compatibility lookup in M0

## 9. Binding validation boundary

M0 binding validation is pure and local:

```text
expected published Request identity/digest fixture/value
                +
WorkflowRevision.request RecordRef
                ->
exact match or typed rejection
```

M0 does not resolve authoritative state from disk/database. M1 will resolve references against the actual Kernel lineage/store and reject stale/conflicting predecessors there.

The M0 validator must reject:

- missing parent reference
- wrong parent contract kind
- wrong parent record ID
- wrong parent content digest
- malformed digest
- substituted newer/different parent even when semantically similar

## 10. Canonical content identity

Reuse `kernel.canonical.content_digest()` unchanged.

For M0 contract identity, digest the exact canonical versioned content that a candidate proposes:

```text
contract_kind
protocol_version
schema_version
payload, including exact relation-specific bindings
```

Do not digest:

- Kernel-assigned publication `record_id`
- filesystem/storage location
- projection/head metadata
- write time
- transient parser objects

Tests must prove:

- object insertion order does not change identity
- array order remains meaningful where the schema defines ordered data
- changing objective/scope/criterion/binding/version changes identity
- declared published digest must equal recomputed candidate-content digest

If digest text validation requires a helper, prefer a tiny helper based on the existing canonical constants/format rather than duplicating the canonical algorithm or introducing a schema framework.

## 11. Test plan

### Exact-version and envelope tests

- known `request` v1/v1 dispatch succeeds
- known `workflow_revision` v1/v1 dispatch succeeds
- unknown contract kind rejects
- unknown future protocol version rejects
- unsupported schema version rejects
- reader fallback is impossible
- missing/extra envelope keys reject
- candidate carrying `record_id`, `content_digest`, `published`, or `authoritative` keys rejects

### Request tests

- minimal valid Request parses deterministically
- empty objective rejects
- empty/malformed scope rejects
- missing acceptance criteria rejects
- unknown payload fields reject
- golden Request canonical bytes/digest remain fixed

### Workflow Revision tests

- minimal valid one-task revision parses deterministically
- missing Request binding rejects
- parent kind other than Request rejects
- malformed digest rejects
- wrong Request ID rejects when checked against expected parent
- stale/substituted Request digest rejects
- zero/multiple-task representation is impossible or rejected
- unknown task/workflow fields reject
- golden Workflow Revision canonical bytes/digest remain fixed

### Published-shape/authority regression tests

- published record with incorrect declared content digest rejects
- parsing a candidate does not produce a record ID or authority flag
- parsing a published-shaped value does not mutate state or provide a Kernel publication API
- canonical-looking path/filename is never part of protocol admission semantics

The last two are primarily API-boundary assertions; do not invent a fake state store merely to test them.

### Regression checks

Run at minimum:

```bash
PYTHONPATH=src python -m unittest discover -s tests/contracts -p 'test_*.py' -v
PYTHONPATH=src python -m unittest discover -s tests/kernel -p 'test_*.py' -v
python -m compileall -q src tests
```

Existing canonical, Runtime Capability Profile, and Attempt admission tests must remain green.

## 12. Implementation order

Use one reviewable PR for M0 unless implementation exposes a normative contradiction.

Recommended commit sequence:

1. **Protocol primitives + exact dispatch**
   - strict envelope
   - protocol-specific typed rejection
   - exact dispatch table
   - unknown-version/fallback negative tests
2. **Request + one-task Workflow Revision v1**
   - v1 value types/readers
   - relation-specific Request binding
   - strict-key/payload negative tests
3. **Golden/binding adversarial coverage**
   - fixed fixtures/digests
   - stale/substituted binding tests
   - forged publication metadata tests
   - regression suite

If step 1 reveals that the governing spec does not uniquely determine a correctness-relevant field or digest boundary, stop production implementation of that semantic point and update the governing spec/ADR first.

## 13. M0 exit gate

M0 may be checked in Issue #34 only when all are true:

- Request v1 and one-task Workflow Revision v1 have deterministic strict readers.
- Dispatch is exact on contract/protocol/schema and has no latest-reader fallback.
- Unknown/unsupported versions fail closed with typed rejection.
- Exact Request identity+digest substitution attacks fail closed.
- Candidate publication-looking metadata cannot confer authority and is not silently ignored.
- Canonical contract golden vectors are fixed and existing canonical behavior is unchanged.
- No database/store/CAS/replay/DAG/Attempt/E2E/compatibility-registry machinery was introduced.
- Existing contract/kernel regression tests pass.

After merge, attach the PR and test evidence to Issue #34 before checking M0.

## 14. Explicit deferrals / next handoff

### M1 only after M0

- filesystem-backed append-only authoritative lineage outside checkout
- atomic Kernel admission + publication
- Kernel-assigned durable record identity
- idempotency identity
- stale writer/predecessor/head fencing
- derived projection after authoritative commit
- deterministic replay and fault injection

### M2 only after M1

- Attempt Packet
- stub Host
- Result
- Verification
- terminal Receipt
- one-task protocol E2E

### M7 / first real cross-version edge

- compatibility registry
- compatibility/migration rule provenance
- retained old-lineage replay conformance
- reader/rule retirement reachability

This boundary is deliberate: M0 should make M1 possible, not partially implement M1 or simulate M2.