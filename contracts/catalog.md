# Contract Catalog Draft

All authoritative contracts are published through one logical Kernel authority boundary.
Hosts, adapters, and tools may produce candidates or observations and may persist records on behalf of that boundary, but they are not independent authoritative publishers.
Canonical repository placement, schema validity, producer role, or verdict text does not confer authority.

| Contract | Writer/Proposer | Authoritative Publisher | Authority / Required Binding |
|---|---|---|---|
| Request Contract | Intake/Planner | Kernel after required human alignment | approved objective/scope/AC |
| Decision Proposal | Human/agent proposal | Kernel after human approval | none until approved |
| Human Approval Record | Human Authority | Kernel | approval bound to exact decision/effect subject and scope |
| Decision Record | Human approval | Kernel | durable material decision |
| Workflow Revision | Planner/Conductor proposal | Kernel after deterministic admission + required human gate | admitted graph/policy; digest must equal checked candidate subject |
| Plan Check | Plan Checker candidate | Kernel | semantic judgement bound to exact candidate digest; `PASS` is never an admission predicate by itself |
| Context Pack | Context Compiler candidate | Kernel | immutable selection record bound to exact admitted/published source identities/digests |
| Attempt Packet | Context Compiler candidate | Kernel | execution contract bound to workflow/task/context/workspace/runtime envelope, required capabilities, and admitted Runtime Capability Profile identity |
| Role Capability Grant | Policy/Kernel candidate | Kernel/Host | bounded execution capabilities for an exact role/attempt; cannot be widened by the role, adapter defaults, inherited runtime configuration, or native tool mapping |
| Runtime Capability Profile | Host/runtime adapter observation | Kernel | immutable observed runtime/adapter/configuration/tool-mapping identity plus semantic capability and effective-permission set used for admission |
| Workspace Snapshot | Host observation | Kernel | exact effective workspace/content identity used by downstream Result/Review/Verify/Release |
| Runtime Observation | Runtime adapter/Host observation | Kernel | observed runtime fact bound to Attempt, Runtime Capability Profile, and output snapshot; never completion authority |
| Result | Implementer candidate | Kernel after validation | candidate task result bound to Attempt, Observation, and output snapshot; does not itself advance workflow state |
| Review | Reviewer candidate | Kernel after validation | semantic judgement over exact Result/snapshot; not transition authority |
| Evidence | Host/adapter/test tool observation | Kernel | observed fact bound to exact subject snapshot and execution context |
| Verification | Verifier candidate | Kernel after validation | semantic acceptance judgement bound to exact Result/snapshot and evidence set; not transition authority |
| Finding | Reviewer/Verifier/Host candidate | Kernel | unresolved observation with immutable lineage |
| Release Authorization | Human/policy decision candidate | Kernel | separately authorized external effect bound to exact verified snapshot and expected target state |
| Release Receipt | Release executor observation | Kernel | actual released target/content identity bound to authorization |
| Receipt | Kernel | Kernel | typed `checkpoint` or `terminal` result over exact lineage after deterministic transition predicates; only `terminal` establishes terminal run state |

## Catalog invariants
- Candidate and admitted/published identities are distinct even when payloads are identical.
- Kernel admission predicates are deterministic policy checks plus required human approvals; they never reduce to trusting an LLM verdict field.
- External-effect authorization is independent from verification readiness.
- Capability admission is against an exact Runtime Capability Profile; runtime family names, executable presence, or command acceptance are insufficient.
- `unsupported`, `unknown`, or `partial` cannot satisfy a required capability unless the Attempt Packet explicitly admits the named degraded mode.
- A Runtime Capability Profile identity change invalidates prior admission for execution under that changed runtime/configuration.

Draft schemas should be introduced only when the corresponding vertical slice is implemented.
Canonical digest representation and compatibility rules belong to the protocol specification and must be shared by every producer/validator.
