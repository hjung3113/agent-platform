# Superpowers — obra/superpowers

Status: STRONG UPSTREAM SKILL CANDIDATE
License: MIT

Primary sources:
- README: https://github.com/obra/superpowers
- subagent-driven-development:
  https://github.com/obra/superpowers/blob/main/skills/subagent-driven-development/SKILL.md
- writing-skills:
  https://github.com/obra/superpowers/blob/main/skills/writing-skills/SKILL.md
- porting:
  https://github.com/obra/superpowers/blob/main/docs/porting-to-a-new-harness.md

High-value concepts:
- harness-agnostic skills + thin per-harness tool mapping
- brainstorming -> worktree -> plan -> execution -> review -> finish flow
- fresh subagent per task
- spec-compliance review before code-quality review
- TDD and systematic debugging disciplines
- verification-before-completion
- skill authoring tested like TDD using pressure scenarios/evals

Good direct-reuse candidates (subject to pinned revision and attribution):
- test-driven-development
- systematic-debugging
- verification-before-completion
- using-git-worktrees
- requesting-code-review / receiving-code-review
- finishing-a-development-branch
- writing-skills

Adapt rather than directly bind:
- subagent-driven-development orchestration; local Kernel/Attempt protocol should own dispatch/state.
