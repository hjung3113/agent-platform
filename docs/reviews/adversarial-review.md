# Adversarial Review — Integrated Scaffold

Status labels: BLOCKER / HIGH / MEDIUM / ACCEPTABLE.

## Existing perspective 1 — Role separation and authority bleed

Finding: **HIGH, partially fixed.**

The original scaffold mixed `Memory Steward`, `Context Compiler`, and host-like responsibilities
with agent personas. The revised scaffold makes Kernel/Host/Context Compiler deterministic system
actors and keeps `agents/roles/` for reasoning roles.

Remaining attack:
- Knowledge Curator can still become a shadow authority if it writes decisions rather than proposals.
- Conductor can still become a coding super-agent if runtime permissions do not enforce read-only.

Required proof:
permission tests + publication tests showing these roles cannot write authoritative records/product code.

## Existing perspective 2 — Structural completeness / missing subsystem

Finding: **HIGH, improved.**

The earlier seven-spec split hid the run protocol inside Knowledge/Memory. That made approved
knowledge and operational state easy to conflate.

Fix:
split a dedicated Spec 03 — Contracts, Protocol & Run State.

Remaining missing pieces:
- concrete schema-version migration policy
- cancellation/reconciliation protocol
- secrets/redaction evidence policy
- artifact retention/GC policy
- exact promotion/application semantics for verified output

## Existing perspective 3 — End-to-end workflow wiring

Finding: **HIGH.**

The nominal flow is now continuous from intake to receipt, but three seams remain failure-prone:

1. **Plan -> Kernel:** a Plan Checker PASS must bind the exact plan/workflow digest the Kernel admits.
   Otherwise a revised plan can be executed after an old check.
2. **Runtime -> Review:** review/verify must bind the exact content snapshot, not only Git HEAD;
   dirty/untracked content can otherwise escape.
3. **Verify -> Release:** verified readiness must not automatically authorize push/merge/deploy.

These are explicit hard handoff invariants in `end-to-end-wiring.md`, but they need contract tests.

---

## New perspective 4 — Artifact authority, replay, and crash consistency

Finding: **BLOCKER before implementation of resume.**

Two source designs disagree:
- append-only event history as authority
- one atomically replaced run state as authority

Trying to keep both authoritative would create split-brain recovery.

Recommendation:
run a small crash-consistency spike and choose one normative authority.
Current draft prefers immutable transition lineage + derived atomic head/checkpoint, but this is not
yet proven across Windows/Linux filesystems.

Test cases:
- crash after artifact write before head publication
- crash after head temp write before rename
- duplicate Observe/Resume
- stale writer
- partial filesystem cleanup
- recovery with missing projection

## New perspective 5 — Context economics and routing load

Finding: **HIGH if the platform imports external catalogs wholesale.**

ECC demonstrates a huge skill catalog; GSD and Matt explicitly respond to routing/listing cost with
namespace routers and user-vs-model invocation taxonomy.

Risk:
the integrated project can recreate context rot at startup by advertising too many agents/skills.

Recommendation:
- small default model-invoked core
- user-invoked namespace/router commands
- progressive disclosure
- optional profile packs
- measure eager description-token budget in CI

Acceptance:
a new runtime session should discover the core route without loading hundreds of skill descriptions.

## New perspective 6 — Failure, recovery, idempotency, and retry loops

Finding: **HIGH.**

A bounded retry count alone is insufficient. FeedbackOps shows that repeated redispatch requires
origin classification and durable admission identity.

Required additions:
- idempotency key per write attempt
- failure origin enum
- retry admission record
- no model escalation as a recovery shortcut
- circuit breaker on repeated same-origin failure
- typed BLOCKED/material-decision outcomes
- cancellation reconciliation distinct from failure

## New perspective 7 — Portability and upstream drift

Finding: **HIGH.**

Directly copying Superpowers/Matt/ECC skills creates a second maintenance problem.
Cross-harness behavior can drift independently from upstream and from local adapters.

Required additions:
- `vendor/upstream-skills.lock.yaml`
- source commit/tag + license + local patch hash
- upstream update diff command
- skill behavior/eval regression before update
- no automatic update into production projects

GSD is too coupled to copy wholesale; adapt the concepts.

## New perspective 8 — Security, permission, and external-effect boundaries

Finding: **HIGH.**

A well-structured workflow is not a security boundary.

Risks:
- Conductor accidentally write-enabled
- executor gaining network/secret access through runtime defaults
- malicious Context Dump or repository docs injecting workflow policy
- symlink/path escape
- "verified" being treated as "approved to deploy"

Required:
- deny-first adapter profiles where possible
- canonical path/symlink checks
- untrusted-input boundary during Intake
- explicit external-read/network capability
- secret/redaction policy for evidence
- separate release authorization

---

# Overall verdict

**Architecture direction: ACCEPT WITH BLOCKERS.**

The role/spec decomposition is materially better than the first scaffold and has a complete conceptual
flow. Do not start broad implementation until these four blockers have explicit proofs:

1. run-state authority/crash model
2. digest-bound Plan Checker -> admitted Workflow handoff
3. exact content-identity Review/Verify binding
4. upstream skill pin/update/eval mechanism

After those, build a narrow vertical slice:

Request Contract -> one Task -> fresh Attempt -> one runtime -> evidence -> independent Verify -> Receipt.

Only then add multi-runtime, repair, parallel scheduling, and visual workflow UX.
