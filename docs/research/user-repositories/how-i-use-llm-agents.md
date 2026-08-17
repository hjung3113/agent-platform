# how-i-use-llm-agents

Status: PRODUCT PRINCIPLES SOURCE

Evidence:
- `docs/20-workflows/harness-patterns.md`: choose the smallest harness by failure cost;
  single agent -> plan/execute/verify -> independent review -> worktree DAG ->
  evidence harness -> operator orchestrator.
- highlights role separation, observable outcomes, merge re-verification, receipt-based completion.

Adopt:
- complexity/risk-based escalation
- evidence-over-claims
- avoid agent-count as a goal
