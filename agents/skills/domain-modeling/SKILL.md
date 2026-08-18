---
name: domain-modeling
description: Build and sharpen a project's domain model. Use when discussing codebase terminology, writing or editing a CONTEXT.md, or recording or editing an ADR.
---

# Domain Modeling

Actively build and sharpen the project's domain model as you design. This is the *active* discipline — challenging terms, inventing edge-case scenarios, and writing the glossary and decisions down when they crystallise. Merely reading `CONTEXT.md` for vocabulary is not this skill.

## Project override

Existing repository conventions are authoritative over the bundled fallback formats. In this project, preserve the established `CONTEXT.md` structure, including both vocabulary and relationships; do not rewrite it into a glossary-only shape. Existing ADR format/status rules also win. A proposed ADR edit remains a proposal until the governing Human/Kernel process admits it; never mark a material decision accepted merely because this skill wrote the file.

## File structure

Most repos have a single context:

```
/
├── CONTEXT.md
├── docs/
│   └── adr/
└── src/
```

If a `CONTEXT-MAP.md` exists at the root, the repo has multiple contexts. The map points to where each one lives.

Create files lazily — only when you have something to write. If the repository already has context/ADR conventions, extend those conventions rather than creating a competing structure. Use [CONTEXT-FORMAT.md](./CONTEXT-FORMAT.md) and [ADR-FORMAT.md](./ADR-FORMAT.md) only as fallback guidance where the repository has no stronger convention.

## During the session

### Challenge against the glossary

When the user uses a term that conflicts with the existing language in `CONTEXT.md`, call it out immediately and resolve the conflict explicitly.

### Sharpen fuzzy language

When the user uses vague or overloaded terms, propose a precise canonical term and distinguish nearby concepts.

### Discuss concrete scenarios

Stress-test domain relationships with specific scenarios, especially edge cases that force precise boundaries between concepts.

### Cross-reference with code

When the user states how something works, check whether the code and governing specs agree. Surface contradictions instead of silently choosing one interpretation.

### Update domain context inline

When terminology is resolved, update the appropriate project context document while preserving its established structure. Do not batch unrelated cleanups into the same change.

### Offer ADRs sparingly

Only offer to create an ADR when all three are true:

1. **Hard to reverse** — the cost of changing your mind later is meaningful.
2. **Surprising without context** — a future reader will wonder why the choice exists.
3. **The result of a real trade-off** — genuine alternatives existed and a choice was made for specific reasons.

If any condition is missing, skip the ADR.
