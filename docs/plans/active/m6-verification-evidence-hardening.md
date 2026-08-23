# M6 — Verification / Evidence Hardening Implementation Plan

Status: **Active** (hardened after `glm-5.3`-high adversarial review; see §13)
Tracker: Issue #5 ("Adversarial Review: Verification/Evidence Soundness")
Milestone: **M6 only**
Primary issue: #5

This document is the execution plan for M6 of the MVP roadmap. It hardens the M2 verification
contract (`VerificationV1`) so that terminal PASS depends on criterion-level admissible
evidence rather than verifier prose, without inventing a multi-attempt retry/replan
orchestration layer (M7), a real evidence-content-discovery mechanism, or additional runtimes
(M9).

Normative semantics remain owned by the specs/ADRs. If implementation reveals a contradiction
with those authorities, update the governing design first rather than encoding a local
interpretation here.

## 1. Sources and current baseline

Primary design sources:

- [`mvp-implementation-roadmap.md`](./mvp-implementation-roadmap.md) — M6 section
- [Issue #5](https://github.com/hjung3113/agent-platform/issues/5) — adversarial review
  objective/scope/questions, plus the
  [8 findings folded in from the M5 failure-mode ledger](https://github.com/hjung3113/agent-platform/issues/5#issuecomment-5386949987)
  (per-record applicability worked through in §1.1)
- [`docs/research/failure-mode-ledger.md`](../../research/failure-mode-ledger.md) — M5
  deliverable
- `m3-real-host-security-boundary.md` / `m4-deterministic-context-compiler.md` — style/
  precedent; M6 reuses their frozen-dataclass + `to_canonical_value()` + `.digest`/`.identity`
  property idiom and their fail-closed-before-construction exception pattern rather than
  inventing parallel machinery (§7)

Already implemented on `main` and reused unchanged in semantics unless a section below says
otherwise:

- `kernel/protocol_v1.py` — `VerificationV1`, `CoverageEntryV1`, `_COVERAGE_STATUSES` (`{
  SATISFIED, UNSATISFIED, BLOCKED, UNPROVEN }`, line 50), `_VERDICTS` (`{PASS, FAIL,
  BLOCKED}`, line 51), `_computed_verdict` (lines 525–535), `read_verification_v1` (lines
  538–589). **The four coverage states the roadmap's M6 bullet names already exist as a
  reader-enforced enum** — this predates M6, it is M2 contract shape. M6 does not add new
  states; it makes them mean something where it honestly can (§3, §4).
- `kernel/publish.py:351–381` — the `ContractKind.VERIFICATION.value` branch of
  `_kind_binding_rejection`: binds `VerificationV1.result` to the run's committed Result
  (`:352–358`), requires `coverage` to name every acceptance criterion from the bound Workflow
  Revision's task in order (`:359–365`), requires every `SATISFIED` entry's `evidence_digest`
  to equal the Result's `output_snapshot_digest` exactly (`:366–374`). **This is the only
  evidence class that exists today** — not a hierarchy of classes, one class (§5).
- `kernel/publish.py:376–380` — self-verification closed by exactly one literal string
  comparison, `value.verifier_identity == attempt_value.implementer_identity`. Any two
  different strings pass, including two strings typed by the same actor under the same
  runtime/session/profile. This is the target the roadmap's "self-verification through
  role/profile switching" exit bullet names — and, per §6 below, a target this single-runtime
  deployment cannot honestly close beyond what already exists.
- `kernel/publish.py:382–397` — Receipt admission requires the bound Verification's
  `verdict == "PASS"` exactly, trusting the reader-level recompute (`_computed_verdict`)
  rather than re-deriving PASS at Receipt time. §7 explains why M6 does not add a second
  recompute here — and, confirmed against the real code, Receipt publish already re-reads the
  committed Verification through `read_candidate` (`_committed_contract`, `publish.py:238–245`),
  which re-runs `read_verification_v1` and therefore re-computes `_computed_verdict`
  (`protocol_v1.py:564–569`) on every Receipt admission already, before this plan changes
  anything.
- `kernel/publish.py:213–245` (`_committed_contract`), `publish.py:62–69` (`_NEXT_KIND`, a
  strict single-successor map), `publish.py:616–620` (`RUN_ALREADY_TERMINAL` fires before any
  other admission check), and `publish()`'s own docstring (`:475–481`): the run shape is a
  **strict linear chain, exactly one committed record per contract kind** — Request → Workflow
  Revision → Attempt Packet → Result → Verification → Receipt. There is no retry, no second
  Attempt/Result/Verification within one run today (confirmed:
  `test_publish_m2.py:364` rejects a second Verification candidate as
  `INVALID_CANDIDATE_KIND_FOR_RUN_STATE`). `test_fail_or_blocked_verification_publishes_and_
  run_stays_open` means only that the run is not yet terminal (no Receipt committed). This
  constrains §4/§9 below and is why several roadmap bullets are honestly scoped down.
- `execution/host.py:276–282` and `kernel/runtime_capability.py` (`RuntimeCapabilityProfile`,
  `.identity` property, lines 160–164) — M3's real, reusable derived-identity pattern, already
  bound into `AttemptPacketV1.runtime_capability_profile_identity` and re-verified fail-closed
  at execute-time (`StaleRuntimeCapabilityProfileError`). `probe_opencode_profile` is
  deterministic over `(binary, config_paths)` (`opencode_adapter.py:248–259`) — this
  determinism is load-bearing for §6's scoping below, not just a convenience.
- `kernel/protocol_v1.py:122–133` — `RuntimeObservationV1` (`runtime_identity`,
  `output_snapshot_digest`) embedded in `ResultV1` (`:136–149`). The Host publishes
  `runtime_identity=profile.runtime` today (`host.py:404–405`), a short display string
  (`"opencode@{version}+{binary_digest}"`, `opencode_adapter.py:258`) — **a different, weaker
  identity than `profile.identity`** (the full profile content digest,
  `runtime_capability.py:160–164`), which is what `AttemptPacketV1` actually binds. This
  mismatch, and the producer-side change needed to close it, is §5.2's real subject. Note also
  (correcting an overstatement): `CoverageEntryV1.evidence_digest` (`:156`) is equally an
  evidence-bearing field — `RuntimeObservationV1` is not the *only* one, just the one whose
  binding to the admitted execution environment is unverified today.
- No `Finding` record type, no `ContractKind.FINDING`, exists anywhere.
  `VerificationV1.findings` is `tuple[str, ...]` — opaque prose strings, no id, no
  fingerprint, no lifecycle (§4).
- `verification/stub_verifier.py:31–40` — applies one boolean match uniformly to every
  criterion; never produces `BLOCKED`/`UNPROVEN`; docstring stale-references "M5" for the
  milestone that is now M6 (harmless comment staleness, fixed in passing per §10).

### 1.1 Ledger finding applicability (closes M5→M6 gate honestly, not just by citation)

The [8 M6-tagged ledger findings](https://github.com/hjung3113/agent-platform/issues/5#issuecomment-5386949987)
worked through against the actual gaps above, each closed-by / already-closed-by / or
deferred-with-reason — not silently skipped:

1. **Semantically-forged-but-digest-valid provenance reaching a Receipt.** Partially closed by
   this plan: §5.2 (environment binding) and §6 (recorded, shape-validated verifier-environment
   identity) narrow the surface where a Result/Verification could claim provenance the Kernel
   never checked. Not fully closed — full recursive cross-record consistency (the ledger
   source's actual fix) is bigger than M6's evidence-policy scope; the binding chain
   (`verify_binding` at every downstream publish, §1 above) already prevents the specific
   "Result from one session bound into a Receipt for another" shape, since every ref is
   checked against the run's own committed record, not just digest-well-formed.
2. **Dangling reference / stale concurrent write in durable-state checks.** Out of M6's scope —
   this is `kernel/lineage_store.py`'s lock/scan/fencing domain (M1), not the
   Verification/Evidence contract M6 owns. Already substantially covered by the existing
   run-lock + head re-derivation-by-scan design (`publish.py`'s docstring); M6 adds nothing
   here and should not, since it is a different layer's concern.
3. **Racy admission-proof idempotency / unsigned nonce evidence.** Directly relevant to §6:
   the ledger's warning about "unsigned, tamperable evidence accepted as proof of a distinct
   execution identity" is exactly HIGH 3's finding about the original draft's
   `verifier_runtime_capability_profile_identity` field — a free, unverified string is
   precisely this failure mode. Closed in this revision by retracting the hard distinctness
   gate (§6) and shape-validating the field instead, so it cannot silently masquerade as a
   stronger guarantee than it is.
4. **Fail-closed checks rejecting legitimate evidence under log rotation.** Out of scope — no
   log-rotation/telemetry-tailing analogue exists in this codebase's evidence model yet
   (this system has no rotating audit log at all); deferred until one exists.
5. **Absent/empty evidence accepted as fresh state.** Already closed today, worth stating
   explicitly rather than leaving implicit: `read_verification_v1` requires `evidence_digest`
   to be a valid content digest whenever `status == "SATISFIED"` (`protocol_v1.py:493–499`),
   and `publish.py:366–374` requires that digest to equal the Result's real
   `output_snapshot_digest` — absent or empty evidence cannot reach `SATISFIED` today. M6 adds
   the `evidence_class` pin (§5.1, HIGH 4 correction) so a *present but wrong-class* value is
   equally caught.
6. **Verification wired into tests but not the production path.** Directly addressed: §9's
   integration/regression plan and §12's exit gate require every new check to be exercised
   through the real `_kind_binding_rejection` publish boundary (the actual production path),
   not a standalone unit test of a check function in isolation.
7. **Mismatched-field false rejection masking a real integrity check.** This is exactly what
   BLOCKER 1 (§5.2, original draft) was — the review caught the plan about to ship the same
   defect class the ledger warned about. Closed by this revision's producer-side fix (§5.2,
   §10 step 0).
8. **Circular approval/receipt digests and ambiguous record ownership.** Not directly
   applicable to M6's scope — `VerificationV1`/`FindingV1` are read-only-embedded-in-published-
   record data with a single writer (whatever process calls `publish()`), not a separate
   approval-digest scheme with its own circular-reference risk. `_committed_contract`'s
   exactly-one-per-kind invariant (§1) already gives Verification/Receipt unambiguous
   single-writer ownership at the Kernel boundary.

## 2. M6 scope decision

M6 proves one thing: **a published Verification's PASS/FAIL/BLOCKED verdict is grounded in
real, checked evidence properties for the one-Attempt-per-run system that exists today** —
evidence class (pinned, checked), evidence-environment binding (real, checked), and a
non-PASS verdict that cannot omit its structured record of why. It does **not** prove: genuine
execution-environment independence between implementer and verifier (this deployment has one
runtime, one binary, one machine, and an in-process verifier — see §6 for why that check is
retracted, not merely softened), multi-attempt retry/reopen across runs (M7 owns cross-run
continuity), a second evidence-trust tier (no second evidence mechanism exists to build one
from), or per-criterion differentiated evidence policy (single global policy, same YAGNI shape
as M3's `M3_REQUIRED_CAPABILITIES = ()` and M4's single `CONTEXT_BUDGET_MAX`).

**Candidate real hardenings** (frozen for this milestone; every one is grounded in a specific,
cited gap in §1, verified against the real committed producer/consumer code, not invented):

1. Evidence-class identity on `CoverageEntryV1`, pinned and enforced on every `SATISFIED`
   entry — a versioned string with a real comparison rule, not a fabricated hierarchy (§5.1).
2. Environment binding between `ResultV1.observation.runtime_identity` and the Attempt's
   admitted `runtime_capability_profile_identity` — including the producer-side (`host.py`)
   change this requires (§5.2).
3. A real derived verifier-environment identity, recorded and shape-validated, **not gated for
   distinctness** — the honest scope given this deployment's real determinism (§6).
4. Structured `FindingV1` embedded in `VerificationV1.findings`, replacing the opaque string
   tuple, with identity/fingerprint/reader-enforced shape rules and an omission-closing publish
   rule (§4).
5. A dedicated known-wrong mutation/self-test suite exercising every real rejection path above
   (§9).

**Explicitly not built** (see §11 for the full carried-forward list): a `ContractKind.FINDING`
top-level record; cross-run Finding resolve/reopen/supersede triggering; a second
evidence-trust tier; per-criterion evidence policy differentiation; a hard gate on
verifier/implementer environment distinctness (retracted, §6); publish-boundary Finding
transition-table resolution (demoted to reader-level shape rules, §4.3); any retry/flaky-
evidence machinery beyond what the existing one-shot linear chain already guarantees
structurally (§8).

## 3. Coverage states: making the existing enum mean something, honestly

`_COVERAGE_STATUSES` already has all four states; `stub_verify` only ever emits
`SATISFIED`/`UNSATISFIED`. M6 does not change `_computed_verdict`'s priority order (all-
`SATISFIED`→`PASS`, any-`BLOCKED`→`BLOCKED`, else `FAIL` — `UNPROVEN` folds into the `FAIL`
branch, which is correct: an unproven criterion must not pass silently).

**Stated honestly (correcting the original draft's overclaim):** M6 does **not** give
`stub_verify` a real path to produce `BLOCKED`/`UNPROVEN` from a real execution outcome.
§5.2's environment check runs at **Result publish** and *rejects* the Result outright — a
Result that fails environment binding never becomes visible to any verifier, so "the
verifier distinguishes an environment-check-failure and reports UNPROVEN" describes a case
that cannot occur: by the time a Result reaches `stub_verify`, it has already passed
environment binding. `BLOCKED`/`UNPROVEN` remain producer-discretionary states this milestone,
exercised only by hand-authored test fixtures (§9) — same "named deferral, not silently
unused machinery" discipline as M4 §12. What M6 *does* deliver against this roadmap item: the
publish boundary now enforces environment failures as hard rejections upstream of
verification (§5.2), which is arguably the stronger guarantee — a bad environment binding
never reaches "unproven," it never reaches the verifier at all.

## 4. `FindingV1`: structured, embedded, not a new contract kind

### 4.1 Why embedded in `VerificationV1`, not a new `ContractKind.FINDING`

The roadmap's "durable Finding identity/fingerprint and explicit resolution/reopen/supersede
lineage" bullet reads naturally as "Finding is its own published record." It is not, in M6,
for a concrete structural reason verified against the real code: `_committed_contract`
(`publish.py:213–245`) raises if it ever finds zero or multiple committed records of one kind,
and `_NEXT_KIND` (`publish.py:62–69`) is a strict single-successor map — a `FINDING` kind
would need to sit at zero-or-more positions between Verification and Receipt, which is a
change to that single-successor invariant itself, not an additive schema change in the shape
M3/M4 both were. And since the real system has exactly one Verification per run
(`test_publish_m2.py:364` confirms a second is rejected), a separately-published Finding
record would carry all the machinery of independent publish timing while never actually being
published at a different time than its parent Verification. AGENTS.md rule 9 (YAGNI) and rule
11 (surgical) both point the same direction: embed.

```python
@dataclass(frozen=True)
class FindingV1:
    criterion: str                    # which acceptance criterion this finding is about
    fingerprint: str                  # content_digest({"criterion": ..., "description": ...})
    description: str
    state: str                        # one of _FINDING_STATES
    predecessor: RecordRef | None      # None in every real M6 path (§4.3)

    def to_canonical_value(self) -> dict[str, object]: ...
```

`_FINDING_STATES = frozenset({"OPEN", "RESOLVED", "REOPENED", "SUPERSEDED"})`.

`fingerprint` is `content_digest({"criterion": self.criterion, "description":
self.description})` — a stable identity for recognizing "the same" finding again later,
independent of which run or Verification record it happens to be embedded in. This is the
forward-compatible hook for M7: a later run's Verification could embed a `FindingV1` whose
`predecessor` is a `RecordRef` to the Verification record that contained the finding being
resolved, and whose `fingerprint` matches. **No code path constructs a non-`None` `predecessor`
in M6** — there is no second Verification in one run's lineage to resolve against, and
cross-run linkage is M7's run-continuity concept, which does not exist. `predecessor` is real,
typed, canonical-value-covered machinery exercised only by synthetic reader-shape test
fixtures (§9) — the same YAGNI-with-a-real-hook shape as M4's `OmissionRecord` (M4 §5.3).

`VerificationV1.findings: tuple[FindingV1, ...]` replaces `tuple[str, ...]`.

### 4.2 Omission-closing publish rule

Real, closeable gap: today nothing requires `findings` to be non-empty when `verdict !=
"PASS"`. A verifier could publish `verdict=FAIL` with `UNSATISFIED`/`BLOCKED` coverage entries
and `findings=()`, and nothing rejects it — the failure would leave no structured record. This
is the concrete, single-run-scoped, real form of the roadmap's "unresolved blocking Finding
cannot disappear by omission" exit bullet (the cross-run form — a *later* run silently omitting
a Finding a prior run raised — needs M7's run-continuity concept and is out of scope, §2).

New publish-boundary rule in `_kind_binding_rejection`'s `VERIFICATION` branch (§1's existing
checks, extended), all reported under `VERIFICATION_COVERAGE_MISMATCH` (same code already used
for the sibling checks in this branch — same defect class, not a new code):

- every coverage entry with `status != "SATISFIED"` must have exactly one embedded `FindingV1`
  with `criterion == entry.criterion` and `state == "OPEN"` (`predecessor is None`);
- **conversely** (closing the gap the review's MEDIUM 1 found in the original draft): every
  embedded `FindingV1`'s `criterion` must name a coverage entry whose `status != "SATISFIED"`
  — a Finding cannot be attached to a criterion the same Verification simultaneously claims is
  `SATISFIED`;
- `verdict == "PASS"` with any non-empty `findings` is rejected (existing reader-level rule,
  `protocol_v1.py:573–577`, now typed over `FindingV1` instead of `str`).

**Duplicate-criterion counting (LOW-severity gap closed):** `TaskV1.acceptance_criteria`
permits duplicate strings and `coverage` mirrors them one-for-one (`publish.py:360–365`), so
"exactly one Finding per non-`SATISFIED` entry" is ambiguous by existence-check alone when two
entries share criterion text. The rule is by **count**, not existence: the number of
`state == "OPEN"` Findings naming a given criterion text must equal the number of
non-`SATISFIED` coverage entries naming that same text.

### 4.3 What resolution/reopen/supersede actually is in M6

**Rescoped after review (HIGH 6 — the original draft assigned transition-table enforcement to
`read_verification_v1`, but a payload reader has no lineage access by this codebase's own
stated discipline — `read_verification_v1`'s docstring, `protocol_v1.py:543–547`, says
cross-record checks "belong to the publish boundary, not here," and `FindingV1` carries no
predecessor-*state* field for a reader to compare against anyway).** M6 builds exactly what a
reader can honestly enforce — **shape rules only**:

- `state` must be one of `_FINDING_STATES`;
- `state == "OPEN"` requires `predecessor is None`;
- `state in {"RESOLVED", "REOPENED", "SUPERSEDED"}` requires `predecessor is not None`.

The real state-**transition** table (`OPEN → RESOLVED`, `OPEN → REOPENED`,
`RESOLVED → REOPENED`, any state `→ SUPERSEDED`, terminal states rejecting further transition)
requires resolving `predecessor`'s `RecordRef` against committed lineage, locating the prior
Finding by `fingerprint`, and comparing its recorded state — genuine publish-boundary,
lineage-aware validation. No code path in M6 constructs a non-`None` predecessor to need this
(§4.1), so it is recorded here as a **named M7 design note**, not implemented: when cross-run
Finding continuity becomes real, the transition table above is the contract to enforce at the
publish boundary, keyed on `fingerprint`.

## 5. Evidence-class and environment requirements

### 5.1 Evidence class: a versioned identity hook with a real, enforced pin

`CoverageEntryV1` gains `evidence_class: str`, following the `name@revision` idiom M4 used for
`ContextPack.estimator` (`"byte_length_estimator@1"`, `context_compiler.py:138`) — a
digest-covered identity that lets a future real second class change the contract's meaning
without changing its shape. The only real value in M6 is
`"result_snapshot_digest_equality@1"` — pinned, no `"or equivalent"` hedge. Shape is enforced
at the reader using the existing `name@revision` validator already in this codebase
(`_require_versioned_identity`, `runtime_capability.py:25–29`), reused rather than
reinvented — not merely "required non-empty string," which the original draft specified and
which would let two producers spell the same class differently with nothing to catch it.

**The real enforcement (closing HIGH 4 — the original draft declared this exit bullet without
implementing it):** every `SATISFIED` coverage entry must have
`evidence_class == "result_snapshot_digest_equality@1"` exactly; reject
`VERIFICATION_COVERAGE_MISMATCH` otherwise. With exactly one real class in M6, this collapses
to "the one real class is required," which is the honest form of "weaker evidence cannot
satisfy a stronger required class" for a hierarchy of one — stated as such, not overclaimed as
comparison logic against classes that don't exist (§12).

### 5.2 Environment binding: a real producer-side fix, not just a new comparison

**Corrected after review (BLOCKER 1 — the original draft's comparison was unsatisfiable by any
real Result).** The real Host publishes `RuntimeObservationV1.runtime_identity =
profile.runtime` (`host.py:404–405`), a short display string
(`"opencode@{version}+{binary_digest}"`) — while `AttemptPacketV1` binds
`runtime_capability_profile_identity = profile.identity`, the full profile content digest.
These two strings are never equal by construction; every real Result and every existing
fixture (`test_publish_m2.py:100,123`; `golden-digests.json:11,15`; `test_replay.py:102`;
`test_fault_injection.py:111`) mismatches the same way. Comparing them directly, as originally
drafted, would reject every honest Result the system can produce — exactly ledger finding #7's
failure mode (§1.1).

**The real fix is a producer-side semantic change**, added to §10 as an explicit `host.py`
step: `host.execute()`'s Result construction changes to publish
`RuntimeObservationV1.runtime_identity = profile.identity` (the same full content digest
already bound into the Attempt) instead of `profile.runtime`. This makes the observation's
claimed runtime identity exactly the value the Attempt already admitted — the environment
binding then compares two values that are the *same identity by construction* when the
execution is honest, and disagree only when it is not. New publish-boundary check in
`_kind_binding_rejection`'s `RESULT` branch: `value.observation.runtime_identity ==
attempt_value.runtime_capability_profile_identity`; reject a new
`PublishRejectionCode.RESULT_ENVIRONMENT_BINDING_MISMATCH` if not.

This is a real, if narrow, blast-radius change: `host.py`'s Result construction,
`test_host.py:256`'s `startswith(f"opencode@{FAKE_VERSION}+")` assertion (which must change to
assert the digest-shaped identity instead), and every fixture enumerated above (§9, §10).

## 6. Verifier-environment identity: recorded, shape-validated, not gated for distinctness

**Retracted and re-scoped after review (BLOCKER 2 — the original draft's second
self-verification check was unsatisfiable by the honest path, not just imperfect).**
`probe_opencode_profile` is deterministic over `(binary, config_paths)`
(`opencode_adapter.py:248–259`). In the real driver, verification is an in-process function
call (`run_one_task.py:228–234`), not a separate runtime execution — probed with the same
binary and configs the Attempt used, the verifier's profile identity **equals** the Attempt's
`runtime_capability_profile_identity` with probability 1. A hard check rejecting equality
between these two values would reject every honest Verification this system can produce —
`run_one_task` could never publish a Verification at all, and the only way to satisfy the
check would be probing the verifier against a different config path chosen for no reason but
to manufacture distinctness — a polite fiction, not a real environment separation, and exactly
the kind of guarantee-misattribution M4 §13 HIGH 1 already established this document series
must not ship (also HIGH 3's finding, once the field is examined closely: a free, unverified
string cannot honestly claim "environment identity, not just its name, must differ" in the
first place — see ledger finding #3, §1.1).

**What M6 actually does:** `VerificationV1` gains `verifier_runtime_capability_profile_identity:
str` — the same real `RuntimeCapabilityProfile.identity` (M3, reused unchanged), probed at
verification time. It is **recorded and shape-validated only** — the reader requires it to be
a well-formed content digest (`sha256:agent-platform-json-v1:<64 hex>`, the same shape
`profile.identity` itself produces) — but the publish boundary does **not** compare it against
the Attempt's `runtime_capability_profile_identity` for distinctness. The existing
self-verification check (`publish.py:376–380`, `verifier_identity == implementer_identity`)
is **unchanged**, not extended.

**Stated as an explicit scope limit (§11), not a silent gap:** this deployment has exactly one
runtime, one binary, and one machine; environment-identity distinctness between implementer and
verifier is not a property it can exhibit honestly today. M6 records real derived-identity
evidence for a future genuinely-separate execution channel (a distinct process, container, or
remote runtime — M7/M9 territory) to gate on; it does not pretend to gate on it now. A future
milestone that introduces such a channel is the one that can honestly turn this into a hard
check.

## 7. Why Kernel PASS admissibility gets no new Receipt-time recompute

The roadmap's "deterministic Kernel PASS admissibility" bullet could naively read as "add a
recompute of `_computed_verdict(coverage)` at Receipt-publish time, in addition to the existing
`verdict == "PASS"` check." That would be the exact tautology M4 §6's HIGH-1 review finding
named for a different check — and, verified against the real code, it would also be **strictly
redundant with what already happens**: Receipt admission reads the committed Verification
through `_committed_contract` (`publish.py:238–245`), which calls `read_candidate`, which
re-runs `read_verification_v1` and therefore already re-computes `_computed_verdict`
(`protocol_v1.py:564–569`) on every single Receipt publish today, before this milestone changes
anything. A second explicit recompute would be checking the same recomputation a third time.
**Deterministic PASS admissibility is delivered by §§4–6's hardening at Verification-publish
time**, where the real teeth are: the omission-closing rule (§4.2), the pinned-evidence-class
rule (§5.1), and the environment-binding check (§5.2) all run *before* a Verification with
`verdict == "PASS"` can exist at all. Receipt admission's existing `verdict != "PASS"` check
is sufficient once what it trusts is actually hardened upstream.

## 8. Stale/flaky/retry evidence: already structurally guaranteed, not new machinery

Verified against the real code: `_NEXT_KIND` (`publish.py:62–69`) is a strict single-successor
map, `RUN_ALREADY_TERMINAL` (`publish.py:616–620`) fires before any other admission check, and
`verify_binding` runs at every downstream publish — there is provably no second
Attempt/Result/Verification within one run's lineage. The one-shot linear chain therefore
already guarantees, with zero new M6 code, that evidence bound to a non-current Attempt/Result
cannot satisfy any criterion for a later terminal Receipt. "Flaky" and "retry" evidence are not
expressible in the current one-Attempt-per-run model at all — they are M7's "retry/repair/
replan" territory, which does not exist yet. This bullet is satisfied for the system that
exists today by the existing binding chain; a dedicated staleness-detection subsystem now, with
no second Attempt/Result ever producible to exercise it against, would be unexercisable
machinery of exactly the kind AGENTS.md rule 9 warns against. Stated as an explicit scope limit
in §11, not silently dropped.

## 9. Test plan

### Protocol/reader (`product/tests/contracts/test_protocol_v1.py`, extended)

- `FindingV1` reader: exact-keys enforcement, `state` must be one of `_FINDING_STATES`,
  `fingerprint` must be a valid content digest matching `content_digest({"criterion":...,
  "description":...})` recomputed from the payload, and the `state`↔`predecessor` shape rules
  from §4.3 (OPEN requires `None`, the other three require non-`None`)
- `predecessor` shape: `None` accepted; a well-formed `RecordRef` accepted at the reader layer
  (payload-shape only — real lineage resolution is the M7 design note in §4.3)
- `evidence_class` on `CoverageEntryV1`: enforced `name@revision` shape via
  `_require_versioned_identity` (not "any non-empty string"); on every `SATISFIED` entry, must
  equal `"result_snapshot_digest_equality@1"` exactly or the candidate is rejected
  (§5.1 — publish-boundary, not reader-boundary, since it is a cross-field-with-status rule)
- `verifier_runtime_capability_profile_identity` shape: must be a well-formed content digest
  (§6) — no reader shape test existed for this field in the original draft; this closes that
  gap
- golden-digest fixtures regenerated for the new `VerificationV1` wire shape
  (`product/tests/fixtures/protocol/v1/verification.json`, `golden-digests.json`)
- schema-version dispatch: a `VERIFICATION` candidate declaring the new `schema_version=2`
  shape with a stale-shaped payload (e.g. old-format `findings` as bare strings) is rejected
  `MALFORMED_PAYLOAD`; a candidate correctly declaring `schema_version=1` in the **retained
  legacy shape** (§10 step 1) still parses — proving the bump is additive, not a silent
  history break — and a `schema_version=1` candidate carrying the *new* v2 fields is rejected
  `UNSUPPORTED_SCHEMA_VERSION` (the real code name, `protocol.py:72`, `:365–370` — not
  `UNKNOWN_SCHEMA_VERSION`, which appears nowhere in this codebase)
- **replay fixture (closing HIGH 2):** a run containing a committed `schema_version=1`
  Verification (constructed against the legacy shape) still replays cleanly after the v2 bump
  — proves the retained legacy reader keeps `replay.py`'s integrity check
  (`replay.py:97–99,155–160`) and `_committed_contract`'s re-parse both working against
  pre-M6 history

### Publish boundary (`product/tests/kernel/test_publish_m6.py`, new file — M3/M4's naming
precedent suggests a dedicated file per milestone rather than extending `test_publish_m2.py`
past its own milestone's scope)

- **Omission-closing, both directions (§4.2):** an `UNSATISFIED` coverage entry with
  `findings=()` is rejected; the same candidate with a correctly-shaped `FindingV1` publishes;
  **new (MEDIUM 1 fix)** a `FindingV1` naming a `SATISFIED` criterion in a non-PASS
  Verification is rejected; a Finding referencing a nonexistent criterion is rejected;
  `verdict == "PASS"` with non-empty `findings` is rejected; **new (LOW 1 fix)** duplicate
  acceptance criteria with matching per-criterion OPEN-Finding counts publish, mismatched
  counts reject
- **Pinned evidence class (§5.1, HIGH 4 fix):** a `SATISFIED` entry with
  `evidence_class != "result_snapshot_digest_equality@1"` is rejected
  `VERIFICATION_COVERAGE_MISMATCH`; the pinned value publishes
- **Environment binding (§5.2, BLOCKER 1 fix):** built against the corrected `host.py` producer
  — a `RESULT` candidate whose `observation.runtime_identity` (now `profile.identity`-shaped)
  disagrees with the bound Attempt's `runtime_capability_profile_identity` is rejected
  `RESULT_ENVIRONMENT_BINDING_MISMATCH`; the real Host's actual output (post-fix) publishes
  cleanly — this positive case is the fixture that would have caught BLOCKER 1 before it shipped
- **Verifier-environment identity (§6, BLOCKER 2 fix):** shape-only fixtures — malformed
  (non-digest-shaped) `verifier_runtime_capability_profile_identity` is rejected at the reader;
  a well-formed one, **even when it equals the Attempt's own** (the honest, expected outcome
  for this deployment), publishes — this is the fixture proving the retraction actually took,
  not just that the field exists
- Self-verification (`publish.py:376–380`, unchanged): `verifier_identity ==
  implementer_identity` still rejects — regression only, no new case, since §6 does not extend
  this check

### Verifier (`product/tests/verification/test_stub_verifier.py`, extended + `stub_verify`
updated per §10)

- every emitted coverage entry carries `evidence_class="result_snapshot_digest_equality@1"`
- every non-`SATISFIED` entry carries a well-formed embedded `FindingV1` satisfying §4.2's
  count rule from the producer side
- `verifier_runtime_capability_profile_identity` is threaded through and digest-shaped
- **no test asserts `stub_verify` ever produces `BLOCKED`/`UNPROVEN` from a real input** (§3 —
  stated honestly; those states stay hand-authored-fixture-only this milestone)

### Known-wrong mutation suite (`product/tests/kernel/test_verification_mutation.py`, new —
directly satisfies the roadmap's "known-wrong mutation/self-test suite" bullet)

Starting from one real, fully-published Request→Workflow Revision→Attempt→Result chain fixture
(built through the corrected `host.py` producer path), mutate exactly one field per case and
assert the specific rejection code, each alongside its untouched-sibling case still publishing:

- wrong `evidence_digest` (`VERIFICATION_COVERAGE_MISMATCH`)
- wrong `evidence_class` on a `SATISFIED` entry (`VERIFICATION_COVERAGE_MISMATCH`)
- `verifier_identity == implementer_identity` (`SELF_VERIFICATION_REJECTED`, unchanged check)
- `observation.runtime_identity` mismatched against the admitted profile identity
  (`RESULT_ENVIRONMENT_BINDING_MISMATCH`)
- malformed `verifier_runtime_capability_profile_identity` (reader `MALFORMED_PAYLOAD`)
- `UNSATISFIED`/`BLOCKED` coverage entry with no matching `FindingV1` (`VERIFICATION_COVERAGE_
  MISMATCH`)
- a `FindingV1` naming a `SATISFIED` criterion (`VERIFICATION_COVERAGE_MISMATCH`)
- `findings` non-empty while `verdict == "PASS"` (existing rule, now typed)

### Regression (blast radius stated in full — MEDIUM 3 fix; the original draft understated
this)

- `product/tests/kernel/test_publish_m2.py` — every `VERIFICATION` fixture (`dispatch_
  verification` and its callers) and every `RESULT` fixture touches the v2 wire shape and the
  corrected `runtime_identity` producer value; `test_self_verification_rejects` still passes
  unmodified in behavior
- `test_replay.py:102`, `test_fault_injection.py:111` — Result fixtures updated for the
  corrected `runtime_identity`
- `test_protocol_golden_m2.py:86–124,139–190`, `test_protocol_v1_m2.py` — golden and payload
  fixtures updated for the v2 `VerificationV1` shape
- `test_stub_verifier.py` — read-back/digest tests updated for the new fields
- **`test_m3_integration.py:109–132`, `test_m4_integration.py:102–149`** — these drive the real
  `run_one_task` → `host.execute()` → publish-Result path and therefore exercise the corrected
  `host.py` producer directly; they are **not** "stay green unchanged" (the original draft's
  claim) — they need the same `runtime_identity` producer fix and, once applied, prove the
  fix works end-to-end through the real driver, not just fixtures
- `test_m6_integration.py` (new, M3→M4 naming precedent) — full chain publish/replay through
  the real hardened checks with real evidence-class/environment data, not fixture shortcuts

## 10. Implementation order

0. **`execution/host.py` producer fix (BLOCKER 1 — new step, was missing entirely):** change
   Result construction to publish `RuntimeObservationV1.runtime_identity = profile.identity`
   instead of `profile.runtime`. Update `test_host.py:256`'s assertion accordingly. This must
   land *before* §5.2's publish-boundary check, since the check is unsatisfiable against the
   old producer value.
1. `kernel/protocol_v1.py` schema change: `FindingV1` + `_FINDING_STATES`; `CoverageEntryV1`
   gains `evidence_class` (shape-validated via `_require_versioned_identity`);
   `VerificationV1.findings` becomes `tuple[FindingV1, ...]`; `VerificationV1` gains
   `verifier_runtime_capability_profile_identity` (digest-shape validated). **Retain the v1
   reader (HIGH 2 fix):** register a second reader at `(ContractKind.VERIFICATION, 1, 1)`
   against a frozen legacy type (e.g. `_LegacyVerificationV1`, `findings: tuple[str, ...]`,
   no new fields) used only for replaying pre-M6 history — it does not run any of §4/§5/§6's
   new rules, since `publish()` is never invoked during replay, only re-parse-for-integrity
   (`replay.py:97–99,155–160`). Register the new shape at `(ContractKind.VERIFICATION, 1, 2)`
   under the existing `VerificationV1` name (call sites elsewhere in the codebase referring to
   `VerificationV1` mean the new shape going forward). **Fix the three version-stamping sites
   that assumed one blanket `SCHEMA_VERSION` (HIGH 2b):** `verification_v1_content_digest`
   (`protocol_v1.py:252–262`), `publish.py`'s `_candidate_content` bare-`ReaderOutcome` path
   (`publish.py:164–169`), and `run_one_task._as_candidate` (`run_one_task.py:73–89`) must all
   select `schema_version` per contract kind (a small `_SCHEMA_VERSION_BY_KIND` mapping,
   defaulting to `1`, with `VERIFICATION → 2`) rather than stamping the bare module constant.
2. `kernel/publish.py`: `RESULT_ENVIRONMENT_BINDING_MISMATCH` rejection code + `RESULT` branch
   check (§5.2, built against the step-0 producer fix); `VERIFICATION` branch gains the
   bidirectional omission-closing rule (§4.2) and the pinned-evidence-class rule (§5.1). No
   change to the self-verification check (§6 — retracted, not extended).
3. `verification/stub_verifier.py`: `evidence_class="result_snapshot_digest_equality@1"` on
   every entry, embedded `FindingV1` per non-`SATISFIED` entry (count-matched per §4.2),
   `verifier_runtime_capability_profile_identity` parameter threaded through from a real
   probed profile (reuse `probe_opencode_profile`, no new probing path, no distinctness
   claim). Fix the stale "Real evidence policy is M5" docstring reference to M6 in passing.
4. Golden-digest fixtures regenerated for the new `VerificationV1` v2 wire shape.
5. Test suite (§9): protocol-reader extensions (including the v1-retention replay fixture),
   `test_publish_m6.py`, `test_verification_mutation.py`, `stub_verifier` extensions, and the
   full regression list above (including `test_host.py`, `test_replay.py`,
   `test_fault_injection.py`, both M3/M4 integration suites).
6. `test_m6_integration.py` proving identical Kernel publish/replay/PASS/FAIL invariants
   through the real hardened checks, driven through the corrected `host.py` producer.

## 11. Explicit scope limits carried forward (not gaps to silently close here)

Per AGENTS.md rule 9 (YAGNI) and M3/M4's own explicit-deferrals precedent:

- **Genuine execution-environment independence between implementer and verifier** (§6): this
  deployment has one runtime, one binary, one machine, and an in-process verifier —
  `probe_opencode_profile`'s determinism means implementer and verifier profile identities
  collide with probability 1 under any honest same-config probe. M6 records a real,
  shape-validated verifier-environment identity as forward evidence; it does not gate on
  distinctness, because doing so would either reject every honest run or measure a decorative
  config-file choice rather than genuine separation. Revisit only when a genuinely separate
  execution channel (distinct process/container/remote runtime) exists to probe against — M7
  or M9 territory.
- **`ContractKind.FINDING` as an independently-published record** (§4.1): the strict linear
  chain has no slot for it without a lineage-shape change disproportionate to what
  one-Attempt-per-run needs.
- **Cross-run Finding resolve/reopen/supersede triggering, and the publish-boundary
  transition-table it needs** (§4.3): needs M7's run-continuity concept, which does not exist.
  Reader-level shape rules are real now; the lineage-aware transition table is a named M7
  design note, not implemented.
- **A second evidence-trust tier** (§5.1): exactly one real evidence class exists; the
  `evidence_class` field is a forward-compatible hook with a real pin, not a hierarchy.
- **Per-criterion evidence policy differentiation**: single global policy, same deferral shape
  as M3's per-task capability-requirement gap (still open, re-checked at every milestone
  boundary) and M4's single `CONTEXT_BUDGET_MAX`.
- **New stale/flaky/retry-detection machinery** (§8): the existing one-shot linear chain
  already structurally guarantees this bullet for the system that exists today.
- **Cross-record recursive provenance validation** (ledger finding #1, §1.1) and
  **concurrent-write/dangling-reference fencing** (ledger finding #2, §1.1): different layers'
  concerns (M1's lineage store, a future full-provenance-graph validator), not M6's
  Verification/Evidence contract.

## 12. M6 exit gate

Exit evidence restated at this deliverable's honest scope, corrected against the review's
findings rather than the original draft's declared-but-unimplemented claims:

- a `SATISFIED` coverage entry whose `evidence_class` differs from the one real, pinned class
  (`result_snapshot_digest_equality@1`) is rejected at publish — a real, enforced check (§5.1,
  HIGH 4 fix), not a declared-but-unenforced field
- a coverage entry lacking a valid `SATISFIED`-required evidence binding is `UNSATISFIED`/
  `UNPROVEN`/`BLOCKED` and blocks PASS — unchanged from M2; `UNPROVEN`/`BLOCKED` remain
  producer-discretionary and fixture-exercised only this milestone, stated honestly (§3)
- a Result whose claimed runtime identity disagrees with the Attempt's admitted execution
  environment is rejected before it can become evidence for any criterion (§5.2, built on the
  corrected `host.py` producer — this is the check that would have been unshippable without
  BLOCKER 1's fix)
- self-verification via the existing `verifier_identity`/`implementer_identity` string check
  is rejected, unchanged from M2; genuine environment-provenance independence beyond that is
  explicitly out of scope for this single-runtime deployment (§6, §11) — not claimed as closed
- an unresolved blocking Finding cannot disappear by omission **within one run's Verification
  publish**, in both directions (a non-SATISFIED criterion without a Finding, and a Finding
  attached to a SATISFIED criterion — §4.2) — the cross-run form is explicitly out of scope
  (§11) pending M7
- wrong evidence digest, wrong evidence class, wrong environment binding, malformed
  verifier-environment identity, and omitted/misattached Findings are all rejected by the
  known-wrong mutation suite (§9), each proven alongside its untouched-sibling case still
  publishing correctly through the real, corrected producer path

## 13. Adversarial review log

Reviewed by `glm-5.3` (effort `high`, via `opencode`) against issue #5's checklist (including
the 8 M6-tagged ledger findings), the roadmap's M6 section, M3/M4's plan + §13 review
precedent, and the actual M2–M5 code on `main` (`8452411`) — every code-level claim was
checked against the committed source, including exact line numbers. Verdict: 2 BLOCKER, 6
HIGH, 4 MEDIUM, 3 LOW. All 15 are addressed directly in the sections above (this document is
the post-hardening state):

- **BLOCKER 1** (§5.2's environment-binding check was unsatisfiable by every real Result — it
  compared `RuntimeObservationV1.runtime_identity` [Host emits `profile.runtime`, a short
  display string] against `AttemptPacketV1.runtime_capability_profile_identity` [`profile.
  identity`, the full content digest] — two differently-derived values that never agree by
  construction, verbatim ledger finding #7's failure mode). Every fixture and the real
  `host.py` path would have failed to publish any Result, killing the M2–M4 E2E surface.
  Fixed: §5.2 now specifies the required producer-side change (`host.py` emits
  `profile.identity`), added as implementation-order step 0, with the full fixture/citation
  blast radius enumerated in §9/§10.
- **BLOCKER 2** (§6's second self-verification check was unsatisfiable by the honest path —
  `probe_opencode_profile`'s determinism over `(binary, config_paths)` means an in-process
  verifier probed the same way as the Attempt collides with the Attempt's own profile identity
  with probability 1, so the check would reject every honest Verification and no run could
  ever terminate). Fixed: §6 retracts the distinctness gate entirely, records the field as
  shape-validated evidence only, and states the single-runtime deployment reality as an
  explicit scope limit (§11) rather than a guarantee the system cannot honestly provide.
- **HIGH 1** (§1's claim that all 8 ledger findings were "addressed by name" was false — none
  were named, and several sit inside M6's claimed territory). Fixed: new §1.1 works through
  every finding individually — closed-by, already-closed-by-existing-check-with-citation, or
  deferred-with-reason.
- **HIGH 2** (the schema-version bump as drafted would break `replay()` on every existing run
  with a v1 Verification, understated its own version-stamping blast radius across three call
  sites, and asserted a rejection code, `UNKNOWN_SCHEMA_VERSION`, that does not exist). Fixed:
  §10 step 1 now retains a legacy v1 reader for replay, enumerates all three version-stamping
  sites needing per-kind selection, corrects the code name to the real
  `UNSUPPORTED_SCHEMA_VERSION`, and §9 adds a replay-of-legacy-history fixture.
- **HIGH 3** (§6's original claim that the new field made independence "the environment
  identity itself, not just its name" was inverted — the field was a free, caller-asserted
  string with no shape or provenance check, so it duplicated `verifier_identity`'s exact trust
  model one field deeper). Fixed: folded into §6's retraction — the field is now explicitly
  described as recorded-and-shape-validated-only, with the honest guarantee stated, not the
  overclaimed one.
- **HIGH 4** (§12's "weaker evidence cannot satisfy a stronger class" exit bullet had no
  implementing mechanism — `evidence_class` was declared but never compared against anything).
  Fixed: §5.1 adds the real publish-boundary pin (`SATISFIED` requires the exact pinned class),
  with a §9 mutation fixture.
- **HIGH 5** (§3's claim that `stub_verify` would learn to distinguish an
  "environment-check-failure" as `UNPROVEN` was structurally impossible — §5.2's check runs at
  Result publish and rejects outright, so a failing case can never reach the verifier to be
  distinguished). Fixed: §3 now states honestly that `UNPROVEN`/`BLOCKED` remain
  producer-discretionary and fixture-only this milestone, and reframes the real delivered
  guarantee (environment failures rejected upstream, never reaching "unproven").
- **HIGH 6** (§4.3's transition-table enforcement was assigned to the payload reader, which
  this codebase's own documented discipline says has no lineage access, and no mechanism could
  actually produce the invalid-transition rejection §9 asserted). Fixed: §4.3 demotes to
  reader-level shape rules only (state ∈ `_FINDING_STATES`, state↔predecessor coupling) and
  records the real transition table as a named M7 design note rather than claiming it is
  enforced now.
- **MEDIUM 1** (§4.2's omission-closing rule was one-directional — a Finding attached to a
  `SATISFIED` criterion in a non-PASS Verification passed every stated check). Fixed: §4.2 adds
  the converse rule and a §9 fixture.
- **MEDIUM 2** (multiple §1 citations had wrong line numbers, though every underlying
  behavioral claim checked out). Fixed: all citations in this revision were re-verified against
  the real committed line numbers.
- **MEDIUM 3** (§9's regression blast radius was understated — several fixture sites and both
  M3/M4 integration suites, which drive the real producer path BLOCKER 1 touches, were claimed
  to "stay green unchanged"). Fixed: §9's regression section now enumerates the full site list
  and correctly states that the integration suites need the same producer fix, not that they
  are unaffected.
- **MEDIUM 4** (§9 specified `evidence_class` as "required non-empty string," contradicting
  §5.1's own claim that it follows the `name@revision` idiom this codebase already validates
  elsewhere). Fixed: §5.1/§9 now specify the real `_require_versioned_identity` shape check,
  reused rather than reinvented, plus the previously-missing shape check for
  `verifier_runtime_capability_profile_identity`.
- **LOW 1** (duplicate acceptance-criteria text made "one Finding per non-SATISFIED entry"
  ambiguous by existence-check alone). Fixed: §4.2 specifies count-based matching.
- **LOW 2** (§1 overstated `RuntimeObservationV1` as "the only evidence-bearing shape,"
  eliding `CoverageEntryV1.evidence_digest`). Fixed: wording corrected in §1.
- **LOW 3** (§6's "reused unchanged, no parallel probing mechanism invented" elided the
  relevant difference — same deterministic function, different call site and timing — which is
  exactly what makes the two identities collide). Folded into BLOCKER 2's fix — §6 now states
  the determinism explicitly as the reason the check is retracted.
