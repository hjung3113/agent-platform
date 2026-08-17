# Artifact and Run-State Model

## Authority phases
A payload moves through distinct authority phases:

`Candidate -> Kernel admission -> Published authoritative record -> Derived projection`

- **Candidate**: proposed content or judgement. It remains non-authoritative even when schema-valid, stored under a canonical path, or produced by a privileged-named role.
- **Admitted**: the exact candidate identity/digest has passed deterministic Kernel policy checks and every required Human Authority gate.
- **Published**: the admitted identity has been durably committed through the single Kernel authority boundary.
- **Derived projection**: a rebuildable view over published lineage; it cannot introduce new authoritative facts.

An LLM verdict such as `PASS` is candidate semantic evidence, never an admission predicate by itself.

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
- A passing Plan Check is required semantic evidence when policy requires it, but does not itself authorize admission.
- Kernel may admit a Workflow Revision only when its canonical content digest equals the Plan Check subject digest, deterministic admission predicates pass, and any material Human Authority gate is satisfied.
- Every successor Workflow Revision created by replan requires a new Plan Check over that successor digest.
- Any transformation that changes canonical content produces a new candidate requiring the applicable gate again.
- Context Pack and Attempt Packet bind their authoritative source lineage and cannot silently replace sources.
- Release Authorization binds the verified snapshot plus the expected target state; Release Receipt records the actual released identity.

## Publication authority
There is one logical authoritative publication boundary: Kernel.
Agents, adapters, hosts, orchestration helpers, and tools may produce candidates or observations, and storage components may persist on behalf of the authority boundary, but they do not independently create competing authoritative records.
Canonical repository placement, schema validity, producer role, or verdict text cannot bypass admission.

## Authoritative run state
Per [ADR-0007](../adr/0007-run-state-authority.md), immutable transition lineage admitted and published by the Kernel is the sole authoritative operational run state.

Authoritative transition publication is the protocol commit point. Current-state/run-head documents are derived checkpoints or caches only and cannot introduce facts absent from lineage.

Each transition identifies the exact causal/predecessor lineage it extends. A stale or conflicting candidate cannot replace or reinterpret published lineage; it is rejected or represented as a new explicit successor transition.
Duplicate publication of the same logical operation is idempotent and cannot create a second authoritative fact.

## Derived projections
- active decisions
- current run status
- eligible tasks
- open findings
- phase summaries
- dashboards

A projection may be cached but must cite exact immutable source identities/digests. Missing, stale, corrupt, or conflicting projections are rebuilt or rejected from authoritative lineage.

Replay of the same accepted lineage must produce the same derived state, eligible task set, and transition inputs.

## Receipt semantics
A Receipt is explicitly typed as checkpoint or terminal.
A checkpoint Receipt records a durable progress/result boundary but does not terminate the run.
Only a terminal Receipt establishes terminal run state.
