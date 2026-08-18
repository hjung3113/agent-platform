# CONTEXT.md Format

This file is fallback guidance from the upstream skill. Existing project context structure overrides it.

## Structure

```md
# {Context Name}

{One or two sentence description of what this context is and why it exists.}

## Language

**Order**:
{A one or two sentence description of the term}
_Avoid_: Purchase, transaction

**Invoice**:
A request for payment sent to a customer after delivery.
_Avoid_: Bill, payment request
```

## Rules

- Be opinionated when multiple words exist for the same concept.
- Keep definitions tight.
- Prefer project-specific domain concepts over generic programming terms.
- Group terms when natural clusters emerge.
- Preserve any repository-defined additional sections, relationships, or authority semantics.

## Single vs multi-context repos

A single-context repo can keep one root `CONTEXT.md`. A multi-context repo may use a root `CONTEXT-MAP.md` pointing at context-specific documents. Infer the established structure from the repository before creating anything new.
