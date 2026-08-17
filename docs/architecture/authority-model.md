# Authority and Publication Model

| Concern | Authority |
|---|---|
| Product goal/scope/material decision | Human Authority |
| Normative product behavior | Human-approved, Kernel-published spec/contract revision |
| Record admission/publication | Kernel |
| Authoritative operational run state | Immutable Kernel-published transition lineage |
| Repository/runtime observed facts | Harness Host/adapters as observations only |
| Workflow eligibility/transition calculation | Deterministic orchestration logic over admitted state |
| Workflow revision admission / run transition publication | Kernel |
| Context selection | deterministic Context Compiler over admitted source identities |
| Implementation | Implementer (candidate output only) |
| Semantic review | Reviewer (candidate judgement only) |
| Acceptance verdict proposal | Verifier (candidate judgement only) |
| Terminal run result | Kernel Receipt |
| External release action | Human authorization + Release Captain under admitted authorization |
| Derived summary/index/run-head | no authority |

## Authority invariants
- Repository location, filename, schema validity, producer role, or a `PASS` field never confers authority by itself.
- LLM outputs are candidate inputs to admission. An LLM verdict is never an admission predicate.
- A candidate becomes admissible only after deterministic Kernel policy checks and every required Human Authority gate.
- Only the Kernel may publish an admitted candidate as an authoritative record or advance authoritative workflow/run state.
- Adapters and the Harness Host may publish observed facts only within their observation authority; observations cannot become completion or policy decisions without Kernel admission.
- Verified readiness and authorization for an external effect are separate states.

Deterministic orchestration logic may calculate an eligible set or transition candidate, but calculation does not grant publication authority. Kernel validates and publishes the authoritative transition.

Conductor, Planner, Plan Checker, Implementer, Reviewer, Verifier, adapters, and runtime hosts cannot publish authoritative workflow/run state merely because they produced structurally valid output.
