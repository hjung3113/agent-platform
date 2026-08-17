# End-to-End Wiring Contract

## 0. Intake
Raw human material -> Intake candidate -> Alignment Gate -> approved Request Contract.

## 1. Planning
Request + repository/decision context -> Architect/Planner -> candidate Workflow/Tasks.

## 2. Plan quality
Plan Checker verifies goal coverage, dependencies, wiring, scope, locked decisions.
Failure returns structured issues to planner. PASS permits Kernel admission only for the exact checked candidate digest.
If admission-time normalization or transformation changes canonical content, the resulting candidate requires a new Plan Check.
Every successor Workflow Revision proposed by replan returns through this same Plan Check gate.

## 3. Scheduling
Kernel admits an immutable Workflow Revision whose canonical content digest matches the passing Plan Check subject digest.
Deterministic orchestration logic derives the eligible set and transition candidate solely from the admitted revision plus authoritative immutable lineage.
Kernel remains the only authority that publishes the resulting run transition.

## 4. Attempt compilation
Context Compiler resolves authoritative sources and compiles Context Pack + Attempt Packet.
Both artifacts bind the exact task/workflow revision plus every authoritative source identity and digest they consume.
Stale, substituted, or conflicting source bindings fail closed.

## 5. Admission & execution
Host probes selected runtime/transport, then binds an exact Workspace Snapshot before execution.
Snapshot identity represents all release-relevant workspace content and state; repository HEAD alone is not sufficient when staged, unstaged, untracked, generated, or nested repository content can affect the result.
The Attempt Packet binds the admitted workflow/task, context pack, workspace snapshot, runtime capability set, resource claims, and allowed execution envelope.
Parallel attempts may launch only when admitted logical resource claims prove non-conflict.

## 6. Observation
Adapter/Host records Runtime Observation and the exact produced output snapshot identity.
Implementer publishes only a candidate Result referencing the producing Attempt, Observation, and output snapshot digest.

## 7. Independent judgement
Reviewer checks spec/quality against the Result's exact snapshot.
Verifier checks declared acceptance using evidence bound to that same subject snapshot.
Evidence for another snapshot, attempt, input, or incompatible environment is stale and cannot satisfy the verdict.

## 8. Transition
Kernel validates publication identity, schema/version, parent lineage, digest bindings, admitted transition policy, and reconciliation/resource constraints before publishing one of:
- next Task transition
- repair Attempt
- retry Attempt
- replan request
- material decision request
- typed block
- terminal Receipt

Retry, repair, replan, material-decision, reconciliation, blocked, and terminal outcomes are distinct. Replan never mutates an admitted revision; it creates a successor candidate that returns to the Plan Check gate.

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
- immutable Kernel-published transition lineage is the sole authoritative run state
- Plan Check subject digest must equal the admitted Workflow Revision digest
- every successor Workflow Revision requires a fresh Plan Check over that successor digest
- eligible task derivation uses only the admitted revision and authoritative lineage and must be deterministic
- Context Pack and Attempt Packet cannot silently substitute authoritative inputs
- Workspace/output snapshot identity covers effective content, not only repository HEAD
- Result, Review, Verification, Release Authorization, and Release Receipt bind an explicit subject snapshot and parent lineage
- Evidence is accepted only for the exact snapshot and execution context it observed
- Authoritative publication has one logical writer boundary; components may propose or persist on its behalf but cannot independently create competing authority
- unresolved fan-in conflicts, ambiguous state, stale bindings, unknown resource conflicts, and reconciliation-required overlap fail closed
- No step consumes pane/chat prose as workflow state
- No role both implements and final-verifies the same snapshot
