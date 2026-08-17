# Spec 07 — Governance, Safety & Release

## Goal
Constrain authority, permissions, retries, and external effects.

## Required behavior
- Human Authority approves material scope/policy changes
- deny-first where runtime permissions support it
- touch/new-file allowlists for bounded changes
- TTY or equivalent explicit human checkpoint for irreversible transitions when applicable
- fail-closed on stale/unknown/ambiguous contract state
- retry budgets and origin-classified circuit breaker
- conductor is read-only on product code
- release/push/merge/deploy are separately authorized external effects
- security/safety gates cannot be bypassed by convenience/auto flags
- upstream copied assets retain license/attribution

## Release
Verified readiness and release authorization are different states.
