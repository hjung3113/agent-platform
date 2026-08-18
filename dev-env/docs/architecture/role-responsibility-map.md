# Role Responsibility Map

Roles describe **responsibility seats**, not mandatory personas or processes. A specialist role exists only when independent judgement, authority, context, or lifecycle is operationally useful.

## Minimum viable seats

For the first vertical slice:
- **Human Authority** — only where material scope/policy/external-effect approval is actually required.
- **Planner** — produces the candidate Workflow Revision. It may also perform lightweight analysis/conductor work.
- **Implementer** — executes the admitted task and produces candidate output.
- **Verifier** — independent from the Implementer for the verified snapshot; performs both spec/quality review and acceptance/evidence verification in the baseline profile.

The hard separation is **Implementer != final Verifier for the same snapshot**. Other role boundaries are policy-driven, not universal.

## Optional specialist seats

Introduce these only when the stated failure mode is concrete:
- **Conductor** — multi-agent/multi-workflow coordination would otherwise overload the Planner.
- **Analyst/Researcher** — evidence gathering needs an independent context/budget or provenance boundary.
- **Architect/Planner specialization** — architecture and execution planning genuinely need different expertise/lifecycles.
- **Plan Checker** — high-risk or complex plans require independent semantic critique before Kernel admission.
- **Reviewer** — semantic quality review must be independent from acceptance verification. Otherwise Verifier covers both responsibilities.
- **Release Captain** — a separately authorized external effect needs an execution seat distinct from readiness verification.
- **Knowledge Curator** — durable derived-memory stewardship becomes large enough to justify a dedicated seat.

A role split is rejected when it only renames sequential prompt steps without creating enforceable independence or reducing a concrete failure mode.

## Deterministic system responsibilities

Logical responsibilities remain distinct:
- authoritative admission/publication and run transitions
- runtime/workspace/capability enforcement
- context selection/binding
- task eligibility/scheduling
- contract validation
- evidence normalization

They do **not** imply six deployable subsystems. The MVP deployment boundary is:
- **Kernel process** — authority, transition logic, scheduling, contract validation, context assembly, evidence normalization as deterministic internal modules/functions.
- **Harness Host boundary** — runtime/workspace/capability enforcement where process or sandbox separation is real.

Split a deterministic responsibility into its own service/package only when there is an independent security boundary, failure domain, scaling need, release lifecycle, or reusable protocol boundary.

## Role-cluster source map
- Conductor: FeedbackOps conductor + thin-harness orchestrator
- Analyst: migration discovery/evidence + env-setup brownfield scan + GSD researcher
- Architect/Planner: GSD planner + FeedbackOps architect autonomy + Matt to-spec/to-tickets
- Plan Checker: GSD goal-backward plan-checker
- Implementer: FeedbackOps implementation seat + Superpowers fresh subagent executor
- Reviewer: FeedbackOps reviewer/visual reviewer + Superpowers spec then quality review
- Verifier: thin-harness verifier + migration composite judge + GSD post-verifier
- Release Captain: Orca/FeedbackOps release gate patterns
- Knowledge Curator: thin memory steward + lifetime derived-memory curator, stripped of decision authority
