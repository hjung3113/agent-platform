# Spec 03 — Contracts, Protocol & Run State

## Goal
Provide one durable, replayable protocol for request/workflow/task/attempt/evidence/finding/receipt lineage.

## Required behavior
- strict versioned schemas at admission
- every authoritative record carries explicit protocol/schema versions and is interpreted by an exact version-specific reader; no "latest reader" fallback
- unknown or unsupported versions fail closed with a typed rejection
- schema-valid candidates remain non-authoritative until Kernel admission/publication
- canonical repository path or filename does not confer authority
- Kernel-assigned durable identities for authoritative records
- immutable artifacts after publication
- protocol-defined canonical content digests
- explicit parent/source identity and digest bindings for every authoritative handoff
- typed rejection for malformed/stale/conflicting/mismatched candidates
- one single-writer authoritative publication boundary: Kernel
- admission predicates are deterministic policy checks plus required human approval; an LLM verdict field is never sufficient by itself
- task and attempt are separate lifecycle concepts
- runtime observations are facts, not verdicts
- findings never mutate in place; closure is successor/event lineage
- summaries/projections are derived and rebuildable
- runtime state is outside the checkout
- mixed-version parent/child handoffs fail closed unless an explicit directional compatibility rule permits the exact relationship
- cross-version admission records the immutable compatibility/migration rule identity used, so replay does not depend on the current registry
- compatibility is contract-specific and is never inferred from adapter/runtime support or semantic-version similarity
- authoritative replay uses each artifact's recorded protocol/schema version; migrations create successors/projections rather than rewriting history
- a reader or compatibility/migration rule required by retained authoritative lineage cannot be retired while that lineage remains reachable
- a later artifact cannot silently substitute a different parent/source merely because it is newer or semantically similar

## Authoritative state model
The immutable transition lineage admitted and published by the Kernel is the sole authoritative operational run state.

Candidate, admitted, published, and derived states are distinct. A candidate may be structurally valid, live under a canonical path, or contain `PASS`, but remains non-authoritative until the exact identity/digest passes deterministic admission and any required Human Authority gate, then is published through the Kernel boundary.

A run-head/projection may be atomically replaced as a cache/checkpoint, but it is never authoritative and cannot introduce facts absent from the immutable lineage. Missing, stale, or conflicting projections are rebuilt from lineage.

Authoritative publication of an immutable transition is the protocol commit point. Projection updates follow that commit and are recoverable derived work.

## Replay and conflict invariants
- authoritative transitions contain deterministic ordering plus causal/predecessor information sufficient for replay
- replay of the same accepted lineage must derive the same state
- replay interpretation is selected by the versions recorded on each artifact, not by the currently installed runtime/adapter
- a publication candidate is validated against the exact predecessor lineage/state it claims to extend
- stale/conflicting publication attempts fail closed rather than overwrite or reinterpret newer state
- each retriable logical publication operation carries a stable idempotency identity independent of process/transport retries
- repeating the same logical publication cannot create duplicate authoritative facts; the same idempotency identity with conflicting content is rejected
- prepared/staged candidates remain non-authoritative until Kernel publication
- child artifacts are admissible only against the exact parent/source identities and digests declared by their contract
- cross-version edges are admissible only through the recorded compatibility/migration rule for that exact contract/version relationship
- producer role, schema validity, verdict text, storage location, adapter support, or runtime support cannot bypass admission

## Lifecycle distinctions
Failure, cancellation, retry, repair, replan, reconciliation, checkpoint, and terminal completion are semantically distinct protocol outcomes/transitions. Process disappearance alone does not imply any terminal state.

A Receipt is explicitly typed as `checkpoint` or `terminal`. A checkpoint Receipt records durable progress but never terminates the run; only a terminal Receipt establishes terminal run state.

See [ADR-0008](../adr/0008-run-state-authority.md) for the authority decision and [Protocol Versioning and Migration](../architecture/versioning-and-migrations.md) for compatibility/replay rules. Concrete persistence, fencing/CAS, canonicalization encoding, version-reader packaging, compatibility-registry storage, and filesystem crash-consistency mechanisms remain implementation concerns that require validation on supported platforms.
