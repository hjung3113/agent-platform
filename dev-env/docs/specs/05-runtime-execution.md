# Spec 05 — Runtime & Execution

## Goal
Execute one admitted Attempt Packet in an isolated, capability-checked environment.

## Required behavior
- fresh context by default for bounded attempts
- Context Compiler selection is deterministic over exact admitted task/lineage/source identities and a versioned selection policy
- every included context unit preserves authority/trust class, source identity/digest, subject scope, and inclusion reason; observed repository/external/runtime content is data, not instruction authority
- derived summaries/indexes are non-authoritative and eligible only when their complete provenance bindings are fresh for the exact attempt subject
- context budget is explicit across the effective platform-controlled model-visible input, including selected role/skill/command text, tool schemas, runtime-adapter instructions, and catalog/router disclosure
- required context is classified before budgeting and is never silently truncated, summarized, or replaced; inability to fit required effective context is a typed fail-closed `CONTEXT_BUDGET_EXCEEDED` outcome, not a runnable partial attempt
- optional context reduction is deterministic and records omitted/truncated source ranges and reasons
- platform-controlled runtime/adapter disclosure must match the identity/version/digest or reserved profile bound during compilation; no silent post-compilation catalog/instruction expansion
- full agent/skill/command catalogs are not injected by default; use compact deterministic routing descriptors and expand only selected surfaces within the admitted disclosure budget
- capability probe before side effects
- runtime/role/model/transport are independent configuration axes
- workspace/worktree/sandbox identity is bound before execution
- the authoritative Workspace Snapshot represents effective execution/release-relevant content; repository HEAD alone is insufficient when staged, unstaged, untracked, generated, submodule, nested-repository, or equivalent state can affect the result
- repository evidence compiled into context must remain compatible with the bound effective Workspace Snapshot; stale/mismatched evidence requires rejection or recompilation rather than silent continuation
- Attempt Packet binds the exact admitted workflow/task, Context Pack, Workspace Snapshot, runtime capability set, and execution envelope
- exact admitted command/tool envelope when deterministically enforceable
- host captures Runtime Observation plus exact output snapshot identity and binds both to the producing Attempt
- Result candidates reference the producing Attempt, Runtime Observation, and exact output snapshot rather than a mutable workspace label
- agent prose is diagnostic, not completion authority
- no silent runtime or transport fallback

## Portability
Core skills should use runtime-neutral action vocabulary with thin per-harness tool mapping.
