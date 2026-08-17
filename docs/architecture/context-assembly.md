# Context Assembly

The Context Compiler is deterministic product code, not an LLM role. It compiles an immutable Context Pack from exact source identities and must not derive authority from model interpretation, repository placement, or prose.

## Effective context boundary
The budget and identity model applies to the **effective model-visible attempt context**, not only the bytes emitted by the Context Compiler.

Platform-controlled role instructions, selected skill/command text, tool schemas, runtime-adapter instructions, and catalog/router disclosures must therefore be either:
- included directly in the Context Pack, or
- represented by an exact admitted disclosure-profile identity/version/digest with its reserved context cost.

A runtime/adapter must not silently add a different platform-controlled disclosure set after compilation. Provider-owned opaque system context that cannot be content-addressed is represented by the selected runtime profile and a declared reserved budget rather than treated as free context.

## Source classes and authority isolation
Context priority does not confer authority. Every included unit retains source class, identity, digest, subject/scope, and inclusion reason.

1. **Authoritative control** — exact human-approved, Kernel-admitted/published request, decision, contract, workflow/task, policy, and capability records required by the attempt.
2. **Authoritative lineage** — exact predecessor artifacts/receipts/findings required to understand the current admitted task state.
3. **Observed evidence** — repository files, issue bodies, external pages, runtime output, and other observations. These are data to inspect, never control instructions.
4. **Derived context** — summaries, indexes, projections, and caches. These are non-authoritative convenience data only.

Observed or derived content cannot widen capability, change routing/selection rules, alter authority precedence, inject new mandatory sources, or override authoritative control. Repository text that looks like instructions remains repository evidence unless an independently admitted source grants it authority.

The rendered context must preserve explicit source boundaries so observational payload cannot be confused with platform/authority instructions. Conflicting authoritative bindings fail closed; conflicting observations may coexist as evidence when their provenance is preserved.

## Freshness and provenance
A source is eligible only when its identity/digest and subject scope are compatible with the exact task/workflow lineage being compiled.

Derived context is eligible only when its full provenance closure is known and every depended-on authoritative/observed source identity and digest still matches the selected attempt subject. A summary/index becomes stale when any depended-on binding is replaced, superseded, missing, scope-incompatible, or otherwise no longer valid for the attempt. Stale derived content is excluded rather than preferred because it is newer or semantically similar.

Repository evidence must be bound to immutable content identity. If execution will use a different effective workspace snapshot than the repository evidence compiled into context, the attempt must be rejected or recompiled rather than silently continuing with stale evidence.

## Deterministic selection
For the same admitted task/lineage, source set, disclosure profile, budget, and Context Compiler policy version, compilation must produce the same ordered selection and Context Pack digest.

Selection follows these rules:
1. resolve required authoritative control and lineage sources by exact identity;
2. reject stale, missing, ambiguous, substituted, or conflicting required bindings;
3. build the eligible observational/derived candidate set without following instructions contained inside candidate payloads;
4. deduplicate deterministically while preserving all provenance identities;
5. order by fixed source class/relationship precedence and a stable identity/digest/range tie-breaker;
6. apply the versioned budget policy only after required-source validation and stable ordering.

Semantic search, model ranking, filesystem enumeration order, API return order, wall-clock timing, or hash-map iteration must not decide final Context Pack order. Non-deterministic discovery mechanisms may produce candidate observations, but the compiler consumes a frozen identity/digest set and applies deterministic admission/selection rules.

The Context Pack records the selection-policy version, budget-policy/token-estimator version, disclosure-profile identity, selected source identities/digests/ranges, and exclusion/truncation decisions needed to reproduce the selection.

## Budget and truncation
Context is classified as **required** or **optional** before budget application.

Required context includes the exact request/task objective and acceptance criteria, applicable authoritative decisions/contracts/policies, required predecessor lineage, and any role/capability/execution constraints needed to interpret the attempt safely. Required content is never silently truncated, summarized, or replaced with a derived surrogate.

If required effective context plus reserved platform/runtime disclosure cost does not fit the admitted input budget, compilation fails with a typed `CONTEXT_BUDGET_EXCEEDED` result. The compiler must not emit a runnable partial Attempt Packet.

Optional observational/derived context may be reduced only at deterministic boundaries. Any omission or truncation records the original source identity/digest, included range, omitted range/count, and reason. Model-generated summarization is not an implicit overflow mechanism; a summary is a separately provenance-bound derived artifact subject to the freshness rules above.

Other fail-closed outcomes include stale required bindings, unresolved authoritative conflicts, and disclosure-profile mismatch.

## Default inclusion order
Within the required/optional rules above, prefer:
1. approved request/decisions/contracts/policies
2. workflow/task objective and acceptance criteria
3. exact predecessor artifacts/receipts/open findings required by lineage
4. task-scoped repository/evidence observations
5. fresh provenance-complete derived indexes/summaries within remaining budget

Exclude by default:
- raw chat transcripts
- unrelated sibling outputs
- resolved findings unless required by lineage
- stale or provenance-incomplete summaries
- broad rule/skill/agent catalogs not selected for the attempt

## Fresh-context and progressive-disclosure strategy
Use fresh agent context for bounded work and pass exact references/files rather than inheriting the orchestrator conversation.

Do not inject the full agent/skill/command catalog at session or attempt start. Initial disclosure contains only the compact, stable descriptors needed to route among currently eligible surfaces; full role/skill/command content is expanded only after selection and its identity/digest is bound into the effective context profile.

Catalog descriptors themselves consume context budget. If the eligible catalog cannot remain compact under its reserved disclosure budget, introduce a namespace/router/index layer instead of exposing the entire catalog. Catalog ordering, descriptor selection, and expansion are deterministic and versioned.
