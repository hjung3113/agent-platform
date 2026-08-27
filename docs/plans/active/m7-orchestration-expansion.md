# M7 — Orchestration Expansion (Slice 1: Linear Multiple Tasks) Implementation Plan

Status: **Reviewed** (pre-implementation adversarial review complete — §13; ready for
implementation dispatch)
Tracker: Issue #4 ("deterministic orchestration after replay/authoritative state is stable")
Milestone: **M7, slice 1 of N** — see §2 for why this plan covers only expansion-order step 1

This document is the execution plan for the first M7 slice. M6 (PR #48, merged) proved a
single-task Request → Workflow Revision → Attempt → Result → Verification → Receipt chain is
authoritative, replayable, and evidence-hardened. M7 exists to expand that proven one-task state
machine "only as each additional orchestration behavior is needed"
(`mvp-implementation-roadmap.md` M7 goal) through the roadmap's nine-step expansion order. This
plan implements **only step 1 — linear multiple tasks** — and explicitly defers steps 2–9 (§11).

Normative semantics remain owned by the specs/ADRs. If implementation reveals a contradiction
with those authorities, update the governing design first rather than encoding a local
interpretation here.

## 1. Sources and current baseline

Primary design sources:

- [`mvp-implementation-roadmap.md`](./mvp-implementation-roadmap.md) — M7 section (lines
  323–350): nine-step expansion order, explicit instruction not to implement a later step
  merely because Spec 04 names it, primary issue #4
- [`docs/specs/04-workflow-orchestration.md`](../../specs/04-workflow-orchestration.md) —
  normative Workflow Revision contract fields, deterministic eligibility rules, dependency/
  fan-in/repair/retry/replan definitions, resource isolation rules, authority boundary
- [`docs/adr/0009-reviewer-verifier-split-trigger.md`](../../adr/0009-reviewer-verifier-split-trigger.md)
  — Reviewer/Verifier split trigger and independence shape (§6 explains why this is deferred
  out of slice 1)
- [`HANDOFF.md`](../../../HANDOFF.md) — M6 completion state, M7 kickoff notes (per-task
  capability-requirement gap, M4's structurally-empty `lineage`/`observed` source classes)
- `m6-verification-evidence-hardening.md` — style/precedent; this plan reuses its
  sources-and-baseline-with-citations discipline and its scope-decision-before-design shape
  rather than inventing parallel machinery

Already implemented on `main`, verified against the real code (not the roadmap's general
vocabulary):

- `kernel/protocol_v1.py:128–139` (`WorkflowRevisionV1`) — **exactly one task per Workflow
  Revision.** The dataclass is `request: RecordRef; task: TaskV1` — a single object field, not
  a task array. `read_workflow_revision_v1`'s own docstring (`:541–545`) states this
  explicitly: "Exactly one task exists by construction: the schema has a single `task` object
  field, not a task array or dependency graph." There is no `TaskV1` field for dependency
  edges, ordering/tie-break metadata, resource claims, retry/repair/replan limits, or fan-in
  policy anywhere in this file. **Every Spec-04 Workflow Revision contract field beyond
  `request`/`task` is unimplemented** — M7 slice 1 is not extending existing multi-task
  machinery, it is building the first multi-task shape from zero.
- `kernel/publish.py:64–71` (`_NEXT_KIND`) — a **strict single-successor map** with exactly one
  entry per contract kind: `REQUEST → WORKFLOW_REVISION → ATTEMPT_PACKET → RESULT →
  VERIFICATION → RECEIPT`. `_committed_contract` (`:217–249`) raises `RuntimeError` if it ever
  finds zero or multiple committed records of one kind in a run — **one run holds at most one
  record of each kind, full stop.** This is the single biggest structural constraint slice 1
  must resolve (§4).
- `kernel/publish.py:668–672` — `RUN_ALREADY_TERMINAL` fires once a Receipt is committed, for
  any candidate that reaches that check — but the idempotency-key shortcut at `publish.py:657–
  661` runs first and returns the existing publication for a matching idempotency key + content
  digest before `RUN_ALREADY_TERMINAL` is ever evaluated (`publish.py:534–537`'s docstring
  states this exception explicitly). This ordering is load-bearing for §4.2/§8's crash-resume
  design: a re-invocation with the same derived idempotency key hits the shortcut, not the
  terminal rejection, for as long as the record it's re-publishing already exists identically.
- `kernel/publish.py:375` (VERIFICATION branch) reads `revision.task.acceptance_criteria`, and
  `execution/attempt.py:83–88` (`build_attempt_packet`) and `execution/host.py:297–299`
  (`execute()`'s M4 pre-spawn drift check) both read `revision.task.task_id`/
  `revision.task.to_canonical_value()` directly. All three are real, load-bearing reads of the
  single-task field §4.1 removes — not just the two binding-check sites (`publish.py:329–345`'s
  `ATTEMPT_PACKET` branch) originally scoped in an earlier draft of this plan. §4.4 now covers
  all four sites.
- `kernel/replay.py:169–183`'s fold is an `isinstance` chain over `RequestV1`,
  `WorkflowRevisionV1`, `AttemptPacketV1`, `ResultV1 | _LegacyResultV1`, `VerificationV1 |
  _LegacyVerificationV1…`, `ReceiptV1` — mirroring the M6 legacy-reader-retention pattern for
  `RESULT`/`VERIFICATION` (`replay.py:24–30` imports both legacy result/verification types).
  Retaining a `_LegacyWorkflowRevisionV1` reader at the protocol layer (§4.1) without a matching
  fold branch would make it parse-but-vanish at replay — this plan's replay design (§4.6, new)
  closes that the same way M6 closed it for Result/Verification.
- `kernel/lineage_store.py` (via `kernel/publish.py:33–38`'s imports: `HeadProjection`,
  `RunHandle`, `open_run`) — one run = one append-only directory, one lock, one head
  projection, re-derived by full directory scan on every publish (`publish.py:642–649`). This
  primitive is task-count-agnostic at the storage layer — it does not assume one task, only one
  linear sequence of records. This matters for §4's design choice.
- `execution/run_one_task.py:216–393` (`run_one_task`) — the only real driver, and its name is
  literal: it publishes Request → Workflow Revision → one Attempt → one Result → one
  Verification → (if PASS) one Receipt, in a straight line, with no loop over tasks anywhere in
  the function body.
- `execution/policy.py:1–34` — `M3_REQUIRED_CAPABILITIES` and `M3_ADMITTED_PERMISSIONS` are
  **one fixed global table**, imported unchanged by every Attempt regardless of task content.
  There is no per-task capability-requirement field on `TaskV1` or anywhere else. This is the
  gap `HANDOFF.md`'s "Explicit scope limits" section says "likely gets closed" by M7 — flagged
  as a live design question in §7, not assumed in scope.
- `kernel/runtime_capability.py` (grepped for `risk_tier`/`risk` — no matches) and
  `product/src/` overall (grepped for `plan.check`/`risk_tier` — no matches anywhere) —
  **no risk-tier computation and no Plan Check machinery exist in code at all.** Both are pure
  spec/ADR concepts today (`docs/specs/04-workflow-orchestration.md:19`, ADR-0009). This is
  decisive for §6.
- `docs/specs/06-review-verification-evidence.md:19–24` — the Reviewer/Verifier split
  normative text (mirrors ADR-0009 verbatim: per-Task deterministic risk-tier predicate,
  computed by Kernel at admission time, reusing Plan Check's risk-tier computation at an
  independent threshold; parallel independent blind identities when split; Reviewer findings
  are blocking on equal footing with Verifier findings via the same lineage/closure rules M6
  built).
- `product/tests/kernel/test_m6_integration.py:1–35` — the current real integration-test shape:
  one `RequestV1`, one `TaskV1`, driven through `run_one_task`, replayed via `kernel.replay`.
  Slice 1 must not break this fixture's meaning (a single-task Workflow Revision must remain a
  valid, first-class shape — not a special case bolted onto a new multi-task-only schema).

## 2. M7 slice 1 scope decision

**Why slice 1 covers only expansion-order step 1 (linear multiple tasks), not steps 1–3 or
more:** the roadmap explicitly warns "do not implement a later step merely because Spec 04
names it" and requires "each expansion must have an executable scenario and negative tests"
(roadmap §5, M7 section). §1 above establishes that **even step 1 alone is not incremental** —
it requires changing the run's per-kind-cardinality invariant (`_NEXT_KIND`,
`_committed_contract`), the Workflow Revision contract shape, and the driver's control flow.
Layering step 2 (DAG dependency validation) or step 3 (resource claims) onto an unproven
multi-task run shape in the same slice would repeat exactly the mistake Lens D of the
roadmap's own adversarial review warned against (§3, "premature generalization" —
"multiply state and failure combinations before the base invariants are executable"). A
linear (strictly sequential, no fan-out, no explicit dependency edges beyond "comes after the
previous task") multi-task run is the smallest real step that exercises the cardinality change
this milestone must prove, with its own executable scenario and negative tests, matching M6's
own "prove one thing" scope-decision discipline (`m6-verification-evidence-hardening.md` §2).

**Slice 1 proves:** a single Workflow Revision can admit an ordered sequence of N ≥ 1 tasks;
the Kernel deterministically derives which task is eligible next from the admitted revision and
committed lineage alone; each task gets its own real Attempt/Result/Verification cycle with the
same M3–M6 evidence/environment/execution-identity guarantees already proven for one task; the
run reaches a terminal state only after every task's Verification is `PASS`; and a Verification
`FAIL`/`BLOCKED` for any task blocks the run without silently skipping ahead. It does **not**
prove: branching dependency graphs (step 2), resource-claim conflict detection (step 3), retry/
repair/replan (steps 4–6), fan-in (step 7), reconciliation (step 8), or concurrent execution of
independent tasks (step 9) — all named explicitly in §11, not silently dropped.

**Explicitly not built in slice 1** (full list in §11): dependency-edge contract fields beyond
strict sequence order; resource claims; any retry/repair/replan machinery; parallel task
execution; ADR-0009's Reviewer/Verifier split (§6); a per-task capability-requirement policy
mechanism (§7); a `Workflow Revision`-level fan-in merge policy field (nothing to merge with
strictly linear tasks).

## 3. Structural choice: Option A, user-confirmed

Before §4's design was finalized, one structural choice needed a decision, because it changes
the shape of every section below and there was a real trade-off, not an obviously-correct
answer. **The user selected Option A** in review; this section is retained (rather than deleted)
so the trade-off and the road not taken stay visible to a future reader, per this plan's own
citation discipline.

**Option A — one run stays one task; a new outer grouping record sequences per-task runs.**
Keep `kernel/lineage_store.py`'s run primitive, `_NEXT_KIND`, and `_committed_contract`'s
one-record-per-kind invariant completely unchanged (zero risk to M1–M6's proven invariants).
Add a new outer contract (e.g. `WorkflowRunV1`) that is not itself a `kernel/lineage_store.py`
run — it is a Kernel-computed *projection* over an ordered set of existing one-task runs, each
still Request → Workflow Revision → Attempt → Result → Verification → Receipt exactly as today,
with a shared parent `WorkflowRevisionV1` binding all of them. Eligibility becomes "which
per-task run has no committed Receipt yet, in admitted order." This reuses M1's storage/locking/
replay primitive completely unchanged — least invasive, most YAGNI-aligned — but "the run" as a
unit of atomic authoritative history no longer corresponds to "the workflow," which every
current test and integration fixture assumes are the same thing.

**Option B — one run becomes one multi-task workflow; per-kind cardinality becomes per-
`(kind, task_id)`.** Change `_NEXT_KIND`/`_committed_contract` to key on `(ContractKind,
task_id)` instead of `ContractKind` alone, so one run holds N Attempt/Result/Verification/
Receipt cycles, one set per task, inside one lineage/lock/head-projection. This keeps "the run"
and "the workflow" as the same unit (arguably closer to Spec 04's framing of Workflow Revision
as the top-level authority boundary), but touches `_NEXT_KIND`, `_committed_contract`,
`_kind_binding_rejection`'s per-kind branches, and the head-projection's "current head kind"
concept everywhere they assume a total order over kinds alone — a substantially larger blast
radius across `kernel/publish.py`.

This plan is written **on Option A** (§4–§10 below): the smaller, more reversible change,
directly following AGENTS.md rule 1 (reuse before invention) — M1's run primitive already does
everything Option A needs, unmodified.

## 4. Design: `WorkflowRevisionV1` becomes a task sequence; per-task runs stay unchanged

### 4.1 Contract shape change

`kernel/protocol_v1.py:128–139`'s `WorkflowRevisionV1` changes from a single `task: TaskV1`
field to `tasks: tuple[TaskV1, ...]` (non-empty). `_require_string_sequence` (`:491–507`)
validates sequences of non-empty *strings* only (`acceptance_criteria`'s own idiom) and cannot
validate a sequence of `TaskV1` objects — a new `_require_task_sequence` helper is needed
instead, following the same non-empty-check shape (`MALFORMED_PAYLOAD` on an empty list) but
calling `_read_task_v1` (`:528–536`, unchanged) per element instead of `_require_nonempty_string`.
`TaskV1` itself
(`:114–125`) is unchanged — no dependency-edge field yet (that is step 2's scope, §11).
Ordering is array order — the roadmap's "deterministic ordering/tie-break metadata" bullet
(Spec 04) is honestly satisfied for slice 1 by "declaration order in the admitted revision,"
the same way M2's original one-task shape trivially satisfied ordering by having only one
task; a real tie-break rule for concurrent-eligible tasks is step 9's territory once tasks can
be concurrently eligible at all (they cannot, under strict linear sequencing).

`read_workflow_revision_v1` (`:540–563`) changes to read a non-empty task array instead of one
object, rejecting a duplicate `task_id` within the same revision (`MALFORMED_PAYLOAD`) — task
identity must be unique within a revision for `_committed_contract`-style per-task lookups
(§4.2) to be unambiguous.

`WorkflowRevisionV1.to_canonical_value()` changes `"task": self.task.to_canonical_value()` to
`"tasks": [t.to_canonical_value() for t in self.tasks]` — a genuine wire-shape change, requiring
the same schema-version-bump + legacy-reader-retention pattern M6 built twice (round 1 for
`VERIFICATION`, round 2 for `RESULT`) and already generalized into
`schema_version_for_kind`/`_SCHEMA_VERSION_BY_KIND` (`protocol_v1.py:94–97,350–353`) — reused
here, not reinvented: `WORKFLOW_REVISION_SCHEMA_VERSION = 2` added to `_SCHEMA_VERSION_BY_KIND`,
registered via `register_reader(ContractKind.WORKFLOW_REVISION, PROTOCOL_VERSION,
WORKFLOW_REVISION_SCHEMA_VERSION, read_workflow_revision_v1)` (matching the existing
`register_reader` call pattern at `protocol_v1.py:1097–1108`) at `(WORKFLOW_REVISION, 1, 2)`.

**Legacy reader, and the M6 precedent it follows (LOW 3):** the current unversioned registration
(`protocol_v1.py:1099–1101`, at `(WORKFLOW_REVISION, PROTOCOL_VERSION, SCHEMA_VERSION)` i.e.
`(WORKFLOW_REVISION, 1, 1)`) is repointed to a new `read_legacy_workflow_revision_v1` — the
retained single-`task`-field reader, kept byte-for-byte equivalent to today's
`read_workflow_revision_v1` so every pre-M7 committed record still parses identically. Following
M6's own precedent for "newer shape submitted under the older schema version"
(`read_legacy_result_v1`, `protocol_v1.py:685–694`: a v1-schema payload carrying a v2-only field
is rejected `UNSUPPORTED_SCHEMA_VERSION`, not `MALFORMED_PAYLOAD`), `read_legacy_workflow_revision_v1`
rejects a payload containing a `"tasks"` key with `UNSUPPORTED_SCHEMA_VERSION` — a
schema-version-1 candidate carrying the new array shape is a version-labeling error, not a
malformed payload.

### 4.2 Per-task run sequencing (Option A)

A new `WorkflowRunV1`-shaped **projection**, not a `lineage_store` run — computed by a new
pure function (e.g. `kernel/workflow_eligibility.py`, new file, mirroring `kernel/replay.py`'s
existing "pure deterministic projection over authoritative lineage" idiom) that takes:

- the admitted `WorkflowRevisionV1` (its `tasks` sequence), and
- the set of per-task-run terminal states for every `task_id` in that sequence (each a
  separate `kernel/lineage_store.py` run, keyed by a stable, derivable run identity — see
  below)

and returns the deterministic next-eligible-task (or "workflow complete" / "workflow blocked")
purely as a function of those two inputs — satisfying Spec 04's "Eligibility is a pure
projection of (1) the exact admitted Workflow Revision, and (2) the exact authoritative
immutable transition lineage" (Spec 04 lines 21–26) exactly, without inventing new lineage
machinery for it.

**Cross-run task-sequence-digest agreement (closes MEDIUM 2; digest scope corrected during
implementation — see §4.4's genesis-binding note and §13's addendum):** because §4.4 commits a
copy of the admitted `tasks` sequence into every per-task run's own `WorkflowRevisionV1` record,
the eligibility projection's second input is not trusted blindly — it recomputes a **task-sequence
sub-digest**, `content_digest({"tasks": [t.to_canonical_value() for t in record.tasks]})`, from
each per-task run's own committed `WORKFLOW_REVISION` record and fails closed
(`WORKFLOW_REVISION_DIGEST_DIVERGENCE`, a new eligibility-level rejection, not a `publish.py` code
since nothing is being published here) if any two per-task runs in the same workflow disagree on
that sub-digest. This is deliberately **not** the full record's content digest: each per-task
run's `WorkflowRevisionV1.request` field is required (§4.5, unchanged) to bind that run's own
genesis Request, so it correctly differs run to run — only `tasks` is the shared, admitted
content. This is exactly Spec 04 line 34's "ambiguous ... state fails closed" applied to the one
new way ambiguity can enter under Option A: a buggy or malicious driver passing a different
`tasks` sequence into task 2's `run_one_task` than task 1's. Each individual per-task run's own
publish-time binding checks (§4.4/§4.5) do not catch this because each run only ever sees its own
copy — the projection is the one place all copies are compared side by side.

**Per-task run identity, and the semantics HIGH 2 requires it to state (closes HIGH 2):**
each task's one-task run needs a stable, re-derivable identity so a second `run_one_task`-style
call for the same task in the same workflow is a genuine retry-of-publish (idempotent) rather
than a fresh, unrelated run. `run_one_task`'s existing `idempotency_prefix` parameter
(`run_one_task.py:229`) is already the exact mechanism `publish()` uses for this
(`_find_idempotent_publish`, `publish.py:285–304`) — reused, not reinvented.

The per-task run's genesis Request idempotency key is **content-derived**, not caller-supplied:
`workflow_idempotency_prefix = content_digest({"tasks": [t.to_canonical_value() for t in
tasks]})` — the same task-sequence sub-digest defined above, computed once over the admitted
`tasks` sequence itself (not a `WorkflowRevisionV1` record, which does not exist yet as a single
object at this point — see §4.3/§4.4: there is no single "the admitted revision" record shared
verbatim across runs, only a shared `tasks` sequence that each run wraps in its own
`WorkflowRevisionV1` bound to its own genesis Request) — and the per-task genesis key is a
**digest of the composed pair**, not raw string
concatenation: `idempotency_key = content_digest({"workflow_revision_digest":
workflow_idempotency_prefix, "task_id": task.task_id, "record": "request"})`, using the same
canonical-JSON `content_digest` primitive every other identity in this codebase already uses
(`kernel/canonical.py`) rather than a hand-built delimited string. This closes two things at
once:

- **Retry-safety, chosen explicitly:** content-derived means re-invoking `run_workflow` for the
  *same admitted revision* (byte-identical `tasks` sequence) always re-derives the same keys and
  resumes/idempotently-republishes rather than creating fresh duplicate runs — matching this
  section's "genuine retry-of-publish" framing and §9's idempotent-reinvocation test. The
  consequence, stated explicitly rather than left implicit: two separately-driven workflows that
  happen to admit byte-identical task sequences intentionally share the same per-task runs. This
  is not a new risk this slice introduces — it is the same content-addressed-dedup semantics
  `_find_idempotent_publish` already applies to every other record kind in this codebase
  (`publish.py:285–304`) — and there is no way, nor any slice-1 need, to force two identical
  workflows to execute as genuinely separate runs; that would require a caller-supplied
  distinguishing field slice 1 does not add.
- **No delimiter-injection collision:** because the key is a digest of a structured
  `{workflow_revision_digest, task_id, record}` object rather than a hyphen-joined string,
  `task_id` values like `"a-b"` cannot collide with a different `(prefix, task_id)` pair that
  happens to concatenate to the same characters — `task_id` is an arbitrary non-empty string
  (`protocol_v1.py:467–470,532`) with no charset restriction, so string concatenation was unsafe
  and digest composition is required, not merely nicer.

**Concurrent-genesis race (explicitly not fixed here):** the genesis idempotency scan
(`publish.py:453–496`) runs before run creation with no cross-run lock, so two concurrent
`run_workflow` invocations for the same workflow can both create a per-task run for the same
task before either commits. This is a pre-existing M1-class gap (the same race exists for any
two concurrent callers publishing the same idempotency key today), not new to or fixed by this
slice — noted here and in §8 rather than left silent.

### 4.3 Driver change

`execution/run_one_task.py` gains a new caller-facing function, `run_workflow`, and `run_one_task`
itself gains one new parameter (closes HIGH 1 — §4.3 and §4.4 as originally drafted were jointly
unsatisfiable, since `run_one_task.py:244–247` constructs `WorkflowRevisionV1(request=...,
task=task)` itself and cannot simultaneously "stay unchanged" and "commit the full multi-task
revision"):

`run_one_task` gains an optional `admitted_tasks: tuple[TaskV1, ...] | None = None` parameter
(**not** a full `WorkflowRevisionV1` — see §4.4's genesis-binding note for why that was the
original, contradictory design). When `None` (every existing M2–M6 call site, unchanged — this is
what "backward compatible" actually means here, not "the function body never changes"),
`run_one_task` builds `WorkflowRevisionV1(request=request_published.record_ref, tasks=(task,))`
exactly as today's single-`task=task`-field construction, adapted to the §4.1 tuple shape. When
`admitted_tasks` is supplied, `run_one_task` builds
`WorkflowRevisionV1(request=request_published.record_ref, tasks=admitted_tasks)` — **this run's
own** genesis Request (required by §4.5's unchanged `GENESIS_REQUEST_BINDING_MISMATCH` check) paired
with the **shared** `tasks` sequence passed down from `run_workflow`. This is the mechanism
`run_workflow` uses to satisfy §4.4's requirement that every per-task run in a workflow commits a
`WorkflowRevisionV1` whose `tasks` field is byte-identical across the whole workflow. Each
per-task run's committed `WorkflowRevisionV1` therefore has both a different `record_id`
(`{run_id}:{sequence}` per `publish.py:706`) **and** a different full-record content digest (its
`request` field differs, correctly) — what is shared identically is only the `tasks`-only
sub-digest defined in §4.2, and that is what §4.2's cross-run digest-agreement check (MEDIUM 2)
verifies actually holds.

`run_workflow(tasks: tuple[TaskV1, ...], ...)` takes the admitted `tasks` sequence directly (not
a `WorkflowRevisionV1` object — there is no single such record shared across runs; each run
builds its own, per above) and iterates it in order, calling `run_one_task` once per task with
`admitted_tasks=tasks` and the derived idempotency key from §4.2 (in place of today's
caller-supplied `idempotency_prefix` string), and stops at the first task whose Verification is
not `PASS`, returning a typed result naming which task blocked and why, rather than silently
continuing to the next task with an incomplete workflow.

### 4.4 What the per-task `WorkflowRevisionV1` published inside each one-task run actually is,
and every real site that reads the old `revision.task` field (closes BLOCKER 1, BLOCKER 2)

**Genesis-request-binding contradiction, found during implementation dispatch, fixed here (see
§13's addendum):** an earlier draft of this section said each per-task run commits "the full
admitted multi-task revision, unchanged across every per-task run" — i.e. the identical
`WorkflowRevisionV1` record, byte-for-byte, in every run. That is impossible: §4.5's
`_kind_binding_rejection` WORKFLOW_REVISION branch (`publish.py:322–328`, unchanged by this slice)
requires `value.request` to bind to **that run's own** genesis Request record ref
(`_genesis_record_ref(run)`), and every per-task run has its own, distinct genesis Request (its
own `record_id`, since each is a separate `kernel/lineage_store` run). A candidate carrying task
1's run's Request ref would therefore fail `GENESIS_REQUEST_BINDING_MISMATCH` the moment it was
published into task 2's run. Publishing "the same record verbatim" across runs is not just
impractical, it is structurally rejected by an existing, unchanged check.

The corrected design (§4.3): each per-task run's committed `WorkflowRevisionV1` binds **that
run's own** genesis Request (satisfying §4.5 unchanged) while sharing a **byte-identical `tasks`
field** with every other per-task run in the workflow. What is "the same" across runs is the
`tasks` sequence and its sub-digest (§4.2), not the whole record and not the whole record's
content digest — those legitimately differ per run because `request` differs per run. Every real
site that currently reads `revision.task` must change to "locate the bound task within
`revision.tasks` by the relevant `task_id`, reject if absent" — there are **four** such sites, not
the one originally scoped here; an earlier draft of this plan covered only the first and left the
other three unaddressed, which is a plan defect an adversarial review caught (three of the four
crash every real publish/execute path under the new schema, not just an edge case):

1. **`kernel/publish.py:333`, `_kind_binding_rejection`'s `ATTEMPT_PACKET` branch.** Changes from
   `value.task_id != revision.task.task_id` to a lookup of `value.task_id` within `revision.tasks`,
   rejecting `ATTEMPT_TASK_BINDING_MISMATCH` if no task in the bound revision has that id (instead
   of comparing against a single field).
2. **`kernel/publish.py:375`, the `VERIFICATION` branch.** `covered != revision.task
   .acceptance_criteria` crashes with `AttributeError` under the new schema on every Verification
   publish — this branch was missing from earlier drafts of §4.4/§10 entirely. It also forces a
   design decision that must be stated, not left to an implementer to guess: coverage must be
   compared against **the specific task this run's committed Attempt Packet is bound to**, located
   by `attempt_value.task_id` — `attempt_value` is already re-read at `publish.py:414` for the
   self-verification check, so no new lookup is added, only reused for this comparison too. The
   fix: locate `task = next(t for t in revision.tasks if t.task_id == attempt_value.task_id)`
   (falling through to a typed rejection, not an unhandled `StopIteration`, if none matches —
   `ATTEMPT_TASK_BINDING_MISMATCH` should already have made this unreachable by the time
   `VERIFICATION` publishes, but the branch must not assume that silently) and compare
   `covered != task.acceptance_criteria`.
3. **`execution/attempt.py:83–88`, inside `build_attempt_packet`.** `revision.task.task_id`,
   `revision.task.to_canonical_value()` — the same "locate by `task_id` within `revision.tasks`,
   fail closed if absent" fix, raising the existing `TaskBindingMismatchError` (already this
   function's error type for exactly this class of mismatch, reused not invented) when the
   committed revision contains no task with the packet's `task_id`.
4. **`execution/host.py:297–299`, inside `execute()`'s M4 third pre-spawn check.** Same fix, same
   "locate by `task_id`, fail closed" shape, raising the existing `StaleContextPackError` (again
   this function's established error type for this check, unchanged in kind). An earlier draft of
   this plan (§5) claimed `execution/host.py` was "completely unchanged" by slice 1 — that claim
   was false; §5 below is corrected to say so.

This keeps one canonical, content-addressed **task-sequence** digest shared identically across
every task's run (§4.2) — exactly what lets `run_workflow` (§4.3) pass the same `tasks` sequence
into each per-task run (via `admitted_tasks`), each run wrapping it in a `WorkflowRevisionV1`
bound to that run's own genesis Request, and have §4.2's cross-run task-sequence-digest agreement
check verify all copies agree on the part that must agree. The **full** per-run
`WorkflowRevisionV1` record and its full content digest are not shared across runs, and are not
expected to be — `_find_idempotent_publish`'s content-digest equality operates per-run, on each
run's own candidate against that same run's own prior publishes, exactly as it already does for
every other kind.

### 4.5 `_kind_binding_rejection`'s `WORKFLOW_REVISION` branch (currently a no-op) gains real checks

Today `_kind_binding_rejection` (`publish.py:320–328`) only checks the genesis Request binding
for a `WORKFLOW_REVISION` candidate — nothing validates `tasks` structurally beyond the reader's
own shape rules. Slice 1 adds: duplicate `task_id` rejection (already at the reader per §4.1,
restated here as the publish-boundary's own defense-in-depth, matching M1's stated precedent of
checking both layers) is sufficient; no cross-record lineage check is needed at this kind since
nothing has been published yet that a multi-task revision could conflict with.

### 4.6 `kernel/replay.py`'s fold gains a `_LegacyWorkflowRevisionV1` branch (closes BLOCKER 3)

`replay.py:169–183`'s fold is an `isinstance` chain with a branch per contract-value type
(`RequestV1`, `WorkflowRevisionV1`, `AttemptPacketV1`, `ResultV1 | _LegacyResultV1`,
`VerificationV1 | _LegacyVerificationV1 | _LegacyVerificationV1RoundOne`, `ReceiptV1`). §4.1
retains a `_LegacyWorkflowRevisionV1`-shaped reader for pre-M7 records, but a value of that type
matches **none** of the existing branches — it silently falls through the whole chain, and
`RunState.workflow_revision` (`replay.py:45,114`) is left `None` for that run. No exception is
raised; replay "succeeds" while quietly discarding real committed state, exactly the class of
defect this plan's own discipline (and M6's own replay-fold precedent) exists to prevent.

Fix, following M6's own pattern exactly (`replay.py:24–30`'s existing legacy-type imports for
`_LegacyResultV1`/`_LegacyVerificationV1*`, and the corresponding `RunState` field-type widening
already done for those two kinds): `RunState.workflow_revision`'s type widens to
`WorkflowRevisionV1 | _LegacyWorkflowRevisionV1 | None`, and the fold gains an
`elif isinstance(value, (WorkflowRevisionV1, _LegacyWorkflowRevisionV1)):` branch (merging with
the existing `WorkflowRevisionV1` branch at `:171` rather than adding a separate one, since both
assign to the same field). §9's replay fixture (below) is written to assert the *folded value*
equals the legacy single-task revision, not merely that replay raises no exception — an assertion
this weak would have let BLOCKER 3 pass a naive version of the same test.

## 5. What slice 1 deliberately does not change

- `kernel/lineage_store.py` — completely unchanged (Option A, §3).
- `AttemptPacketV1`, `ResultV1`, `RuntimeObservationV1`, `VerificationV1`, `FindingV1`,
  `ReceiptV1` — completely unchanged **as contract shapes**. Every M3–M6 evidence/environment/
  execution-identity/Finding-lineage guarantee applies identically to each task's per-task run;
  slice 1 adds no new evidence machinery.
- `execution/policy.py`, `verification/stub_verifier.py`, `verification/stub_verifier_cli.py` —
  completely unchanged; every task's Attempt still binds the same fixed
  `M3_ADMITTED_PERMISSIONS`/`M3_REQUIRED_CAPABILITIES` table (§7 explains why per-task
  differentiation is not this slice's scope).
- **Correction to an earlier draft of this section:** `execution/host.py` and
  `execution/attempt.py` are **not** unchanged — both read the removed `revision.task` field and
  are fixed in §4.4 (BLOCKER 2). Only their *error types and overall check structure* are
  unchanged (`TaskBindingMismatchError`, `StaleContextPackError` — same classes, same trigger
  conditions, just relocated from a field read to a `revision.tasks` lookup).
- **Correction to an earlier draft of this section:** `kernel/replay.py` is **not** unchanged —
  its fold gains one new branch (§4.6, BLOCKER 3) so retained pre-M7 `_LegacyWorkflowRevisionV1`
  values don't silently vanish from `RunState`. `replay()`'s per-run contract (one run in, one
  `RunState` out, folded purely from that run's own committed records) is unchanged; only the
  fold's coverage of value types grows, the same way M6 grew it for `ResultV1`/`VerificationV1`.
  No separate workflow-level replay helper is added in slice 1 — §9's replay assertions operate
  per-task-run, on the unchanged `replay()` contract, plus §4.2's eligibility projection which
  composes per-task-run terminal states (not per-task-run *replay*) into the workflow view.

## 6. ADR-0009 Reviewer/Verifier split: out of scope for slice 1

**Not in scope**, for a concrete, code-grounded reason, not a schedule-convenience deferral:
ADR-0009's split trigger is "a deterministic, per-Task risk-tier predicate... it reuses the
same risk-tier computation Plan Check admission uses" (ADR-0009, Decision, first two bullets).
§1 confirms **neither risk-tier computation nor Plan Check exists anywhere in this codebase**
— not a stub, not a partial implementation, zero matches for `risk_tier`/`risk profile`/
`plan.check` across `product/src/`. Building the Reviewer/Verifier split without first building
the risk-tier predicate it is explicitly specified to reuse would mean inventing a second,
divergent risk classification just for this one gate — directly the kind of "two separately
tunable gates" language in ADR-0009 presumes a **shared** predicate exists first, which it does
not. Implementing ADR-0009 correctly requires Plan Check and risk-tier machinery to exist as
real, load-bearing code before the split can honestly reuse it, not synthesize it standalone.
That is a separate, larger slice — plausibly its own M7 sub-slice after linear multiple tasks
and DAG eligibility exist, since risk tier is naturally computed from admitted Task attributes
that only matter once tasks are a first-class admitted collection (which slice 1 makes true for
the first time). Recorded here as a named follow-on, not silently dropped.

## 7. M3's per-task capability-requirement gap: also out of scope for slice 1

`HANDOFF.md`'s carried-forward scope-limit list says this gap is "still open, still deferred to
M7's real orchestration layer or a dedicated contract change" — "likely," not committed. §1
confirms `execution/policy.py`'s `M3_REQUIRED_CAPABILITIES`/`M3_ADMITTED_PERMISSIONS` are one
fixed global table with no per-task field to key off of. Closing this gap requires either (a) a
new field on `TaskV1` naming required capabilities/permission scope, checked at Attempt
admission per-task instead of via one global constant, or (b) a policy-lookup keyed on task
attributes. Slice 1's `TaskV1` change is limited to making tasks a sequence (§4.1); adding a
capability-requirement field to `TaskV1` in the same PR would couple an orthogonal M3-era gap
to the multi-task cardinality change this slice is actually proving, violating this plan's own
§2 narrow-scope discipline. Left as an explicit carried-forward gap (§11), revisited once a
concrete slice needs a task whose declared capability needs differ from another task's in the
same workflow — the exact "revisit when a concrete milestone need makes one of these
load-bearing" test the roadmap's cross-cutting rule 2 (YAGNI) sets.

## 8. Eligibility, blocking, and the linear-only negative-space this slice must prove

Per Spec 04 ("Unknown, ambiguous, stale, or reconciliation-required state fails closed rather
than guessing eligibility"), slice 1's eligibility function (§4.2) must fail closed on cases
that cannot arise from strictly sequential admitted `tasks`, so real negative tests exist even
though the graph shape is trivial:

- a per-task run's Verification is `FAIL`/`BLOCKED` — the workflow's next-eligible-task
  computation returns "blocked at task N," not "skip to task N+1"
- a per-task run has no committed records at all (never started) while an earlier task in
  sequence is still incomplete — eligibility must never report a later task as eligible while
  an earlier one is unresolved, since slice 1 defines "linear" as sequential dependency purely
  by array position (step 2's explicit dependency-edge contract does not exist yet)
- two per-task runs for the same `task_id` inside one workflow (a real bug or a non-idempotent
  retry with different content) — the idempotency-key content-digest mismatch path
  (`IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_CONTENT`, already real in `publish.py:300–303`) is
  reused unchanged; no new code needed, but a positive test proving it fires in the
  multi-task caller path is a slice-1 deliverable
- **in-flight (crashed mid-chain) per-task run — closes HIGH 3.** A per-task run whose head is
  `ATTEMPT_PACKET` or `RESULT` (started, not yet terminal) is neither "complete" (head=`RECEIPT`,
  `PASS`) nor "blocked" (head=`VERIFICATION`, non-`PASS` verdict) nor "never started" (no
  committed records). Per Spec 04 line 34 this is exactly the kind of state that must not be
  guessed at silently — and §4.2's per-task run identity is deliberately content-derived and
  deterministic (HIGH 2), and `run_one_task` is already per-record resumable via its fixed
  `{idempotency_prefix}-request/-workflow/-attempt/…` keys (`run_one_task.py:240,255,279,338,358,
  375`) with the idempotency scan preceding head fencing (`publish.py:657–661` vs `:690–699`), so
  the eligibility rule slice 1 adopts is: **an in-flight task is reported eligible** (not blocked,
  not skipped) — resuming it means re-invoking `run_one_task` with the same derived keys, which
  idempotently continues the chain from wherever it stopped rather than restarting or erroring.
  §9 adds a driver test proving this: crash after task 1's Attempt Packet is published (before its
  Result), re-invoke `run_workflow`, assert it resumes task 1 rather than treating the workflow as
  blocked or re-running task 1 from scratch.
- **cross-run revision-digest divergence — see §4.2's `WORKFLOW_REVISION_DIGEST_DIVERGENCE`
  check** (MEDIUM 2): fails closed rather than picking either per-task run's copy as canonical.
- concurrent-genesis race (§4.2): a pre-existing M1-class gap, not fixed by this slice's design —
  documented here rather than silently assumed away.

## 9. Test plan

### Protocol/reader (`product/tests/contracts/test_protocol_v1_m7.py`, new — following
M3/M4/M6's per-milestone dedicated-file naming precedent)

- `WorkflowRevisionV1` reader: non-empty `tasks` sequence accepted; empty sequence rejected
  `MALFORMED_PAYLOAD`; duplicate `task_id` within one revision rejected; schema-version
  dispatch — a `schema_version=2` (`tasks` array) candidate parses; a `schema_version=1`
  candidate carrying `tasks` instead of `task` is rejected `MALFORMED_PAYLOAD` (wrong reader for
  its declared version); a `schema_version=1` legacy single-`task` candidate still parses
  through the retained legacy reader
- golden-digest fixtures regenerated for the new `WorkflowRevisionV1` v2 wire shape
- a schema-version-1 candidate carrying a `"tasks"` key is rejected `UNSUPPORTED_SCHEMA_VERSION`
  by the legacy reader (§4.1, LOW 3), not `MALFORMED_PAYLOAD`
- **replay fixture (strengthened, closes BLOCKER 3):** a run containing a committed pre-M7
  schema-v1 `WorkflowRevisionV1` (single `task`) replays through `replay()` and the fold's new
  `_LegacyWorkflowRevisionV1` branch (§4.6) — the test asserts `RunState.workflow_revision`
  **equals the legacy single-task revision value**, not merely that `replay()` raises no
  exception. An assertion that only checks "no exception" would pass even with BLOCKER 3's bug
  present (silent `None`), so this is a deliberate strengthening, not a rewording.

### Publish boundary (`product/tests/kernel/test_publish_m7.py`, new)

- multi-task `WorkflowRevisionV1` with 2–3 tasks publishes at genesis-successor position
  unchanged (no change to `_NEXT_KIND`, Option A)
- `AttemptPacketV1` binding against a multi-task revision: `task_id` matching any task in
  `tasks` binds correctly (§4.4 fix 1); `task_id` matching none of them rejects
  `ATTEMPT_TASK_BINDING_MISMATCH`
- duplicate-`task_id` `WorkflowRevisionV1` candidate rejected at publish (defense-in-depth,
  §4.5), mirroring the reader-level rejection
- **VERIFICATION publish against a multi-task revision (closes BLOCKER 1):** a Verification
  whose coverage matches task N's `acceptance_criteria` (located by the committed Attempt
  Packet's `task_id`, §4.4 fix 2) is accepted in task N's per-task run even when it does **not**
  match task 0's (or any other task's) criteria — proving the fix locates the correct task
  rather than comparing against a fixed position or a concatenation of all tasks' criteria

### Eligibility (`product/tests/kernel/test_workflow_eligibility.py`, new — the new pure
projection function from §4.2)

- same admitted revision + same set of per-task terminal states always yields the identical
  eligible/next task (determinism, Spec 04's core requirement) — run twice, assert equal
- all tasks' runs terminal with `PASS` Receipts → workflow complete
- task N's run `FAIL`/`BLOCKED` → workflow blocked at task N, task N+1 never reported eligible
  (§8)
- task N+1 has no committed run yet while task N's is incomplete → task N+1 never eligible
- unknown `task_id` in per-task-run lookup (a run exists that does not correspond to any task
  in the admitted revision) → fails closed, not silently ignored
- **task N's per-task run is in-flight (head=`ATTEMPT_PACKET` or `RESULT`, not yet terminal) →
  task N itself is reported eligible (resume), not task N+1 and not "blocked"** (closes HIGH 3)
- **two per-task runs in the same workflow have committed `WORKFLOW_REVISION` records whose
  `tasks` fields produce different task-sequence sub-digests (their `request` fields legitimately
  differ and must be ignored by this check) → `WORKFLOW_REVISION_DIGEST_DIVERGENCE`, fails
  closed** (closes MEDIUM 2)

### Driver (`product/tests/execution/test_run_workflow.py`, new — exercises the real
`run_workflow` end-to-end through the real fixture OpenCode binary, same pattern as
`test_m6_integration.py`)

- a 2-task linear workflow where both tasks' expected output matches: both per-task runs reach
  terminal `PASS` Receipts, `run_workflow` reports workflow-complete
- a 2-task linear workflow where task 1's Verification is `FAIL`: `run_workflow` stops after
  task 1, task 2 never gets an Attempt Packet published (the negative test proving "does not
  silently continue")
- **a 2-task linear workflow where task 1's Verification is `BLOCKED`** (closes LOW 4 — the
  driver-level negative test previously covered `FAIL` only): same assertion shape as the `FAIL`
  case, task 2 never gets an Attempt Packet published
- idempotent re-invocation of `run_workflow` for an already-fully-completed workflow returns
  the existing per-task publications rather than creating duplicate runs (exercises §4.2's
  derived idempotency-key scheme end-to-end)
- **crash-resume (closes HIGH 3):** a 2-task workflow where task 1's Attempt Packet is published
  but the run is interrupted before task 1's Result; re-invoking `run_workflow` resumes task 1
  (via `run_one_task`'s existing per-record idempotent resumption) and completes the workflow,
  rather than treating task 1 as blocked or re-running it from an empty state

### Regression

- `product/tests/kernel/test_publish_m2.py`, `test_publish_m6.py`, `test_m3_integration.py`,
  `test_m4_integration.py`, `test_m6_integration.py` — every fixture constructing a
  `WorkflowRevisionV1` directly needs updating for the `tasks` tuple shape (or moving to the
  legacy-schema-v1 constructor where the fixture's intent is specifically to exercise pre-M7
  replay); `run_one_task`'s default (`admitted_tasks=None`) behavior is unchanged (§4.3), so
  fixtures calling it directly (not through the new `run_workflow`) keep working once their
  `WorkflowRevisionV1` construction is updated
- `test_replay.py`, `test_fault_injection.py` — Workflow Revision fixtures updated the same way
- **(closes MEDIUM 1 — missing from an earlier draft of this inventory)**
  `product/tests/execution/test_attempt.py`, `test_attempt_and_host.py`, `test_host.py`,
  `product/tests/kernel/test_verification_mutation.py`, `product/tests/contracts/
  test_protocol_v1.py` — all construct `WorkflowRevisionV1(` directly or read `.task` off one;
  `test_protocol_golden.py`'s regeneration is already covered by the golden-digest bullet above

## 10. Implementation order

1. `kernel/protocol_v1.py`: `WorkflowRevisionV1.tasks` (schema v2), new
   `_require_task_sequence` helper (§4.1, LOW 5), `read_legacy_workflow_revision_v1` retained at
   `(WORKFLOW_REVISION, 1, 1)` rejecting a `"tasks"` key with `UNSUPPORTED_SCHEMA_VERSION` (§4.1,
   LOW 3), `WORKFLOW_REVISION_SCHEMA_VERSION = 2` added to `_SCHEMA_VERSION_BY_KIND` and
   registered at `(WORKFLOW_REVISION, 1, 2)`, duplicate-`task_id` rejection at the reader.
2. `kernel/publish.py`: `_kind_binding_rejection`'s `ATTEMPT_PACKET` branch changed to locate
   the bound task by `task_id` within `revision.tasks` (§4.4 fix 1); the `VERIFICATION` branch
   changed to locate the bound task by the committed Attempt Packet's `task_id` before comparing
   `acceptance_criteria` (§4.4 fix 2, **BLOCKER 1**); `WORKFLOW_REVISION` branch gains the
   duplicate-`task_id` defense-in-depth check (§4.5). No change to `_NEXT_KIND` or
   `_committed_contract` (Option A).
3. `execution/attempt.py`'s `build_attempt_packet` and `execution/host.py`'s `execute()` third
   pre-spawn check: both changed to locate the bound task by `task_id` within `revision.tasks`,
   fail closed with their existing `TaskBindingMismatchError`/`StaleContextPackError` types if
   absent (§4.4 fixes 3–4, **BLOCKER 2**).
4. `kernel/replay.py`: `RunState.workflow_revision` widened to `WorkflowRevisionV1 |
   _LegacyWorkflowRevisionV1 | None`; fold gains the merged branch (§4.6, **BLOCKER 3**).
5. New `kernel/workflow_eligibility.py`: the pure per-task-terminal-state → next-eligible-task
   projection (§4.2, §8), including the in-flight-resumable rule (HIGH 3) and the cross-run
   `WORKFLOW_REVISION_DIGEST_DIVERGENCE` check (MEDIUM 2).
6. `execution/run_one_task.py`: `run_one_task` gains the optional `admitted_tasks` parameter
   (§4.3, **HIGH 1**, default-`None` behavior unchanged — each run still binds its own genesis
   Request, per the genesis-binding fix in §4.4); new `run_workflow` function reusing
   `run_one_task` per-task with the digest-composed idempotency-key scheme (§4.2, **HIGH 2**).
7. Golden-digest fixtures regenerated for the new `WorkflowRevisionV1` wire shape.
8. Test suite (§9): protocol-reader extensions plus the strengthened v1-retention replay
   assertion, `test_publish_m7.py` (including the BLOCKER-1 coverage-by-task test),
   `test_workflow_eligibility.py` (including the in-flight and digest-divergence cases),
   `test_run_workflow.py` (including the BLOCKED-driver and crash-resume cases), and the full
   regression list (including the five previously-missing files, MEDIUM 1).

## 11. Explicit scope limits carried forward (not gaps to silently close here)

Per AGENTS.md rule 9 (YAGNI) and M3/M4/M6's own explicit-deferrals precedent — this is the
roadmap's own nine-step expansion order, restated as what remains after slice 1:

- **Step 2 — DAG dependency validation and deterministic eligibility.** Slice 1's ordering is
  strict array-position sequence only; no explicit dependency-edge contract field, no cycle
  detection, no non-linear graph shape. `TaskV1` gains no `depends_on`-style field this slice.
- **Step 3 — logical Resource Claims with read/write conflict semantics.** No resource-claim
  contract field exists; nothing in slice 1 needs it since tasks never run concurrently.
- **Steps 4–6 — bounded retry, repair, replan.** No successor-revision machinery, no bounded
  reattempt budget, no escalation policy. A `FAIL`/`BLOCKED` per-task Verification blocks the
  workflow (§8); nothing retries it automatically.
- **Step 7 — fan-in with explicit merge/conflict policy.** Nothing to merge in a strictly
  linear sequence.
- **Step 8 — reconciliation-required handling.** No `reconciliation_required` state exists;
  not reachable from any slice-1 code path.
- **Step 9 — proven-safe parallel execution.** `run_workflow` (§4.3) is a strict sequential
  loop; no concurrency.
- **ADR-0009 Reviewer/Verifier split** (§6): blocked on risk-tier/Plan Check machinery that
  does not exist yet; a named follow-on slice, not implemented here.
- **M3's per-task capability-requirement gap** (§7): `TaskV1` gains no capability/permission
  field this slice; `execution/policy.py`'s fixed global table is unchanged.
- **M4's `lineage`/`observed` Context Unit source classes** (`HANDOFF.md`'s carried-forward
  note: "stay structurally empty until M7 gives them real predecessors/tool output") — slice 1
  gives each task its own real prior-task Result/Receipt to serve as a real predecessor in
  principle, but wiring that into the Context Compiler's source-class machinery is a separate,
  not-yet-scoped follow-on; no `context_compiler.py` change is part of this plan.
- **Spec 04's `workflow/risk profile and admitted policy` contract field and the Plan-Check
  requirement predicate (Spec 04 lines 17, 19) — a named deviation, not a silent gap** (closes
  MEDIUM 3). Spec 04 requires admission to reject a Workflow Revision missing required policies,
  and requires a deterministic predicate over the candidate revision to decide whether an
  independent Plan Check is required before admission. Neither exists in this codebase (§1, §6)
  and slice 1 does not add them — `WorkflowRevisionV1` gains only `tasks`, no `risk_profile` or
  `admitted_policy` field. This is the same missing machinery §6 already defers ADR-0009's split
  on; recorded here explicitly so a reader of Spec 04's "Workflow revision contract" field list
  does not assume slice 1's `tasks`-with-array-order shape satisfies it.
- **FAIL/BLOCKED permanence under slice 1's deterministic per-task run identity** (closes
  MEDIUM 4). §4.2's content-derived idempotency keys mean a `FAIL`/`BLOCKED` per-task run is
  *permanently* pinned to that outcome: any re-invocation of `run_workflow` for the same admitted
  revision re-derives the identical key, hits the existing dead-chain idempotently
  (`publish.py:657–661`), and reports the same blocked outcome again. Recovering requires a new
  admitted revision (different `tasks` content, hence a different digest) until steps 4–6
  (retry/repair/replan) exist — this is the correct fail-closed behavior for this slice, not a
  bug, and it must not be "fixed" later by salting/randomizing the idempotency key, which would
  silently break the crash-resume behavior HIGH 3's fix depends on (§4.2, §8).

## 12. M7 slice 1 exit gate

Restated at this slice's honest, narrow scope against the roadmap's M7 exit-evidence bullets
(the bullets not addressed here are steps 2–9's, restated in §11 as not-yet-applicable rather
than failed):

- same admitted multi-task revision + same per-task-run lineage always yields the identical
  eligible/next task and identical workflow-complete/blocked outcome (§4.2, §8 — determinism
  test, run twice)
- a `FAIL`/`BLOCKED` per-task Verification blocks the workflow; the next task's Attempt Packet
  is never published (§8, §9's driver negative test)
- duplicate/unknown `task_id` references fail admission (§4.1, §4.4, §4.5)
- a fully-completed multi-task workflow replays identically per task through the unchanged
  `kernel/replay.py` per-run replay (Option A — no new replay machinery, reused unchanged)
- pre-M7 single-task `WorkflowRevisionV1` history remains replayable **with its folded value
  preserved**, not merely without exception, through the retained legacy reader and replay fold
  (§4.6, §9)
- idempotent re-invocation of the workflow driver does not create duplicate per-task runs, and
  correctly resumes an in-flight (crashed mid-chain) per-task run rather than treating it as
  blocked (§4.2, §8, §9)
- Verification coverage for a multi-task revision is checked against the specific bound task's
  acceptance criteria, not a fixed position or another task's criteria (§4.4, §9)

## 13. Adversarial review log

Reviewed pre-implementation by `glm-5.3` (effort `high`, via `opencode`, `--auto`) against the
real committed code (`kernel/protocol_v1.py`, `kernel/publish.py`, `kernel/replay.py`,
`execution/attempt.py`, `execution/host.py`, `execution/run_one_task.py`), the governing roadmap/
spec/ADR documents, and this plan's first draft. Every citation in the draft's §1 baseline was
spot-checked against the real file:line and found accurate (see the review's own appendix); the
findings below are omissions in the draft's change inventory, not fabricated or mistaken
citations. **Verdict: 3 BLOCKER, 3 HIGH, 4 MEDIUM, 5 LOW — all fixed in the design sections
above** (this log summarizes after the fact; it is not itself the fix, matching M6's own
discipline).

- **BLOCKER 1** — `publish.py:375`'s `VERIFICATION` branch reads `revision.task
  .acceptance_criteria`, crashing on every v2 Verification publish; the draft's change inventory
  didn't cover this branch. **Fixed:** §4.4 fix 2 — locate the bound task by the committed
  Attempt Packet's `task_id`, compare against that task's criteria; §9 adds the coverage-by-task
  test; §10 step 2.
- **BLOCKER 2** — `execution/attempt.py:83–88` and `execution/host.py:297–299` also read
  `revision.task` and crash under the new schema; the draft's §5 falsely claimed `host.py` was
  unchanged and never mentioned `attempt.py` at all. **Fixed:** §4.4 fixes 3–4 — both locate the
  task by `task_id` within `revision.tasks`, fail closed with their existing error types; §5
  corrected; §10 step 3.
- **BLOCKER 3** — `replay.py:169–183`'s fold has no branch for `_LegacyWorkflowRevisionV1`; a
  retained pre-M7 revision silently folds to `workflow_revision=None` instead of preserving its
  value. **Fixed:** §4.6 (new) — `RunState.workflow_revision` widened, fold branch added,
  following M6's own Result/Verification retention pattern exactly; §9's replay fixture
  strengthened to assert the folded value, not just clean replay; §5 corrected; §10 step 4.
- **HIGH 1** — §4.3/§4.4 as originally drafted were jointly unsatisfiable: `run_one_task.py:244–
  247` constructs the revision itself, so it couldn't both "stay unchanged" and "commit the full
  multi-task revision." **Fixed:** §4.3 — `run_one_task` gains an optional `admitted_tasks`
  parameter (a bare `tasks` tuple, not a full `WorkflowRevisionV1` — see the addendum below),
  default-`None` behavior unchanged for every existing caller; `run_workflow` supplies it; §10
  step 6.
- **HIGH 2** — §4.2's `workflow_idempotency_prefix` provenance was unstated, and raw string
  concatenation of prefix+`task_id` allowed delimiter-injection key collisions. **Fixed:** §4.2 —
  content-derived from the admitted `tasks` sequence's own sub-digest (see the addendum below for
  why it is a `tasks`-only sub-digest, not a whole-revision digest), key composed by hashing a
  structured `{workflow_revision_digest, task_id, record}` object instead of string concatenation
  (the field is still named `workflow_revision_digest` in the composed key for continuity; its
  value is the `tasks`-only sub-digest); the two-identical-workflows-share-runs consequence stated
  explicitly; the pre-existing concurrent-genesis race noted, not fixed; §10 step 6.
- **HIGH 3** — Eligibility never named the in-flight (crashed mid-chain) per-task run state,
  leaving retry-after-partial-crash unspecified. **Fixed:** §4.2/§8 — in-flight → that task is
  eligible (resume via `run_one_task`'s existing per-record idempotency); §9 adds the
  crash-resume driver test; §10 step 5.
- **MEDIUM 1** — §9's regression inventory missed five test files that construct
  `WorkflowRevisionV1(` directly. **Fixed:** Regression section lists all five; §10 step 8.
- **MEDIUM 2** — nothing checked that every per-task run's committed revision copy agrees.
  **Fixed:** §4.2 — the eligibility projection compares committed `WORKFLOW_REVISION` digests
  across the workflow, fails closed (`WORKFLOW_REVISION_DIGEST_DIVERGENCE`) on divergence; §9
  adds the divergence test; §10 step 5.
- **MEDIUM 3** — Spec 04's `workflow/risk profile and admitted policy` field and Plan-Check
  predicate weren't named as an unimplemented deviation. **Fixed:** §11 — recorded explicitly,
  tied to §6's ADR-0009 deferral.
- **MEDIUM 4** — FAIL/BLOCKED permanence under deterministic keys was un-traced, risking a future
  "fix" (key salting) that would silently break crash-resume. **Fixed:** §11 — stated explicitly
  as correct fail-closed behavior for this slice, with the salting anti-fix named and rejected.
- **LOW 1** — §1 claimed `RUN_ALREADY_TERMINAL` fires "before any other admission check,"
  dropping the load-bearing idempotency-shortcut exception HIGH 3's fix depends on. **Fixed:**
  §1 — citation corrected to name the exception.
- **LOW 2** — `WorkflowRunV1` naming drifted between "a new outer contract" (§3) and "a pure
  projection" (§4.2). **Fixed:** §3/§4.2 now consistently describe a pure projection with no
  committed record.
- **LOW 3** — §9 expected `MALFORMED_PAYLOAD` for a `tasks`-shaped payload under schema v1,
  diverging from M6's `UNSUPPORTED_SCHEMA_VERSION` precedent for the same "newer shape, older
  version" case. **Fixed:** §4.1/§9/§10 — `UNSUPPORTED_SCHEMA_VERSION`, matching precedent.
- **LOW 4** — §9's driver negative test covered `FAIL` only, not `BLOCKED`. **Fixed:** §9 adds
  the BLOCKED-driver fixture.
- **LOW 5** — §4.1 wrongly claimed `_require_string_sequence` (string-only) could validate the
  `tasks` array (objects). **Fixed:** §4.1/§10 step 1 — new `_require_task_sequence` helper.

**Deferral soundness (confirmed by the review, no plan change needed):** ADR-0009's split
deferral (§6) and the M3 capability-requirement gap deferral (§7) were both independently
verified against the real code (zero risk-tier/Plan-Check implementation anywhere in
`product/src/`; `policy.py`'s fixed global table confirmed) and found sound — code-grounded, not
schedule-convenience assertions. The roadmap's slice-1-only scope discipline (§2) and this plan's
consistency with `HANDOFF.md`'s M7 kickoff notes were also confirmed.

### Addendum — genesis-request-binding contradiction, found by the implementing agent, not the review

The `glm-5.3` review above checked every `revision.task`-reading call site (BLOCKER 1/2/3) but did
not trace whether the corrected design's central claim — "every per-task run commits an identical
copy of the full admitted multi-task revision" (the post-BLOCKER-fix wording of §4.4) — was
actually publishable. It was not: `codex --model gpt-5.6-luna -c model_reasoning_effort="max"`,
dispatched to implement this plan verbatim, correctly stopped before writing any code and reported
the contradiction rather than guessing around it (per this repo's own stop-on-blocker discipline,
`HANDOFF.md`'s M6-round-2 precedent) — no files changed, no commit made, first dispatch attempt.

**The contradiction:** `_kind_binding_rejection`'s `WORKFLOW_REVISION` branch (`publish.py:322–
328`, unchanged by this slice, already spot-checked accurate by the review) requires
`value.request` to bind to *that run's own* genesis Request (`_genesis_record_ref(run)`). Every
per-task run has a distinct genesis Request (distinct `record_id`, since each is a separate
`lineage_store` run). A `WorkflowRevisionV1` candidate carrying task 1's run's Request ref is
therefore structurally rejected the moment it is published into task 2's run —
`GENESIS_REQUEST_BINDING_MISMATCH`, an existing, correct check, not a bug to route around.

**The fix (applied directly to §4.2/§4.3/§4.4 above, not left as a follow-on):** what is shared
identically across every per-task run in a workflow is the `tasks` sequence and its sub-digest —
not the whole `WorkflowRevisionV1` record and not its full content digest. Each per-task run
builds its own `WorkflowRevisionV1(request=<this run's own genesis Request ref>, tasks=<the
shared sequence>)`. `run_one_task`'s new parameter is renamed `admitted_tasks: tuple[TaskV1, ...]
| None` (a bare tasks tuple, not a `WorkflowRevisionV1`), `run_workflow` takes `tasks` directly as
its admitted input (there was never a single already-admitted `WorkflowRevisionV1` record for it
to hold, since no per-task run's Request exists until that run's own `run_one_task` call
publishes it), and §4.2's cross-run digest-agreement check (MEDIUM 2) compares a `tasks`-only
sub-digest — `content_digest({"tasks": [...]})` — recomputed from each run's own committed record,
rather than the full record digest. This is a strictly smaller, more mechanical fix than it might
sound: no new contract fields, no change to `_kind_binding_rejection`'s existing genesis-binding
check, no change to `_NEXT_KIND`/`_committed_contract` — only which digest the eligibility
projection and the idempotency-key derivation compute.

This was not escalated to the user as an architecture decision (unlike M6 round 2's spec-retraction
question) because there was no real tradeoff to weigh: the alternative (rebinding every per-task
run's genesis Request to a single shared value) would require inventing a new kind of Request
record shared across runs, which Option A's own rationale (§3 — reuse M1's run primitive
completely unchanged) already rules out, and no other design satisfies both `_kind_binding_
rejection`'s existing check and §4.4's original "one canonical shared identity" goal at the same
time except narrowing what "shared" means to `tasks`. The plan is corrected in place (§4.2–§4.4,
§9's eligibility/regression test descriptions, §10 steps 5–6) rather than logged as a deferred
gap, matching this document's own discipline for BLOCKER/HIGH findings.

## 14. Round 2 review (PR #49, post-implementation, against `a4f6121`)

PR #49 opened for `a4f6121`. GitHub's `chatgpt-codex-connector` auto-review (2 inline findings)
plus a manual adversarial pass by the repo owner (4 findings, posted as PR review comments) found
**6 real defects, all against this slice's own core guarantee** ("strict ordered multi-task
execution" — not later-slice behavior). Decision: blocking, no merge yet. All 6 fixed directly
below (§14.1–§14.6) — no protocol/contract schema change required for any of them; all are
driver-layer (`execution/run_one_task.py`) or eligibility-module (`kernel/workflow_eligibility.py`)
fixes.

### 14.1 [P1] Eligibility trusts the caller-supplied `task_runs` mapping key, not the run's own committed identity

`project_workflow_eligibility()` / `_state_kind()` never check that a `RunState` returned under key
`"task-1"` actually belongs to task 1 — only `_validate_revision_copies()`'s tasks-sequence-digest
check runs, which every per-task run passes identically by construction (§4.4). A completed
task-2 run's `RunState` supplied under key `"task-1"` is silently accepted as task 1 complete.

**Fix:** in `_state_kind()` (or a new helper called from it), when `state.attempt_packet` is not
`None`, read its `task_id` and compare against the mapping key passed in (requires threading the
key through — change `_state_kind(state)` to `_state_kind(task_id, state)` and thread through its
one call site in `project_workflow_eligibility`'s loop and `_validate_revision_copies`'s callers as
needed). On mismatch, raise a new `WorkflowEligibilityRejectionCode.TASK_IDENTITY_MISMATCH` rather
than accepting. Add a negative test: task-2's completed `RunState` supplied under `"task-1"` must
raise, not return `complete`.

### 14.2 [P1] Eligibility silently repairs out-of-order committed work instead of failing closed

The projection loop returns the first non-complete task and stops — it never checks whether a
*later* task_id's state is already in-flight/complete while an earlier one is not. A lineage where
task 2 completed before task 1 ever ran (a real ordering violation, since Option A's per-task runs
are independently addressable) is normalized into "task 1 next, then already-complete task 2"
instead of being rejected.

**Fix:** after computing `_state_kind` for every task in order, if any task's kind is anything
other than `"not_started"` while an earlier task's kind is not `"complete"`, raise a new
`WorkflowEligibilityRejectionCode.TASK_ORDER_VIOLATION` before returning a normal
`NEXT_TASK`/`WORKFLOW_COMPLETE` result. Add negative tests: task-1 `not_started` + task-2
`in_flight`; task-1 `not_started` + task-2 terminal-PASS `complete`.

### 14.3 [P1] The fail-closed eligibility/divergence projection is never called on the real execution path

`run_workflow()` just loops `tasks` in order and calls `run_one_task()` unconditionally for each —
it never calls `project_workflow_eligibility()` at all. `_validate_revision_copies`'s divergence
check therefore never runs against real committed state.

**Fix (bounded to this slice, no new contract field, no new persistent workflow-identity concept):**
add a read-only lookup — `kernel/publish.py` gains
`find_committed_run_for_idempotency_key(state, idempotency_key, expected_digest) -> str | None`,
a thin wrapper around the existing `_find_genesis_idempotent_publish` lookup path with **no
side effect when no match is found** (unlike `publish()`, it must never create a new run as a
side effect of looking). In `run_workflow()`, before executing each task in sequence: compute that
task's `request` idempotency key from the *current* `tasks` argument, look up any already-committed
run via the new helper, and if found, `kernel.replay.replay(state, run_id)` it into a
`task_runs: dict[str, RunState]` entry for that task_id. Once all already-committed task runs (if
any) are collected, call `project_workflow_eligibility(candidate_revision, task_runs)` — where
`candidate_revision` is a `WorkflowRevisionV1`-shaped stand-in built from `tasks` for the purpose of
this call (request ref can be a placeholder since `project_workflow_eligibility` only reads
`.tasks` off it) — and only then proceed with the loop, using the projection's verdict
(`NEXT_TASK`/`WORKFLOW_COMPLETE`/`WORKFLOW_BLOCKED`) to decide whether to call `run_one_task` for
each task rather than blindly calling it regardless. Any `WorkflowEligibilityRejected` raised here
(including `WORKFLOW_REVISION_DIGEST_DIVERGENCE`, §4.2's cross-run digest-agreement check) must
propagate as a typed driver-level failure, not be swallowed. Add an integration test: run task 1 to
completion, then call `run_workflow()` again with task 1 replaced by a different task at the same
`task_id` (same task_id, different `objective`/`acceptance_criteria` — a genuinely different tasks
digest) — must raise divergence, not silently start a fresh, unrelated run.

### 14.4 [P1] `run_workflow()` reuses one `expected_output_digest` for every task

A single `expected_output_digest` parameter is forwarded unchanged to every `run_one_task()` call.
Any real (non-`noop`) multi-task workflow where task 1 and task 2 produce different workspace
snapshots cannot verify correctly — one of the two tasks is guaranteed to fail verification
regardless of which single digest is chosen. The existing `test_run_workflow.py` uses `noop` for
both tasks, which masks this because a no-op task's output digest never changes.

**Fix (driver-API-only change, no contract change):** `run_workflow()`'s
`expected_output_digest: str` parameter becomes `expected_output_digests: tuple[str, ...]` — same
length as `tasks`, index-aligned — and it passes `expected_output_digests[i]` to each
`run_one_task()` call instead of one shared value. Update the one existing caller
(`test_run_workflow.py`) and add a new 2-task integration test where both tasks actually mutate the
workspace (not `noop`) and have distinct expected output digests, proving both tasks can pass in
the same workflow.

### 14.5 [P2, codex inline finding, `run_one_task.py:395`] Crash-resume rebuilds and republishes the Attempt Packet before checking for an existing committed one

If the process crashes after publishing the Result (workspace already mutated) and is reinvoked,
`run_one_task()` unconditionally calls `build_attempt_packet()` from the *current* (now-modified)
workspace and republishes it under the same attempt idempotency key before ever reaching the
`existing_result` lookup — the freshly-rebuilt packet has a different `workspace_snapshot_digest`
than the originally-committed one, so `publish()` rejects with
`IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_CONTENT` instead of resuming.

**Fix:** mirror the existing `_read_existing_contract`/`existing_result` pattern already used for
Result/Verification/Receipt — before calling `build_attempt_packet`, call
`_read_existing_contract(state, request_published.run_id, ContractKind.ATTEMPT_PACKET)`; if found,
reuse the committed `AttemptPacketV1` (skip `build_attempt_packet` and the `publish()` call
entirely) instead of rebuilding from the current workspace. Add a crash-resume regression test:
publish through Result, mutate the workspace out-of-band (simulating a completed side effect before
a crash), reinvoke `run_one_task` with the same arguments, assert it reuses the committed Attempt
Packet rather than raising `IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_CONTENT`.

### 14.6 [P2, codex inline finding, `run_one_task.py:126`] Workflow idempotency key omits Request identity

`workflow_record_idempotency_key()` derives its key from `(tasks_digest, task_id, record)` only.
Two distinct Requests that happen to decompose into an identical task sequence derive the same
genesis key for task 1's `"request"` record; since genesis idempotency keys are searched globally
across all runs (`_find_genesis_idempotent_publish`), the second, independently-valid Request is
rejected with `IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_CONTENT` instead of starting its own run.

**Fix:** fold the Request's own content identity into the key namespace — since `request` (the
`RequestV1` value) is already a parameter available before any key is computed, add
`request_identity = content_digest(request.to_canonical_value())` and include it in
`workflow_record_idempotency_key()`'s digested payload (alongside `workflow_revision_digest`,
`task_id`, `record`) for every per-task record, not only downstream ones. This is a pure key-
derivation change — no contract/schema field changes. Add a regression test: two distinct
`RequestV1` values (different `objective`) with identical `tasks` sequences must each get their own
run, not collide.

### Dispatch

All 6 fixes above are bounded to `kernel/workflow_eligibility.py`, `kernel/publish.py` (one new
read-only helper), and `execution/run_one_task.py` — no protocol/contract schema version bump, no
change to `_kind_binding_rejection`'s existing genesis-binding check. Dispatched for implementation
in the same worktree (`m7-orchestration-expansion-slice1`) on top of `a4f6121`.
