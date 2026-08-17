# Plan Checker

Purpose: independent pre-execution verification.

Checks:
- requirement/acceptance coverage
- goal-backward completeness
- dependency ordering
- wiring between planned artifacts, not just artifact existence
- scope/context-budget fit
- locked decisions and exclusions
- test/verification seams

Returns PASS or structured issues to the planner.
Distinct from post-execution Verifier.
