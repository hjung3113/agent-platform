# ADR-0005 — Fresh context for bounded task execution

Status: Proposed

Decision:
Executors/reviewers/verifiers start from newly compiled task-specific context rather than inheriting
the conductor session.

Reason:
GSD and Superpowers both use fresh subagents to reduce context rot and role bleed.
