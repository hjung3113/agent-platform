# Matt Pocock Skills

Status: STRONG CONCEPT + SELECTIVE DIRECT-REUSE CANDIDATE
License: MIT

Primary sources:
- README: https://github.com/mattpocock/skills
- Invocation taxonomy:
  https://github.com/mattpocock/skills/blob/main/.agents/invocation.md
- grill-with-docs:
  https://github.com/mattpocock/skills/blob/main/docs/engineering/grill-with-docs.md
- to-spec:
  https://github.com/mattpocock/skills/blob/main/docs/engineering/to-spec.md
- to-tickets:
  https://github.com/mattpocock/skills/blob/main/docs/engineering/to-tickets.md
- writing-great-skills:
  https://github.com/mattpocock/skills/blob/main/skills/productivity/writing-great-skills/SKILL.md

High-value concepts:
- user-invoked vs model-invoked is the primary skill split
- router skill compensates for human cognitive load when explicit skills proliferate
- model-invoked descriptions have permanent context cost
- progressive disclosure and no-op pruning
- `grill-with-docs` updates domain vocabulary and ADRs while aligning
- `to-spec` turns settled context into a buildable spec
- `to-tickets` slices work vertically; expand-contract exception for wide refactors
- codebase-design/deep-module vocabulary and deletion test
- triage state machine verifies claims before marking ready

Good reuse/adaptation candidates:
- grilling / grill-with-docs
- domain-modeling
- codebase-design
- to-spec
- to-tickets
- diagnosing-bugs
- code-review
- writing-great-skills
- resolving-merge-conflicts

Integration rule:
User-invoked skills may orchestrate local model-invoked disciplines but may not create a
second authoritative workflow state outside the Kernel protocol.
