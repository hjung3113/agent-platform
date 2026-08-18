# Adoption Ledger

| Pattern | Decision | Destination |
|---|---|---|
| Model roles separate from Kernel/Host | ADOPT | `agents/` vs `src/kernel` |
| Human approval bound to durable decision | ADOPT | Spec 02/03/07 |
| Fresh context per bounded task | ADOPT | Spec 05, ADR-0005 |
| Goal-backward Plan Checker | ADOPT | role + policy-conditional gate in Spec 04 |
| Spec review then quality review | ADAPT | reviewer profiles, Spec 06 |
| Runtime/role/transport independent | ADOPT | adapters + Spec 05 |
| Skills canonical, commands thin | ADOPT | ADR-0003 |
| User/model invocation taxonomy | ADOPT | `agents/README.md` |
| Rule vs deterministic Hook distinction | ADAPT | `agents/README.md` + runtime adapters |
| Skill metadata/validation + behavior eval | ADAPT | `agents/skills/README.md`, Spec 08 |
| Namespace routers | ADAPT | command routing |
| Vertical-slice tickets | ADAPT | planning skill |
| Four-plane memory | ADAPT | authority/research/derived; operational state removed |
| Immutable Kernel-published transition lineage as run-state authority | ADOPT | ADR-0008 + Spec 03 |
| Mutable run-head/current-state as independent authority | REJECT AS AUTHORITY / ALLOW DERIVED | ADR-0008 |
| Cross-runtime canonical source + derived emit/drift control | ADOPT | Spec 08 + installation |
| Pinned upstream skill admission/update with regression eval | ADOPT | Spec 08 + vendor lock |
| Visual DAG editor | DEFER | Platform optional |
| Broad ECC skill catalog | REJECT DEFAULT / OPTIONAL PACK | vendor packs |
| Universal discuss-plan-execute-done phase machine | REJECT UNIVERSAL | retain as workflow profile |
| Arbitrary parallelism | DEFER | prove resource isolation first |
| Automatic model escalation on failure | REJECT | typed failure routing |
| Pane/heartbeat as completion | REJECT | liveness only |
