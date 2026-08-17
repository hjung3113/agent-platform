# Unified Agent Platform — Domain Context

## Core vocabulary

- **Human Authority** — the only actor allowed to approve material product/scope/policy decisions.
- **Kernel** — deterministic publication and state-transition authority.
- **Harness Host** — deterministic boundary that validates runtime capability, workspace identity,
  artifacts, evidence, and host-observed facts. It is implemented inside the product, not an LLM role.
- **Conductor** — read-only orchestration role that proposes decomposition, routing, and next actions.
- **Workflow Revision** — immutable admitted task graph and policy for a run.
- **Task** — one bounded unit in a workflow graph.
- **Attempt** — one runtime execution of a task.
- **Context Pack** — bounded, provenance-linked context selected for one attempt.
- **Attempt Packet** — immutable execution contract for one attempt.
- **Artifact** — immutable task output or protocol record.
- **Evidence** — provenance-linked observed fact supporting a claim.
- **Finding** — independently observed unresolved problem; never a decision.
- **Receipt** — host/kernel published result record, not an agent self-report.
- **Material Decision** — a change to goal, scope, constraints, acceptance, external effects,
  or another durable authority requiring human approval.
- **Derived Memory** — regenerable index/cache; never a source of truth.
- **Skill** — reusable discipline/workflow knowledge. Canonical unit for agent-side behavior.
- **Command** — thin user-facing entry point to a skill/workflow.
- **Adapter** — runtime-specific or transport-specific mapping layer.

## Relationships

Human Authority approves durable decisions and workflow revisions.
The Kernel admits/publishes authoritative records.
The Conductor proposes work but does not edit product code or authoritative state directly.
The Context Compiler deterministically builds Context Packs and Attempt Packets.
Executors produce candidate results.
Reviewers and Verifiers produce independent findings/evidence.
The Kernel advances state from admitted evidence and policy.
