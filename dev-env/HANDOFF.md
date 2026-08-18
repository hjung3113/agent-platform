# Handoff

## Completed in this slice

- Integrated the fail-closed Attempt admission seam with the `RuntimeCapabilityProfile` primitive already on `main`.
- Removed the duplicate simplified capability model from the superseded PR #30 design.
- Admission now binds the exact runtime profile identity, rejects unsupported/partial/unknown required capabilities, and rejects runtime effective permissions that exceed the Attempt's admitted `PermissionEnvelope`.
- External effects require both an effective runtime grant and an exact authorization binding for ordered effects, target, target precondition, snapshot, and plan.
- Workspace containment, observed-context isolation, and fail-closed pre-retention redaction checks remain in the bounded seam.
- Durable authorization consumption and admission-to-use filesystem race closure are intentionally not claimed by this pure policy boundary.

## Validation

- `PYTHONPATH=src python -m unittest discover -s tests/contracts -p 'test_*.py' -v` — 20 passed.
- `PYTHONPATH=src python -m unittest discover -s tests/kernel -p 'test_*.py' -v` — 9 passed.
- `python -m compileall -q src tests` — passed.

## Next session — fixed scope

Follow Issue #34's milestone order. Implement **M0 — Minimum protocol foundation only** using [`docs/plans/active/m0-minimum-protocol-foundation.md`](docs/plans/active/m0-minimum-protocol-foundation.md) as the detailed implementation plan.

Required M0 scope:

1. Strict candidate/published protocol wire shapes without creating publication authority.
2. Exact `(contract_kind, protocol_version, schema_version)` reader dispatch; no latest-reader fallback.
3. Protocol-specific typed rejection results.
4. Exact `contract_kind + record_id + content_digest` Request binding primitive.
5. Minimal Request v1 and one-task Workflow Revision v1 only.
6. Strict-key parsing so forged publication metadata/unknown fields fail closed.
7. Canonical golden vectors and stale/substituted binding negative tests using the existing `src/kernel/canonical.py` implementation.
8. Existing contract/kernel regression suites remain green.

Do **not** implement M1 publication/replay or M2 E2E in the M0 slice.

## Deferred until the corresponding gate

### M1 — after M0 passes

- filesystem-backed append-only authoritative lineage outside checkout
- atomic Kernel admission + publication
- durable publication identity and idempotency
- stale-writer/predecessor/head fencing
- derived projection after commit
- deterministic replay/fault injection

### M2 — after M1 passes

- Attempt Packet / Result / Verification / terminal Receipt
- explicit stub Host boundary
- one-task protocol E2E

### Later milestones

- #7/#8 Host/runtime enforcement: actual process/network/secret isolation, adapter-reported effective profiles, drift-triggered re-admission, and admission-to-use path race closure.
- #5 verification/evidence soundness after authoritative lineage/snapshot bindings exist.
- #4 deterministic orchestration after replay/authoritative state is stable.
- #6 context compilation and #24 skill supply-chain after the core Kernel/runtime boundaries are executable.
- #9/#25 compatibility registry, historical cross-version rule provenance, retained-lineage replay, and reader/rule retirement reachability remain M7/real-cross-version-edge work except for M0's exact-reader rejection tests.
