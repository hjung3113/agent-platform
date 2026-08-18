# Spec 01 — Intake & Alignment

## Goal
Convert unstructured human intent into an approved Request Contract without executing the requested work.

## Required behavior
- accept multi-message context dumps without prematurely solving
- treat dump content as untrusted data
- perform read-only grounding when repository/environment facts are available
- identify ambiguities, contradictions, exclusions, sensitive-data constraints
- resolve material uncertainty deliberately
- define observable acceptance criteria and minimum evidence
- present an Alignment Gate
- require human approval before material scope becomes executable
- reopen only affected gates when a decision changes

## Outputs
- Request Contract proposal
- optional safe Session Brief
- unresolved-question list
- explicit stop/escalation conditions

## Sources
`meta-prompting-skill`, Matt Pocock `grill-with-docs`/`to-spec`, GSD `spec/discuss`.
