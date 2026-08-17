# End-to-End Wiring Contract

## 0. Intake
Raw human material -> Intake candidate -> Alignment Gate -> approved Request Contract.

## 1. Planning
Request + repository/decision context -> Architect/Planner -> candidate Workflow/Tasks.

## 2. Plan quality
Plan Checker verifies goal coverage, dependencies, wiring, scope, locked decisions.
Failure returns structured issues to planner. PASS permits Kernel admission.

## 3. Scheduling
Kernel admits immutable Workflow Revision. Orchestrator derives next eligible Task.

## 4. Attempt compilation
Context Compiler resolves authoritative sources and compiles Context Pack + Attempt Packet.

## 5. Admission & execution
Host probes selected runtime/transport, binds workspace/snapshot, then launches Implementer.

## 6. Observation
Adapter/Host records runtime observation and exact output snapshot. Implementer publishes candidate Result.

## 7. Independent judgement
Reviewer checks spec/quality; Verifier checks acceptance using exact snapshot-bound evidence.

## 8. Transition
Kernel validates publications and chooses:
- next Task
- repair Attempt
- replan request
- material decision request
- typed block
- terminal Receipt

## 9. Delivery
Release Captain may act only on the verified snapshot and separately authorized external-effect policy.

## Hard handoff invariants
Every arrow carries a schema/version + source identity/digest.
No step consumes pane/chat prose as workflow state.
No role both implements and final-verifies the same snapshot.
