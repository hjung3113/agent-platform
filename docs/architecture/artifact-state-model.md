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
- Every successor Workflow Revision created by replan requires a new Plan Check over that successor digest.
- Any transformation that changes canonical content produces a new candidate requiring the applicable gate again.
- Context Pack and Attempt Packet bind their authoritative source lineage and cannot silently replace sources.
- Release Authorization binds the verified snapshot plus the expected target state; Release Receipt records the actual released identity.

## Publication authority
There is one logical authoritative publication boundary: Kernel.
Agents, adapters, hosts, orchestration helpers, and tools may produce candidates or observations, and storage components may persist on behalf of the authority boundary, but they do not independently create competing authoritative records.

## Authoritative run state
Per [ADR-0007](../adr/0007-run-state-authority.md), immutable transition lineage admitted and published by the Kernel is the sole authoritative operational run state.

Authoritative transition publication is the protocol commit point. Current-state/run-head documents are derived checkpoints or caches only and cannot introduce facts absent from lineage.

## Derived projections
- active decisions
- current run status
- eligible tasks
- open findings
- phase summaries
- dashboards

A projection may be cached but must cite exact immutable source identities/digests. Missing, stale, corrupt, or conflicting projections are rebuilt or rejected from authoritative lineage.

Replay of the same accepted lineage must produce the same derived state, eligible task set, and transition inputs.
