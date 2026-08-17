# End-to-End Wiring Contract

## 0. Intake
Raw human material -> Intake candidate -> Alignment Gate -> approved Request Contract.

## 1. Planning
Request + repository/decision context -> Architect/Planner -> candidate Workflow/Tasks.

## 2. Plan quality
Plan Checker verifies goal coverage, dependencies, wiring, scope, locked decisions.
Failure returns structured issues to planner. PASS permits Kernel admission only for the exact checked candidate digest.
If admission-time normalization or transformation changes canonical content, the resulting candidate requires a new Plan Check.

## 3. Scheduling
Kernel admits an immutable Workflow Revision whose canonical content digest matches the passing Plan Check subject digest.
Orchestrator derives next eligible Task from that admitted revision.

## 4. Attempt compilation
Context Compiler resolves authoritative sources and compiles Context Pack + Attempt Packet.
Both artifacts bind the exact task/workflow revision plus every authoritative source identity and digest they consume.
Stale, substituted, or conflicting source bindings fail closed.

## 5. Admission & execution
Host probes selected runtime/transport, then binds an exact Workspace Snapshot before execution.
Snapshot identity represents all release-relevant workspace content and state; repository HEAD alone is not sufficient when staged, unstaged, untracked, generated, or nested repository content can affect the result.
The Attempt Packet binds the admitted workflow/task, context pack, workspace snapshot, runtime capability set, and allowed execution envelope.

## 6. Observation
Adapter/Host records Runtime Observation and the exact produced output snapshot identity.
Implementer publishes only a candidate Result referencing the producing Attempt, Observation, and output snapshot digest.

## 7. Independent judgement
Reviewer checks spec/quality against the Result's exact snapshot.
Verifier checks declared acceptance using evidence bound to that same subject snapshot.
Evidence for another snapshot, attempt, input, or incompatible environment is stale and cannot satisfy the verdict.

## 8. Transition
Kernel validates publication identity, schema/version, parent lineage, and digest bindings before choosing:
- next Task
- repair Attempt
- replan request
- material decision request
- typed block
- terminal Receipt

A later artifact cannot substitute a different parent, result, snapshot, or evidence set without creating a new lineage successor and re-running the required gate.

## 9. Delivery
Verified readiness and release authorization are separate states.
Release Authorization binds the exact verified snapshot, intended external effect, target identity, and expected pre-release target state.
Immediately before the external effect, the release path must revalidate those bindings and fail closed if the target or snapshot changed.
Release Receipt records the actual released content/target identity so it can be checked against the authorization and verification lineage.

## Hard handoff invariants
Every authoritative artifact carries:
- schema/protocol version
- durable artifact identity
- canonical content digest
- exact parent/source artifact identities and digests required by its contract

Additionally:
- Plan Check subject digest must equal the admitted Workflow Revision digest.
- Context Pack and Attempt Packet cannot silently substitute authoritative inputs.
- Workspace/output snapshot identity covers effective content, not only repository HEAD.
- Result, Review, Verification, Release Authorization, and Release Receipt bind an explicit subject snapshot and parent lineage.
- Evidence is accepted only for the exact snapshot and execution context it observed.
- Authoritative publication has one logical writer boundary; components may propose or persist on its behalf but cannot independently create competing authority.
- Unknown, stale, ambiguous, mismatched, or incompatible handoff state fails closed.
- No step consumes pane/chat prose as workflow state.
- No role both implements and final-verifies the same snapshot.
