# Contract Catalog Draft

All authoritative contracts are published through one logical Kernel authority boundary.
Hosts, adapters, and tools may produce candidates or observations and may persist records on behalf of that boundary, but they are not independent authoritative publishers.

| Contract | Writer/Proposer | Authoritative Publisher | Authority / Required Binding |
|---|---|---|---|
| Request Contract | Intake/Planner | Kernel after human alignment | approved objective/scope/AC |
| Decision Proposal | Human/agent proposal | Kernel after human approval | none until approved |
| Decision Record | Human approval | Kernel | durable material decision |
| Workflow Revision | Planner/Conductor proposal | Kernel | admitted graph/policy; digest must equal passing Plan Check subject |
| Plan Check | Plan Checker candidate | Kernel after digest validation | pre-execution judgement bound to exact candidate digest |
| Context Pack | Context Compiler candidate | Kernel | immutable selection record bound to exact authoritative source identities/digests |
| Attempt Packet | Context Compiler candidate | Kernel | execution contract bound to workflow/task/context/workspace/runtime envelope |
| Workspace Snapshot | Host observation | Kernel | exact effective workspace/content identity used by downstream Result/Review/Verify/Release |
| Runtime Observation | Runtime adapter/Host observation | Kernel | observed runtime fact bound to Attempt and output snapshot |
| Result | Implementer candidate | Kernel after validation | candidate task result bound to Attempt, Observation, and output snapshot |
| Review | Reviewer candidate | Kernel after validation | semantic judgement over exact Result/snapshot |
| Evidence | Host/adapter/test tool observation | Kernel | observed fact bound to exact subject snapshot and execution context |
| Verification | Verifier candidate | Kernel after validation | acceptance verdict bound to exact Result/snapshot and evidence set |
| Finding | Reviewer/Verifier/Host candidate | Kernel | unresolved observation with immutable lineage |
| Release Authorization | Human/policy decision candidate | Kernel | authorized external effect bound to verified snapshot and expected target state |
| Release Receipt | Release executor observation | Kernel | actual released target/content identity bound to authorization |
| Receipt | Kernel | Kernel | terminal or checkpoint result over exact lineage |

Draft schemas should be introduced only when the corresponding vertical slice is implemented.
Canonical digest representation and compatibility rules belong to the protocol specification and must be shared by every producer/validator.
