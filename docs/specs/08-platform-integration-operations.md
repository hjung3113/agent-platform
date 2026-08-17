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

## UI
Workflow UI may edit candidate workflow definitions and show projections; Kernel remains publication/state authority.
