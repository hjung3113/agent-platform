# Installation

Install managed platform surfaces through a manifest that records ownership.
Never overwrite project-owned files silently.
Support init, upgrade, adopt-existing, doctor, and uninstall.

Runtime-specific emitted artifacts are derived from runtime-neutral canonical roles/skills by default. Runtime-specific extensions must be explicit and versioned rather than silently forking canonical semantics.

Generated runtime files are managed/derived output, not a second source of truth. Direct edits are reported as drift; the operator may regenerate from canonical source or explicitly adopt the change back into the canonical source when ownership permits it.

Upgrade is transactional for managed files: validate ownership, pinned upstream provenance, required behavior/eval gates, and emitted drift before promotion, and retain a rollback target to the last admitted managed state.
