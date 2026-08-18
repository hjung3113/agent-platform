# ECC (affaan-m/ECC)

Status: ADAPT; selective upstream reuse only
License: MIT

Primary sources:
- README: https://github.com/affaan-m/ECC
- Skill development guide: https://github.com/affaan-m/ECC/blob/main/docs/SKILL-DEVELOPMENT-GUIDE.md
- Shorthand guide: https://github.com/affaan-m/ECC/blob/main/the-shortform-guide.md

Observed concepts:
- explicit Agent / Skill / Command / Hook / Rule taxonomy
- skills as durable workflow surface; commands increasingly compatibility/entry shims
- hooks for lifecycle/tool automation
- broad specialized agent catalog
- memory/continuous learning/context budget/security scanning
- multi-harness support

Adopt:
- canonical skill + thin command model
- hook/rule distinction
- skill metadata/validation conventions
- optional codebase onboarding/context-budget/security skill ideas

Do not import wholesale:
- hundreds of skills create routing/context/maintenance load and duplicate local roles.
- local platform should curate a much smaller default set, with optional packs.

Direct-copy policy:
MIT permits reuse with notice. Any copied skill must be pinned and attributed in
`vendor/upstream-skills.lock.yaml`, with local deltas recorded.
