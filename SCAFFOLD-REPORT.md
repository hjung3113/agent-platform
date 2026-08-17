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

## Critical unresolved decision

Run-state authority still needs a spike:
- event-replay-first (`thin-agent-harness`)
- atomic mutable run-state commit point (`opencode-orchestrated-agent-workflow`)

The scaffold preserves both research trails and does not pretend the conflict is resolved.

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
