# Role Clusters — Detailed Source Evidence

This document answers "why does this role exist, and which surveyed source actually supports it?"

## 1. Conductor

**Role boundary:** read-only product-code orchestration; proposes decomposition/routing/replan,
reads canonical state, collects host-side evidence, never self-completes work.

Evidence:
- `hjung3113/feedbackops-workflow`
  - `toolkit/docs/agents/conductor-persona.md`
  - explicit read-only rule; state comes from `.review/*.json`, not pane scrollback;
    liveness is distinct from correctness; owns tier/task split and redispatch policy.
- `hjung3113/thin-agent-harness`
  - `docs/roles/orchestrator.md`, `docs/architecture.md`
  - chooses next eligible task and loop transition but does not gain Human Authority.
- `hjung3113/how-i-use-llm-agents`
  - `docs/20-workflows/harness-patterns.md`
  - operator orchestrator exists to remove repeated routing/state-management labor.

Why not merge with Implementer:
FeedbackOps explicitly treats conductor source edits as role bleed. Keeping it read-only prevents
the orchestrator from bypassing independent review by "just fixing" the code itself.

## 2. Analyst / Researcher

**Role boundary:** discover facts, uncertainty, dependencies, behavior, and evidence before decisions.

Evidence:
- `hjung3113/agent-migration-pipeline`
  - README, `docs/03-evidence-and-verification.md`
  - legacy discovery, behavior contract, evidence grades A-D/?, characterization captures.
- `hjung3113/env-setup`
  - README brownfield flow
  - Cluster -> Extract -> Judge -> Synthesis -> Confirm; evidence-gated doc creation.
- `gsd-build/get-shit-done`
  - phase/project researcher agents/workflows
  - planning starts with research when required.

Why not give decision authority:
Research may be incomplete or inferential. The migration repo explicitly separates confidence of
evidence from correctness and keeps unknowns as unknowns.

## 3. Architect / Planner

**Role boundary:** turn approved scope into seams, task graph, resource boundaries, and executable plan proposals.

Evidence:
- GSD `agents/gsd-planner.md`
  - goal-backward must-haves, dependency waves, bounded 2-3-task plans.
- Matt Pocock `to-spec` / `to-tickets`
  - deep test seams, vertical tracer-bullet slices, expand-contract exception for wide refactors.
- FeedbackOps conductor/architect split
  - architect gets intra-chunk autonomy; conductor owns cross-chunk/tier decisions.

Why Architect and Planner are one initial role:
Both operate before execution on the same approved scope. Split them only if real traces show
architecture and delivery planning need separate contexts/permissions.

## 4. Plan Checker

**Role boundary:** independent verification that the plan WILL achieve the goal before execution.

Evidence:
- GSD `agents/gsd-plan-checker.md`
  - goal-backward analysis, requirement coverage, task completeness, dependency graph,
    key-link/wiring checks, context compliance.
- GSD `docs/FEATURES.md`
  - plan checker loop up to bounded iterations; distinct from post-execution verifier.

Why it is not Reviewer:
A code reviewer evaluates produced output. The Plan Checker attacks missing work/wiring before code exists.
This was a concrete omission in the first scaffold.

## 5. Implementer

**Role boundary:** execute one admitted packet inside bounded resources and publish candidate result/artifacts.

Evidence:
- FeedbackOps implementation seat and ROUND-STATE/touch-boundary model.
- Superpowers `subagent-driven-development`
  - fresh subagent per task; narrowly constructed context.
- GSD fresh executor context per plan.

Why fresh context:
Both GSD and Superpowers treat inherited long-session context as a source of drift. The attempt should
receive compiled task context, not the conductor's entire history.

## 6. Reviewer

**Role boundary:** independent semantic/quality review over an exact output snapshot.

Evidence:
- FeedbackOps `ISSUE-N-REVIEW` lifecycle and visual reviewer persona.
- Superpowers `subagent-driven-development`
  - spec-compliance review first, code-quality review second.
- Matt Pocock `code-review`
  - reusable review discipline rather than workflow state owner.

Why profiles instead of role explosion:
Spec, quality, architecture, security, and visual review share publication semantics. They differ in
criteria/tooling, so they are reviewer profiles until permission/state differences justify separate roles.

## 7. Verifier

**Role boundary:** final acceptance judgement over declared criteria and evidence.

Evidence:
- `thin-agent-harness/docs/roles/verifier.md`, architecture authority flow.
- `agent-migration-pipeline/docs/03-evidence-and-verification.md`
  - composite judge, explicit expected sources, mutation self-test.
- GSD post-execution verifier
  - goal achievement, not task-completion claims.

Why distinct from Reviewer:
Reviewer findings can be advisory/quality-focused. Verifier owns the acceptance verdict proposal for
the exact snapshot; Kernel still owns terminal receipt publication.

## 8. Release Captain

**Role boundary:** separately authorized external effects after verified readiness.

Evidence:
- `orcaskills` Agent Workflow template: release decision after verifier.
- FeedbackOps release role and fresh REVIEW/VERIFY requirement.
- `how-i-use-llm-agents`: commit/push/PR/merge permissions treated separately.

Why separate from Verifier:
"Correct/ready" and "authorized to publish externally" are different decisions.

## 9. Knowledge Curator

**Role boundary:** propose documentation/index maintenance; no material decision authority.

Evidence:
- thin-agent-harness Memory Steward concepts.
- lifetimeworkflow derived-memory regeneration and human-owned constitution.
- env-setup evidence-gated documentation synthesis.

Why stripped of original authority:
The integrated design gives Kernel/Human Authority the publication/decision boundary. A model curator
may detect drift and propose fixes but cannot silently rewrite accepted history.

---

# Deterministic non-agent cluster

These are **not agent roles** despite earlier repositories sometimes naming them as roles:

- Kernel / publication authority
- Harness Host / runtime observation and workspace admission
- Context Compiler
- Scheduler / eligibility engine
- Contract Validator
- Evidence Normalizer

Primary evidence:
- `thin-agent-harness/docs/architecture.md`
- `opencode-orchestrated-agent-workflow/docs/design/file-protocol.md`
- `general-ai-harness/docs/design/THIN_MVP_GRILL.md`

Reason:
Their correctness must come from code/schema invariants, not persona compliance.
