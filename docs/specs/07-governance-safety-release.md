# Spec 07 — Governance, Safety & Release

## Goal
Constrain authority, permissions, retries, and external effects.

## Required behavior
- Human Authority approves material scope/policy changes
- deny-first where runtime permissions support it
- each attempt/role executes under an explicit admitted capability envelope
- authoritative publication/write capability is reserved to Kernel-owned code paths
- touch/new-file allowlists for bounded changes
- TTY or equivalent explicit human checkpoint for irreversible transitions when applicable
- fail-closed on stale/unknown/ambiguous contract or authorization state
- retry budgets and origin-classified circuit breaker
- conductor is read-only on product code and cannot widen its own capabilities
- release/push/merge/deploy are separately authorized external effects bound to exact effect, target, and verified subject/snapshot
- no role, verifier, adapter, runtime, or convenience/auto flag may infer or self-create external-effect authorization
- security/safety gates cannot be bypassed by convenience/auto flags
- upstream copied assets retain license/attribution

## Release
Verified readiness and release authorization are different states. A verification `PASS` cannot create a Release Authorization. Release Captain executes only effects explicitly permitted by a valid authorization record and the Host must reject stale, mismatched, ambiguous, or absent authorization.
