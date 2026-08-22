# MVP Implementation Roadmap

Status: **Active**

This document is the implementation sequencing authority for the first executable agent-platform MVP. Normative semantics remain owned by the architecture, ADR, and spec documents; this roadmap decides **what to implement first, what to defer, and what evidence is required before advancing**.

Primary design anchors:

- [`docs/architecture/end-to-end-wiring.md`](../../architecture/end-to-end-wiring.md)
- [`docs/specs/03-contracts-protocol-state.md`](../../specs/03-contracts-protocol-state.md)
- [`docs/specs/04-workflow-orchestration.md`](../../specs/04-workflow-orchestration.md)
- [`docs/specs/05-runtime-execution.md`](../../specs/05-runtime-execution.md)
- [`docs/specs/06-review-verification-evidence.md`](../../specs/06-review-verification-evidence.md)
- [`docs/architecture/runtime-boundaries.md`](../../architecture/runtime-boundaries.md)
- [`docs/architecture/security-and-data-boundaries.md`](../../architecture/security-and-data-boundaries.md)
- [`docs/architecture/versioning-and-migrations.md`](../../architecture/versioning-and-migrations.md)

## 1. Strategy decision

Use a **big-picture-first, vertical-slice implementation strategy**.

The big picture is fixed only far enough to preserve authority boundaries, handoff invariants, milestone dependencies, and explicit deferrals. Implementation then proceeds milestone by milestone through the smallest end-to-end slice that can prove those invariants.

Do **not** implement Spec 01 through Spec 08 as independent horizontal completion projects. Most open adversarial issues attack the same handoff and authority seams from different angles, so horizontal spec completion would create unused abstractions before the first executable workflow exists.

The MVP target remains:

```text
Request
  -> Workflow Revision
  -> Attempt Packet
  -> Result
  -> Verification
  -> terminal Receipt
```

Scheduling, validation, context assembly, evidence normalization, and replay begin as deterministic Kernel-internal responsibilities. Harness Host remains a separate execution/security boundary. Additional services or standalone artifact families are introduced only when a concrete lifecycle, reuse, scaling, failure-domain, or security boundary requires them.

## 2. Current baseline

Already implemented on `main`:

- deterministic canonical JSON serialization and content digest primitives in `src/kernel/canonical.py`
- minimum `RuntimeCapabilityProfile`, permission envelope, capability status, and fail-closed required-capability admission primitives in `src/kernel/runtime_capability.py`
- focused contract tests for both primitives

Most `src/context`, `src/execution`, `src/orchestration`, `src/verification`, and related test directories are still scaffolding. The roadmap therefore treats the canonical/digest and runtime-capability work as existing foundations, not reasons to generalize those subsystems early.

## 3. Adversarial review of the implementation plan

The initial roadmap was reviewed from five failure-oriented perspectives.

### Lens A — dependency inversion and wrong implementation order

**Attack:** Implement all six standalone MVP contract families before any authoritative publication path exists.

**Finding: HIGH.** A contract-first horizontal PR can freeze speculative fields and lifecycle distinctions that have not yet been exercised. This recreates the over-engineering problem identified by Issue #10.

**Correction:** implement shared protocol envelope/version-reader primitives plus only the contracts needed by the current slice. Start with Request/Workflow Revision for Kernel publication; add Attempt/Result/Verification/Receipt when the one-task E2E slice reaches them. Contract fields are justified by an executable invariant or current handoff, not by future completeness.

### Lens B — false confidence from a mocked E2E

**Attack:** A stub Host makes `Request -> Receipt` pass, and the project treats runtime/security concerns as solved.

**Finding: HIGH.** A mocked E2E proves protocol wiring, lineage, and verification gates only. It cannot prove workspace containment, process/network enforcement, runtime drift handling, redaction, or real adapter behavior.

**Correction:** Milestone M2 explicitly has a narrow claim: **protocol E2E**. M3 is a mandatory separate Host/security gate before any real-runtime readiness claim. Test names and milestone evidence must state which boundary is real versus stubbed.

### Lens C — temporary authority bypass becoming permanent architecture

**Attack:** During incremental implementation, tests or adapters write authoritative-looking files directly because Kernel publication is not convenient yet.

**Finding: BLOCKER.** A temporary bypass would invalidate the central architecture rule and can silently become the de-facto state path.

**Correction:** no milestone may introduce a second authoritative writer, even temporarily. Producers create candidates/observations only. Authoritative publication and run-state advancement must go through one Kernel boundary from M1 onward. Test fixtures may construct historical authoritative records only through explicit replay/fixture helpers that cannot be used as production publication APIs.

### Lens D — premature generalization

**Attack:** Build generic DAG scheduling, fan-in, distributed state, multi-runtime parity, v2 migration, service boundaries, or release machinery before the one-task path is trustworthy.

**Finding: HIGH.** These features multiply state and failure combinations before the base invariants are executable.

**Correction:** enforce explicit expansion triggers. Linear one-task precedes DAG; one runtime precedes portability matrix; v1 reader dispatch precedes v2 migration; in-process deterministic modules precede services; no release subsystem exists for workflows without separately authorized external effects.

### Lens E — roadmap drift and ambiguous milestone completion

**Attack:** The roadmap becomes prose that different sessions interpret differently; work advances while required negative tests remain unfinished.

**Finding: HIGH.** Without entry/exit gates, implementation can skip hard failure paths and still appear complete.

**Correction:** every milestone below has explicit scope, non-goals, and exit evidence. The tracking issue points back to this document and uses the same ordered milestone checklist. A milestone is complete only when its exit evidence is attached to the tracking issue or its linked implementation issues/PRs. If implementation reveals a normative contradiction, update the relevant design/ADR first instead of encoding a local guess.

## 4. Cross-cutting implementation rules

These apply to every milestone.

1. **Reuse before invention.** Before substantive implementation, inspect the repository research/reference material and relevant proven upstream/user repositories described by `AGENTS.md`; adapt validated patterns while preserving this project's contracts and authority boundaries.
2. **YAGNI by default.** Do not create a service, plugin layer, repository abstraction, standalone record family, or configuration surface without a current executable need.
3. **Fail closed.** Unknown version, stale digest, ambiguous state, unsupported capability, unresolved resource conflict, missing required evidence, or unknown redaction status does not produce a runnable/success state.
4. **One writer boundary.** Models, adapters, Host, Context Compiler, Verifier, and orchestration helpers never publish authoritative run state directly.
5. **Exact bindings.** Every correctness-relevant handoff binds the exact subject/parent/source identity and digest required by the governing contract.
6. **Negative tests are milestone deliverables.** Happy-path tests alone never close a milestone.
7. **Determinism is observable.** Stable serialization, ordering, replay, eligibility, context selection, and policy decisions must have reproducible tests rather than prose claims.
8. **No silent fallback.** Runtime, transport, workspace, capability, evidence, context, or version substitution requires an explicit successor/admission path.
9. **Keep external effects separate.** Verification readiness never implies authorization to push, merge, deploy, publish, or perform another irreversible external effect.
10. **Reconcile concurrent work before implementation.** At milestone start, inspect merged/open PRs and related issues so overlapping implementation is reviewed and adapted rather than duplicated blindly.

## 5. Ordered milestones

### M0 — Minimum protocol foundation

**Goal:** establish only the protocol machinery required for a trustworthy first authoritative record.

**Implement:**

- minimum candidate/published record envelope required by Spec 03
- exact `(protocol_version, contract/schema_version) -> reader` dispatch with no latest-reader fallback
- typed validation/rejection results
- parent/source identity + digest binding primitives
- minimal Request and one-task Workflow Revision contract shapes
- golden vectors extending the existing canonical digest tests where needed

**Reuse:** existing `src/kernel/canonical.py`; do not replace it with a framework without a demonstrated gap.

**Non-goals:** all MVP contract families, compatibility registry for hypothetical v2, JSON-schema ecosystem, database store, generic workflow DAG.

**Exit evidence:**

- unknown/unsupported versions fail closed
- canonical digest golden vectors are stable
- malformed/stale parent bindings are rejected
- a schema-valid candidate still has no authoritative effect before Kernel publication

**Primary issues:** #1, #3, #9, #25.

---

### M1 — Kernel authoritative publication and replay spine

**Goal:** make immutable Kernel-published lineage the only operational authority.

**Implement:**

- concrete local append-only authoritative lineage store outside the managed checkout
- atomic admission + authoritative publication boundary
- Kernel-assigned durable publication identity
- stable logical idempotency identity
- expected-predecessor/sequence/head-digest fencing sufficient to reject stale/conflicting writers
- derived run-head/projection updated only after the authoritative commit point
- deterministic replay/reducer from authoritative lineage
- Request and Workflow Revision publication through this path
- fault-injection seams around commit/projection boundaries

Prefer a simple concrete filesystem-backed implementation first. Introduce a storage abstraction only when a second real backend or a testability boundary demonstrates the need.

**Non-goals:** distributed consensus, database-backed event store, leases across multiple machines, production HA.

**Exit evidence:**

- same idempotency key + same content returns the existing authoritative publication
- same idempotency key + conflicting content fails closed
- stale predecessor/conflicting successor fails closed
- crash/fault after authoritative commit but before projection update rebuilds the same projection
- projection loss/corruption cannot change authority
- no non-Kernel production path can publish authoritative run state

**Primary issues:** #1, #2, #3.

---

### M2 — One-task protocol E2E

**Goal:** prove the complete protocol path once before integrating a real runtime.

**Implement just in time:**

- deterministic one-task eligibility
- minimal Attempt Packet
- stub/fake Host execution boundary with explicit test identity
- Result bound to producing Attempt and exact output snapshot identity
- minimal Evidence/Verification representation embedded where practical
- independent Verifier execution identity
- deterministic Kernel verification-admissibility check
- terminal Receipt

The stub Host is intentionally not a security proof. Its purpose is to close the protocol and authority loop.

**Non-goals:** real model execution, context budgeting, network/process sandbox enforcement, DAG scheduling, release authorization for a no-external-effect workflow.

**Exit evidence:**

- `Request -> Workflow Revision -> Attempt -> Result -> Verification -> terminal Receipt` succeeds for one task
- Implementer self-verification is rejected
- stale/mismatched Result, snapshot, Evidence, source, or Runtime Capability Profile binding is rejected
- Verifier `PASS` with missing required evidence cannot create terminal success
- replay of the accepted lineage yields identical terminal state
- duplicate terminal publication does not create a duplicate fact
- no-external-effect workflow terminates without release machinery

**Primary issues:** #1, #3, #5, #10.

---

### M3 — Real Host/security boundary and first runtime adapter

**Goal:** replace the fake execution boundary with one enforceable runtime path without generalizing portability yet.

**Default first runtime:** OpenCode. Additional runtimes remain deferred until M9.

**Implement:**

- effective Workspace Snapshot identity including outcome-relevant tracked/staged/unstaged/untracked/generated/nested state as applicable
- resolved workspace containment and escape rejection
- bind exact Runtime Capability Profile to Attempt admission and execution
- effective permission-envelope comparison after native/default/inherited configuration is resolved
- deny-first filesystem/network/process/credential/external-effect behavior where the runtime can enforce it
- no silent runtime/transport/tool fallback
- Runtime Observation and exact output snapshot provenance
- pre-retention redaction/sensitivity gate sufficient for retained runtime output/evidence
- deterministic adapter conformance fixtures independent of model/network availability; live runtime smoke tests are supplemental

**Non-goals:** all runtimes, general plugin system, release automation, sophisticated secret-classification taxonomy.

**Exit evidence:**

- traversal/symlink/equivalent supported escape cases fail closed
- unsupported/partial/unknown required capability cannot execute unless an explicitly admitted degraded mode exists
- runtime/config/tool-mapping drift changes profile identity and invalidates stale admission
- inherited/default permissions cannot widen the admitted envelope
- runtime exit/stdout cannot directly establish completion
- retained canary secret fixtures do not persist raw secret material

**Primary issues:** #7, #8.

---

### M4 — Deterministic Context Compiler

**Goal:** compile only the exact authoritative/relevant context required for an Attempt without turning observed data into instruction authority.

**Implement:**

- structured Context Unit with trust/authority class, source identity/digest, scope, inclusion reason, required/optional class, and content/range
- deterministic ordering and deduplication
- frozen candidate identities for one compilation
- versioned selection policy and token/cost estimator identity
- provenance-closure freshness checks for derived context
- required/optional budget accounting across actual platform-controlled disclosure
- typed `CONTEXT_BUDGET_EXCEEDED`
- deterministic optional omission/truncation record
- runtime disclosure profile identity/reserved-cost binding

Start in-process. Do not create a Context service.

**Exit evidence:**

- shuffled filesystem/API/input order produces the same selected order and digest
- malicious repository/issue/external/runtime text cannot add capabilities, mandatory sources, approval, PASS, or policy
- stale derived context fails after any bound authoritative dependency changes
- undersized required-context budget produces no runnable Attempt
- disclosure drift after compilation rejects or recompiles rather than silently expanding context

**Primary issue:** #6, with security overlap in #8.

---

### M5 — Cross-project failure-mode ledger

**Goal:** mine sibling repositories' own git history/issues/PRs for concrete failure/regression/bug records — not design-pattern adoption, which `docs/research/adoption-ledger.md` already covers — and turn them into a ledger that feeds the next milestone's adversarial review instead of rediscovering the same mistakes from scratch.

**Method:**

1. scan git log/issues/PRs per repo for failure, regression, and bug records first (titles/commit messages/labels only)
2. for flagged items only, read the actual PR body/diff to extract root cause and the fix/improvement actually applied
3. record source repo + commit/PR reference, failure mode, their fix, applicability to agent-platform (module/future milestone), status

**Scope:**

Full failure-mode mining — `opencode-orchestrated-agent-workflow`, `agent-migration-pipeline`, `general-low-reasoning-agent-harness`, `thin-agent-harness`.

Applicability-only scan (conceptual repo, not a failure-mining target) — `meta-prompting-skill`: record current-project applicability only, not failure modes.

**Deliverable:** new `docs/research/failure-mode-ledger.md`, separate from `adoption-ledger.md`.

**Exit evidence:**

- each of the 4 mining-scope repos shows scan evidence (git log/issue/PR pass completed)
- meta-prompting-skill applicability note recorded
- findings folded into M6's adversarial review checklist before M6 design starts

**Primary issue:** #46.

---

### M6 — Verification hardening

**Goal:** make terminal PASS depend on criterion-level admissible evidence, not on verifier prose.

**Implement:**

- acceptance-criterion coverage states: `SATISFIED`, `UNSATISFIED`, `BLOCKED`, `UNPROVEN`
- evidence-class/trust/independence/environment requirements per criterion or policy
- deterministic Kernel PASS admissibility
- verifier execution-provenance independence
- durable Finding identity/fingerprint and explicit resolution/reopen/supersede lineage
- stale/flaky/retry evidence rules required by current evidence types
- known-wrong mutation/self-test suite

Keep Reviewer and Verifier as one independent Verifier responsibility unless policy later requires two enforceable judgements.

**Exit evidence:**

- weaker evidence cannot satisfy a stronger required evidence class
- missing/unproven required criterion blocks PASS
- self-verification through role/profile switching in the same execution identity is rejected
- unresolved blocking Finding cannot disappear by omission
- wrong/stale snapshot and intentionally wrong output fixtures are rejected

**Primary issue:** #5.

---

### M7 — Orchestration expansion

**Goal:** expand from the proven one-task state machine only as each additional orchestration behavior is needed.

**Expansion order:**

1. linear multiple tasks
2. DAG dependency validation and deterministic eligibility
3. logical Resource Claims with read/write conflict semantics
4. bounded retry
5. repair
6. replan successor revision
7. fan-in with explicit merge/conflict policy
8. reconciliation-required handling
9. proven-safe parallel execution

Do not implement a later step merely because Spec 04 names it; each expansion must have an executable scenario and negative tests.

**Exit evidence:**

- same admitted revision + lineage always yields identical eligible set/order/next action
- cycles, missing/self references, and ambiguous dependencies fail admission
- retry/repair/replan budgets terminate and cannot loop indefinitely
- changed Workflow Revision cannot reuse stale digest-bound plan evidence when policy requires a new check
- conflicting logical resources serialize/block even when filesystem paths differ
- unresolved fan-in/reconciliation cannot guess a successor

**Primary issue:** #4.

---

### M8 — Protocol compatibility and recovery conformance

**Goal:** prove that v1 history remains reproducible as the codebase evolves before a real v2 migration is required.

**Implement:**

- retained v1 schema/record golden fixtures
- previous-version replay fixtures
- directional compatibility registry only when a real cross-version edge exists
- immutable compatibility/migration rule identity on admitted cross-version edges
- reader/rule reachability checks before retirement
- supported-platform crash/recovery validation matrix for the chosen persistence mechanism

The reader-dispatch mechanism exists from M0; M8 hardens evolution behavior rather than inventing versioning late.

**Exit evidence:**

- retained v1 lineage replays identically under newer application/runtime/adapter code
- unknown future and unsupported known versions fail closed
- changing the current compatibility registry cannot reinterpret an already admitted historical edge
- required historical reader/rule cannot be retired while reachable lineage depends on it
- supported Windows/Linux crash/recovery tests preserve authoritative-lineage semantics

**Primary issues:** #2, #9, #25.

---

### M9 — Runtime portability and generated-runtime drift

**Goal:** prove the canonical runtime-neutral contracts preserve meaning across additional supported runtimes.

**Implement:**

- add Claude/Codex/Roo adapters one at a time after the first runtime contract is stable
- cross-runtime canonical-action conformance matrix
- deterministic canonical role/skill -> runtime-specific emit
- direct runtime-file drift detection
- explicit/versioned runtime-specific extensions
- runtime hook/rule identity in capability/drift control

**Exit evidence:**

- same canonical action has equivalent observable effect/failure/evidence semantics across declared supported runtimes
- runtime-specific unsupported semantics fail rather than degrade silently
- generated output from identical canonical inputs is deterministic
- direct runtime-file edits are detected as drift
- runtime hook/rule changes that affect behavior invalidate prior admission identity

**Primary issue:** #7.

---

### M10 — Managed skill supply chain and external-effect/release extensions

**Goal:** add operational distribution/update machinery only after the Kernel/Host/context/verification foundations can enforce it.

**Implement:**

- Issue #24 upstream skill revision/provenance/local-delta/eval gate
- rollback to previous admitted upstream revision
- runtime drift checks before promotion
- separately authorized external-effect path only for workflows that actually require push/merge/deploy/publish or equivalent effects
- exact effect/target/snapshot/precondition binding and release receipt where applicable

**Non-goals:** automatic promotion into managed projects or treating verification as release authorization.

**Exit evidence:**

- changed upstream content cannot promote without provenance + regression evidence
- failed update leaves previous admitted revision usable
- local modifications remain detectable
- external effect without exact matching authorization fails closed
- stale target/snapshot/effect authorization cannot be replayed or escalated

**Primary issues:** #8, #24.

## 6. Milestone dependency graph

```text
M0 protocol foundation
  -> M1 authoritative publication/replay
      -> M2 one-task protocol E2E
          -> M3 real Host + first runtime
              -> M4 deterministic context
                  -> M5 cross-project failure-mode ledger
                      -> M6 verification hardening
                          -> M7 orchestration expansion
                              -> M8 compatibility/recovery conformance
                                  -> M9 multi-runtime portability
                                      -> M10 supply-chain/release extensions
```

This is the default implementation order. A later milestone may receive research, fixtures, or design clarification early, but **production implementation that depends on an unproven earlier invariant does not bypass the gate**.

## 7. Per-milestone PR discipline

Each implementation milestone should be delivered as small coherent PRs, normally one invariant cluster per PR. A useful default is:

1. contract/pure deterministic primitive
2. authority/admission wiring
3. negative and replay/conformance tests
4. integration slice

Do not split merely to satisfy this template; split when reviewability or independent rollback improves.

Every PR should state:

- milestone and linked tracking issue
- exact invariant(s) added
- explicit non-goals
- tests proving failure as well as success
- reference implementation/research reused or adapted, with provenance where required
- any design contradiction discovered

## 8. Completion definition for the MVP roadmap

The roadmap is not complete because every speculative feature exists. It is complete when:

- the one-task path is authoritative, replayable, independently verified, and fail-closed
- a real Host/runtime path enforces the admitted execution envelope
- context and evidence are exact, fresh, bounded, and provenance-bound
- orchestration expansion that the product actually uses is deterministic and bounded
- retained protocol history remains replayable
- supported runtimes pass declared conformance gates
- external effects, when present, remain separately authorized
- no subsystem relies on prompt obedience for an invariant that the design requires to be machine-enforced

Anything beyond those needs requires a new executable scenario, issue, or ADR rather than being pulled forward speculatively.
