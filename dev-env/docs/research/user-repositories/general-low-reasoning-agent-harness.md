# general-low-reasoning-agent-harness

Status: ADAPT

Evidence:
- `docs/ARCHITECTURE.md`: workflow-enforcement axis separated from deployment axis.
- `docs/WORKFLOW.md`: discuss -> plan -> execute -> done, TTY approval, stale approval,
  state/roadmap sync, check/doctor, pre-commit scope gate.
- README/docs: profiles, skill packs, OpenCode/Roo adapters, install/upgrade/adopt/uninstall.

Adopt:
- deployment vs workflow separation
- install/manifest ownership model
- diagnostics/status/doctor
- scope gate and stale approval concepts
- weak-model-friendly explicit workflow support

Modify:
- phase machine becomes one workflow template/policy, not the universal run state.
