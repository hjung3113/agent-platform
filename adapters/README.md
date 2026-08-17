# Adapter Boundary

Adapter axes are independent:
- runtime: Codex / Claude Code / OpenCode / Roo
- transport: direct / Herdr / Orca / cmux
- tracker: GitHub / Linear / local files
- workspace: directory / git worktree / sandbox/container

No adapter may silently fall back to a different runtime, role, model, transport, workspace mode, permission mode, or canonical action.
Capability probing occurs before side effects and produces a Runtime Capability Profile bound to the Attempt Packet.

Runtime adapters are translators, not policy authorities. They may map canonical actions to native primitives only when the mapping preserves the action's observable effect, permission boundary, failure meaning, and evidence obligations.

Adapter defaults are part of the effective configuration. After defaults, inherited runtime configuration, aliases, and native tool permissions are resolved, the effective permission envelope must be equal to or narrower than the admitted envelope. Otherwise admission fails.

Unsupported, unknown, or partially supported required capabilities fail closed. Degradation is allowed only when the admitted Attempt Packet explicitly names that degraded mode; otherwise a different runtime/configuration requires a successor Attempt and independent capability admission.

Each runtime adapter must expose enough identity to detect semantic drift: runtime version, adapter version, effective configuration identity, tool/action mapping identity, and capability probe result. A changed profile invalidates prior capability admission even when the runtime family name is unchanged.
