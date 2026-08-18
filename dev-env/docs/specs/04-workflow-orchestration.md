# Spec 04 — Workflow & Orchestration

## Goal
Select and advance bounded work without letting the model invent authority or execution order.

## Workflow revision contract
An admitted Workflow Revision is immutable and binds the complete orchestration semantics needed to derive work:

- stable task identities
- explicit dependency edges and dependency satisfaction conditions
- deterministic ordering/tie-break metadata
- task resource claims and access mode
- workflow/risk profile and admitted policy
- retry/repair/replan limits and escalation policy
- fan-in merge policy where multiple upstream results converge

Admission must reject unknown task references, self-dependencies, structural cycles, ambiguous dependency semantics, missing required policies, and incompatible graph references.

Whether independent Plan Check is required is determined by the workflow/risk policy through a deterministic predicate over the exact candidate revision and its admitted policy inputs. When required, the Plan Check must be independent from the authoring Planner and bound to the exact canonical Workflow Revision digest before Kernel admission. A simple workflow may omit the independent Plan Check only when that deterministic policy permits it. A passing Plan Check is semantic evidence only and never authorizes admission by itself. Kernel separately applies deterministic admission predicates and requires Human Authority approval for material scope/policy changes. Changed canonical workflow content cannot reuse a previously passing Plan Check.

## Deterministic eligibility and next action
Eligibility is a pure projection of:

1. the exact admitted Workflow Revision, and
2. the exact authoritative immutable transition lineage.

Derived caches, pane/chat prose, runtime exit status, unordered collection traversal, wall-clock arrival order, or model judgement cannot independently change eligibility.

For the same admitted revision and authoritative lineage:
- the eligible task set must be identical
- task ordering must be identical
- the selected next action must be identical

When multiple tasks are eligible, the Workflow Revision must provide a canonical deterministic ordering/tie-break rule. Unknown, ambiguous, stale, or reconciliation-required state fails closed rather than guessing eligibility.

## Dependency and fan-in semantics
A dependency is satisfied only by the explicit admitted completion condition for that edge; artifact existence or process completion alone is insufficient unless the contract says so.

Fan-in must declare:
- exact upstream inputs being merged
- merge strategy
- conflict behavior
- authority responsible for producing the merged candidate

A fan-in with conflicting inputs and no admitted conflict resolution policy is blocked. Implicit latest-wins, runtime-order-wins, or model-selected merge behavior is forbidden.

## Repair, retry, replan, and material decisions
These outcomes are distinct:

- **retry**: another attempt of the same admitted task contract
- **repair**: bounded corrective attempt that does not change the admitted workflow contract
- **replan**: proposes a successor Workflow Revision and therefore requires Kernel admission; the Plan Check requirement is reevaluated for that exact successor by the deterministic workflow/risk policy
- **material decision**: requires Human Authority before a dependent revision can be admitted
- **blocked**: no admitted transition is currently safe or permitted

Retry/repair/replan policy must be bounded and must define escalation when the same failure class repeats. Attempt identity is never reused. Replan creates a successor revision rather than mutating the admitted revision in place.

Repeated failure cannot loop indefinitely between retry, repair, and replan. Exhausted admitted budgets transition to the declared blocked/escalation outcome.

## Resource isolation and parallel execution
Path separation alone does not prove independence.

Tasks declare logical resource claims using stable resource identities and access modes such as read/write. Resources may represent paths as well as non-path state such as generated outputs, shared configuration, dependency locks, migration/database state, release targets, or other workflow-defined shared state.

Parallel execution is permitted only when the admitted resource claims prove that concurrent tasks cannot produce a conflicting effect. Unknown or unresolved resource overlap is serialized or blocked, never assumed safe.

A task/attempt in `reconciliation_required` blocks retry, successor execution, or conflicting parallel work for its affected resources until reconciliation produces an authoritative transition.

## Authority boundary
- Conductor and Architect/Planner may propose task splits, risk profile, repair, replan, and candidate Workflow Revisions.
- When policy requires independent Plan Check, Plan Checker judges the exact candidate revision before admission; its verdict is candidate semantic evidence, not publication/admission authority.
- Deterministic orchestration logic computes eligibility and transition candidates from admitted state; it has no independent publication authority.
- Human Authority approves material scope/policy changes before dependent admission.
- Kernel is the sole authority that admits Workflow Revisions and publishes authoritative run transitions.

No model role, runtime adapter, host process, or orchestration helper may bypass Kernel admission by directly publishing workflow state, and no `PASS` verdict can substitute for Kernel admission predicates.
