---
name: diagnosing-bugs
description: Diagnosis loop for hard bugs and performance regressions. Use when the user says diagnose/debug, or reports something broken, failing, throwing, or slow.
---

# Diagnosing Bugs

A disciplined diagnosis loop. Skip phases only when explicitly justified.

Read relevant `CONTEXT.md`, governing specs/ADRs, and repository instructions before forming a theory.

## Redact

Commands, outputs, and captured artifacts may contain secrets. Redact secrets before retaining or presenting them; prefer environment variables over embedding credentials. If redacted evidence is insufficient, state the gap.

## Phase 1 — Build a feedback loop

Build a tight pass/fail signal that goes red on **this exact bug**. Prefer, in order where applicable:

1. Failing test at a real seam.
2. CLI invocation with fixture input and known-good output.
3. Replay of a captured trace/event/log through the code path.
4. Throwaway harness exercising the smallest meaningful subsystem.
5. Property/fuzz loop for intermittent wrong output.
6. Bisection or differential harness for regressions between known states.
7. Protocol/API/browser loop only when the bug actually lives at that boundary.
8. Human-in-the-loop script as last resort; use `scripts/hitl-loop.template.sh` as a generic template.

Tighten the loop until it is red-capable, deterministic enough for the bug class, fast enough to iterate, and runnable by the available environment.

## Phase 2 — Reproduce + minimise

Run the loop and confirm it reproduces the user's exact symptom. Minimise the scenario one input/caller/config/data/step at a time until every remaining element is load-bearing.

## Phase 3 — Hypothesise

Generate 3–5 ranked, falsifiable hypotheses. Each must predict what observation or controlled change would support or refute it. Avoid single-hypothesis anchoring.

## Phase 4 — Instrument

Map every probe to a hypothesis. Change one variable at a time. Prefer debugger/REPL inspection, then targeted logs. For performance regressions establish a measurement baseline and use profiling/query plans/bisection rather than log volume.

Tag temporary instrumentation uniquely so cleanup is mechanical.

## Phase 5 — Fix + regression test

Turn the minimised repro into a regression test at a correct seam before the fix when feasible. Apply the smallest fix, watch the test pass, then rerun the original feedback loop. If no correct seam exists, record that architectural limitation instead of manufacturing a weak test.

## Phase 6 — Cleanup

Before declaring done:

- original repro no longer fails;
- regression evidence passes or the missing seam is documented;
- temporary instrumentation/prototypes are removed;
- the confirmed root cause is captured in the change/PR evidence;
- no retained secret material was introduced.
