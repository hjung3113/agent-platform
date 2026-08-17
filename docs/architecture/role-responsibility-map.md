# Role Responsibility Map

## Human/LLM roles
Human Authority, Conductor, Analyst/Researcher, Architect/Planner, Plan Checker,
Implementer, Reviewer, Verifier, Release Captain, Knowledge Curator.

## Deterministic system actors
Kernel, Harness Host, Context Compiler, Scheduler/Orchestration Engine,
Contract Validator, Evidence Normalizer.

This separation is intentional. Earlier designs that placed all of these under "roles"
made it too easy to confuse an LLM persona with executable authority.

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
