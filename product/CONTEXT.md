# Unified Agent Platform — Domain Context

## Core vocabulary

### Authority & state

- **Human Authority** — the only actor allowed to approve material product/scope/policy decisions.
- **Kernel** — deterministic publication and state-transition authority.
- **Harness Host** — deterministic boundary that validates runtime capability, workspace identity,
  artifacts, evidence, and host-observed facts. It is implemented inside the product, not an LLM role.
- **Context Compiler** — deterministic Kernel-internal subsystem that builds Context Packs and
  Attempt Packets from exact source identities; not an LLM role and does not derive authority from
  model interpretation.
- **Authority Phase** — the four states a payload moves through: **Candidate** (proposed, never
  authoritative) → **Admitted** (passed deterministic Kernel policy + required Human Authority
  gates) → **Published** (durably committed through the Kernel boundary) → **Derived projection**
  (rebuildable view over published lineage, e.g. run-head, eligible tasks, dashboards; cannot
  introduce new authoritative facts).
- **Material Decision** — a change to goal, scope, constraints, acceptance, external effects,
  or another durable authority requiring human approval.
- **Human Approval Record** — the standalone record binding an approver to the exact Material
  Decision/effect, subject identity/digest, and approval scope.
- **Reconciliation-Required State** — a blocked state after an ambiguous crash/cancellation that
  prevents conflicting retry, successor, or parallel work until an authoritative reconciliation
  transition resolves it.
- **Derived Memory** — regenerable, filesystem-persisted index/cache (`product/memory/derived/`);
  never a source of truth. One concrete storage form of a Derived projection.

### Roles

- **Planner** — produces the candidate Workflow Revision; the minimum viable seat.
- **Implementer** — executes the admitted task and produces candidate output.
  _Avoid_: Executor.
- **Verifier** — independent from the Implementer for a given snapshot; performs both
  spec/quality review and acceptance/evidence verification in the baseline profile.
- **Reviewer** — optional seat that performs semantic/spec-quality review independently
  from acceptance verification, when policy requires two distinct judgements. Otherwise
  the Verifier covers both.
- **Conductor** — read-only orchestration role that proposes decomposition, routing, and next
  actions; optional seat introduced when multi-agent/multi-workflow coordination would
  overload the Planner.
- **Analyst/Researcher** — optional seat for evidence gathering that needs an independent
  context/budget or provenance boundary.
- **Architect/Planner** — optional specialization when architecture and execution planning
  need genuinely different expertise/lifecycles.
- **Plan Checker** — optional seat providing independent semantic critique of a candidate
  Workflow Revision before Kernel admission, when policy requires it for high-risk/complex plans.
- **Release Captain** — optional seat that executes a separately authorized external effect,
  distinct from readiness verification.
- **Knowledge Curator** — optional seat for durable Derived Memory stewardship; proposal-only,
  never decision authority.

The hard invariant across all roles: no role may both implement and final-verify the same snapshot.

### Records

- **Request (Contract)** — published intake record a Planner turns into a candidate Workflow Revision.
- **Workflow Revision** — immutable admitted task graph and policy for a run.
- **Task** — one bounded unit in a workflow graph.
- **Attempt** — one runtime execution of a task.
- **Context Pack** — bounded, provenance-linked context selected for one attempt.
- **Attempt Packet** — immutable execution contract for one attempt.
- **Result** — Implementer's candidate output for an Attempt; not authoritative completion state.
- **Runtime Observation** — Host/adapter-captured runtime observation bound to the producing
  Attempt and exact output snapshot; embeddable in Result until it needs its own lifecycle.
- **Workspace Snapshot** — the authoritative identity of effective workspace content used for
  execution, review, verification, and release; repository HEAD alone is not sufficient.
  _Avoid_: Snapshot Manifest.
- **Review** — optional standalone record of Reviewer findings; embeddable in Verification
  until Reviewer/Verifier independence is explicitly required.
- **Verification** — the Verifier's acceptance/evidence judgement over an exact Result snapshot.
- **Evidence** — provenance-linked observed fact supporting a claim; stale if bound to a
  different snapshot, attempt, input, or environment.
- **Finding** — independently observed unresolved problem; never a decision.
- **Plan Check** — optional independent semantic critique record binding the canonical digest
  of the exact candidate plan/workflow it checked; a `PASS` is semantic evidence only, never
  admission authority by itself.
- **Role Capability Grant** — admitted execution envelope (tools, write/network/secret scope)
  available to one attempt/role; embeddable in the Attempt Packet.
- **Runtime Capability Profile** — immutable per-runtime/adapter/configuration record of
  supported canonical actions, effective permission envelope, and cancellation/reconciliation
  guarantees; bound to the Attempt Packet and re-required whenever its identity changes.
- **Release Authorization** — separately authorizes a concrete external effect (push/PR/merge/
  deploy/release); binds the exact verified snapshot, effect set/order, target identity, and
  expected pre-release target state. Verified readiness alone cannot create it.
  _Avoid_: External Effect Authorization.
- **Release Receipt** — records the actual released content/target identity.
- **Receipt** — host/kernel published result record, not an agent self-report; explicitly typed
  as checkpoint (progress boundary) or terminal (ends the run).
- **Artifact** — immutable task output or protocol record.
- **Skill** — reusable discipline/workflow knowledge. Canonical unit for agent-side behavior.
- **Command** — thin user-facing entry point to a skill/workflow.
- **Adapter** — runtime-specific or transport-specific mapping layer.

## Relationships

Human Authority approves durable decisions and workflow revisions.
The Kernel admits/publishes authoritative records.
The Conductor proposes work but does not edit product code or authoritative state directly.
The Context Compiler deterministically builds Context Packs and Attempt Packets.
Implementers produce candidate Results.
Reviewers and Verifiers produce independent findings/evidence.
The Kernel advances state from admitted evidence and policy.
