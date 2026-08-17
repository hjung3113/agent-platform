# Security and Data Boundaries — Draft

## Trust boundaries
- Human direct approvals are trusted authority events only when bound to the exact requested decision/effect identity.
- Context dumps, repository files, issue bodies, external pages, model outputs, and runtime stdout are untrusted inputs unless resolved to an admitted/published identity.
- Adapters observe; they do not decide completion.
- Evidence may contain sensitive data and requires redaction policy before durable publication.
- Canonical repository placement or schema validity does not convert untrusted input into authority.

## Required controls
- path normalization and symlink-escape rejection
- deny-first runtime permissions when available
- explicit network/external-read capability
- secrets/credential patterns excluded from retained prompts/evidence by default
- no hidden runtime/model fallback
- role-specific capability envelopes enforced by the Host, not only prompt instructions
- authoritative publication/write capability reserved to Kernel-owned code paths
- candidate outputs isolated from authoritative stores/namespaces until admission
- external effects require a separate authorization bound to exact effect, target, and snapshot/subject identity
- capability configuration may narrow authority but cannot silently widen it

## Authorization records
- **Human Approval Record** — binds approver, material decision/effect, exact subject identity/digest, and approval scope.
- **Role Capability Grant** — admitted execution envelope defining the tools, write scope, network scope, and other side effects available to one attempt/role.
- **External Effect Authorization** — separately authorizes a concrete push/merge/deploy/release or equivalent irreversible effect; verification readiness alone cannot create it.

Authorization records must be explicit, scope-bounded, non-inferable from model prose, and rejected when stale, mismatched, or ambiguous.

## Open
A concrete redaction schema and secret-scanner policy must be selected before evidence retention is enabled.
