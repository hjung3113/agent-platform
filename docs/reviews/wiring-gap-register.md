# Wiring Gap Register

| Gap | Severity | Current treatment |
|---|---|---|
| Event authority vs mutable run-state authority unresolved | HIGH | explicit spike before protocol implementation |
| No implemented schema catalog yet | HIGH | contracts catalog first; schemas only with vertical slices |
| Plan Checker absent in earlier scaffold | CLOSED | added explicit role/spec gate |
| Kernel/Host previously mixed with agent roles | CLOSED | moved to `src/` |
| Context Compiler could become model-authored prompt glue | HIGH | deterministic subsystem + provenance contract |
| Reviewer vs Verifier overlap | MEDIUM | reviewer=quality/spec findings; verifier=acceptance verdict |
| Knowledge Curator might gain hidden decision authority | MEDIUM | proposal-only rule |
| Visual workflow editor could drift from kernel schema | MEDIUM | UI edits candidate contracts only |
| Upstream skill updates could silently change behavior | HIGH | pinned lock + eval gate required |
| Release authorization could be conflated with verified readiness | HIGH | Release Captain + separate policy |
| Parallel tasks may share logical resources despite path separation | HIGH | exact-path v1 only; richer resources deferred |
| Manual evidence can be vague/non-reproducible | MEDIUM | required scenario/observation/uncertainty metadata |

## Follow-up documents added after review

- `docs/architecture/versioning-and-migrations.md`
- `docs/architecture/security-and-data-boundaries.md`
- `docs/architecture/cancellation-and-recovery.md`
- `docs/operations/artifact-retention.md`
- `docs/research/role-clusters.md`

These reduce documentation gaps but do not close the run-state authority blocker.
