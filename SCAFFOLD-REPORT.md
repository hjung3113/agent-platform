# Scaffold Report

## Structural change from the earlier draft

The previous 7-spec design is now 8 specs:
- Knowledge/Decisions/Research remains durable context.
- Contracts/Protocol/Run State is a separate core because operational state has different authority,
  lifecycle, and crash/replay semantics.

Agent roles were also corrected:
- Added explicit `Plan Checker`.
- Removed Kernel/Host/Context Compiler from agent persona space.
- Visual/Security/Spec/Quality review are reviewer/verifier profiles, avoiding role explosion.

## Run-state authority decision

ADR-0007 resolves the earlier competing state patterns:
- immutable Kernel-published transition lineage is the sole authoritative operational state
- mutable run-head/current-state documents are derived checkpoints/caches only
- workflow eligibility and recovery must be replayable from authoritative lineage

Concrete persistence/fencing and platform crash-consistency validation remain implementation work; they do not reopen the semantic authority decision.

## Workflow/orchestration design constraints

Before parallel or autonomous multi-task execution is introduced, the admitted workflow contract must preserve:
- deterministic eligibility and canonical task ordering
- explicit dependency completion semantics
- fresh digest-bound Plan Check for every Workflow Revision, including replan successors
- bounded retry/repair/replan with explicit escalation
- declared fan-in conflict behavior
- logical resource isolation rather than path-only isolation
- Kernel-only authoritative transition publication

## Recommended first implementation slice

Request Contract
-> one admitted Task
-> Plan Checker digest binding
-> one fresh Attempt
-> one runtime adapter
-> exact content snapshot
-> independent verification
-> host/kernel Receipt

No parallelism, no visual editor, no automatic upstream skill sync until this slice is proven.
