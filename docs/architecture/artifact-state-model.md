# Artifact and Run-State Model

## Immutable lineage
Authoritative lineage is expressed through immutable artifacts and explicit parent bindings.

Core artifacts:
- Request
- Decision
- Workflow Revision
- Plan Check
- Context Pack
- Attempt Packet
- Workspace Snapshot
- Runtime Observation
- Result
- Review
- Evidence
- Verification
- Finding
- Release Authorization
- Release Receipt
- Receipt

Each authoritative artifact carries a schema/protocol version, durable identity, canonical content digest, and the exact parent/source identities and digests required by its contract.
A child artifact is valid only against those exact parents; substituting a newer or equivalent-looking artifact creates a different lineage.

## Snapshot identity
A Workspace Snapshot is the authoritative identity of the effective workspace content used for execution, review, verification, and release.
Repository HEAD may be one input to snapshot identity but is not sufficient when staged, unstaged, untracked, generated, submodule, nested-repository, or other release-relevant content can differ.

Result, Review, Verification, Evidence, Release Authorization, and Release Receipt must name the exact subject snapshot they concern.
Verification evidence for another subject snapshot is stale by definition.

## Gate binding
- Plan Check binds the canonical digest of the candidate plan/workflow it checked.
- Kernel may admit a Workflow Revision only when its canonical content digest equals the passing Plan Check subject digest.
- Any transformation that changes canonical content produces a new candidate requiring the applicable gate again.
- Context Pack and Attempt Packet bind their authoritative source lineage and cannot silently replace sources.
- Release Authorization binds the verified snapshot plus the expected target state; Release Receipt records the actual released identity.

## Publication authority and commit point
There is one logical authoritative publication boundary: the Kernel.
Agents, adapters, hosts, and tools may produce candidates or observations, and storage components may persist on behalf of that boundary, but they do not independently create authoritative run-state records.

The immutable transition lineage admitted and published by the Kernel is the sole authoritative operational run state.
Publication of an immutable transition is the protocol commit point. Projection updates occur after that commit and are recoverable derived work.

## Replay and conflict semantics
Authoritative transitions must carry enough deterministic ordering and causal/predecessor information to replay the same accepted lineage into the same derived state.
A stale or conflicting candidate cannot replace or reinterpret already-published lineage; it must be rejected or represented by a new explicit successor transition.
Duplicate publication of the same logical operation is idempotent and must not create a second authoritative fact.

## Derived projections
- active decisions
- current run status
- eligible tasks
- open findings
- phase summaries
- dashboards

A projection may be cached but must cite exact immutable source identities/digests and cannot introduce facts absent from authoritative lineage.
Missing, stale, or conflicting projections are rebuilt from authoritative lineage rather than treated as a competing source of truth.

## Receipt semantics
A Receipt is explicitly typed as checkpoint or terminal.
A checkpoint Receipt records a durable progress/result boundary but does not terminate the run.
Only a terminal Receipt establishes the terminal run result.

This authority decision is fixed by ADR-0007. Concrete durable-write, atomic-replace, fencing/CAS, and filesystem crash-consistency mechanisms remain implementation concerns that require validation on supported platforms.
