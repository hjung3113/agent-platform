# Spec 05 — Runtime & Execution

## Goal
Execute one admitted Attempt Packet in an isolated, capability-checked environment.

## Required behavior
- fresh context by default for bounded attempts
- context compiler selects only task/lineage-relevant authoritative material
- context budget is explicit; essential content is never silently truncated
- capability probe before side effects
- runtime/role/model/transport are independent configuration axes
- workspace/worktree/sandbox identity is bound before execution
- exact admitted command/tool envelope when deterministically enforceable
- host captures runtime observations and output snapshot identity
- agent prose is diagnostic, not completion authority
- no silent runtime or transport fallback

## Portability
Core skills should use runtime-neutral action vocabulary with thin per-harness tool mapping.
