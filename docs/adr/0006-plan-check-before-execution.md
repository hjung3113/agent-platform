# ADR-0006 — Independent plan checking before execution

Status: Proposed

Decision:
Non-trivial workflows require a Plan Checker distinct from the authoring Architect/Planner and from
post-execution Verifier.

Reason:
A plan can contain all task names while still fail to wire the outcome together. Goal-backward plan
verification catches this before code is written.
