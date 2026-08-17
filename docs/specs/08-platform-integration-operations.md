# Spec 08 — Platform, Integration & Operations

## Goal
Install, adapt, inspect, recover, and optionally visualize the platform without changing core authority.

## Required behavior
- install/upgrade/uninstall/adopt with ownership-aware manifests
- runtime and transport capability diagnostics
- status/next/doctor/audit surfaces
- profile and skill-pack deployment
- WSL/Docker/local sandbox support
- optional Herdr/Orca/cmux transport adapters
- optional visual DAG editor as projection/editor, never run authority
- transactional upgrade/rollback for managed files
- cross-runtime skill sync with drift detection
- observability separates liveness from correctness

## Canonical runtime-neutral source
Runtime-specific role/skill/command surfaces are derived from runtime-neutral canonical sources by default. A runtime-specific extension is permitted only when the runtime exposes semantics that cannot be represented by the canonical action vocabulary; the extension must be explicit, versioned, capability-admitted, and must not redefine canonical contract meaning.

Generated runtime artifacts are derived deployment output, not independent authority. Direct edits to generated surfaces are detected as drift and must either be discarded/regenerated or explicitly adopted back into the canonical source through the ownership-aware adopt flow.

## Upstream skill admission and update
Vendored or imported upstream skills are admitted only with:
- exact upstream repository and revision plus content identity/digest
- license/attribution metadata
- recorded local destination and local delta/patch identity
- behavior/eval suite identity and last accepted result
- explicit update policy and rollback target

Import or update is a gated operation: review the upstream diff and local delta, run the applicable behavior/regression evals, validate emitted runtime drift, and only then promote the new pinned revision. Automatic upstream promotion into managed projects is forbidden. An update failure leaves the previously admitted revision usable.

## UI
Workflow UI may edit candidate workflow definitions and show projections; Kernel remains publication/state authority.
