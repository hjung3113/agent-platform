# Contract Catalog Draft

All authoritative records are published through one logical Kernel authority boundary.
Hosts, adapters, and tools may produce candidates or observations and may persist records on behalf of that boundary, but they are not independent authoritative publishers.
Canonical repository placement, schema validity, producer role, or verdict text does not confer authority.

## Contract-shape rule

A conceptual contract does **not** automatically require a standalone schema, table/file, service, or lifecycle. Prefer embedding adjacent data while preserving exact identity/digest/provenance bindings. Promote a concept to a standalone contract only when it needs an independent authority gate, asynchronous lifecycle, retention policy, reuse boundary, or external protocol surface.

## Minimum viable contract profile

The first vertical slice uses six standalone record families:

| Contract | Writer/Proposer | Authoritative Publisher | Required Binding |
|---|---|---|---|
| Request Contract | Human/Planner | Kernel | objective/scope/acceptance criteria and required human alignment |
| Workflow Revision | Planner | Kernel | admitted task graph/policy and exact Request lineage |
| Attempt Packet | Kernel/internal context assembly | Kernel | workflow/task, context-source bindings, capability envelope, exact Runtime Capability Profile identity, workspace snapshot identity |
| Result | Implementer candidate | Kernel after validation | Attempt, exact Runtime Capability Profile, output snapshot, runtime observation/provenance |
| Verification | independent Verifier candidate | Kernel after validation | exact Result/snapshot plus evidence and blocking findings |
| Receipt | Kernel | Kernel | exact accepted lineage and deterministic transition outcome; only `terminal` establishes terminal run state |

This is sufficient to prove authority, lineage, execution, independent verification, runtime-capability binding, stale-binding rejection, replay/idempotency, and terminal transition end-to-end.

## Deferred/conditional concepts

| Concept | Default MVP shape | Promote to standalone when... |
|---|---|---|
| Decision Proposal | ephemeral candidate | a resumable approval workflow needs it |
| Human Approval Record | conditional standalone | material scope/policy/external-effect approval is required |
| Decision Record | conditional standalone | a material decision must remain durable authority |
| Plan Check | omitted for simple workflow | policy requires independent semantic plan critique |
| Context Pack | embedded in Attempt Packet | context selection is reused, asynchronous, independently retained, or externally consumed |
| Role Capability Grant | embedded in Attempt Packet | grants have an independent lifecycle/revocation/protocol surface |
| Runtime Capability Profile | immutable Host/runtime observation embedded or content-addressed by Attempt | the profile is reused, independently retained/queried, or needs a protocol surface outside the Attempt lifecycle |
| Workspace Snapshot | embedded identity/binding | snapshots are independently stored/reused/retained |
| Runtime Observation | embedded in Result | observations stream independently or need separate retention/query semantics |
| Evidence | embedded/attached to Verification | evidence is asynchronous, shared, large, or independently retained |
| Review | folded into Verification | semantic quality review must be independently judged from acceptance verification |
| Finding | embedded in Verification | findings need lifecycle independent of the verification that created them |
| Release Authorization | omitted | a separately authorized external effect exists |
| Release Receipt | omitted | an external effect is executed and must be reconciled |

## Catalog invariants
- Candidate, admitted, and published authority states remain distinct even when they are not separately persisted.
- Kernel admission predicates are deterministic policy checks plus required human approvals; they never reduce to trusting an LLM verdict field.
- No role may both implement and final-verify the same snapshot.
- Embedded data must preserve the same exact subject/source identity, digest, provenance, and stale-binding rejection required of a standalone record.
- External-effect authorization is independent from verification readiness.
- Capability admission is against an exact Runtime Capability Profile; runtime family names, executable presence, or command acceptance are insufficient.
- `unsupported`, `unknown`, or `partial` cannot satisfy a required capability unless the Attempt Packet explicitly admits the named degraded mode.
- A Runtime Capability Profile identity change invalidates prior admission for execution under that changed runtime/configuration.

Additional schemas should be introduced only when the corresponding vertical slice or promotion condition is implemented.
Canonical digest representation and compatibility rules belong to the protocol specification and must be shared by every producer/validator.
