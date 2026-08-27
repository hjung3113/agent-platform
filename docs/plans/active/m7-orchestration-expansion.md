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
completion, then call `run_workflow()` again for the *same* `tasks` sequence with task 1's
`RunState` mutated out-of-band into an order-violating shape (task 2 marked complete while task 1
is not) — must raise `TASK_ORDER_VIOLATION` (§14.2), not silently proceed.

**Correction — found by the implementing agent on first dispatch, not the review, same class as
the §4.4 addendum above:** the original wording of this fix additionally required an integration
test proving that calling `run_workflow()` again with task 1's *content changed* (different
`objective`/`acceptance_criteria` under the same `task_id`) raises `WORKFLOW_REVISION_DIGEST_
DIVERGENCE` rather than starting a fresh run. `codex --model gpt-5.6-luna -c
model_reasoning_effort="max"` correctly stopped before writing code and reported that this cannot
be made true under the lookup mechanism this same fix specifies: the per-task idempotency key
*is* `content_digest({"tasks": [...]})` folded in (§4.2, §14.6) — changing task 1's content changes
every downstream key, so `find_committed_run_for_idempotency_key` looks up a key that was never
written and correctly returns "not found." There is no divergence signal to raise; the two
sequences are, by this slice's own content-addressed design, two different workflows, not one
workflow whose revision diverged. Requiring the "raise divergence" test was an error in this
directive's own drafting, not a real gap in the implementation being planned.

**Fixed by retraction, not by inventing new lookup machinery:** `_validate_revision_copies`'s
cross-run digest-agreement check remains in `workflow_eligibility.py` (harmless, and it does still
apply to `task_runs` maps assembled by *other* callers that do not derive their keys the same
way this slice's driver does) but is **structurally unreachable from `run_workflow()`'s own
call path** — every `task_runs` entry `run_workflow()` can ever assemble via
`find_committed_run_for_idempotency_key` is, by construction of the key, already guaranteed to
share the current `tasks` digest. This is the same class of documented, deliberately-kept dead
scaffold as M4's `OmissionRecord`/optional-candidate machinery (see HANDOFF.md's carried-forward
scope limits) — not a defect to route around with a new task_id-only cross-digest run index, which
would be a real structural addition (a scan-all-runs-by-task_id index) out of this slice's bounded
scope. Detecting "a caller changed task 1's content and calls it the same workflow" is not a
guarantee this slice's content-addressed design makes or needs to make; nothing downstream depends
on it. Revisit only if a later milestone gives workflows a persistent identity independent of task
content (out of scope here, likely M7's own later steps or never).

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

---

# M7 — Slice 2: DAG Dependency Validation and Deterministic Eligibility

Status: **Draft, not yet reviewed** (pre-implementation adversarial review pending)
Tracker: Issue #4 (same tracker as slice 1)
Milestone: **M7, slice 2 of N** — roadmap expansion-order step 2 only

Slice 1 (above) landed and merged (`062c580`) as a strictly linear multi-task Workflow Revision:
ordering is pure array position, "dependency" means only "comes after the previous array index."
This slice implements the roadmap's step 2 — **DAG dependency validation and deterministic
eligibility** — and nothing past it. All baseline citations below are checked against `main` at
`df89f48` (post-slice-1-merge HEAD), not the roadmap's general vocabulary.

## S1. Scope decision: only step 2, not step 3 or later

The roadmap's M7 section (`mvp-implementation-roadmap.md` lines 323–341) explicitly separates
step 2 ("DAG dependency validation and deterministic eligibility") from step 3 ("logical Resource
Claims with read/write conflict semantics") and warns against implementing a later step merely
because Spec 04 names it in the same paragraph as the Workflow Revision contract's full field
list (`docs/specs/04-workflow-orchestration.md` lines 9–15, which names dependency edges,
resource claims, risk/policy, retry/repair/replan limits, and fan-in policy all in one bulleted
contract). This slice implements **only** the dependency-edge and eligibility-set bullets. It
does **not** add a resource-claim field, a risk/policy field, retry/repair/replan machinery, or a
fan-in merge-policy field to `TaskV1`/`WorkflowRevisionV1` — those remain exactly as absent as
slice 1 left them (verified: `grep -rn "resource_claim\|risk_profile\|admitted_policy\|fan_in" product/src/` returns nothing).

**Slice 2 proves:** an admitted Workflow Revision's tasks can declare explicit dependency edges
(not just array position); Kernel admission rejects unknown task references, self-dependencies,
structural cycles, and duplicate/ambiguous edges for the same task, at the same admission
boundary slice 1 used for duplicate `task_id` (reader + publish-time defense-in-depth); the
eligibility projection computes a real **eligible set** (every task whose dependencies are all
satisfied) and a deterministic tie-break **next action** over that set, per Spec 04's "the
eligible task set must be identical... task ordering must be identical... the selected next
action must be identical" (`04-workflow-orchestration.md` lines 29–34); and a task whose
dependency chain includes a `FAIL`/`BLOCKED` ancestor is correctly reported blocked rather than
silently treated as still-pending or skipped.

**It does not prove:** resource-claim conflict detection (step 3); retry/repair/replan (steps
4–6); fan-in merge policy (step 7, though DAG admission does allow a task to declare more than
one dependency, i.e. converging edges — see S3's explicit note on why this is not fan-in);
reconciliation-required handling (step 8); or concurrent execution of independent-branch tasks
(step 9 — this slice's driver stays strictly sequential, one task materialized at a time, exactly
like slice 1, even though the DAG shape now permits more than one task to be simultaneously
eligible in principle).

## S2. Baseline (verified against `main` at `df89f48`)

- `kernel/protocol_v1.py:118–128` (`TaskV1`) — exactly `task_id`, `objective`,
  `acceptance_criteria`. No dependency-edge field of any kind.
- `kernel/protocol_v1.py:131–141` (`WorkflowRevisionV1`) — `request: RecordRef; tasks:
  tuple[TaskV1, ...]`. Ordering is purely array position; nothing in the schema states or
  enforces a dependency relationship between tasks beyond "index i precedes index i+1" as
  encoded in `workflow_eligibility.py`'s positional check (below).
- `kernel/protocol_v1.py:33` — `WORKFLOW_REVISION_SCHEMA_VERSION = 2` (slice 1's bump from the
  pre-M7 single-`task` shape). `kernel/protocol_v1.py:1167–1172` registers
  `read_workflow_revision_v1` at `(WORKFLOW_REVISION, 1, 2)`; `:1160–1166` retains
  `read_legacy_workflow_revision_v1` at `(WORKFLOW_REVISION, 1, 1)`, rejecting a `"tasks"` key
  with `UNSUPPORTED_SCHEMA_VERSION`. This is the exact precedent slice 2 reuses for its own
  schema bump (S4).
- `kernel/protocol_v1.py:528–545` (`_require_task_sequence`) — validates non-empty list, calls
  `_read_task_v1` per element, rejects duplicate `task_id` within the sequence
  (`MALFORMED_PAYLOAD`). This is the reader-level structural-validation idiom slice 2's
  dependency-graph checks extend (S4).
- `kernel/publish.py:322–335` (`_kind_binding_rejection`'s `WORKFLOW_REVISION` branch) —
  currently re-checks duplicate `task_id` as publish-time defense-in-depth (`:323–328`, same rule
  as the reader, checked at both layers — M1's stated precedent, restated by slice 1 §4.5) before
  the genesis-Request binding check (`:329–334`). No dependency-graph check exists here yet.
- `kernel/workflow_eligibility.py` (full file, 204 lines) — `project_workflow_eligibility`
  computes a per-task `_state_kind` (`not_started`/`in_flight`/`fail`/`blocked`/`complete`), then
  a **positional** order-violation check (`for index, kind in enumerate(state_kinds): if kind !=
  "not_started" and any(earlier_kind != "complete" for earlier_kind in state_kinds[:index])`,
  lines 182–189) — "earlier" means "lower array index," not "declared dependency" — then returns
  the first non-complete task in array order as `NEXT_TASK`, or the first `fail`/`blocked` task
  as `WORKFLOW_BLOCKED`. `WorkflowEligibility` (lines 43–61) exposes a single `task`, not a set.
  `_validate_revision_copies` (lines 85–102) is the unchanged cross-run digest-agreement check
  from slice 1 (§4.2 of the slice-1 plan) — it compares whole-`tasks`-sequence digests and is
  unaffected by adding a field to `TaskV1`, since it will still digest whatever `TaskV1.
  to_canonical_value()` returns, tested by S9.
- `execution/run_one_task.py:510–610` (`run_workflow`) — the driver's `while True` loop
  recomputes `project_workflow_eligibility` every iteration (good — this generalizes to DAGs
  without change), but on `NEXT_TASK` it does `eligible_index = task_ids.index(eligibility.task
  .task_id); for index in range(eligible_index + 1): materialize(index)` (lines 607–610), and on
  `WORKFLOW_BLOCKED` it does the same up to and including the blocked index (lines 596–600).
  **Both loops assume array index implies "everything before it is already done or must be
  materialized in that order"** — true only under slice 1's strict linear semantics. Under a DAG
  this is actively wrong: task 3 could be array-index 1 (declared early) but depend on task 5
  (declared late), and materializing "every index up to the eligible one" would try to run tasks
  the eligible task does not actually depend on, out of dependency order, before their own
  dependencies are satisfied. This must change (S5).
- `kernel/replay.py` — the `WORKFLOW_REVISION` fold branch (merged with
  `_LegacyWorkflowRevisionV1` per slice 1 §4.6) folds whatever `WorkflowRevisionV1`/
  `_LegacyWorkflowRevisionV1` value is committed, unchanged by content shape — adding a field to
  `TaskV1` needs no replay-fold change, only a schema-version-aware reader change (S4), the same
  way slice 1 added `tasks` without touching the fold's dispatch structure beyond the one new
  `isinstance` arm.
- `docs/specs/04-workflow-orchestration.md` lines 6–34 — normative source for S3/S5's design
  (dependency edges, admission rejection list, eligible-set/ordering/next-action determinism,
  dependency-satisfaction-by-explicit-condition-only).
- ADR-0009 and `execution/policy.py`'s fixed global capability table — **rechecked, still zero
  risk-tier/Plan-Check code anywhere in `product/src/`** (same grep as slice 1 §1, re-run against
  current HEAD, same empty result). DAG dependency validation does not require risk-tier
  computation — a dependency edge is a structural fact about task ordering, not a policy
  judgement — so ADR-0009's split stays deferred for the same reason slice 1 deferred it,
  unaffected by this slice.

## S3. Design decision: `TaskV1.depends_on`, resolved in-plan (not escalated)

**The question:** does `workflow_eligibility.py` get extended in place, or does DAG eligibility
become a separate module, per `HANDOFF.md`'s explicit "don't assume either way going in"?

**Resolution:** extend in place — not a genuine architecture fork, because the module's own
docstring already states its real contract at the right level of abstraction: "reads only an
admitted task sequence and replayed per-task lineage" and "does not publish records, inspect
runtime state, or mutate a derived cache" (`workflow_eligibility.py:1–6`). Nothing about that
contract is linear-specific — `_state_kind` (per-task terminal-state classification),
`_validate_revision_copies` (cross-run digest agreement), and the overall pure-projection shape
are unchanged by moving from "index i precedes i+1" to "task A precedes task B iff B declares A
in `depends_on`." Only the order-violation check and the eligible/next-task selection logic
change. A separate module would duplicate `_state_kind`/`_validate_revision_copies` or import
them from the "linear" module under a name that no longer describes what it does — worse on both
AGENTS.md rule 1 (reuse before invention) and rule 13 (smallest mechanism). The module is
renamed in its docstring only (not its filename or public function names, which are already
generic — `project_workflow_eligibility`, not `project_linear_eligibility`) to describe DAG
projection instead of linear projection.

**The dependency field:** `TaskV1` gains `depends_on: tuple[str, ...]` — each element a
`task_id` string referencing another task in the same `WorkflowRevisionV1.tasks` sequence.
Order within `depends_on` is declaration order (digested as given, like `acceptance_criteria` —
no canonicalization/sorting is applied, so two revisions listing the same dependency set in a
different order are legitimately different committed content with different digests; this is
consistent with every other tuple-shaped field in this protocol and is not a new inconsistency
slice 2 introduces). A task with an empty `depends_on` tuple has no dependencies (eligible as
soon as `not_started`, same as every slice-1 task).

**Converging edges are allowed, and this is explicitly not fan-in (step 7):** a task may name
more than one entry in `depends_on` (e.g. task C depends on both A and B). Spec 04 requires "an
explicit admitted completion condition" per edge — for this slice, the completion condition for
every edge is simply "the named task's per-task run is terminal-`complete`" (dependency
satisfaction is boolean-AND across `depends_on`, no partial-success or artifact-level condition).
This is deliberately not fan-in: fan-in (Spec 04 lines 36–45, "Dependency and fan-in semantics")
requires a declared **merge
strategy**, **conflict behavior**, and **an authority responsible for producing a merged
candidate** when multiple upstream *results* must be combined into one artifact/decision. Slice 2
adds no merge-strategy field, no conflict-behavior field, and does not attempt to combine
task C's upstream Results into anything — C's own Attempt/Result/Verification chain runs exactly
as any slice-1 task's does, using C's own workspace and its own task objective/acceptance
criteria; C merely cannot start until A and B are both `complete`. Recorded explicitly per this
plan's own "not silently dropped" discipline.

**Named Spec 04 conformance deviations (added after round-1 review, MEDIUM-2 — three normative
readings this slice fixes rather than leaves implicit, per slice 1 §11 MEDIUM 3's own
named-deviation discipline and roadmap Lens E's "resolve normative contradictions in the design
doc, not as local guesses"):**

1. Spec 04 line 11/34's "deterministic ordering/tie-break metadata" is satisfied by the revision's
   own `tasks` array order — this slice adds no separate tie-break field. The ordered tuple *is*
   the revision-bound canonical ordering; array position was already load-bearing for slice 1's
   identical requirement and nothing about a DAG changes that.
2. Spec 04 line 10/37's per-edge "dependency satisfaction condition" is fixed at the protocol
   version level (schema v3) to a single universal condition — "the named predecessor's per-task
   run is terminal-`complete`" — rather than being admitted per-edge contract content. No
   candidate can express a different condition for a different edge this slice.
3. Spec 04 line 17's "incompatible graph references" admission-rejection case is vacuously
   satisfied for this slice: `depends_on` entries are intra-revision `task_id` strings only, with
   no cross-revision or external reference expressible at all, so there is no reference shape that
   could be "incompatible" beyond the four cases S4 already rejects (unknown, self, duplicate,
   cyclic).

## S4. Contract shape change

`TaskV1` (`protocol_v1.py:118–128`) gains `depends_on: tuple[str, ...]`. `to_canonical_value()`
adds `"depends_on": list(self.depends_on)`. Because `TaskV1` is only ever read as part of a
`WorkflowRevisionV1` payload (never published standalone), the shape change is versioned the same
way slice 1 versioned the `task` → `tasks` change: bump `WORKFLOW_REVISION_SCHEMA_VERSION` from
`2` to `3`, add `read_workflow_revision_v1_v3` (or extend the existing function name — naming
follows whatever convention the implementer finds already established; the substance is a new
reader registered at `(WORKFLOW_REVISION, 1, 3)`), and retain the current `read_workflow_revision_v1`
(today's v2 reader, no `depends_on`) at `(WORKFLOW_REVISION, 1, 2)` as the new legacy reader for
that version — following the exact `read_legacy_workflow_revision_v1` precedent already in the
file (a v2-schema payload carrying a `"depends_on"` key inside any task object is rejected
`UNSUPPORTED_SCHEMA_VERSION`, mirroring `read_legacy_workflow_revision_v1`'s existing `"tasks"`-key
check at the v1→v2 boundary). `kernel/replay.py`'s fold needs no new `isinstance` arm — v2 and v3
`WorkflowRevisionV1` values are still the same Python type (`depends_on` is just a field on the
nested `TaskV1`), unlike the v1→v2 change which was a genuine type change (`_LegacyWorkflowRevisionV1`
vs `WorkflowRevisionV1`). Only the pre-M7 single-`task` legacy type (v1) still needs its own fold
branch, already present since slice 1.

**Reader fork, made explicit (added after round-1 review, MEDIUM-1 — "today's v2 reader
retained" is unimplementable as a bare statement because the v1-legacy, v2-legacy, and v3 readers
currently share `_read_task_v1`/`_TASK_KEYS`/`_require_task_sequence`, and `depends_on` is a
required field on `TaskV1` per S9's own fixture-migration test):** `depends_on` is a required
constructor field on `TaskV1` (default-free, matching `task_id`/`objective`/`acceptance_criteria`
— no silent `None`/optional shape). This means the retained v1 and v2 legacy readers cannot reuse
`_read_task_v1` unchanged; they must construct `TaskV1(..., depends_on=())` explicitly. Concretely:
a new `_TASK_V3_KEYS` (or `_read_task_v1` parameterized by an explicit key set/depends-on flag) is
added for the v3 reader only; the retained v2 reader gets its own task-reading path that rejects a
`"depends_on"` key inside any task object with `UNSUPPORTED_SCHEMA_VERSION` (mirroring
`read_legacy_workflow_revision_v1`'s existing `"tasks"`-key check at the v1→v2 boundary, not a bare
`_require_exact_keys` call, which would return the wrong rejection code) and otherwise constructs
`TaskV1(..., depends_on=())`; the v1 reader is unaffected beyond the same explicit
`depends_on=()` construction, since it never had a `depends_on` key to reject in the first place.
This is the same fork the existing `read_legacy_workflow_revision_v1` precedent already performs
with `_LEGACY_WORKFLOW_REVISION_KEYS`/`_LEGACY_COVERAGE_ENTRY_KEYS` — slice 2 extends the same
pattern one level deeper (per-task key sets, not just per-revision key sets), it does not
introduce a new one.

**Reader-level structural validation (new `_validate_task_dependency_graph` helper, called from
both the reader and the publish-time defense-in-depth check per S5 — one implementation, two call
sites, matching AGENTS.md rule 13):**

- **Unknown task reference:** every `task_id` named in any `depends_on` must appear as some
  task's own `task_id` in the same `tasks` sequence. Reject `MALFORMED_PAYLOAD` (reader) /
  a new `PublishRejectionCode.WORKFLOW_REVISION_UNKNOWN_DEPENDENCY` (publish defense-in-depth) —
  naming follows the existing `WORKFLOW_REVISION_TASK_ID_DUPLICATE` precedent
  (`publish.py:PublishRejectionCode`) for a per-revision structural defect.
- **Self-dependency:** a task naming its own `task_id` in its own `depends_on`. Reject
  `MALFORMED_PAYLOAD` / `WORKFLOW_REVISION_SELF_DEPENDENCY`.
- **Duplicate edge (ambiguous dependency semantics):** the same `task_id` appearing more than
  once in one task's `depends_on` tuple. Reject `MALFORMED_PAYLOAD` /
  `WORKFLOW_REVISION_DUPLICATE_DEPENDENCY` — Spec 04 explicitly lists "ambiguous dependency
  semantics" as a required-rejection case (line 17), and a duplicated edge has no meaning beyond
  a single edge, so treating it as accepted-but-redundant would silently paper over malformed
  input rather than failing closed.
- **Structural cycle:** cycle detection over the directed graph `task_id → depends_on` **must use
  an iterative algorithm (Kahn's-algorithm topological sort, failing if any node is never
  dequeued), not recursive DFS** (added after round-1 review, LOW-1 — a hostile or generated deep
  chain, e.g. 10⁴+ tasks or a long cycle, would raise an unhandled `RecursionError` under
  recursive DFS instead of a typed `MALFORMED_PAYLOAD` rejection, breaking this reader's
  fail-closed-typed contract). Run once over the full `tasks` sequence after every task's own
  `depends_on` list has been individually validated against the three checks above. Reject
  `MALFORMED_PAYLOAD` / `WORKFLOW_REVISION_DEPENDENCY_CYCLE`.
- **Prerequisite (added after round-1 review, LOW-1):** each task's `depends_on` is validated as a
  string sequence with `allow_empty=True` (reusing `_require_string_sequence`, `protocol_v1.py:
  509–525` — *not* `acceptance_criteria`'s `allow_empty=False` call shape, which would wrongly
  reject every dependency-free task's empty tuple) before any of the four structural checks run.

All four checks are pure functions of the candidate's own `tasks` sequence — no lineage lookup,
no I/O — matching every other reader-level validation in this file.

## S5. Publish-boundary defense-in-depth

`kernel/publish.py`'s `_kind_binding_rejection` `WORKFLOW_REVISION` branch (currently: duplicate
`task_id` check, then genesis-Request binding check — `publish.py:322–335`) gains a call to the
same `_validate_task_dependency_graph` helper (S4) immediately after the existing duplicate-
`task_id` check and before the genesis-Request binding check, returning the same typed
rejections. This is defense-in-depth only (a malformed candidate should already be rejected by
the reader before `publish()` is ever called with a parsed value) — matching slice 1 §4.5's own
stated rationale for checking duplicate `task_id` at both layers.

## S6. Eligibility change (`kernel/workflow_eligibility.py`)

**`WorkflowEligibility` gains a new field, additive:**

```python
@dataclass(frozen=True)
class WorkflowEligibility:
    status: WorkflowEligibilityStatus
    task: TaskV1 | None = None          # unchanged: the deterministic tie-break "next action"
    reason: str = ""
    eligible_tasks: tuple[TaskV1, ...] = ()   # new: the full ready set, Spec-04-required
```

(field order changed after round-1 review, LOW-3 — `eligible_tasks` is appended **after**
`reason`, not inserted before it, so any future positional-argument construction cannot silently
bind `reason`'s string into `eligible_tasks`'s tuple slot; all three current call sites already use
keyword arguments and are unaffected.)

`task` keeps its slice-1 meaning (the single task the driver should materialize next) so slice
1's own tests and `run_workflow`'s existing `eligibility.task` reads keep working unchanged.
**`eligible_tasks` is every task with state kind `not_started` *or* `in_flight`** whose entire
`depends_on` set has state kind `complete`, in **declaration order** (the same "array order is the
deterministic tie-break rule" choice slice 1 already made for its own ordering bullet, §4.1 of the
slice-1 plan, now doing real tie-break work for the first time since more than one task can be
simultaneously ready). `task` is `eligible_tasks[0]` when `eligible_tasks` is non-empty and status
is `NEXT_TASK`.

**Correction after round-1 review (HIGH-1):** the draft definition above originally read "every
**not_started** task" only, which silently dropped slice 1's in-flight-resume rule (§8 of the
slice-1 plan, proven by `test_in_flight_task_is_eligible_for_resume`) — an `in_flight` task
(Attempt Packet committed, no Result yet, e.g. a crash mid-chain) with satisfied dependencies must
still be resume-eligible and still be the selected `task`, exactly as it already is under slice
1's positional rule. Fixed in the definition above (`not_started` **or** `in_flight`) rather than
left as a draft error; S9 gains an explicit test for both the in-flight-with-satisfied-deps case
(eligible, selected) and the in-flight-with-unsatisfied-dep case (impossible in practice since a
committed Attempt Packet implies its own dependencies were already satisfied when it was
materialized, but the order-violation check below still covers it defensively for any state that
should never occur).

**Order-violation check, generalized from positional to dependency-based:** the existing check
(lines 182–189) — "no task may be anything but `not_started` while an earlier-index task is
incomplete" — becomes "no task may be anything but `not_started` while any task it
`depends_on` is not `complete`." The rejection code stays `TASK_ORDER_VIOLATION` (its name
already reads correctly for the generalized meaning — "an ordering constraint was violated,"
whether the constraint was positional or graph-based — introducing a second, near-duplicate code
for the same failure class would fragment the enum without adding real information for a
caller deciding how to react). This is a deliberate reuse, called out here so a reviewer does not
mistake it for a missed rename.

**Blocking semantics — explicit scope decision, not escalated (documented per AGENTS.md rule
10):** if **any** task's state kind is `fail` or `blocked`, the overall workflow status is
`WORKFLOW_BLOCKED`, exactly like slice 1 — even if other, dependency-independent branches still
have tasks that would otherwise be `eligible_tasks`. The alternative (report `NEXT_TASK` for
still-progressable independent branches while one branch is blocked) was considered and
rejected for this slice: it would require the driver to safely continue materializing one
branch while another sits blocked, which is a real form of "proceeding with partial workflow
state" that step 9 ("proven-safe parallel execution") and steps 4–6 (retry/repair/replan, which
govern *how* a blocked branch might ever become unblocked) are the roadmap's named place for —
introducing it here would be exactly the "build DAG scheduling... before the one-task path is
trustworthy" mistake the roadmap's own adversarial-review Lens D warns against (line 79),
applied one layer up: partial-branch continuation before single-branch blocking is even proven.
Slice 2's `eligible_tasks` field still reports the true ready set (useful for tests and future
slices to consume), but `project_workflow_eligibility`'s **status** stays `WORKFLOW_BLOCKED`
workflow-wide the instant any task is `fail`/`blocked`, matching slice 1's existing fail-closed
posture rather than inventing new partial-continuation semantics. If this default should be
different, it is a plan/roadmap decision, not a "figure it out during implementation" gap — this
slice takes the conservative default without escalating because slice 1's identical posture was
never itself flagged as a defect by either review round, and the roadmap explicitly assigns
per-branch continuation logic to later, named steps.

## S7. Driver change (`execution/run_one_task.py`)

The `run_workflow` loop's `for index in range(eligible_index + 1): materialize(index)` /
`for index in range(blocked_index + 1): materialize(index)` patterns (lines 596–600, 607–610)
are **positional and DAG-incompatible** — they must change regardless of what "index" would mean
under a DAG, because eligibility no longer implies "everything at a lower index is done or must
be run first." The fix is a simplification, not just a compatibility shim: since
`project_workflow_eligibility` is recomputed fresh every loop iteration and already guarantees
(via the order-violation/dependency check, S6) that a task it reports as `NEXT_TASK`/
`eligible_tasks[0]` has every dependency already `complete`, the driver needs to materialize
**only that one task**, not a range:

```python
while True:
    eligibility = project_workflow_eligibility(candidate_revision, task_runs)
    if eligibility.status is WorkflowEligibilityStatus.WORKFLOW_COMPLETE:
        for task_id in task_ids:
            materialize_by_task_id(task_id)
        return RunWorkflowResult(task_results=tuple(results))
    if eligibility.status is WorkflowEligibilityStatus.WORKFLOW_BLOCKED:
        for task_id in task_ids:
            if state_kind_of(task_id) != "not_started":
                materialize_by_task_id(task_id)
        return RunWorkflowResult(
            task_results=tuple(results),
            blocked_task=eligibility.task,
            reason=eligibility.reason,
        )
    assert eligibility.task is not None
    materialize_by_task_id(eligibility.task.task_id)
```

where `materialize_by_task_id` is the existing `materialize` closure (lines 566–588) with its
`index: int` parameter changed to `task_id: str` and its `task = tasks[index]` line changed to a
`task_id → TaskV1` lookup (a dict built once from `tasks`, mirroring the existing
`task_ids = tuple(task.task_id for task in tasks)` line's own precedent for precomputing
task-identity structures). `RunWorkflowResult` and its `blocked_task`/`workflow_complete`
properties are unchanged (S8 confirms no result-shape change). This also fixes a latent
inefficiency in slice 1's own code, noted here rather than silently carried forward: slice 1's
range-based materialize already redundantly re-materializes already-complete earlier tasks every
iteration (a cheap no-op via `materialized.get(task.task_id)`, but still a wasted loop) — the
single-task materialize removes that waste as a side effect of the DAG fix, not as a separate
unscoped optimization.

**Correction after round-1 review (HIGH-2):** the original sketch returned immediately on
`WORKFLOW_COMPLETE`/`WORKFLOW_BLOCKED` without materializing anything, which breaks the exact
idempotent-re-invocation and crash-resume guarantees S9/S12 require and slice 1 already
established (§9, §14.3): `results`/`materialized` are process-local and start empty on every
fresh `run_workflow` call, so a re-invocation against an already-completed or already-blocked
workflow must still re-materialize every task with committed lineage to reconstruct
`task_results` — this is a safe idempotent no-op via each materialize call's existing
`materialized.get(task_id)` short-circuit, not a re-execution. The reviewer's finding that the
complete-branch loop is *not* actually DAG-incompatible (materializing every already-complete task
in any order is a safe recovery no-op regardless of array position) is correct and is why the
complete/blocked branches above loop over `task_ids` directly rather than through
`eligible_tasks` — only the `NEXT_TASK` branch needed the DAG-aware single-task rewrite; the
recovery branches only needed their index-range replaced with a task_id-keyed iteration. On
`WORKFLOW_BLOCKED`, every task whose state kind is not `not_started` (i.e. `in_flight`,
`complete`, `fail`, or `blocked` — anything with committed lineage) is materialized, including the
blocked task's own chain; a genuinely `not_started` independent branch is never touched, matching
S6's blocking-scope decision (blocked status is workflow-wide, but materialization still only
touches tasks that actually ran). `state_kind_of` is the same per-task state-kind classification
`project_workflow_eligibility` already computes internally (`_state_kind`), threaded through or
recomputed identically — not a new concept.

## S8. What slice 2 deliberately does not change

- `kernel/lineage_store.py`, `kernel/publish.py`'s `_NEXT_KIND`/`_committed_contract` — unchanged
  (Option A, slice 1 §3, still holds: DAG dependency validation is purely a Workflow-Revision-
  shape and eligibility-projection concern, not a per-run cardinality concern).
- `AttemptPacketV1`, `ResultV1`, `VerificationV1`, `ReceiptV1`, `execution/policy.py`,
  `verification/stub_verifier*.py` — completely unchanged, same as slice 1 §5.
  **Correction after implementation blocker (round 1 dispatch, BLOCKER
  `PLAN_CONTRADICTION_FROZEN_VERIFIER_TASK_SHAPE` — resolved in-plan, no real tradeoff, same
  precedent as slice 1 §4.4):** the bullet above is over-broad by exactly one file.
  `execution/run_one_task.py:218` sends `task.to_canonical_value()` to the verifier subprocess,
  and `verification/stub_verifier_cli.py::_read_task` (lines 33–47) requires the task key set to
  be exactly `{task_id, objective, acceptance_criteria}` — so S4's canonical-payload change
  breaks every real verification (`task_keys_mismatch`) while S9 still demands the real-binary
  end-to-end DAG driver. Resolution: `stub_verifier_cli.py`'s `_read_task` gains a **mechanical
  wire-shape update only** — accept `depends_on` as a key (required in the payload it receives,
  validated as an `allow_empty=True` string sequence), pass it into the `TaskV1` constructor —
  and `product/tests/verification/test_stub_verifier_cli.py` gains the matching fixture update.
  Verifier semantics (coverage/verdict/execution-identity logic, `stub_verifier.py` itself) are
  unchanged; `stub_verifier.py` consumes a `TaskV1` object in-process and needs no change. This
  file is hereby added to the touch allowlist for that single function's key-set/constructor
  update and nothing else.
- `workflow_record_idempotency_key`/`workflow_task_sequence_digest`
  (`execution/run_one_task.py:115–136`) — unchanged in *code shape*; they already digest
  `task.to_canonical_value()` for every task in the sequence, so a `depends_on` field
  automatically participates in the existing digest without any code change (verified by S9's
  digest-regeneration test, not assumed). **This is not idempotency-neutral — see the explicit
  decision below (HIGH-3, added after round-1 review).**
- **Idempotency-key orphaning across the v2→v3 upgrade — decided explicitly, not left implicit
  (HIGH-3, round-1 review):** adding `"depends_on": []` to `TaskV1.to_canonical_value()` changes
  `workflow_task_sequence_digest` for every task, *including* pre-slice-2 tasks with no
  dependencies, because the digested value now has an extra key that wasn't there before. Every
  committed slice-1-era workflow's per-record idempotency keys were derived from the old digest.
  Post-upgrade, re-invoking `run_workflow` on a slice-1-era workflow (completed, blocked, or
  in-flight) derives new keys that miss the startup idempotency lookup
  (`run_one_task.py:551–561`), so eligibility sees the whole workflow as fresh `not_started` and
  the driver publishes a new genesis Request and re-executes the entire workflow in new runs. No
  record is corrupted — every new run is internally correct and fail-closed — but this **is** a
  real behavior change for pre-upgrade history, and this plan accepts it explicitly rather than
  silently: it is the v2→v3 analogue of pre-M7 single-task runs already being non-resumable
  through `run_workflow`, and the per-task binding digests that actually gate re-execution safety
  (`attempt.py:96–98`, `host.py:311–312`) are unaffected — both sides recompute post-upgrade and
  agree, so no unsafe reuse or corruption is possible, only a fresh run-set instead of a resumed
  one. S9 gains an explicit test asserting this documented behavior (re-invoking a v2-era
  completed/blocked workflow under v3 code starts a fresh run-set, no reuse, no crash) so the
  consequence is proven, not assumed.
- `RunWorkflowResult`'s public shape (`execution/run_one_task.py:94–112`) — unchanged; S7's
  driver-loop rewrite is an internal implementation change only. **Observable ordering of
  `task_results` does change** (added after round-1 review, LOW-2): under slice 1's linear
  execution, `results` append order equals `tasks` array order; under a DAG, materialization order
  is eligibility-driven declaration order among ready tasks, so `task_results` can legitimately
  differ from `tasks` array order (e.g. the task at array index 2 completing before index 1). This
  is a real, if minor, observable change to a public result type and is named here rather than
  left for a caller to discover. Similarly, the per-task `expected_output_digests[index]` lookup
  (slice 1 §14.4's fix) moves to the same `task_id → TaskV1` map S7 already builds, alongside the
  materialize lookup — not a separate change.
- `kernel/replay.py`'s fold structure — unchanged (S4: no new Python type, only a new schema
  version + new/legacy reader pair, exactly like a same-type field addition would be for any
  other contract).
- Resource claims, retry/repair/replan, fan-in merge policy, reconciliation, parallel execution —
  none of these gain any contract field or code path this slice (S1, S3's fan-in note).

## S9. Test plan

### Protocol/reader (`product/tests/contracts/test_protocol_v1_m7_slice2.py`, new)

- `TaskV1.depends_on` round-trips through `to_canonical_value()`/the v3 reader for a valid DAG
  (e.g. `A → []`, `B → []`, `C → [A, B]`)
- schema-version dispatch: a `schema_version=3` candidate with `depends_on` fields parses; a
  `schema_version=2` candidate whose task objects carry a `depends_on` key is rejected
  `UNSUPPORTED_SCHEMA_VERSION` by the (now-legacy) v2 reader; a `schema_version=2` candidate
  without `depends_on` still parses through the v2 reader unchanged (regression: slice 1's own
  shape must remain valid, un-migrated)
- unknown dependency reference rejected `MALFORMED_PAYLOAD`
- self-dependency rejected `MALFORMED_PAYLOAD`
- duplicate edge within one task's `depends_on` rejected `MALFORMED_PAYLOAD`
- two-node cycle (`A → [B]`, `B → [A]`) and three-node cycle (`A → [B]`, `B → [C]`, `C → [A]`)
  both rejected `MALFORMED_PAYLOAD`
- golden-digest fixtures regenerated for the v3 wire shape (following slice 1's own precedent,
  §9 of the slice-1 plan)
- replay regression: a v2-schema-committed `WorkflowRevisionV1` (no `depends_on`) still replays
  and folds correctly through the unchanged fold structure (S4)

### Publish boundary (`product/tests/kernel/test_publish_m7_slice2.py`, new)

- valid DAG publishes at the unchanged `WORKFLOW_REVISION` successor position (no `_NEXT_KIND`
  change)
- each of the four structural rejections (unknown reference, self-dependency, duplicate edge,
  cycle) also rejected at the publish boundary via the shared `_validate_task_dependency_graph`
  helper (S5) — proving the defense-in-depth call site actually fires, not just the reader

### Eligibility (`product/tests/kernel/test_workflow_eligibility_dag.py`, new)

- diamond DAG (`A → []`, `B → [A]`, `C → [A]`, `D → [B, C]`): only `A` eligible while nothing has
  run; after `A` completes, `eligible_tasks == (B, C)` in declaration order, `task == B` (tie-break);
  after `B` and `C` both complete, only `D` eligible; after `D` completes, `WORKFLOW_COMPLETE`
- `B` completing before `A` (an out-of-order committed lineage, the DAG analogue of slice 1's
  HIGH-2-era `TASK_ORDER_VIOLATION` case) — fails closed with `TASK_ORDER_VIOLATION`, not
  silently accepted
- `A` fails (`FAIL`/`BLOCKED` verdict): `WORKFLOW_BLOCKED` workflow-wide even though an unrelated
  independent task with no dependency on `A` would otherwise be `eligible_tasks`-ready (S6's
  documented scope decision — proves the decision is actually implemented, not just described)
- same fixture run twice → identical `eligible_tasks`, identical `task`, identical status
  (determinism, Spec 04's core requirement, same test shape as slice 1 §9's own determinism test)
- cross-run digest-agreement check (`_validate_revision_copies`, unchanged) still fires correctly
  when `TaskV1.depends_on` is part of what's compared — two per-task runs whose committed
  `tasks` sequences differ only in one task's `depends_on` value must be caught as
  `WORKFLOW_REVISION_DIGEST_DIVERGENCE`, proving the unchanged digest function actually covers
  the new field rather than assuming it does
- **(added after round-1 review, HIGH-1)** in-flight resume under a DAG: a diamond DAG with `A`
  complete and `B` `in_flight` (Attempt Packet committed, no Result) and satisfied deps reports
  `B` in `eligible_tasks` and as `task` (resume-eligible, not dropped from the ready set) —
  the DAG-generalized analogue of slice 1's `test_in_flight_task_is_eligible_for_resume`

### Driver (`product/tests/execution/test_run_workflow_dag.py`, new)

- the same diamond DAG executed end-to-end through the real fixture OpenCode binary (same
  pattern as slice 1's `test_run_workflow.py`): all four tasks reach terminal `PASS` Receipts in
  a dependency-respecting order (`A` before `B`/`C`, both before `D`), `run_workflow` reports
  workflow-complete
- `A` fails verification: `run_workflow` stops, `B`/`C`/`D` never get Attempt Packets published
  (the DAG analogue of slice 1's linear negative test)
- crash-resume across a DAG: `A` and `B` complete, `C`'s Attempt Packet is published but the
  process is interrupted before `C`'s Result; re-invoking `run_workflow` resumes `C` (not `D`,
  which still cannot start) rather than restarting `C` or misreporting the workflow as blocked
- idempotent re-invocation of a fully-completed DAG workflow returns existing per-task
  publications, no duplicate runs (same idempotency mechanism as slice 1, unchanged — this test
  exists to prove the DAG driver loop rewrite, S7, didn't accidentally break it)
- crash-resume/blocked re-invocation actually returns a populated `task_results` (added after
  round-1 review, HIGH-2): re-invoke `run_workflow` against an already-`WORKFLOW_COMPLETE`
  diamond DAG and assert `task_results` contains all four tasks' Results, not an empty tuple;
  re-invoke against an already-`WORKFLOW_BLOCKED` DAG (one branch failed, one independent branch
  still `not_started`) and assert `task_results` contains every task with committed lineage
  (including the blocked task's own chain) but not the untouched `not_started` branch
- **(added after round-1 review, HIGH-3)** v2→v3 idempotency-key orphaning is real and
  documented, not silently absorbed: commit a slice-1-shaped (schema-v2, `depends_on`-free)
  workflow to completion, then re-invoke `run_workflow` against the same Request under v3 code —
  assert a fresh run-set is created (new genesis Request, new per-task runs) rather than a crash
  or a corrupted/mismatched idempotency hit, matching S8's explicit HIGH-3 decision

### Regression

- every slice-1 fixture that constructs a `WorkflowRevisionV1`/`TaskV1` directly
  (`test_publish_m7.py`, `test_workflow_eligibility.py`, `test_run_workflow.py`, and the five
  files slice 1's own MEDIUM-1 fix already updated) continues to pass, since
  `depends_on` is optional-shaped at the type level only in the sense that an empty tuple is a
  valid value, not in the sense of an `Optional`/default-`None` field that could silently vanish
  — every fixture must be checked to confirm it either already passes `depends_on=()` or is
  updated to do so; a fixture that fails to compile against the new required positional/keyword
  field is exactly the kind of "found the missing site by running the suite, not by claiming it's
  unchanged" verification slice 1's own MEDIUM-1 finding was about

- **Correction found during implementation dispatch, attempt 1 (a real plan contradiction, caught
  by the implementer before writing any code, not guessed around):** blanket `depends_on=()` is
  *not* correct for every existing fixture — it is correct only for fixtures that don't test
  ordering. `test_workflow_eligibility.py`'s `test_later_in_flight_task_before_earlier_task_fails_closed`
  and `test_later_complete_task_before_earlier_task_fails_closed` specifically assert
  `TASK_ORDER_VIOLATION` when `task-2` has lineage but `task-1` (declared first, array position)
  does not. Under S6's pure dependency-based ordering, two dependency-free tasks
  (`depends_on=()` on both) have no ordering relationship at all — `task-2` running before
  `task-1` is not a violation, it's a legitimate independent-branch execution order, exactly the
  behavior a DAG is supposed to allow. Migrating these two tests to `depends_on=()` would silently
  change what they test (from "order violation" to "no violation," making the `assertRaises`
  block simply never raise, which would surface as a test failure, not a silent pass — this was
  caught before any code was written, not after). **Resolution: these two tests specifically
  express a genuine linear dependency, not the absence of one** — update their fixtures to declare
  `task-2.depends_on = ("task-1",)` via the existing `revision(tasks=...)` helper's override
  parameter (`test_workflow_eligibility.py:28`), preserving each test's actual intent (a real
  declared dependency violated by out-of-order lineage) under the new semantics. This is not
  "preserve implicit positional ordering as a fallback" (the implementer's proposed alternative
  2) — that would reintroduce exactly the two-systems-at-once confusion S6 exists to remove, and
  would wrongly force every pair of truly-independent dependency-free tasks back into forced
  array-order execution, defeating the DAG's purpose. Every *other* existing fixture in this
  suite and in `test_publish_m7.py`/`test_run_workflow.py` that does not assert an
  order-violation outcome takes blanket `depends_on=()` as originally specified — only fixtures
  whose assertion depends on an ordering relationship need an explicit edge instead.

## S10. Implementation order

1. `kernel/protocol_v1.py`: `TaskV1.depends_on: tuple[str, ...]` field (required, no default —
   MEDIUM-1); `WORKFLOW_REVISION_SCHEMA_VERSION` bumped 2 → 3; new v3-only task reader/key set
   (`_TASK_V3_KEYS` or an equivalent explicit fork of `_read_task_v1`, MEDIUM-1) with
   `depends_on` support; today's v2 reader forked to its own task-reading path that rejects a
   `depends_on` key with `UNSUPPORTED_SCHEMA_VERSION` and otherwise constructs
   `TaskV1(..., depends_on=())`, retained at `(WORKFLOW_REVISION, 1, 2)`; the v1 legacy reader
   also updated to construct `TaskV1(..., depends_on=())` explicitly; new
   `_validate_task_dependency_graph` helper — `depends_on` validated as an `allow_empty=True`
   string sequence first (LOW-1), then unknown reference / self-dependency / duplicate edge
   checks, then an **iterative** (Kahn's-algorithm, not recursive DFS — LOW-1) cycle check — called
   from the v3 reader.
2. `kernel/publish.py`: `_kind_binding_rejection`'s `WORKFLOW_REVISION` branch calls the same
   `_validate_task_dependency_graph` helper; four new `PublishRejectionCode` members
   (`WORKFLOW_REVISION_UNKNOWN_DEPENDENCY`, `WORKFLOW_REVISION_SELF_DEPENDENCY`,
   `WORKFLOW_REVISION_DUPLICATE_DEPENDENCY`, `WORKFLOW_REVISION_DEPENDENCY_CYCLE`).
2b. `verification/stub_verifier_cli.py`: `_read_task` mechanical wire-shape update only (S8
   correction) — key set gains `depends_on`, validated as an `allow_empty=True` string sequence,
   forwarded into the `TaskV1` constructor; `product/tests/verification/test_stub_verifier_cli.py`
   fixture updated to send `depends_on`. No other change to that file or to `stub_verifier.py`.
3. `kernel/workflow_eligibility.py`: `WorkflowEligibility.eligible_tasks` field added *after*
   `reason` (LOW-3); order-violation check generalized from positional to `depends_on`-based;
   ready-set computation returns every task with state kind `not_started` **or** `in_flight`
   whose deps are all `complete` (HIGH-1 — not `not_started`-only), in declaration order; `task`
   set to `eligible_tasks[0]`; blocking semantics unchanged in shape (workflow-wide
   `WORKFLOW_BLOCKED` on any `fail`/`blocked` task kind, S6).
4. `execution/run_one_task.py`: `run_workflow`'s `NEXT_TASK` branch rewritten to materialize the
   single eligible task by `task_id` (S7); the `WORKFLOW_COMPLETE` and `WORKFLOW_BLOCKED` branches
   keep materializing every task with committed lineage (not `not_started`) before returning,
   switched from index-range to task_id-keyed iteration rather than dropped (HIGH-2); `materialize`
   closure's `index: int` parameter changed to `task_id: str` with a precomputed
   `task_id → TaskV1` lookup, reused for the `expected_output_digests` lookup too (LOW-2).
5. Golden-digest fixtures regenerated for the v3 `WorkflowRevisionV1`/`TaskV1` wire shape.
6. Test suite (S9): protocol-reader extensions, publish-boundary structural rejections,
   DAG eligibility tests (diamond fixture, order-violation, blocking-scope-decision proof,
   determinism, digest-divergence-with-`depends_on`), DAG driver tests (end-to-end,
   negative/blocked, crash-resume, idempotent re-invocation), and the full slice-1 regression
   list confirmed still green with `depends_on=()` on every existing fixture.

## S11. Explicit scope limits carried forward

Per AGENTS.md rule 9 (YAGNI) and this document's own precedent (§11 of the slice-1 plan) — the
roadmap's own nine-step order, restated as what remains after slice 2:

- **Step 3 — logical Resource Claims with read/write conflict semantics.** No resource-claim
  contract field exists; nothing in slice 2 needs it since dependency-respecting execution stays
  strictly sequential (S1, S7).
- **Steps 4–6 — bounded retry, repair, replan.** A `fail`/`blocked` task still blocks the whole
  workflow workfow-wide (S6); nothing retries it automatically, and no partial-branch-continuation
  logic exists for independent branches while one is blocked (S6's explicit scope decision).
- **Step 7 — fan-in with explicit merge/conflict policy.** Converging dependency edges (a task
  depending on more than one predecessor) are structurally supported (S3), but no merge-strategy/
  conflict-behavior/merge-authority field exists — each downstream task still runs its own
  independent Attempt/Result/Verification chain, nothing is combined.
- **Step 8 — reconciliation-required handling.** No `reconciliation_required` state exists; not
  reachable from any slice-2 code path.
- **Step 9 — proven-safe parallel execution.** The driver (S7) still materializes exactly one
  task per loop iteration, sequentially, even when `eligible_tasks` reports more than one ready
  task; no concurrency is introduced.
- **ADR-0009 Reviewer/Verifier split** (unchanged from slice 1 §6): still blocked on risk-tier/
  Plan-Check machinery that does not exist anywhere in `product/src/` (S2 re-confirms the same
  empty grep result against current HEAD).
- **M3's per-task capability-requirement gap** (unchanged from slice 1 §7): `TaskV1` gains only
  `depends_on` this slice, no capability/permission field.
- **Spec 04's `workflow/risk profile and admitted policy` field and Plan-Check requirement
  predicate** (unchanged from slice 1 §11's MEDIUM-3 deviation record): still not implemented;
  DAG dependency validation is orthogonal to risk-tier/policy admission and does not close this
  gap.

## S12. Slice 2 exit gate

- an admitted Workflow Revision may declare explicit dependency edges between tasks, not just
  array position (S3, S4)
- admission rejects unknown task references, self-dependencies, structural cycles, and duplicate
  edges for the same task (S4, S5, S9)
- the same admitted revision + per-task-run lineage always yields an identical eligible task set,
  identical declared-order tie-break, and identical next action (S6, S9 — determinism test, run
  twice, per Spec 04's own wording)
- a task with an unsatisfied dependency is never reported eligible, whether the unsatisfied
  dependency is `not_started`, `in_flight`, or terminally `fail`/`blocked` (S6, S9)
- a `fail`/`blocked` task blocks the whole workflow, including branches with no dependency on the
  failed task (S6's explicit, non-escalated scope decision, proven by a dedicated test in S9)
- pre-slice-2 (`depends_on`-free) `WorkflowRevisionV1` history remains replayable through the
  legacy-reader-retention pattern, with its folded value preserved (S4, S9)
- crash-resume and idempotent re-invocation work identically to slice 1 for a genuinely
  branching (non-linear) DAG, not only for the strictly linear case (S9)

## S13. Round 1 adversarial review (`zai-coding-plan/glm-5.3`, effort `high`, via `opencode`,
`--auto`, against this plan's S1–S12 draft and real code at `main` `df89f48`)

Full findings preserved verbatim at `.review/ISSUE-4-SLICE2-PLAN-REVIEW.md`. **0 BLOCKER, 3 HIGH,
3 MEDIUM, 3 LOW** — no step 3–9 scope creep found (explicitly verified non-finding), plan's
overall scope discipline held. All 9 real findings folded directly into S1–S10 above (not just
logged here), same discipline as slice 1's §13/§14:

- **HIGH-1** — S6's original `eligible_tasks` definition ("every `not_started` task…") silently
  dropped slice 1's in-flight-resume rule, contradicting a live green test
  (`test_in_flight_task_is_eligible_for_resume`) and this plan's own S9 crash-resume test. Fixed
  in S6/S9/S10: `eligible_tasks` includes `in_flight` tasks with satisfied deps.
- **HIGH-2** — S7's driver sketch returned immediately on `WORKFLOW_COMPLETE`/`WORKFLOW_BLOCKED`
  without materializing anything, so a re-invoked completed/blocked DAG would return an empty
  `task_results` — contradicting S12's own idempotent-re-invocation exit criterion. Fixed in
  S7/S9/S10: both recovery branches keep materializing every task with committed lineage,
  switched to task_id-keyed iteration rather than dropped.
- **HIGH-3** — S4's digest change silently orphans every slice-1-era workflow's idempotency keys
  across the v2→v3 upgrade (identical logical content digests differently once `depends_on: []`
  is added), which the plan neither stated nor tested. Decided explicitly in S8 (accept and
  document — same class as pre-M7 single-task non-resumability, no corruption, only a fresh
  run-set on re-invocation) and proven by a new S9 test, rather than left implicit.
- **MEDIUM-1** — "today's v2 reader retained" was unimplementable as stated: the v1/v2/v3 readers
  share `_read_task_v1`/`_TASK_KEYS`, and `depends_on` is a required field per S9's own fixture
  test, so the legacy readers cannot be reused unchanged. Fixed in S4/S10: explicit reader fork
  (v3-only key set; v2/v1 readers construct `depends_on=()` explicitly and the v2 reader rejects a
  present `depends_on` key), matching `read_legacy_workflow_revision_v1`'s existing per-revision
  key-fork precedent one level deeper.
- **MEDIUM-2** — three Spec 04 normative readings (tie-break metadata, per-edge satisfaction
  condition, "incompatible graph references") were resolved by implicit design choice rather than
  named, breaking slice 1 §11 MEDIUM 3's own named-deviation discipline. Fixed in S3: three
  deviations named explicitly with rationale.
- **MEDIUM-3** — S1/S2/S6 contained eight inaccurate file:line citations (Spec 04 line numbers,
  `publish.py`'s branch range, `run_one_task.py`'s end line, `workflow_eligibility.py`'s line
  count) and one wrong-authority attribution (cited "Lens A" for an argument actually made by
  "Lens D"). All eight corrected in place; substance of every citation was otherwise verified
  accurate.
- **LOW-1** — the cycle-detection sketch (recursive DFS) would raise an unhandled `RecursionError`
  on a hostile deep chain instead of a typed rejection, and `depends_on` validation never stated
  `allow_empty=True` (reusing `acceptance_criteria`'s `allow_empty=False` shape would reject every
  dependency-free task). Fixed in S4/S10: iterative (Kahn's-algorithm) cycle detection mandated;
  `allow_empty=True` stated explicitly.
- **LOW-2** — two observable API changes under a DAG went unremarked: `task_results` ordering can
  differ from array order, and the `expected_output_digests[index]` lookup needs the same
  task_id-keying S7 already introduces. Fixed in S8/S10 with one sentence each.
- **LOW-3** — the `WorkflowEligibility` snippet inserted `eligible_tasks` before `reason`,
  silently redefining the third positional argument (harmless today — all call sites use keyword
  arguments — but a latent trap for future positional construction). Fixed in S6:
  `eligible_tasks` appended after `reason`.

Verified non-findings, not re-litigated: S5's publish-boundary insertion point preserves existing
rejection ordering for every current test; no step 3–9 scope creep; declaration-order tie-break is
deterministic and sufficient; S6's workflow-wide blocking decision is properly decided in-plan,
not a dodge; slice-1 round-2 fixes (task-identity trust, out-of-order rejection) generalize
cleanly to the DAG case.

## Implementation outcome note — blocked before S10 (2026-08-28)

Implementation did not start because S4/S8/S9 contained a genuine internal contradiction at the
existing verifier seam. S4 requires a default-free `TaskV1.depends_on` field and requires it in the
canonical task payload; S8 (as drafted) forbade changes to `verification/stub_verifier*.py`; S9
requires the real-binary end-to-end DAG driver. The frozen `stub_verifier_cli.py` accepted only
the pre-Slice-2 task keys and constructed `TaskV1` without `depends_on`, while `run_one_task.py`
sends the canonical task payload to that CLI. The blocker was recorded as `.review/ISSUE-4-BLOCKER.json` with reason code `PLAN_CONTRADICTION_FROZEN_VERIFIER_TASK_SHAPE` (a transient orchestration artifact, not committed); no product code
or tests were changed, and no commit was made.

**Resolution (same session, conductor decision — no real tradeoff):** the S8 correction above
adds `stub_verifier_cli.py::_read_task` (plus its test file) to the touch allowlist for a
mechanical wire-shape update only (accept + validate + forward `depends_on`); verifier semantics
unchanged. Redispatch authorized.

## S14. Round 2 post-implementation review (`zai-coding-plan/glm-5.3`, effort `high`, via
`opencode`, against `git diff df89f48..456b851`)

Full findings preserved at `.review/ISSUE-4-IMPL-REVIEW.md`. **0 BLOCKER, 0 HIGH, 0 MEDIUM,
4 LOW** — every S12 exit gate, determinism requirement, legacy-retention path, and the S8
correction's exact scope verified as non-findings with file:line evidence. Fix directives for the
four LOWs, folded in before the fix dispatch:

- **LOW-1** — publish.py:336–361 translates the shared graph validator's rejection by parsing
  `rejection.reason.split("=", 1)[0]` against a 4-entry map; the helper can also emit its
  duplicate-task-id branch (currently dead at both call sites) and `_require_string_sequence`
  failures (reachable via a hand-built `ParsedCandidate` with a non-string tuple member), and an
  unmapped reason crashes with `RuntimeError` instead of a typed `Rejected`. Fix: stop parsing
  the human-readable reason — give `_validate_task_dependency_graph` a structured failure
  discriminator (dedicated exception attribute or per-check enum) the publish layer switches on;
  map every failure mode the helper can emit to a typed `PublishRejectionCode` (the duplicate
  branch may map to the existing `WORKFLOW_REVISION_TASK_ID_DUPLICATE`; non-string
  `depends_on` members map to `MALFORMED_PAYLOAD`-equivalent typed rejection).
- **LOW-2** — `project_workflow_eligibility` raises raw `KeyError` when a directly-passed
  revision's `depends_on` names a nonexistent task_id (workflow_eligibility.py:186,199), while
  every other malformed input there is a typed `WorkflowEligibilityRejected`. Fix: validate at
  projection entry that every `depends_on` entry is in `task_ids`; raise
  `WorkflowEligibilityRejected(UNKNOWN_TASK_ID, ...)` otherwise.
- **LOW-3** — no negative test pins that `stub_verifier_cli` now *requires* `depends_on` (the
  old 3-key payload must fail `task_keys_mismatch`). Fix: one test in
  `product/tests/verification/test_stub_verifier_cli.py` sending a task payload without
  `depends_on` and asserting the nonzero exit / `task_keys_mismatch` diagnostic.
- **LOW-4** — the plan section itself was uncommitted and referenced
  `.review/ISSUE-4-BLOCKER.json`, which no checkout contains (the blocker lived only in the
  transient worktree `.review/`). Fix (conductor-owned, close-out): commit the plan-doc update
  with the handoff commit and reword the outcome note to describe the blocker rather than cite a
  missing artifact path.

### Fix-verification recheck (clean context, same reviewer model)

`zai-coding-plan/glm-5.3` high re-reviewed `git diff 456b851..ad3ac1a` in a clean session
(`.review/ISSUE-4-FIX-RECHECK.md`): verdict **CLEAN** — all three directives implemented as
specified; full escape-hatch audit of `_validate_task_dependency_graph`'s raise sites confirms
no plain `ProtocolRejected` can bypass publish's typed switch (all `_require_string_sequence`
raise sites wrapped); all three new tests discriminating (each fails on the pre-fix commit);
scope exactly the three LOWs; 426 tests green (162/143/113/8).
