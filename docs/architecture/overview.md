# Architecture Overview

The architecture distinguishes **logical responsibilities** from **mandatory roles, contracts, processes, or services**. A responsibility is split into a separate deployable component or durable contract only when it needs an independent authority boundary, lifecycle, failure isolation, security envelope, reuse boundary, or scaling characteristic.

## Minimum viable vertical slice

The first end-to-end Kernel proof is intentionally small:

```text
Human request
  -> Request Contract
  -> Planner creates a one-task Workflow Revision
  -> Kernel validates + atomically admits/publishes the revision
  -> Kernel-internal scheduling/context assembly selects the Task
  -> Host binds workspace/capabilities and runs Implementer
  -> Result + evidence/snapshot bindings
  -> independent Verifier checks quality + acceptance
  -> Kernel validates lineage/evidence and publishes terminal Receipt
```

Required invariants in this slice:
- only Kernel-owned code publishes authoritative run state
- every published record binds exact parent/source identities and digests needed for correctness
- execution and final verification are independent seats
- stale snapshot/evidence bindings fail closed
- replay/idempotency cannot create a second authoritative fact

The MVP does **not** require a separate Plan Checker, Reviewer, Conductor, Context Compiler service, Scheduler service, Contract Validator service, Evidence Normalizer service, standalone Context Pack, standalone Runtime Observation, or release subsystem.

## Progressive expansion

Add specialization only when the concrete failure it prevents cannot be handled inside the existing boundary:
- **Plan Checker**: when policy requires independent semantic plan critique for complex/high-risk workflows.
- **Reviewer + Verifier split**: when quality review and acceptance verification need distinct independence or policy authority. Otherwise one independent Verifier performs both checks.
- **Conductor / Analyst / Knowledge Curator**: when coordination, research, or long-lived knowledge work is large enough to need an independent seat.
- **Standalone Context Pack / Evidence / Observation records**: when they are reused, produced asynchronously, too large to embed, or have an independent retention/lifecycle requirement.
- **Separate deterministic services**: only for real process/security/failure-isolation/scaling boundaries. Kernel scheduling, validation, context assembly, and evidence normalization may start as internal deterministic modules.
- **Release Captain and release contracts**: only for separately authorized external effects.

The expanded reference flow remains valid as a capability map, but it is not the mandatory deployment or workflow shape.

Cross-cutting concerns:
- Knowledge/decision authority
- Governance/policy
- Runtime/transport adapters
- Observability
- Derived memory
