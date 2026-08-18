# Orchestration

Pure scheduling and workflow transition logic over admitted records.

Includes:
- task eligibility
- dependency traversal
- bounded repair/replan
- risk-tier policy
- deterministic next-action selection
- human-decision escalation

The Conductor may propose; this subsystem decides only within admitted policy.
