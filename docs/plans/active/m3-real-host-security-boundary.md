# M3 — Real Host / Security Boundary and First Runtime Adapter Implementation Plan

Status: **Active** (hardened after GLM-5.3-high adversarial review; see §13)
Tracker: [Issue #34](https://github.com/hjung3113/agent-platform/issues/34)
Milestone: **M3 only**
Primary issues: #7, #8
Supported platforms for this milestone: **macOS and Linux only.** Windows containment/
sandbox semantics (junctions/reparse points) are out of scope until a Windows target is
added (M7-era cross-platform work).

This document is the execution plan for M3 of the MVP roadmap. It replaces M2's fake
execution boundary (`product/src/execution/stub_host.py`,
`product/src/verification/stub_verifier.py`) with one real, enforceable runtime path for
exactly one runtime (OpenCode), without generalizing portability (M8), context compilation
(M4), evidence hardening (M5), or orchestration expansion (M6).

Normative semantics remain owned by the specs/ADRs. If implementation reveals a
contradiction with those authorities, update the governing design first rather than
encoding a local interpretation here.

## 1. Sources and current baseline

Primary design sources:

- [`mvp-implementation-roadmap.md`](./mvp-implementation-roadmap.md) — M3 section
- [`m2-one-task-protocol-e2e.md`](./m2-one-task-protocol-e2e.md) — style/precedent, exact
  scaffolded fields this milestone fills with real values
- [`end-to-end-wiring.md`](../../architecture/end-to-end-wiring.md)
- [`runtime-boundaries.md`](../../architecture/runtime-boundaries.md)
- [`security-and-data-boundaries.md`](../../architecture/security-and-data-boundaries.md)
- [`05-runtime-execution.md`](../../specs/05-runtime-execution.md)
- [`06-review-verification-evidence.md`](../../specs/06-review-verification-evidence.md)
- `product/agents/roles/implementer.md`
- `product/adapters/runtimes/opencode.md`
- `docs/research/user-repositories/opencode-orchestrated-agent-workflow.md`

Issue evidence: #7 (runtime/adapter portability), #8 (security/external effects).

Already implemented on `main` and reused unchanged in semantics:

- `product/src/kernel/canonical.py` — canonical JSON + content digest.
- `product/src/kernel/protocol.py` / `protocol_v1.py` — `ContractKind`, readers; M3 adds
  **no new `ContractKind`** and **no new protocol/schema version**. `AttemptPacketV1`'s
  `workspace_snapshot_digest` and `runtime_capability_profile_identity`, and `ResultV1`'s
  `observation.runtime_identity` / `output_snapshot_digest`, were already declared
  digest/identity-shaped strings in M2 — M3 makes them real computed values instead of
  fixture constants. No contract shape changes; the reader/publish boundary from M1/M2 is
  untouched.
- `product/src/kernel/publish.py` — sole production writer; state machine, binding checks,
  and rejection codes from M1/M2 stay intact and unmodified.
- `product/src/kernel/runtime_capability.py` — `RuntimeCapabilityProfile`,
  `PermissionEnvelope`, `CapabilityStatus`, fail-closed `.require(...)`. M3 is the first
  milestone that actually constructs a profile from a real runtime probe and binds it to
  execution, not just to admission's pure policy check.
- `product/src/kernel/admission.py` — `admit_attempt`, `AttemptRequest`,
  `_resolve_inside` path-containment primitive. M3 is the first milestone that calls this
  with a real `workspace_root` and a real `RuntimeCapabilityProfile` before executing (M2's
  stub explicitly did not call it — see its docstring).

Replaced in this milestone (not extended in place, per the M2 handoff):

- `product/src/execution/stub_host.py` → deleted, replaced by a real Host module set.
- `product/src/verification/stub_verifier.py` → **unchanged**. M3 does not touch
  verification semantics (M5 scope); the real Host produces a real `ResultV1`, and the
  existing digest-equality stub Verifier keeps consuming it exactly as in M2. Only the
  driver wiring that currently calls `stub_execute` moves to the new Host entry point.

## 2. M3 scope decision

M3 proves one thing: **an admitted Attempt executes inside a real, honestly-labeled
enforcement envelope on one real runtime (OpenCode), and its Result binds real Runtime
Observation and real output-snapshot provenance** — not that runtime execution is portable,
not that context is real, not that verification is hardened, not that orchestration expands
beyond one task.

"Honestly-labeled" is load-bearing after adversarial review (§13, §14): M3 delivers **real
process-boundary enforcement** for credentials only (env allow-list — the child process
environment is built from scratch, so an unlisted ambient secret is genuinely invisible to
it). External effects get **real declarative admission rejection** (empty
`external_effects` envelope, any `requested_effects` fails `admit_attempt` before spawn) but
**not** a process-boundary control — the spawned OpenCode process/shell is not prevented
from directly invoking `git push`/`gh`/`curl` (§14 correction). Everything else gets **real
policy-admission enforcement** (fail-closed `admit_attempt`, capability `require()`) only.
M3 does **not** deliver real interception of network calls or of filesystem writes/process
spawns beyond declared candidate paths — pure-Python subprocess wrapping cannot observe or
block a child's `socket()`/`open()`/`fork()` calls, and no real sandbox (seccomp/
`sandbox-exec`/namespaces) is in scope this milestone. Per `security-and-data-
boundaries.md`'s own rule ("if a runtime cannot enforce a required denial/isolation
boundary, that runtime is not admissible for the Attempt"), M3 profiles these axes
`PARTIAL`/`UNKNOWN` rather than `SUPPORTED`, so an Attempt that actually *requires* network
or filesystem/process isolation is rejected by `RuntimeCapabilityProfile.require(...)`
rather than executed under a false enforcement claim.

```text
Attempt Packet (published)
  -> resolve Workspace Snapshot identity (effective, not just HEAD)
  -> resolve real Runtime Capability Profile (OpenCode probe)
  -> admit_attempt() with real workspace_root + real profile (fail closed)
  -> deny-first execution inside the admitted envelope
  -> Runtime Observation + real output Workspace Snapshot identity
  -> pre-retention redaction gate
  -> Result candidate (published exactly as M2's chain already accepts)
```

**Non-goals** (unchanged from roadmap §M3, restated for this doc's own boundary
enforcement): all runtimes beyond OpenCode (M8), general plugin system, release
automation, sophisticated secret-classification taxonomy (a minimal deterministic canary
scanner only), real evidence policy / criterion-level admissibility (M5), Context Compiler
/ real `context_digest` (M4), DAG/retry/repair/replan/parallelism (M6), distributed/
multi-machine sandboxing, full OS-level mandatory-access-control sandbox (best-effort
deny-first enforcement only, explicit fail-closed when the runtime cannot itself enforce a
required denial).

## 3. Effective Workspace Snapshot identity

New module: `product/src/execution/workspace_snapshot.py`.

Repository HEAD alone is insufficient (spec 05, roadmap M3 bullet 1). The effective
snapshot identity is a deterministic digest over, in canonical field order:

- resolved absolute workspace root (containment-checked, §4)
- current branch/HEAD commit id (or explicit "no HEAD" for a fresh worktree)
- staged tree state (`git diff --cached` content, path-sorted)
- unstaged tracked-file state (`git diff` content, path-sorted)
- untracked, non-ignored file paths + content digests (`git status --porcelain=v1
  --untracked-files=all`, filtered through `.gitignore`, path-sorted); an untracked entry
  that is itself a symlink is digested by its **link target string**, not by dereferencing
  and hashing arbitrary target content — this keeps hashing bounded and prevents an
  untracked symlink from silently pulling out-of-workspace content into the identity
- generated-output paths: a **driver-supplied, digest-bound parameter** (`execute`'s
  `declared_generated_paths` argument, §6) — not a `TaskV1` contract field. `TaskV1`
  (`protocol_v1.py`) has no generated-paths key and §1 forbids contract changes this
  milestone, so this list is convention between the packet-construction call site and
  `host.execute`, not an authoritative binding. Because the digest covers the list, a driver
  that passes a different list at compile time vs. execute time is caught by the same
  staleness check as any other delta — but two independent drivers using different
  conventions would legitimately diverge. Binding this to a real contract field is deferred
  to M4's Context Pack. **Corrected after PR review (§14):** each declared path's own
  file/symlink/absent state is hashed — not merely the path name. A first pass hashed only
  the sorted name list, so a Git-ignored generated artifact (the common case for build
  output) could be created, edited, or deleted with no digest change at all, letting distinct
  Result content share one `output_snapshot_digest`.
- nested-repository / submodule roots: **corrected after PR review (§14)** — each nested
  root's identity recurses through its own full `snapshot_identity` (its HEAD commit plus its
  own staged/unstaged/untracked/further-nested state), not merely its commit id. A first pass
  bound only path + commit, so uncommitted changes inside a nested worktree never changed the
  outer digest even though the runtime can read/write that content. Recursion is bounded by
  the real, finite nesting depth of the worktree tree — a nested repo is still a boundary
  (not flattened into the outer repo's own staged/unstaged/untracked state), but its own
  effective state is no longer invisible.

`snapshot_identity(root: Path, declared_generated_paths: tuple[str, ...] = ()) ->
WorkspaceSnapshot` returns a frozen dataclass with a `.digest` content-digest property
(reusing `kernel.canonical.content_digest`) plus the structured evidence fields above, so a
mismatch is diagnosable, not just a single opaque string. Two calls against unchanged
workspace state produce an identical digest (determinism test, §9). Any tracked/staged/
unstaged/untracked delta between "compile-time" and "execute-time" resolution changes the
digest — this is the mechanism, not a side effect, that lets Result binding detect stale
context (spec 05: "stale/mismatched evidence requires rejection or recompilation").

**Explicit non-goal:** this module does not decide *what* context is compiled from the
snapshot (M4) — it only fixes *which* effective content the identity covers.

### 3.1 Collection ordering and residual TOCTOU window

Digest collection (`git diff --cached`, `git diff`, `git status --porcelain`, per-untracked
content reads) is **not atomic** — a concurrent writer between two of these calls can
produce a digest that never corresponded to any single real workspace state. `host.execute`
(§6) closes the *admission-to-spawn* gap this module by itself cannot: `admission.py`'s own
docstring assigns "close admission-to-use races" to the Host, and the recompute in §6 step 1
happens **immediately before** step 4's spawn, not merely once at the top of `execute`. This
shrinks — it does not eliminate — the window between "content last verified" and "content
actually executed against." The plan states this honestly rather than implying race-freedom:
a sufficiently well-timed concurrent tamper (swap file content after the pre-spawn recompute,
restore it before the post-exec recompute) is not detected by snapshot comparison alone. This
residual window is an explicit known limit, closed only by a durable workspace
lease/single-writer guarantee, which is M5/M7-era work, not M3. §9 adds a fixture that proves
detection for the ordinary case (state changes *between* admission and spawn, no restore) so
the mechanism that does exist is tested, without claiming the swap-restore case is closed.

## 4. Workspace containment and escape rejection

`admission._resolve_inside` (existing, M1-era) already resolves symlinks via
`Path.resolve(strict=False)` and rejects anything outside `root` via `relative_to`. M3 does
not replace this primitive — it hardens the test suite around it and wires it into the real
Host's actual candidate-path checks (M2's stub never called `admit_attempt` at all).

New negative fixtures added to `product/tests/execution/test_containment.py`:

- plain `../../etc/passwd`-style traversal
- symlink inside the workspace root pointing outside it
- symlink whose target itself resolves through another symlink (chained escape)
- nested-repository directory used as a candidate path, rejected as an escape unless it
  already appears in the caller's `candidate_paths` list (no implicit descent, §3) — this is
  a `candidate_paths` membership rule, not a new "admitted nested boundary" contract concept
- a path that is textually inside the root but whose resolved realpath is outside due to a
  parent-directory symlink (macOS/Linux equivalent of a Windows junction escape; Windows
  itself is out of scope, see platform note above)
- a symlink loop, or a resolution that raises `EACCES`/`EROFS`/`OSError` — must fail closed

Two cases previously conflated with "ambiguous" are **not** rejections, and get their own
fixtures proving they stay admitted:

- a non-existent path whose existing parent directory resolves inside `root` — this is the
  ordinary shape of a legitimate not-yet-created write target, and `_resolve_inside`'s
  `strict=False` resolution already admits it; a fixture must lock this in, not just the
  rejection cases, since candidate write paths are frequently pre-creation by definition
  (§6.4).
- a non-existent path whose parent directory also does not yet exist, but whose fully
  resolved (non-strict) path still lands inside `root` — admitted for the same reason; M3
  does not require intermediate directories to pre-exist.

If containment cannot be established unambiguously (symlink loop, permission error,
unresolvable target), `_resolve_inside` already returns `None` and callers already treat
that as rejection; this milestone proves that contract with concrete adversarial fixtures,
correctly separated from the legitimate not-yet-existing-path case above, rather than adding
new code.

## 5. Runtime Capability Profile: real probe, bound at execution

New module: `product/src/execution/opencode_adapter.py`.

`probe_opencode_profile(binary_path: str, config_paths: tuple[Path, ...]) ->
RuntimeCapabilityProfile`:

1. Resolves the OpenCode binary path and version (`opencode --version` or equivalent
   deterministic query); `runtime` field is `f"opencode@{version}+{binary_digest}"`.
   **Corrected after PR review (§14):** the version string alone is not identity — a binary
   replaced in place with different code reporting the same `--version` would pass the
   Host's no-silent-substitution recheck unnoticed. `binary_digest` is a content digest of
   the resolved executable's actual bytes, folded into `runtime` (not a new profile field —
   `RuntimeCapabilityProfile`'s schema is frozen M0-era shape) so a substituted binary is
   caught by the identity checks that already exist end to end.
2. Resolves effective configuration by reading OpenCode's actual config precedence order
   (project config -> global config -> environment/CLI overrides, whatever OpenCode's own
   documented resolution order is) and computing `config_identity` as
   `content_digest(effective_config_dict)` — the *merged* result, not just the project
   file, so drift in an inherited/default layer is visible (roadmap bullet: "inherited/
   default permissions must not widen the admitted envelope"). Callers merging multiple
   layers pass them **most general/inherited first, most specific last** — later layers
   override earlier ones (an earlier draft of this doc stated the calling convention
   backwards, which would have let an inherited/global layer silently win over a
   project-specific one; corrected in §14). **Known unenforceable gap, documented honestly:**
   OpenCode's CLI has no flag to pin a spawned process to exactly this probed/merged
   configuration or to suppress its own further discovery of an unprobed global/default
   layer at spawn time — the Host pins only the *project*-layer config by launching OpenCode
   with `cwd` set to the exact resolved workspace root this profile was probed against; the
   global/inherited layer's actual use by the live process is unproven, same enforceability
   class as network denial (§2/§6), not falsely claimed as proven.
3. Resolves the canonical-action -> OpenCode-tool mapping table this adapter declares and
   computes `tool_mapping_identity` the same way.
4. Declares `capabilities` (`Capability(name, status)`) only for canonical actions this
   adapter actually implements a real mapping for; anything unmapped is
   `CapabilityStatus.UNKNOWN`, anything mapped but not enforceable this milestone is
   `PARTIAL` — never silently `SUPPORTED`.
5. Computes `permission_envelope` as the **effective** envelope after step 2's full
   resolution, not the requested/declared one — this is the field
   `admission._runtime_permissions_within_admitted` already fail-closed-compares against
   the caller's admitted envelope.

`RuntimeCapabilityProfile.identity` (existing property, M0-era) is the binding value:
`AttemptPacketV1.runtime_capability_profile_identity` must equal a profile identity
produced by a probe run **at execution time**, not merely at packet-construction time. If
the live probe's identity differs from the packet's declared identity, execution is
rejected before any side effect (`STALE_RUNTIME_CAPABILITY_PROFILE`, an execution-layer
fail-closed outcome — no new `PublishRejectionCode`, since a Result never gets constructed
to publish in this case; §8's driver wiring surfaces it as a typed Host-level error, and no
Kernel record is produced for a run that never executed).

### 5.1 Binding `required_capabilities` and `admitted_permissions` to something authoritative

`admission.AttemptRequest.admitted_permissions` / `.required_capabilities` /
`.candidate_paths` are free parameters (`admission.py`), and no `AttemptPacketV1` field
carries them (§1: no contract change). Left unbound, a caller can pass
`required_capabilities=()` and `admitted_permissions=<the live profile's own effective
envelope>`, and every admission check trivially passes regardless of what actually executes
— this is the exact gap adversarial review flagged as making exit-gate bullets vacuously
satisfiable (§13, HIGH 1).

M3 closes it with a fixed, versioned **M3 execution policy table** —
`product/src/execution/policy.py` — a small hardcoded constant, not a new contract field or
a general RBAC system: `M3_REQUIRED_CAPABILITIES: tuple[str, ...]` and
`M3_ADMITTED_PERMISSIONS: PermissionEnvelope`, the single fixed envelope every M3 Attempt is
admitted against (deliberately narrow: no network, no external effects, filesystem limited
to the workspace root, credentials limited to whatever allow-list the fixture/task
declares). `host.execute` builds its `AttemptRequest` **only** from this constant — it never
accepts a driver-supplied override for these three fields. A driver cannot pass a wider
envelope and have it silently accepted; that would require changing `policy.py` itself,
which is a reviewable code change, not a runtime parameter. This is intentionally the
simplest mechanism that closes the demonstrated gap (AGENTS.md rule 13) — a real per-role/
per-task policy derivation belongs to M4 (Context Compiler-adjacent) or M6 (real
orchestration), not invented here.

**Corrected after PR review (§14) — staleness closure without a contract change:**
`M3_ADMITTED_PERMISSIONS` drift was already implicitly caught (the adapter's resolved
`permission_envelope` is part of `RuntimeCapabilityProfile.to_canonical_value()`, so a
permissions-table change already changes `profile.identity`), but
`M3_REQUIRED_CAPABILITIES` was not bound to anything at all — a future change to that table
could execute an already-published, older Attempt Packet under different requirements with
no staleness mismatch. Both constants are now digested into `config_identity` (§5), so a
policy-table change changes `RuntimeCapabilityProfile.identity` and the Host's existing
execution-time recheck rejects stale attempts automatically.

**Accepted scope limit, stated explicitly (not solved here):** because the fixed policy
table is global rather than bound to the specific published task, M3 cannot express "this
particular task requires network/filesystem/process isolation as a guarantee" — every M3
Attempt is admitted against the same uniform requirement set. This is consistent with M3's
own scope (the plan's single fixed one-task shape throughout this document), not a
per-task differentiation system; real per-task/per-role capability requirements are M4
(Context Compiler-adjacent) or M6 (real orchestration) territory, where task variability
first becomes real.

## 6. Deny-first execution

New module: `product/src/execution/host.py`.

`execute(attempt_ref: RecordRef, attempt: AttemptPacketV1, workspace_root: Path,
opencode_binary_path: str, task: TaskV1, config_paths: tuple[Path, ...] = (),
declared_generated_paths: tuple[str, ...] = (), *, retain_evidence: bool = False,
requested_effects: tuple[str, ...] = ()) -> ResultV1`. **Signature corrected after PR review
(§14):** an earlier draft omitted `task` entirely — the Host spawned OpenCode with no
objective/acceptance-criteria information at all, so the runtime succeeded independently of
what was actually admitted; the E2E chain proved protocol wiring only, not that the
published task reached execution. `task` is the authoritative `TaskV1` the driver already
holds (the same value bound into the published Workflow Revision), rendered as the
runtime's `run` message — mirroring OpenCode's own `run [message..]` positional-argument
shape — not arbitrary compiled context (that stays M4 scope).

1. Recompute `workspace_snapshot_identity` (§3) at execute-time; reject if it doesn't equal
   `attempt.workspace_snapshot_digest` (stale compiled state) —
   `STALE_WORKSPACE_SNAPSHOT`, same execution-layer fail-closed class as §5.
2. Probe the live `RuntimeCapabilityProfile` (§5); reject on identity mismatch.
3. Build an `admission.AttemptRequest` from the *real* resolved `workspace_root` and the
   fixed §5.1 policy constants, call `admission.admit_attempt(...)`; on `BLOCKED`, execution
   never starts.
3.5. **Immediately before spawn** (not merely once at the top of `execute`): re-probe the
   profile identity and re-check the binary path resolved in §5 hasn't changed, and reject
   on any drift — this shrinks the admission-to-spawn window §3.1 describes to the minimum
   practical size, though it does not close it entirely (§3.1). No silent substitution: if
   the probed binary path changes between probe and invoke, execution is rejected rather
   than transparently using the new path (closes roadmap's "no silent runtime/transport/
   tool fallback" bullet, §9/§11).
4. Only after `ADMITTED` and step 3.5's recheck: invoke the OpenCode adapter's process
   wrapper. Enforcement claims below are stated per-axis at the honesty level M3 can
   actually deliver (§2) — some are real process-boundary controls, others are policy
   admission checks only:
   - filesystem (**declared-scope policy check, not interception**): candidate write paths
     are pre-resolved and containment-checked (§4) before the child spawns, and the
     subprocess's working directory is the resolved workspace root. This validates the
     *declared* candidate list; it does not intercept the child's actual `open()`/`write()`
     calls — a pure-Python parent cannot observe or block a subprocess's raw syscalls, and
     OpenCode's own shell/tool surface can write anywhere the process uid can if it chooses
     to. `filesystem-write-beyond-declared` is therefore profiled `PARTIAL` (§5.4), and an
     Attempt that requires real filesystem interception beyond declared-path policy fails
     `require()` rather than executing under a false claim. A real sandbox is M5/M7-era.
   - network (**not enforced this milestone — profiled `PARTIAL`/`UNKNOWN`, not
     `SUPPORTED`**): env-variable manipulation (no proxy vars, no network-shaped env) is
     advisory only — it does not prevent a child (or grandchild) process from calling
     `socket(2)` directly, since no OS-level sandbox (seccomp/`sandbox-exec`/network
     namespace) is in this milestone's scope (§2). M3 does **not** claim network denial is
     enforced at the process boundary. `network` capability status in the OpenCode profile
     is `PARTIAL` whenever the effective envelope is empty, so any Attempt whose task
     actually *requires* network-denial-as-a-guarantee is rejected by `require()` before
     execution rather than executed under an unenforceable claim (`security-and-data-
     boundaries.md`: "if a runtime cannot enforce a required denial/isolation boundary,
     that runtime is not admissible"). Real network isolation is out of scope until a
     concrete per-OS mechanism (Seatbelt profile, seccomp-bpf, network namespace) is
     designed and added as its own milestone increment.
   - process (**declared-scope policy check, same honesty class as filesystem**): the
     adapter rejects any tool invocation outside its own declared canonical-action mapping
     at the point OpenCode asks the adapter to perform an action; it cannot prevent an
     arbitrary grandchild process OpenCode's own shell tool spawns directly. `process-spawn`
     beyond the adapter's mapped surface is profiled `PARTIAL`, same mechanism as filesystem.
   - credentials (**real process-boundary enforcement**): the child process environment is
     built explicitly from an allow-list derived from `permission_envelope.credentials`;
     ambient environment variables are **not** inherited by default. This is real — the
     parent constructs the child's `env` argument from scratch, so an unlisted ambient
     secret is genuinely never visible to the child process (closes the issue #8 "secrets
     exposed via ambient env" failure mode by omission, not detection).
   - external effects (**declarative admission rejection only, not a process-boundary
     control — corrected after PR review, §14**): `permission_envelope.external_effects`
     stays empty for every M3 fixture/adapter path (§5.1's fixed policy); a caller expressing
     `requested_effects` (reachable through `execute`'s own parameter, not only constructible
     directly on `AttemptRequest` as an earlier draft left it) is rejected by
     `admission.py`'s existing `_effects_are_admitted` before spawn. This is real admission-
     level rejection, but it is **not** a process-boundary control: the spawned OpenCode
     process, and any shell/tool it invokes, is not prevented from directly calling
     `git push`/`gh`/`curl`/an equivalent client — same unenforced-at-process-level class as
     network denial above, not the stronger claim an earlier draft made.
5. Every capability this milestone cannot really enforce (network, filesystem/process
   interception beyond declared scope) is declared `PARTIAL` or `UNKNOWN` in the profile
   (§5.4), so `RuntimeCapabilityProfile.require(...)` already fails closed if an Attempt
   requires it — the profile's honesty *is* the control for those axes, and no separate
   enforcement code is invented to paper over what the runtime genuinely cannot guarantee.
5.5. **Corrected after PR review (§14) — a nonzero exit is a real failure, not a discarded
   signal:** "exit code alone does not establish completion" (step 6 below) means a *zero*
   exit / success-claiming stdout is not trusted as proof of success — it never meant a
   nonzero exit should be silently ignored. If the spawned process exits non-zero, `execute`
   raises before building any Result; a crashed/erroring runtime process must not be
   packaged into a Result whose digest happens to reflect unchanged workspace state.
6. Recompute `workspace_snapshot_identity` (§3) at completion — this becomes
   `output_snapshot_digest`. **Runtime exit code / stdout alone never establishes
   completion** (roadmap exit bullet): a zero exit's Result identity is derived from
   actual post-execution workspace state, independent of what OpenCode printed or returned
   (a nonzero exit is handled by step 5.5 above, before this recompute matters).
7. Build `RuntimeObservationV1(runtime_identity=<live profile's f"opencode@{version}+
   {binary_digest}">, output_snapshot_digest=<step 6>)` and `ResultV1(attempt=attempt_ref,
   output_snapshot_digest=<step 6>, observation=...)` — same shape M2 already defined; only
   the values are now real.

`host.execute` replaces `stub_host.stub_execute` as the driver's call site (§8). No Kernel
publish-boundary code changes; `ResultV1` publishes through the existing M2 `publish.py`
path unmodified.

## 7. Pre-retention redaction gate

New module: `product/src/execution/redaction.py`.

`scan_for_retention(text: str | None) -> RedactionResult` — a minimal deterministic
canary-pattern scanner (not a sophisticated classification taxonomy, explicitly deferred per
roadmap): fixed regex set for common high-confidence secret shapes (e.g.
`AKIA[0-9A-Z]{16}`-style AWS key prefixes, `-----BEGIN...PRIVATE KEY-----` PEM blocks,
bearer-token-shaped long high-entropy strings following a `token`/`secret`/`key`/`password`
label). Returns `status: "passed" | "blocked" | "unknown"` — `unknown` for `None` input
(the caller's signal that content could not be decoded as UTF-8), and `unknown`/`blocked`
both count as "not passed."

**Two distinct gates, corrected after PR review (§14) to avoid an impossible ordering:** an
earlier draft implied `host.execute` reuses `admission.admit_attempt`'s pre-spawn
`retain_evidence`/`redaction_status` check for captured stdout/stderr — impossible, since
`admit_attempt` runs *before* the subprocess spawns (§6 step 3), while stdout/stderr exist
only *after* it returns (§6 step 4). The two mechanisms stay genuinely separate: (1)
`admission.py`'s existing `retain_evidence and redaction_status != "passed"` check is a
pre-spawn admission gate for evidence a caller already has in hand *before* execution (still
directly exercised by its own test, independent of stdout); (2) `host.execute`'s own
post-capture gate scans stdout/stderr *after* the subprocess returns and, on `blocked`/
`unknown`, raises `RetentionBlockedError` before building a `ResultV1` — an execution-layer
rejection (§6's error class), not a `PublishRejectionCode`. Subprocess output is captured as
raw bytes and decoded under Host control; a decode failure passes `None` to
`scan_for_retention` rather than crashing.

**Retained-surface scope, stated explicitly (per adversarial review, §13 MEDIUM 4):**
`ResultV1` (`protocol_v1.py`) carries only `RecordRef`s and digests — no stdout/stderr text
field exists, and §1 forbids adding one this milestone. The Kernel lineage store persists
canonical record JSON only. So the only text M3 actually retains anywhere is captured
stdout/stderr **that a driver chooses to pass into the gate before logging/persisting it
outside the Kernel lineage** (e.g. a local debug log a driver writes) — not "any
produced-artifact text" in general, which would drift toward M9's classification taxonomy.
`host.execute` runs `scan_for_retention` over captured stdout/stderr only, at the point
`retain_evidence=True` is requested by the caller (an `execute` parameter, not
`admission.AttemptRequest` — see the two-gate correction above); on `blocked`/`unknown`, the
Attempt fails closed (`RetentionBlockedError`, an execution-layer error, §6) rather than
retaining unredacted content anywhere. This keeps
the gate meaningful rather than vacuously passing because nothing is retained: the exit-gate
claim (§11) is scoped to "captured stdout/stderr, when `retain_evidence=True` is
requested," not to record JSON (which never carries raw text) or to a broader
produced-artifact surface that is explicitly out of scope. Canary secret **test fixtures** (a
real-shaped but fake AWS key, a fake PEM block) prove detection without ever persisting
genuine secret material — the fixtures themselves are synthetic constants checked into the
test file, and the assertion is that the *raw fixture string never appears* in the module's
own output/result values, only a `blocked` status and a redacted placeholder.

## 8. Driver wiring

**Correcting a claim adversarial review found false (§13, HIGH 1):** there is no production
CLI driver today. Grepping the M2-era call sites confirms `stub_execute` is only invoked
from tests (`product/tests/execution/test_attempt_and_host.py`,
`product/tests/kernel/test_m2_integration.py`). M3's deliverable is therefore **library +
tests**, not a call-site swap inside an existing production driver that doesn't exist. This
section states plainly what M3 ships and where its first real caller will live.

Two things change, both required for the chain to work end to end (not "swap only" — the
prior draft understated this, §13 MEDIUM 1):

1. **Attempt-packet construction fills real identities.** `execution/attempt.py`'s
   `build_attempt_packet` currently fills `workspace_snapshot_digest` and
   `runtime_capability_profile_identity` with `_fixture_digest(...)` constants (M2). M3
   replaces those two fields' construction with real calls: `workspace_snapshot_digest =
   workspace_snapshot.snapshot_identity(workspace_root, declared_generated_paths).digest`
   and `runtime_capability_profile_identity = opencode_adapter.probe_opencode_profile(...)
   .identity`, computed at packet-construction (compile) time. `context_digest` stays a
   fixture constant — real Context Compilation is M4, unchanged from M2's scope decision.
   A test asserts `build_attempt_packet` no longer produces the old fixture-constant shape
   for the two fields M3 makes real.
2. **A minimal reference driver** — `product/src/execution/run_one_task.py` — ties
   `build_attempt_packet` -> publish -> `host.execute` -> publish -> `stub_verify` ->
   publish -> (`build_receipt` -> publish) into one callable function for exactly the M2/M3
   one-task shape, replacing the M2 integration test's ad hoc inline sequencing with a named
   entry point. This is still not a CLI or a service — it is the first concrete "production"
   caller referenced in §5.1/§9, so future milestones (M4 context wiring, M6 orchestration)
   have one real place to extend rather than each reinventing the sequence. `test_m3_
   integration.py` (§9) calls this function directly rather than re-deriving the chain
   inline.

No change to how the returned `ResultV1` is published — `publish.py`'s existing
`RESULT_ATTEMPT_BINDING_MISMATCH` etc. still apply unmodified.

## 9. Test plan

### Workspace Snapshot (`product/tests/execution/test_workspace_snapshot.py`)

- deterministic: unchanged workspace state produces an identical digest across repeated
  calls.
- staged/unstaged/untracked/generated-declared each independently change the digest when
  mutated, and are independent of each other (changing one does not mask another).
- nested-repository root contributes its own commit id, not flattened content.
- two workspaces with identical tracked HEAD but different untracked content produce
  different digests (this is the exact gap roadmap bullet 1 calls out).

### Containment (`product/tests/execution/test_containment.py`)

- all six escape fixtures from §4 fail closed.
- both legitimate not-yet-existing-path fixtures from §4 stay admitted (existing parent
  inside root; fully non-existent path resolving inside root) — proving the "ambiguous"
  fixture wasn't accidentally rejecting ordinary write targets.
- a legitimate nested path stays admitted when unambiguously inside the resolved root.

### Attempt-packet real identities (`product/tests/execution/test_attempt.py`)

- `build_attempt_packet`'s `workspace_snapshot_digest` and
  `runtime_capability_profile_identity` equal the real §3/§5 computations for the given
  workspace/profile, not the old M2 `_fixture_digest` constants; `context_digest` remains
  the M2 fixture form (M4 scope, unchanged).

### Runtime Capability Profile / adapter (`product/tests/execution/test_opencode_adapter.py`)

- effective `config_identity` changes when an inherited/default config layer changes, even
  if the project-level file is untouched.
- effective `permission_envelope` is never a superset of what step-2 resolution actually
  grants (a synthetic "runtime tries to widen via default" fixture is rejected).
- unmapped canonical action stays `UNKNOWN`; a mapped-but-unenforceable one stays `PARTIAL`;
  `require(...)` fails closed for both when declared required.
- changing the probed binary version, config, or tool-mapping identity changes
  `RuntimeCapabilityProfile.identity` (drift changes identity — roadmap exit bullet).

### Host / deny-first execution (`product/tests/execution/test_host.py`)

- execution-time profile mismatch (stale admission) is rejected before any side effect —
  `STALE_RUNTIME_CAPABILITY_PROFILE`.
- execution-time workspace snapshot mismatch is rejected before any side effect —
  `STALE_WORKSPACE_SNAPSHOT`.
- workspace state changed **between admission (step 3) and spawn (step 4)** is caught by
  step 3.5's immediate pre-spawn recheck (test injects a mutation via a test-only hook
  between the two steps and asserts rejection) — proves the shrunk-window mechanism from
  §3.1/§6 step 3.5 actually functions; the doc does not claim this closes the full
  swap-restore TOCTOU case (§3.1), only the ordinary concurrent-modification case.
- an Attempt requiring a capability the live profile does not mark `SUPPORTED` is rejected
  by `admit_attempt`/`require()` before the adapter is invoked — this is the test that
  replaces the withdrawn "network call is blocked at the process boundary" claim: an
  Attempt whose required capabilities include network-denial-as-guarantee is rejected
  because the OpenCode profile marks `network` `PARTIAL`, not `SUPPORTED` (§6 step 4).
  A **separate, explicitly-labeled** test may assert the advisory env state (no proxy vars
  set) as a non-enforcement observation only — the test name and docstring must say
  "advisory, not enforced."
- with an empty `permission_envelope.credentials`, ambient environment secrets set in the
  test process are **not** visible inside the executed subprocess (fixture: set a sentinel
  env var in the test process, assert the adapter-invoked subprocess cannot read it). This
  one *is* a real process-boundary enforcement test (§6 step 4 credentials bullet).
- exit code 0 with a stdout claiming success, but no workspace state change, still produces
  a Result whose `output_snapshot_digest` reflects the *unchanged* state — proving
  completion is derived from snapshot identity, not from stdout/exit code.
- `permission_envelope.external_effects` empty (every M3 fixture) means any
  external-effect-shaped request is rejected before execution.
- the probed binary path changing between probe (§5) and step 3.5's pre-spawn recheck is
  rejected rather than silently executed against the new path (closes roadmap's "no silent
  runtime/transport/tool fallback" bullet — previously ungated, §13 LOW 2).

### Redaction (`product/tests/execution/test_redaction.py`)

- synthetic AWS-key-shaped and PEM-block-shaped canary fixtures are detected as `blocked`.
- non-UTF8/binary content resolves to `unknown`, not `passed`.
- ordinary non-secret text resolves to `passed`.
- the canary fixture's raw string value never appears in any assertion output/log the test
  itself prints (meta-test: fail the test file's own construction if it would leak the
  fixture into a shared log path).
- `admission.admit_attempt` with `retain_evidence=True` and a `blocked`/`unknown` scan
  result returns `BLOCKED` (exercises the already-existing `admission.py` check end to end
  for the first time).

### Conformance fixtures (deterministic, no live OpenCode/network required)

- `product/tests/execution/fixtures/fake_opencode/` — a deterministic fake "opencode"
  executable (a small script fixture) that the adapter tests point `binary_path` at, so the
  entire suite above runs without a real OpenCode install or network access.
- a single supplemental **live smoke test**, explicitly marked/skippable
  (`@unittest.skipUnless(shutil.which("opencode") and os.environ.get(
  "AGENT_PLATFORM_LIVE_SMOKE"), ...)`), that runs `host.execute` against the real installed
  OpenCode binary for one trivial task. Never required for CI/regression green.

### End-to-end integration (`product/tests/kernel/test_m3_integration.py`)

- full M2 chain (`Request -> ... -> Receipt`) re-run with `host.execute` replacing
  `stub_execute` as the Result producer, using the fake-OpenCode fixture — proves the swap
  is call-site-only and the Kernel publish boundary is unaffected.

### Regression

```bash
PYTHONPATH=product/src python3.12 -m unittest discover -s product/tests/contracts -p 'test_*.py' -v
PYTHONPATH=product/src python3.12 -m unittest discover -s product/tests/kernel -p 'test_*.py' -v
PYTHONPATH=product/src python3.12 -m unittest discover -s product/tests/execution -p 'test_*.py' -v
PYTHONPATH=product/src python3.12 -m unittest discover -s product/tests/verification -p 'test_*.py' -v
python3.12 -m compileall -q product/src product/tests
```

All M0/M1/M2 suites must remain green. `product/src/verification/` is untouched;
`product/tests/verification/` stays green unmodified.

## 10. Implementation order

Seven PRs, each independently reviewable and each sized so no single PR mixes an
enforcement-boundary change with an unrelated one. PR6 was split from the original six-PR
draft after review (§13, MEDIUM 1) because "swap the call site" alone cannot work without
also filling real identities at packet construction:

1. **Workspace Snapshot identity** — `execution/workspace_snapshot.py` +
   `test_workspace_snapshot.py`. Pure/deterministic, no admission/Host wiring yet.
2. **Containment hardening** — adversarial fixtures against the existing
   `admission._resolve_inside`, `test_containment.py`, including the two legitimate
   not-yet-existing-path fixtures (§4). No production code change expected unless a fixture
   finds a real gap.
3. **OpenCode adapter probe + M3 policy table** — `execution/opencode_adapter.py` (profile
   construction only, no execution yet), `execution/policy.py` (§5.1's fixed
   `M3_REQUIRED_CAPABILITIES`/`M3_ADMITTED_PERMISSIONS` constants) + fake-opencode fixture +
   `test_opencode_adapter.py`.
4. **Deny-first Host** — `execution/host.py` (`execute`), wiring §5's profile probe + §3's
   snapshot recompute + §5.1's fixed policy + `admission.admit_attempt` + step 3.5's
   pre-spawn recheck + the adapter's process wrapper (credentials real, filesystem/process
   declared-scope, network/filesystem/process axes profiled `PARTIAL` per §6) +
   `test_host.py`.
5. **Redaction gate** — `execution/redaction.py` + `test_redaction.py`, wired into
   `host.execute`'s retention path, scoped to captured stdout/stderr only (§7).
6. **Attempt-packet real identities** — `execution/attempt.py`'s `build_attempt_packet`
   updated to compute `workspace_snapshot_digest`/`runtime_capability_profile_identity` via
   §3/§5 instead of `_fixture_digest`; `test_attempt.py` proves the fixture-constant shape
   is gone for those two fields.
7. **Reference driver + E2E integration** — `execution/run_one_task.py` (§8), delete
   `stub_host.py`, `test_m3_integration.py` exercising the full chain through the new
   driver function.

## 11. M3 exit gate

M3 may be checked in Issue #34 only when all are true:

- Traversal, symlink, chained-symlink, and nested-repository escape cases fail closed, and
  the two legitimate not-yet-existing-path cases stay admitted (§4/§9).
- An Attempt requiring a capability the live `RuntimeCapabilityProfile` does not mark
  `SUPPORTED` cannot execute; no implicit degraded mode is invented (only an explicitly
  admitted one would count, and M3 declares none). This is the mechanism that closes
  network and filesystem/process-interception requirements honestly — those axes are
  profiled `PARTIAL`/`UNKNOWN`, not falsely `SUPPORTED` (§2, §6).
- Runtime/config/tool-mapping drift changes `RuntimeCapabilityProfile.identity`, and a
  stale identity at execution time — including drift caught by the immediate pre-spawn
  recheck (§6 step 3.5) — is rejected before any side effect
  (`STALE_RUNTIME_CAPABILITY_PROFILE`); a probed-binary-path change between probe and spawn
  is rejected, not silently substituted (§9).
- The effective permission envelope after inherited/default config resolution is never
  wider than the admitted envelope (§5.5, §9 fixture); no default/inherited layer can
  widen filesystem/network/process/credential/external-effect authority. `admitted_
  permissions`/`required_capabilities` are bound to the fixed §5.1 policy table, not to an
  unbound driver-supplied value.
- Runtime exit code/stdout cannot by itself establish completion — a zero exit's
  `output_snapshot_digest` is derived from actual post-execution Workspace Snapshot state
  (§6.6, §9 fixture); a nonzero exit raises before any Result is built (§6 step 5.5, §14).
- Credential denial (ambient env not inherited) is a real process-boundary control, proven
  by fixture (§9). External-effect denial is real declarative admission rejection, reachable
  through `execute`'s own `requested_effects` parameter, but **not** a process-boundary
  control (§14 correction). Network and filesystem/process-interception-beyond-declared-
  scope are **not** claimed as enforced — this gate does not require a network-blocking
  fixture, only the capability-admission rejection fixture (§9).
- Retained canary secret fixtures (captured stdout/stderr, when `retain_evidence=True`) are
  detected and never persist raw secret material anywhere the gate covers (§7, §9); the gate
  does not claim to cover a broader "any produced-artifact text" surface.
- Deterministic adapter conformance fixtures (fake OpenCode) pass without any live
  runtime/network dependency; the one live smoke test stays supplemental and skippable.
- `build_attempt_packet` (or its M3 form) produces real `workspace_snapshot_digest`/
  `runtime_capability_profile_identity` values, not M2's fixture constants (§8, §9).
- Full M0/M1/M2 regression suites remain green; `verification/` package untouched.
- No context compilation, evidence-policy hardening, orchestration expansion, or
  multi-runtime portability was introduced.

After merge, attach the PR(s) and test evidence to Issue #34 before checking M3.

## 12. Explicit deferrals / next handoff

### M4

- deterministic Context Compiler replacing M2's opaque `context_digest` fixture field with
  a real structured Context Pack; Workspace Snapshot identity (§3, now real) becomes one of
  its freshness-check inputs.

### M5

- hardened criterion/evidence policy, execution-provenance independence (distinct attempt/
  execution identity beyond string inequality), durable Finding lifecycle. M3's real Result/
  Runtime Observation binding makes this possible but does not implement it.

### M6

- retry/repair/replan against a real (not stubbed) execution boundary; multi-task DAG;
  Reviewer/Verifier split real risk-tier computation.

### M8

- additional runtime adapters (Claude, Codex, Roo) built against the same
  `RuntimeCapabilityProfile`/containment/redaction primitives this milestone establishes;
  cross-runtime canonical-action conformance matrix.

### M9

- external-effect/release authorization (`permission_envelope.external_effects` stays empty
  for every M3 path — no push/PR/merge/deploy capability exists yet).

### Not milestone-numbered — open item in `security-and-data-boundaries.md`

- a sophisticated secret-classification taxonomy beyond §7's minimal canary scanner. The
  roadmap does not assign this to any specific milestone number (correcting the prior draft,
  which mislabeled it M9 — roadmap M9 is supply-chain/release, not redaction taxonomy); it
  remains the security doc's explicit "Open" item, revisited when evidence retention needs
  broader coverage than captured stdout/stderr.

### Real sandbox / network and filesystem interception (no milestone number yet)

- a concrete per-OS enforcement mechanism (macOS `sandbox-exec`/Seatbelt profile, Linux
  seccomp-bpf or network namespace) for the axes M3 explicitly could not enforce (§2, §6):
  network denial and filesystem/process interception beyond declared-candidate-path policy.
  Not assigned to M4-M9 by the roadmap; raised here so it isn't lost, and should get an
  explicit milestone slot (roadmap amendment) before any workflow's task genuinely requires
  those guarantees as `SUPPORTED` rather than `PARTIAL`.

This boundary is deliberate: M3 should make M4-M9 possible against a real execution
boundary, not partially implement them or simulate real context assembly, evidence
judgement, or orchestration.

## 13. Adversarial review log

Reviewed by `glm-5.3` (effort `high`, via `opencode`) against roadmap §3's five lenses, the
roadmap M3 section, M2 precedent, and the two governing architecture docs, before this plan
was locked. Full review transcript: `/tmp/glm_review_out.txt` (session-local; not checked
in). Findings and how each was resolved in this revision:

- **BLOCKER 1** (network deny-first claimed as real process enforcement; pure-Python
  subprocess wrapping cannot deliver it) — resolved: §2/§6 now state network is
  `PARTIAL`/`UNKNOWN`, not enforced; §9's process-boundary network-block test replaced with
  a capability-admission-rejection test; §11 gate updated to not require network blocking.
- **HIGH 1** (`admitted_permissions`/`required_capabilities`/`candidate_paths` unbound to
  anything authoritative; exit-gate bullets vacuous; no real driver exists) — resolved:
  §5.1 adds a fixed M3 policy table `host.execute` binds to exclusively; §8 corrects the
  false "call-site swap in an existing driver" claim and adds a named reference driver
  (`run_one_task.py`).
- **HIGH 2** (TOCTOU: recompute-to-spawn window and non-atomic digest collection unclosed)
  — resolved: §3.1 states the residual window honestly and assigns closure to M5/M7; §6
  step 3.5 adds an immediate pre-spawn recheck; §9 adds a fixture for the window it does
  close (concurrent modification between admission and spawn), explicitly not claiming the
  swap-restore case is closed.
- **HIGH 3** (filesystem/process "enforcement" is declared-list validation, not
  interception; §2 overclaimed) — resolved: §2/§6 relabel filesystem/process as
  declared-scope policy checks, `PARTIAL` capability status, real sandbox deferred.
- **MEDIUM 1** (§8 omitted the packet-construction change M3 cannot work without) —
  resolved: §8 now states both required changes; PR6 added to §10.
- **MEDIUM 2** (generated-paths described as a task-contract field that doesn't exist and
  can't be added) — resolved: §3/§4 reworded to "driver-supplied, digest-bound parameter."
- **MEDIUM 3** (missing-intermediate-directory fixture would contradict legitimate write
  candidates) — resolved: §4 splits the fixture into real-ambiguity-rejects and
  legitimate-not-yet-existing-path-admits cases.
- **MEDIUM 4** (redaction gate has no retained text surface in M3; scope drifted toward
  M9-adjacent "any produced-artifact text") — resolved: §7 scopes the gate to captured
  stdout/stderr only, when `retain_evidence=True` is requested.
- **LOW 1-5** — dead-run diagnosability noted in §5 (`STALE_*` execution-layer language
  already states no Kernel record is produced); no-silent-fallback gained an explicit §9/§11
  test (probed-path drift rejection); M9 mislabel fixed in §12; supported platforms named
  at the top of this doc; untracked-file hashing bound/symlink-safety left as a §9
  implementation note for PR1 (skip symlink targets or hash the link string, not unbounded
  dereferenced content).

## 14. Second-round PR review fixes (implementation-phase)

After PR #45 (implementation) and this plan's own PR #44 were opened, the repository owner
and an automated reviewer (`chatgpt-codex-connector`) left adversarial findings against both
the plan and the shipped code. All P1 findings were investigated against the actual
committed code (not assumed correct) and either fixed or explicitly, honestly deferred.
Findings and resolutions, consolidated (individual sections above carry inline
"corrected after PR review (§14)" pointers at the exact claim each fix touches):

- **Generated-output content not hashed** — `generated_digest` hashed only declared path
  names; a Git-ignored artifact could change with no digest change. Fixed: each path's own
  file/symlink/absent state is hashed (§3).
- **Nested-repository dirty state invisible** — nested identity bound only path + HEAD
  commit; uncommitted content inside a nested worktree never changed the outer digest.
  Fixed: nested identity recurses through the nested repo's own full `snapshot_identity`
  (§3).
- **Symlink-loop containment platform/version dependence** — `Path.resolve(strict=False)`'s
  loop-handling behavior is not guaranteed identical across Python versions/platforms.
  Hardened with an explicit, version-independent bounded symlink-chain walk before `resolve`
  (§4); this repository's own test suite already passed the cited case, so this is
  defense-in-depth, not a regression fix.
- **Runtime profile bound only to a reported version string** — a binary substituted in
  place with different code reporting the same `--version` would pass the no-silent-
  substitution recheck. Fixed: a content digest of the executable's actual bytes is folded
  into `runtime` (§5).
- **`M3_REQUIRED_CAPABILITIES`/`M3_ADMITTED_PERMISSIONS` not bound to attempt/profile
  identity** — a future policy-table change could execute an old Attempt Packet under
  different requirements with no staleness mismatch. Fixed: both folded into
  `config_identity`, so a policy change changes `RuntimeCapabilityProfile.identity` and the
  Host's existing execution-time recheck catches drift (§5.1). The narrower "M3 cannot
  express per-task capability requirements" limitation is accepted scope, stated explicitly,
  not solved — see §5.1's closing note.
- **Config precedence documented (and thus exercisable) backwards** — "pass specific first,
  inherited/global last" combined with "later overrides earlier" would let an inherited
  layer silently win. Fixed: corrected calling convention (general-first, specific-last);
  locked in by a new test (§5).
- **Config provenance not proven to match the spawned process** — the probe reads
  `config_paths`, but OpenCode's CLI has no flag to pin a live process to exactly that
  merged view or suppress its own further global-config discovery. **Not solved** — documented
  honestly as the same unenforceable-at-process-level class as network denial; the Host pins
  only the project-layer config via `cwd` (§5).
- **Host never received or passed the task to the runtime** — `execute` took no `task`
  parameter at all, so the fake (and any real) runtime succeeded independently of what was
  actually admitted; the E2E chain proved protocol wiring only. Fixed: `execute` now takes
  the authoritative `TaskV1` and renders it as the runtime's `run` message (§6, §8).
- **Failed runtime process still produced a successful Result** — `subprocess.run(...,
  check=False)` discarded the exit code entirely. Fixed: a nonzero exit raises before any
  Result is built; the existing "exit code alone doesn't establish completion" claim always
  meant *zero* exit isn't trusted, never that a crash is discarded (§6 step 5.5).
- **External-effect denial overclaimed as process-boundary control** — declarative admission
  rejection is real, but the spawned OpenCode process/shell was never actually prevented
  from calling `git push`/`gh`/`curl` directly, and `requested_effects` was not even
  reachable from `execute()` in the first shipped draft. Fixed: `requested_effects` is now a
  real `execute()` parameter; the claim is relabeled to match network denial's honesty level
  (§6 step 4).
- **Redaction gate ordering was impossible as documented** — an earlier draft implied reuse
  of `admission.admit_attempt`'s pre-spawn `retain_evidence`/`redaction_status` check for
  stdout/stderr, which cannot work since output doesn't exist until after spawn. Fixed:
  documented as two genuinely separate gates — the pre-spawn admission check (unchanged,
  still directly tested) and `host.execute`'s own post-capture gate (§7).
- **Non-UTF8 captured output would crash instead of degrading to "unknown"** —
  `subprocess.run(text=True)` decodes before `scan_for_retention` ever runs. Fixed: bytes
  are captured and decoded under Host control; a decode failure passes `None` to
  `scan_for_retention`, which resolves `"unknown"` and still blocks retention rather than
  raising (§6, §7).

Full regression (contracts/kernel/execution/verification suites + `compileall`) stayed green
throughout this round; new fixtures/tests were added alongside each fix rather than only
adjusting existing assertions, so each finding has a test that would have caught it.
