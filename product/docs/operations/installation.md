# Installation

Install managed platform surfaces through a manifest that records ownership.
Never overwrite project-owned files silently.
Support init, upgrade, adopt-existing, doctor, and uninstall.

Runtime-specific emitted artifacts are derived from runtime-neutral canonical roles/skills by default. Runtime-specific extensions must be explicit and versioned rather than silently forking canonical semantics.

Generated runtime files are managed/derived output, not a second source of truth. Direct edits are reported as drift; the operator may regenerate from canonical source or explicitly adopt the change back into the canonical source when ownership permits it.

Upgrade is transactional for managed files: validate ownership, pinned upstream provenance, required behavior/eval gates, and emitted drift before promotion, and retain a rollback target to the last admitted managed state.

## Verifier subprocess invocation

The one-task driver invokes `verification.stub_verifier_cli` with the active
Python interpreter (`sys.executable`) and JSON input on stdin. It derives the
platform source root from the installed `execution` package and prepends that
directory to the child process's `PYTHONPATH`; any inherited `PYTHONPATH`
entries are retained after it. The invocation does not depend on the caller's
working directory for package resolution.

The child emits one canonical Verification payload on stdout. A non-zero exit,
malformed stdout, or rejected payload raises `VerifierSubprocessError`; its
diagnostic includes bounded command, stdout, and stderr captures so bootstrap
and protocol failures remain actionable without allowing unbounded child output
into the caller's error path.
