# Agent Workflow Templates

Templates compose roles and skills; they do not become a second state machine.

Initial templates:
- `simple-change`: implementer -> verifier
- `standard-change`: architect/planner -> plan-checker -> implementer -> reviewer -> verifier
- `high-risk-change`: analyst -> architect -> plan-checker -> implementer -> spec-review -> quality-review -> verifier -> release-captain
- `investigation`: analyst -> reviewer/verifier -> report
- `migration`: discovery -> behavior contract -> design -> implementation -> adversarial review -> composite verification
- `documentation`: evidence extraction -> judge -> synthesis -> human confirm

Kernel policy decides which admitted template/revision is active.
