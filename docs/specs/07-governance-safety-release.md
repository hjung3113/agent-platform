# Spec 07 — Governance, Safety & Release

## Goal
Constrain authority, permissions, retries, and external effects.

## Required behavior
- Human Authority approves material scope/policy changes
- deny-first where runtime permissions support it
- touch/new-file allowlists for bounded changes
- TTY or equivalent explicit human checkpoint for irreversible transitions when applicable
- fail-closed on stale/unknown/ambiguous/mismatched contract state
- retry budgets and origin-classified circuit breaker
- conductor is read-only on product code
- release/push/merge/deploy are separately authorized external effects
- security/safety gates cannot be bypassed by convenience/auto flags
- upstream copied assets retain license/attribution

## Release
Verified readiness and release authorization are different states.

Release Authorization binds:
- the exact verified snapshot identity
- the intended external effect
- the target repository/ref/environment identity
- the expected pre-release target state required to make the authorization valid

Immediately before the external effect, the release path revalidates those bindings and fails closed if the verified snapshot or target state changed.
Release Receipt records the actual released content and target identity and remains traceable to the Verification and Release Authorization that permitted it.
A verified snapshot cannot be substituted by a newer or equivalent-looking snapshot without a new applicable verification/authorization lineage.
