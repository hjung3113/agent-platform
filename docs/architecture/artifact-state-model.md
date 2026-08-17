# Artifact and Run-State Model

## Immutable lineage
Request, Decision, Workflow Revision, Context Pack, Attempt Packet, Runtime Observation,
Result, Review, Evidence, Finding, Receipt.

## Derived projections
- active decisions
- current run status
- eligible tasks
- open findings
- phase summaries
- dashboards

A projection may be cached but must cite exact immutable source identities/digests.

## Open design choice
Two strong source patterns conflict:
1. `thin-agent-harness`: append-only events are authoritative; replay derives current state.
2. `opencode-orchestrated-agent-workflow`: one atomically replaced `run.json` is authoritative,
   immutable artifacts surround it.

Draft direction: immutable transition lineage is authoritative, with an atomically replaced
run-head/projection only as a checkpoint/cache. Before implementation, run a crash-consistency
spike on Windows + Linux filesystems and record ADR.
