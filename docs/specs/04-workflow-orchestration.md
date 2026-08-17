# Spec 04 — Workflow & Orchestration

## Goal
Select and advance bounded work without letting the model invent authority.

## Required behavior
- immutable admitted workflow revisions
- dependency graph with structural cycle/reference validation
- explicit task resources/touch scope
- risk-tier or workflow-profile selection
- pre-execution plan-checker gate
- deterministic eligibility/next-action projection
- bounded repair/replan
- material decision escalation
- repeated-failure circuit breaker
- no implicit model/runtime escalation
- fan-in must declare merge semantics for conflicting inputs
- parallel execution only after resource isolation is proven

## Roles
Conductor proposes; Architect/Planner plans; Plan Checker independently verifies; Kernel admits.
