# Adoption Ledger

| Pattern | Decision | Destination |
|---|---|---|
| Model roles separate from Kernel/Host | ADOPT | `agents/` vs `src/kernel` |
| Human approval bound to durable decision | ADOPT | Spec 02/03/07 |
| Fresh context per bounded task | ADOPT | Spec 05, ADR-0005 |
| Goal-backward Plan Checker | ADOPT | role + Spec 04 |
| Spec review then quality review | ADAPT | reviewer profiles, Spec 06 |
| Runtime/role/transport independent | ADOPT | adapters + Spec 05 |
| Skills canonical, commands thin | ADOPT | ADR-0003 |
| User/model invocation taxonomy | ADOPT | `agents/README.md` |
| Namespace routers | ADAPT | command routing |
| Vertical-slice tickets | ADAPT | planning skill |
| Four-plane memory | ADAPT | authority/research/derived; operational state removed |
| Mutable run.json as sole authority | DEFER/CONFLICT | state-model spike |
| Event log as sole authority | DEFER/CONFLICT | state-model spike |
| Visual DAG editor | DEFER | Platform optional |
| Broad ECC skill catalog | REJECT DEFAULT / OPTIONAL PACK | vendor packs |
| Universal discuss-plan-execute-done phase machine | REJECT UNIVERSAL | retain as workflow profile |
| Arbitrary parallelism | DEFER | prove resource isolation first |
| Automatic model escalation on failure | REJECT | typed failure routing |
| Pane/heartbeat as completion | REJECT | liveness only |
