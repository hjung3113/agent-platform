# Adapter Boundary

Adapter axes are independent:
- runtime: Codex / Claude Code / OpenCode / Roo
- transport: direct / Herdr / Orca / cmux
- tracker: GitHub / Linear / local files
- workspace: directory / git worktree / sandbox/container

No adapter may silently fall back to a different runtime, role, model, or transport.
Capability probing occurs before side effects.
