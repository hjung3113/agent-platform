# GSD — gsd-build/get-shit-done

Status: ADAPT; selected agent concepts, not wholesale workflow ownership
License: MIT

Primary sources:
- Architecture: https://github.com/gsd-build/get-shit-done/blob/main/docs/ARCHITECTURE.md
- Features: https://github.com/gsd-build/get-shit-done/blob/main/docs/FEATURES.md
- Plan checker: https://github.com/gsd-build/get-shit-done/blob/main/agents/gsd-plan-checker.md
- Commands: https://github.com/gsd-build/get-shit-done/blob/main/docs/COMMANDS.md

High-value concepts:
- fresh context per spawned agent
- thin orchestrators that route and update state rather than do worker reasoning
- file-backed planning/state
- dependency waves
- goal-backward Plan Checker before execution
- goal-backward Verifier after execution
- namespace meta-skills/routers to cut eager listing cost
- project-specific agent skill injection
- explicit gate taxonomy
- UAT after automated verification

Adopt:
- Plan Checker role and goal-backward methodology
- fresh-context policy
- thin orchestrator constraint
- namespace routing
- task sizing/context budget discipline
- execution waves only after resource isolation support exists

Do not copy directly:
GSD prompts assume its `.planning/`, command naming, SDK, and artifact conventions.
Adapt principles to the local protocol instead of embedding a second workflow state machine.
