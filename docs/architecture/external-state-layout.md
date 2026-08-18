# External Runtime State Layout

Runtime state is not written into the development checkout.

Suggested root:

```text
~/.unified-agent-platform/
  runs/<run-id>/
    head.json                 # derived/checkpoint projection
    events/                   # immutable transitions
    artifacts/
    evidence/
    findings/
    receipts/
    staging/<actor-id>/
    workspaces/
  indexes/
  logs/
```

Target repositories may optionally contain small human-readable planning/decision documents,
but operational attempts/evidence/workspaces stay outside unless a workflow explicitly owns
repository-local review artifacts.
