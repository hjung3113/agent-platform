# Artifact and Run-State Model

## Authority phases
A payload moves through distinct authority phases:

`Candidate -> Kernel admission -> Published authoritative record -> Derived projection`

These are **authority states, not mandatory separately persisted records**.

- **Candidate**: proposed content or judgement. It remains non-authoritative even when schema-valid, stored under a canonical path, or produced by a privileged-named role.
- **Admitted**: the exact candidate identity/digest has passed deterministic Kernel policy checks and every required Human Authority gate.
- **Published**: the admitted identity has been durably committed through the single Kernel authority boundary.
- **Derived projection**: a rebuildable view over published lineage; it cannot introduce new authoritative facts.

Admission and publication should normally be one atomic Kernel operation. Persist a pre-admission candidate only when an asynchronous/human gate, resumability, or audit requirement gives that candidate an independent lifecycle.

An LLM verdict such as `PASS` is candidate semantic evidence, never an admission predicate by itself.

## Minimum persistent lineage

The first vertical slice requires only these standalone authoritative record families:
- Request
- Workflow Revision
- Attempt Packet
- Result
- Verification
- Receipt

The following concepts may be embedded as provenance-bound fields/attachments in those records until they gain an independent lifecycle:
- Context selection / Context Pack -> Attempt Packet
- Role capability grant -> Attempt Packet
- Workspace Snapshot -> Attempt Packet and Result bindings
- Runtime Observation -> Result
- Evidence -> Verification or Result/Verification attachment
- Review findings -> Verification

Conditional standalone records are introduced only when required:
- Decision / Human Approval for material decisions or gates
- Plan Check when policy requires independent plan critique
- standalone Evidence when produced asynchronously, reused, or retained independently
- Release Authorization / Release Receipt for external effects
- separate Review when Reviewer and Verifier independence is explicitly required

This profile preserves lineage and auditability without requiring one persisted artifact per conceptual step.

## Immutable lineage
Authoritative lineage is expressed through immutable published records and explicit parent bindings.

Each standalone authoritative record carries a schema/protocol version, durable identity, canonical content digest, and the exact parent/source identities and digests required by its contract. Embedded evidence/provenance entries carry the corresponding subject/source identity and digest needed to make substitution detectable.
A child record is valid only against those exact parents; substituting a newer or equivalent-looking record creates a different lineage.

## Snapshot identity
A Workspace Snapshot is the authoritative identity of the effective workspace content used for execution, review, verification, and release.
Repository HEAD may be one input to snapshot identity but is not sufficient when staged, unstaged, untracked, generated, submodule, nested-repository, or other release-relevant content can differ.

Whether snapshot identity is a standalone record or an embedded binding is a storage-shape choice; Result, Verification, Evidence, Release Authorization, and Release Receipt must still name the exact subject snapshot they concern.
Verification evidence for another subject snapshot is stale by definition.

## Gate binding
- A Plan Check binds the canonical digest of the candidate plan/workflow it checked when policy requires that gate.
- A passing Plan Check is semantic evidence only; it does not itself authorize admission.
- Kernel may admit a Workflow Revision when deterministic admission predicates pass, required Human Authority gates are satisfied, and any policy-required Plan Check binds the exact candidate digest.
- A successor Workflow Revision created by replan requires a fresh Plan Check only when the applicable policy requires plan checking for that successor.
- Any transformation that changes canonical content produces a new candidate requiring the applicable gates again.
- Context/evidence may be embedded, but their source and subject bindings cannot be silently replaced.
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
