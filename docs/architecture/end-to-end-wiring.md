# End-to-End Wiring Contract

This document defines correctness invariants. It does **not** require every logical step to be a separate role, process, service, or persisted artifact.

## Minimum viable path

```text
Request Contract
  -> Planner: candidate one-task Workflow Revision
  -> Kernel: deterministic admission + atomic publication
  -> Kernel-internal eligibility/context assembly
  -> Host: capability/workspace binding + Implementer execution
  -> Result with exact output snapshot/runtime provenance
  -> independent Verifier with bound evidence/findings
  -> Kernel: deterministic transition validation
  -> terminal Receipt
```

The MVP proves the core invariants before optional roles/contracts are promoted.

## 0. Intake
Raw human material becomes a Request candidate. A separate Human Approval Record is required only when policy identifies a material alignment/scope/policy decision that needs explicit approval. Otherwise Kernel may validate and atomically publish the Request Contract from the user's direct request.

## 1. Planning
Published Request + admitted repository/decision context -> Planner -> candidate Workflow/Tasks.

A simple one-task workflow does not require separate Conductor, Analyst, Architect, or Plan Checker seats. Those are specialist capabilities that may be introduced by policy or workload complexity.

## 2. Plan quality
Kernel always performs deterministic plan/workflow admission checks: schema, lineage, dependency validity, scope/policy predicates, and required Human Authority gates.

Independent Plan Checker review is **policy-conditional**, not universal. When required, it verifies goal coverage, dependencies, wiring, scope, and locked decisions against the exact candidate digest. `PASS` remains semantic evidence only; it never permits admission by itself.

If admission-time normalization changes canonical content, the transformed content is a new candidate and any applicable semantic/human gate must bind that new digest. A successor Workflow Revision created by replan repeats the Plan Check only when the applicable policy requires it.

## 3. Scheduling
Kernel admits and publishes an immutable Workflow Revision after applicable predicates/gates pass.
Deterministic orchestration derives eligible tasks and transition candidates solely from the admitted revision plus authoritative immutable lineage.

In the MVP, scheduling/orchestration is an internal deterministic Kernel module. It becomes a separate subsystem only when an independent lifecycle, failure domain, security boundary, or scaling need exists.

## 4. Attempt compilation
Deterministic context assembly resolves exact admitted/published sources and creates the Attempt Packet.

The baseline embeds context-source bindings directly in the Attempt Packet; a standalone Context Pack is optional. Regardless of storage shape, source identities/digests are exact, repository paths are discovery hints rather than authority, and stale/substituted/conflicting bindings fail closed.

## 5. Admission & execution
Host probes the selected runtime/transport, validates the admitted capability envelope, and binds the effective Workspace Snapshot before execution.
Snapshot identity represents all release-relevant workspace content and state; repository HEAD alone is insufficient when staged, unstaged, untracked, generated, nested-repository, or equivalent state can affect the result.

The Attempt Packet binds admitted workflow/task, context-source bindings, workspace snapshot identity, runtime capability set, resource claims, and allowed execution envelope.
Parallel attempts may launch only when admitted logical resource claims prove non-conflict.

## 6. Observation
Adapter/Host runtime observations may be embedded in or attached to Result in the MVP. They must retain exact Attempt/output-snapshot provenance.
Implementer submits only a candidate Result and cannot publish authoritative completion state.

Promote Runtime Observation to a standalone record only when observations are asynchronous/streaming, independently retained, reused, or queried as their own lifecycle.

## 7. Independent judgement
The baseline uses one **Verifier independent from the Implementer** to perform both semantic/spec-quality review and acceptance/evidence verification over the exact Result snapshot.

Split Reviewer and Verifier only when policy requires two independently enforceable judgements. A standalone Review and standalone Finding record are likewise optional; findings may be embedded in Verification while preserving exact subject/evidence bindings.

Evidence for another snapshot, attempt, input, or incompatible environment is stale and cannot satisfy a transition predicate.

## 8. Transition
Kernel validates publication identity, schema/version, parent lineage, digest bindings, admitted transition policy, required evidence coverage/provenance, blocking findings, capability state, reconciliation/resource constraints, and required Human Authority approvals before publishing one of:
- next Task transition
- repair Attempt
- retry Attempt
- replan request
- material decision request
- typed block
- terminal Receipt

An LLM `PASS` is never sufficient by itself.
Retry, repair, replan, material-decision, reconciliation, blocked, and terminal outcomes remain distinct. Replan never mutates an admitted revision; it creates a successor candidate and repeats only the gates applicable to that successor.

A later record cannot substitute a different parent, result, snapshot, or evidence set without creating a new lineage successor and re-running the required gate.

## 9. Delivery extension
Release machinery is outside the MVP unless the workflow performs a separately authorized external effect.

When used, verified readiness and release authorization are separate states. Release Authorization binds the exact verified snapshot, intended external effect, target identity, and expected pre-release target state. Immediately before the external effect, the release path revalidates those bindings and fails closed if target or snapshot changed. Release Receipt records actual released content/target identity.

## Hard handoff invariants
Every standalone authoritative record carries:
- schema/protocol version
- durable record identity
- canonical content digest
- exact parent/source identities and digests required for correctness

Embedded provenance/evidence entries carry the equivalent exact bindings needed to detect substitution.

Additionally:
- candidate, admitted, published, and derived authority states are distinct even when admission/publication occur atomically and candidate/admitted states are not separately persisted
- immutable Kernel-published transition lineage is the sole authoritative run state
- when a Plan Check is required, its subject digest must equal the admitted Workflow Revision digest; its `PASS` is not admission authority
- eligible task derivation uses only the admitted revision and authoritative lineage and is deterministic
- embedded or standalone context/evidence cannot silently substitute authoritative inputs
- Workspace/output snapshot identity covers effective content, not only repository HEAD
- Result and Verification bind an explicit subject snapshot and parent lineage; optional Review/Release records do the same when present
- Evidence is accepted only for the exact snapshot and execution context it observed
- authoritative publication and workflow-state advancement have one logical Kernel writer boundary
- unresolved fan-in conflicts, ambiguous state, stale bindings, unknown resource conflicts, and reconciliation-required overlap fail closed
- no step consumes pane/chat prose as workflow state
- no role both implements and final-verifies the same snapshot
