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

Implement the **Minimum Viable Kernel authoritative publication vertical slice** spanning #1, #2, #3, and #25, under the YAGNI constraints from #10.

Required scope:

1. Kernel-only atomic admit/publish path for the MVP record families needed by one-task E2E.
2. Exact predecessor/parent/content-digest lineage checks at publication.
3. Stable idempotency identity: same key + same content returns the existing publication; same key + conflicting content fails closed.
4. Concrete stale-writer fencing/CAS based on expected authoritative predecessor/head identity.
5. Immutable authoritative transition lineage with derived head/projection that can be discarded and rebuilt.
6. Deterministic replay from retained lineage.
7. Golden/replay tests from #25 for digest stability, duplicate publication, stale/conflicting writers, unknown versions, and unsupported mixed-version edges.
8. One-task E2E skeleton: `Request -> Workflow Revision -> Attempt -> Result -> Verification -> terminal Receipt`, without implementing full orchestration or release machinery.

Do **not** expand the next slice into #4 orchestration, #5 full verification/evidence lifecycle, #6 Context Compiler, or #24 skill supply-chain except for the smallest interfaces strictly required by the Kernel vertical slice.

## Known follow-ups after the next slice

- #7/#8 Host/runtime enforcement: actual process/network/secret isolation, adapter-reported effective profiles, drift-triggered re-admission, and admission-to-use path race closure.
- #5 verification/evidence soundness after authoritative lineage/snapshot bindings exist.
- #4 deterministic orchestration after replay/authoritative state is stable.
- #6 context compilation and #24 skill supply-chain after the core Kernel/runtime boundaries are executable.
