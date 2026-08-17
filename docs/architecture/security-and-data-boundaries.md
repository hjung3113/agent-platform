# Security and Data Boundaries — Draft

## Trust boundaries
- Human direct approvals are trusted authority events.
- Context dumps, repository files, issue bodies, external pages, model outputs, and runtime stdout are untrusted inputs.
- Adapters observe; they do not decide completion.
- Evidence may contain sensitive data and requires redaction policy before durable publication.

## Required controls
- path normalization and symlink-escape rejection
- deny-first runtime permissions when available
- explicit network/external-read capability
- secrets/credential patterns excluded from retained prompts/evidence by default
- no hidden runtime/model fallback
- role-specific write permissions
- external effects require separate authorization

## Open
A concrete redaction schema and secret-scanner policy must be selected before evidence retention is enabled.
