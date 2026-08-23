# Failure-Mode Ledger

M5 deliverable per [`mvp-implementation-roadmap.md`](../plans/active/mvp-implementation-roadmap.md)
M5 section, tracking [Issue #46](https://github.com/hjung3113/agent-platform/issues/46). Mines
sibling repositories' own git history/PRs for concrete failure/regression/bug records — not
design-pattern adoption, which [`adoption-ledger.md`](adoption-ledger.md) already covers — so
M6's adversarial review starts from real prior failures instead of rediscovering them from
scratch.

Each mining-scope repo was scanned via `codex --model gpt-5.6-luna -c
model_reasoning_effort="xhigh" --sandbox read-only`: a cheap `git log --all` keyword pass
(fix/bug/regression/revert/hotfix/crash/race/leak/deadlock/security/incident/broke/failed)
first, then a deep read of the actual commit diff/PR body for flagged items only. GitHub
issue/PR API access was unavailable in the sandboxed recon environment for 3 of the 4 repos;
those relied on local PR refs and commit bodies instead. Status is `open` unless noted —
these are unaddressed-in-agent-platform records, not yet-fixed bugs in the source repos (all
were already fixed there).

## opencode-orchestrated-agent-workflow

Scanned git log 2026-07-29..2026-08-18 (147 commits); 43 records flagged, 43 commit diffs
deep-read.

| commit/PR ref | failure mode | their fix | applicability to agent-platform | status |
|---|---|---|---|---|
| PR #47 / 583d361, 7ce8201 | M4 gates passed preflight on non-Homebrew hosts or missing providers, while unsupported OpenCode versions passed. | Resolve runtimes dynamically, skip unavailable external gates, enforce OpenCode ≥1.18.5. | Runtime preflight and CI/provider gates (M3 `execution/opencode_adapter.py` provenance probing) | open |
| PR #47 / 583d361, 7ce8201 | Worker Result retry dropped the first observation and did not consume durable execution budget. | Retain both observation refs, journal retry admission, surface both parse errors. | Attempt budget and Result lineage (M2/M4) | open |
| 4d35c12, 270a403, b255bfb | M0 could claim cancel-reconciliation success from the wrong session; loose "sent/requested" timing. | Dedicated session, fail-closed for unverified reconciliation, record request-finish/process-exit times. | Capability probes and independent verification (M3) | open |
| 09cb345 | Attempt deadlines started only after event-stream readiness, so a stalled event stream delayed timeout enforcement. | Start the deadline independently of event subscription readiness. | Scheduler and runtime deadline control (M7) | open |
| e5bcdac | Omitting the public request silently selected a default action. | Require a non-empty explicit human request before creating a Run. | Intake and public command boundary | open |
| def2e78, 82c905c | Worker Result claims were parsed before kernel observation and could disagree with the actual workspace diff/snapshot. | Split edit/proposal turns; require and validate worker snapshot/resources against observations. | Worker Result and Output Snapshot seam (M3 Workspace Snapshot) | open |
| 82c905c | Command evidence checked mainly output digest; direct command execution allowed provenance mismatch and network access. | Bind evidence to admitted argv/cwd/policy; run commands under network-denying sandboxing. | Command admission and execution security (M3 `execution/policy.py`, network denial still unenforced) | open |
| e725c65, c07da36, 5241eae | Model-inferred materiality could pause ordinary requests; the check occurred after workflow preparation. | Derive explicit request-grounded materiality at intake; checkpoint before dispatch. | Intake and Decision Authority gate | open |
| ec2755f | A non-empty Decision response was effectively treated as acceptance; rejection could not remain durable. | Require explicit accepted/rejected disposition; keep rejection checkpointed until superseded. | Decision records and Promotion controller (M7) | open |
| 75d19ed | Restarted Runs completed without carrying the accepted Decision reference into the Receipt. | Include durable decision refs in Receipt inputs and artifact refs. | Receipt lineage (M1/M2) | open |
| 780f5c2, 9eaf3a7, bf1d860 | Process-death cancellation could stall without an active binding; repeated resume could duplicate cancellation effects. | Write fallback cancellation evidence, reconcile cancelling state, make no-runtime retries idempotent. | Cancellation and recovery state machine (M7) | open |
| e32a0b9 | Transient provider/network failures became generic terminal blocks requiring a new Run. | Emit typed resumable provider-failure blocks; resume without duplicate artifacts. | Provider adapter and recovery (M7) | open |
| 2f681cc, 778749b, 3706c85, 4f5ee4c | Provider accepted a POST but connection loss caused resume to risk a new session/dispatch and lose workspace state. | Durably prepare bindings, mark ambiguous attempts unreachable, reconcile via GET, preserve workspaces. | Runtime attempt journal and reconciliation (M3/M7) | open |
| 4c76ef1, d0e2622, f122a80, 34916fb, 115e425 | Crashes between prepared execution, observation publication, and Run State admission could repeat GETs or admissions. | Persist complete prepared bytes, publish one canonical observation, replay one action per resume. | Crash-safe journal and replay (M1 authoritative publication, M7) | open |
| 358691f, 1cb9808, f09f7af | Result publication left no safe continuation path, allowing downstream graph/verifier replay or multi-action resume. | Rebuild from the Result ref, reuse admitted state, advance one checkpoint/action per resume. | Scheduler continuation and recovery (M7) | open |
| adb4fd8, 58af23c, 6a6a9b6 | Worker edit/proposal/reconciled observations reused IDs or refs, risking overwrite and lost edit provenance. | Separate observations, retain canonical reconciled refs, reject conflicting duplicate IDs. | Runtime observation and artifact store (M3/M4) | open |
| 3f77019, edc27b3, 6617273, 91374ae, a1d0970, 785684f | Digest-valid but semantically forged planner/worker/verifier provenance could reach a completed Receipt. | Recursively validate refs; enforce role, actor, session, task, attempt, graph, packet, and snapshot consistency. | Kernel Receipt verifier and lineage — **directly relevant to M6** (#5 verification/evidence soundness) | open |

## agent-migration-pipeline

Scanned git log 717927a..325126b (175 commits); 35 keyword hits flagged, 5 PR/commit clusters
deep-read (GitHub issue API unavailable, local PR bodies used instead).

| commit/PR ref | failure mode | their fix | applicability to agent-platform | status |
|---|---|---|---|---|
| PR #55 / 5f252ef | Status reporting skipped validation; malformed frontmatter and canonical/legacy alias conflicts could pass. | Validate before status reporting; reject indented nesting and aliases unconditionally. | M2 artifact/admission validation | open |
| PR #56 / 6d60cce | Task-list checkboxes were misclassified as invalid provenance markers. | Exclude checkbox states; add regression coverage. | M2 evidence/record parser | open |
| PR #57 / 0bbabd5, 6180d74 | Durable-state checks accepted dangling references, invalid terminal states, phase-range omissions, stale status, concurrent stale writes. | Resolve references; enforce terminal/actionability/range invariants; hash and recheck state before writes. | `kernel/lineage_store.py` publication atomicity and fencing — **directly relevant to M6** | open |
| PR #60 / b8456aa | Clean-checkout tests failed because PyYAML was undeclared and not installed. | Replace the dependency with a scoped hand-rolled parser. | M0 reproducible test/bootstrap gate | open |
| PR #63 / 076d2a0, 43025b4, 84e3abf, 27f3849 | Command preconditions self-deadlocked; STOP sync could corrupt frontmatter; invalid uniform payloads and command-contract drift passed validation. | Allow producer partial steps; insert at managed markers; validate enums, grammar, canonical names, and shared STOP payloads. | Orchestration admission and typed STOP/Result schema (M7) | open |

## general-low-reasoning-agent-harness

Scanned 4f39d7b (2026-05-15) through 28e071f (2026-06-15), 746 commits; 373 keyword hits, 37
commit candidates deep-read, collapsed to 30 records. Local PR refs #35/#37 checked; GitHub
issue/PR bodies unavailable.

| commit/PR ref | failure mode | their fix | applicability to agent-platform | status |
|---|---|---|---|---|
| 15824b0 | Release tooling created unsigned tags, causing later signed-release verification failures. | Changed `git tag -a` to `git tag -s`; signing misconfiguration now fails early. | Release provenance gate (M10) | open |
| 60018ca | `psutil` exceptions escaped handlers, Windows boot IDs drifted, stale-lock recovery could loop past its timeout. | Caught `psutil.Error`, used stable boot time, added deadline/backoff enforcement. | Kernel lock/lease recovery | open |
| 873d74d | Audit rotation released the lock before rename, letting concurrent writers race and lose or raise. | Held the flock through rotation; locked the new inode before release. | Kernel append-only event log (M1) | open |
| 046d63e | Failed lockfile writes left orphaned partial files blocking subsequent invocations. | Closed and unlinked the lockfile before re-raising the original I/O error. | Kernel lock lifecycle | open |
| 4ad934e | Explicit JSON `null` was treated as an absent field and silently defaulted to permissive mode. | Switched to key-presence checks; rejected explicit nulls. | Protocol state-schema validation — **directly relevant, same class as M4's contract-ref dedup fix** | open |
| 4982152 / 3f07b6d / 1149e0c | Migration recovery could reverse the wrong schema, assume the wrong direction, or fail on transient backup-name collisions. | Added schema guards, persisted direction in sidecars, retried O_EXCL backup creation. | M2 state migration/recovery | open |
| 8f1e465 / dc8cf31 | JTI checking used a racy JSON read-modify-write path; approval nonce files were unsigned and tamperable. | Added atomic per-JTI markers and HMAC-signed nonce files with signature rejection. | M2 admission proof/idempotency — **directly relevant to M6** | open |
| 7568378 | Tag content was resolved before signature verification completed; valid SSH tags could fail under Windows' default Git format. | Forced SSH verification, re-resolved the tag afterward, compared SHAs, read by commit SHA. | Release provenance | open |
| accfcea | Fresh source checkouts crashed on missing optional dependencies; release summaries could remain green after smoke failure. | Added actionable dependency guards and an explicit release-smoke success gate. | Release/build verification | open |
| ed08df9 / d2e6159 | Trust preflight rejected valid state when telemetry tailed the log or the latest transaction was rotated out. | Searched transaction evidence across current and rotated logs while preserving corruption checks. | Kernel lineage/receipt verification — **directly relevant to M6** | open |
| 13aeafb | Transaction audit entries missing `after_sha256` were skipped, hiding torn-write corruption. | Raised a typed integrity failure with a dedicated sub-reason. | Receipt integrity | open |
| c8f4789 | Advanced state with absent, empty, or telemetry-only audit evidence was accepted as fresh state. | Added baseline-aware fail-closed validation for missing provenance evidence. | M2 provenance verification — **directly relevant to M6** | open |
| 71d0fd4 / ae9ec06 | `verify --audit` returned success for advanced state without audit evidence and for zero-byte crash state. | Added distinct exit paths for missing audit evidence and empty crash artifacts. | Kernel recovery/verification | open |
| 562d2ed | A crash after writing the PENDING autopilot sentinel could leave active-but-invalid state; budget exhaustion could block recovery commits. | Added sentinel rollback recovery; exempted required halt/recovery commits from budget checks. | M2 transaction finalization | open |
| d671ba9 | Verification existed in tests but production paths missed replay, anchor, and manifest-chain checks or swallowed failures. | Wired checks into install/check/upgrade; surfaced parse/BOM failures explicitly. | M2 verification wiring — **directly relevant to M6** (production-path vs test-only coverage gap) | open |
| c951acd | Roo built-in ask mode was treated as unknown because validation only knew custom modes, causing 18 failures. | Included Roo's built-in mode set in check and doctor validation. | Adapter-mode validation (M9) | open |
| 227371c | Normal-next exposed harness phase set-plan, breaking the user-facing run flow. | Mapped agent-safe transitions to harness run while retaining advanced canonical commands. | none | open |
| 072a4f7 | Running `harness.py` as `__main__` caused install records to stamp `0.0.0` and ignore the requested version. | Passed the resolved harness version explicitly into install-state construction. | Artifact metadata/bootstrap | open |
| 46a712f | Windows upgrades appeared hung: completion output absent, small staging passes emitted no progress, tag verification could block indefinitely. | Added terminal summaries, authoritative staging counts, a 15-second verification timeout. | Host/runtime operator feedback | open |
| 257d43f | AV/EDR file pins exhausted short retries, aborting large installs into half-installed targets with raw tracebacks. | Extended retries, routed batch replacement through them, added writable preflight and a friendly trap. | Host filesystem adapter (M3 scope, Windows/Linux is M8) | open |
| 5f4418c | Removal counts were incremented after unlink, reporting zero removals; upgrade finalization lacked Windows retry symmetry. | Counted before unlink; shared retry-based manifest finalization. | Artifact manifest/reconciler | open |
| 9131303 | A crash between batch application and finalization could recover a pending manifest with stale rendered-file hashes. | Rewrote the sidecar after post-processing; atomically promoted it to the final manifest. | Kernel atomic publication (M1) | open |
| 29aa46b | Broken stderr pipes caused advisory progress output to abort install/upgrade. | Centralized output through an exception-swallowing advisory emitter. | Worker/transport output | open |
| 5ed7167 | Doctor compared a raw template hash with post-rendered disk content and reported permanent drift. | Recorded the existing rendered destination hash for harness-owned files. | Receipt/provenance hash accounting | open |
| f7d1081 | Audit verification compared incompatible `entry_hash` and state `after_sha256` values, making every clean lifecycle fail. | Tracked and compared the final entry's `after_sha256` field. | Receipt verification — **directly relevant to M6** | open |
| 08c94bd | State commands resolved the harness source tree instead of the project being operated on. | Added cwd ancestry/override resolution; used the installed `harness.py` path. | Host workspace binding (M3 `workspace_snapshot.py`) | open |
| 9d17ef1 / fe2428c / 6fd2750 | Fresh installs repeatedly omitted newly added library modules from the manifest, causing `ModuleNotFoundError`. | Added missing manifest entries, regenerated artifacts, broadened import-smoke/manifest checks. | Runtime packaging | open |
| dd15453 | Hash verification skipped missing files and malformed managed markers, leaving corrupted installs invisible to doctor. | Emitted explicit missing-file and malformed-marker findings. | Integrity verifier | open |
| f090f23 | Malformed phase-state JSON became empty data, so dependent consistency checks ran on invalid input. | Added structured blocking warnings; skipped checks requiring unusable state. | State parser/diagnostics | open |
| 4f437d1 | Migration copied malformed `updated_at` values into review records without validation. | Applied the UTC timestamp regex; fell back to the migration timestamp. | State migration/schema validation | open |

## thin-agent-harness

Scanned 8 commits, 2026-08-11–2026-08-17, plus local PR refs #1/#2; 2 items flagged and
deep-read (GitHub issue/PR API unavailable).

| commit/PR ref | failure mode | their fix | applicability to agent-platform | status |
|---|---|---|---|---|
| b9b9460 / PR #2 | Approval digests were circular: approval referenced a target execution digest unavailable when approval occurred; event, receipt, and conflict ownership was also ambiguous. | Added Host-owned `admitApproval`, self-bound approval digests, atomic event admission/append, typed receipt validation, conflict vocabulary. | M1 Kernel admission; M2 immutable lineage and single-writer publication — **directly relevant to M6** | open |
| d05e54b / issue #6 | `documentVersion` was inconsistently included/excluded from the record digest; advance required caller events despite Host-generated lifecycle events. | Corrected projection rules; made lifecycle admission Host-internal; clarified approval, receipt, candidate, executor ownership. | M1 public admission seam; M2 schema/version, host-event, and no-mutation E2E checks | open |

## meta-prompting-skill (applicability-only, not failure-mining)

Per M5 scope this repo is conceptual, not a failure-mining target — no git-log mining was
run.

Its core pattern — one canonical workflow, thin runtime-specific adapters, explicit state
gates, deterministic validation at the public seam — offers concrete techniques for the
Context Compiler and Kernel: its explicit completion signal, read-only grounding, untrusted-
context handling, and Alignment Gate suggest compiling only after context is complete and
binding sources/scope/exclusions/budget/stop-conditions to each Attempt Packet; its
one-canonical-workflow/thin-adapter split argues for keeping compilation policy
runtime-neutral while OpenCode-specific renderers stay small and are verified by
deterministic cross-renderer contract tests. For the M2 Request→Attempt Packet→Result→
Verification→Receipt path, these contracts could become immutable provenance attached to
Kernel-published lineage, with bounded-autonomy rules keeping generated work mapped to
approved criteria. Its model-free acceptance checks plus a separate opt-in field-evaluation
step are a practical validation pattern that avoids conflating host smoke evidence/feedback
with authoritative Kernel state.

## Scan-evidence summary (exit criterion)

| repo | commits scanned | keyword hits flagged | deep-read | records | issue/PR API |
|---|---|---|---|---|---|
| opencode-orchestrated-agent-workflow | 147 (2026-07-29..2026-08-18) | 43 | 43 | 17 | local refs only |
| agent-migration-pipeline | 175 (717927a..325126b) | 35 | 5 clusters | 5 | unavailable, PR bodies via local `gh` |
| general-low-reasoning-agent-harness | 746 (2026-05-15..2026-06-15) | 373 | 37 → 30 | 30 | unavailable |
| thin-agent-harness | 8 (2026-08-11..2026-08-17) | 2 | 2 | 2 | unavailable |
| meta-prompting-skill | n/a (applicability-only) | n/a | n/a | 1 paragraph | n/a |

All 4 mining-scope repos scanned; `meta-prompting-skill` applicability note recorded. Records
tagged **directly relevant to M6** above should be folded into M6's adversarial review
checklist before M6 design starts, per the roadmap's M5→M6 gate.
