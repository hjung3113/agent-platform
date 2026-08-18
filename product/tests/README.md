# Test Strategy

Before broad feature work, contract tests must prove:
- admission fail-closed behavior
- publication ownership
- idempotent duplicate handling
- stale/conflict rejection
- Plan Checker digest binding
- context source/digest binding
- runtime capability no-fallback
- content-identity review/verify binding
- implementer cannot final-verify own snapshot
- release requires separate authorization
- upstream skill update does not bypass behavior/eval gates

Skill behavior tests should include pressure scenarios where baseline agents fail without the skill.
