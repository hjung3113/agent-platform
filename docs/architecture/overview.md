# Architecture Overview

```text
Human
  -> Intake / Alignment
  -> approved Request Contract
  -> Planner/Architect proposal
  -> Plan Checker
  -> Kernel admission -> Workflow Revision
  -> Orchestrator selects eligible Task
  -> Context Compiler -> Attempt Packet
  -> Host capability/workspace admission
  -> Implementer runtime
  -> Runtime Observation + candidate Result
  -> Reviewer / Verifier
  -> Evidence + Review + Findings
  -> Kernel publication
  -> repair | replan | human decision | next task | receipt
  -> Release Captain for separately authorized external effects
```

Cross-cutting:
- Knowledge/decision authority
- Governance/policy
- Runtime/transport adapters
- Observability
- Derived memory
