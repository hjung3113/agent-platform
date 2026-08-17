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

## Publication authority
There is one logical authoritative publication boundary.
Agents, adapters, hosts, and tools may produce candidates or observations, and storage components may persist on behalf of the authority boundary, but they do not independently create competing authoritative records.

## Derived projections
- active decisions
- current run status
- eligible tasks
- open findings
- phase summaries
- dashboards

A projection may be cached but must cite exact immutable source identities/digests and cannot introduce facts absent from authoritative lineage.

## Open design choice
Two strong source patterns conflict:
1. `thin-agent-harness`: append-only events are authoritative; replay derives current state.
2. `opencode-orchestrated-agent-workflow`: one atomically replaced `run.json` is authoritative,
   immutable artifacts surround it.

Draft direction: immutable transition lineage is authoritative, with an atomically replaced
run-head/projection only as a checkpoint/cache. Before implementation, run a crash-consistency
spike on Windows + Linux filesystems and record ADR.
