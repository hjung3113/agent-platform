# Spec 02 — Knowledge, Decisions & Research

## Goal
Preserve durable knowledge and material decisions while keeping research and derived memory non-authoritative.

## Required behavior
- single canonical project vocabulary
- approved decisions append/supersede; never silently rewrite history
- store research with source, date/revision, confidence/adoption status
- distinguish Decision, Finding, Evidence, Research, Derived Index
- derived indexes must be regenerable and provenance-linked
- conflict/freshness detection must use source identities/digests, not timestamps alone
- knowledge curator may propose but not approve decisions

## Planes
- Constitution/authority: specs, ADRs, approved decisions/contracts
- Research: preserved source-backed investigation
- Derived: regenerable indexes
- Session hints: limited non-authoritative continuity

Run state is explicitly excluded; see Spec 03.
