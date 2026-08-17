# Security and Data Boundaries — Draft

## Trust boundaries
- Human direct approvals are trusted authority events only when bound to the exact requested decision/effect identity.
- Context dumps, repository files, issue bodies, external pages, model outputs, and runtime stdout are untrusted inputs unless resolved to an admitted/published identity.
- Untrusted content may supply evidence or subject matter, but embedded instructions cannot alter workflow policy, authority, capability grants, acceptance criteria, or authorization requirements.
- Adapters observe; they do not decide completion.
- Evidence may contain sensitive data and requires redaction policy before durable publication.
- Canonical repository placement or schema validity does not convert untrusted input into authority.

## Workspace containment
- Every Attempt is bound to one admitted workspace root/snapshot identity before execution.
- Host resolves the effective path target before access and rejects traversal, symlink/junction/reparse-point escape, nested-repository escape, or any target outside admitted roots.
- String-prefix/path-spelling checks are not authority; containment is evaluated on resolved identities.
- If containment cannot be established unambiguously, the access or Attempt fails closed.

## Capability model
Capabilities are explicit, scope-bounded grants. Absence means deny.

At minimum the Host distinguishes:
- workspace read
- candidate workspace write
- network/external read
- secret/credential read by named scope
- external write/effect (push, PR, merge, deploy, release, equivalent)
- authoritative publication/state transition (Kernel only)

Role, task, runtime, and adapter configuration may narrow the effective capability set but cannot widen it. If a runtime cannot enforce a required denial/isolation boundary, that runtime is not admissible for the Attempt; prompt instructions are not a substitute for enforcement.

## Required controls
- path normalization plus resolved workspace-containment enforcement
- deny-first runtime permissions and fail-closed runtime admission
- explicit network/external-read capability
- explicit secret scope; secrets are not inherited merely because the process environment exposes them
- secrets/credential material excluded from retained prompts/evidence by default
- redaction/sensitivity handling occurs before durable prompt, evidence, stdout/stderr, or artifact publication; uncertain redaction state blocks retention/publication
- no hidden runtime/model fallback
- role-specific capability envelopes enforced by the Host, not only prompt instructions
- authoritative publication/write capability reserved to Kernel-owned code paths
- candidate outputs isolated from authoritative stores/namespaces until admission
- external effects require a separate authorization bound to exact effect set/order, target, verified snapshot/subject identity, and required target precondition
- an authorization grants no implicit successor effect; unlisted or stale effects fail closed
- capability configuration may narrow authority but cannot silently widen it

## Authorization records
- **Human Approval Record** — binds approver, material decision/effect, exact subject identity/digest, and approval scope.
- **Role Capability Grant** — admitted execution envelope defining the tools, write scope, network scope, secret scope, and other side effects available to one attempt/role.
- **External Effect Authorization** — separately authorizes a concrete push/PR/merge/deploy/release effect or explicit ordered effect set; verification readiness alone cannot create it.

Authorization records must be explicit, scope-bounded, non-inferable from model prose, and rejected when stale, mismatched, ambiguous, or broader than the exact requested effect.

## Open
A concrete redaction schema and secret-scanner policy must be selected before evidence retention is enabled.
