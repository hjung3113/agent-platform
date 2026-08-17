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
- the authoritative Workspace Snapshot represents effective execution/release-relevant content; repository HEAD alone is insufficient when staged, unstaged, untracked, generated, submodule, nested-repository, or equivalent state can affect the result
- Attempt Packet binds the exact admitted workflow/task, Context Pack, Workspace Snapshot, runtime capability set, and execution envelope
- exact admitted command/tool envelope when deterministically enforceable
- host captures Runtime Observation plus exact output snapshot identity and binds both to the producing Attempt
- Result candidates reference the producing Attempt, Runtime Observation, and exact output snapshot rather than a mutable workspace label
- agent prose is diagnostic, not completion authority
- no silent runtime or transport fallback

## Portability
Core skills should use runtime-neutral action vocabulary with thin per-harness tool mapping.
