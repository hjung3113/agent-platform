# ADR Format

This file is fallback guidance from the upstream skill. Existing project ADR conventions and status/authority rules override it.

ADRs normally live in `docs/adr/` and use sequential numbering. Reuse the repository's existing numbering and template rather than introducing a parallel convention.

## Minimal template

```md
# {Short title of the decision}

{1-3 sentences: what's the context, what was decided or proposed, and why.}
```

Optional sections such as Status, Considered Options, and Consequences should be added only when they add value.

## When to offer an ADR

All three should be true:

1. **Hard to reverse**.
2. **Surprising without context**.
3. **The result of a real trade-off**.

In agent-platform, writing an ADR candidate does not itself make the decision authoritative. Follow the governing Human/Kernel admission rules for status and acceptance.
