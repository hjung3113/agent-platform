# Authority and Publication Model

| Concern | Authority |
|---|---|
| Product goal/scope/material decision | Human Authority |
| Normative product behavior | Approved specs/contracts |
| Record admission/publication | Kernel |
| Authoritative operational run state | Immutable Kernel-published transition lineage |
| Repository/runtime observed facts | Harness Host/adapters |
| Workflow eligibility/transition calculation | Deterministic orchestration logic over admitted state |
| Workflow revision admission / run transition publication | Kernel |
| Context selection | deterministic Context Compiler |
| Implementation | Implementer (candidate output only) |
| Semantic review | Reviewer |
| Acceptance verdict proposal | Verifier |
| Terminal run result | Kernel Receipt |
| External release action | Human authorization + Release Captain |
| Derived summary/index/run-head | no authority |

Deterministic orchestration logic may calculate an eligible set or transition candidate, but calculation does not grant publication authority. Kernel validates and publishes the authoritative transition.

Conductor, Planner, Plan Checker, Implementer, Reviewer, Verifier, adapters, and runtime hosts cannot publish authoritative workflow/run state merely because they produced structurally valid output.
