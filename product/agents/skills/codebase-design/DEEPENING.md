# Deepening

How to deepen a cluster of shallow modules safely, given its dependencies. Assumes the vocabulary in [SKILL.md](SKILL.md): **module**, **interface**, **seam**, **adapter**.

## Dependency categories

### 1. In-process

Pure computation or in-memory state. Merge only when the resulting interface becomes meaningfully deeper and clearer.

### 2. Local-substitutable

Dependencies with realistic local test stand-ins. Test the deepened module through the stand-in at its seam.

### 3. Remote but owned (Ports & Adapters)

For owned services across a network/process boundary, define a port only where the boundary is real. Production and test adapters can satisfy it without leaking transport semantics into the deep module.

### 4. True external

For third-party services, inject an explicit port and use a controlled test adapter/mock at the seam.

## Seam discipline

- **One adapter means a hypothetical seam. Two adapters means a real one.**
- Deep modules may have internal seams without exposing them as public interfaces.
- Do not deepen across a deliberate authority, security, failure-domain, or lifecycle boundary merely to reduce file count.

## Testing strategy: replace, don't layer

- Prefer tests at the deepened module's observable interface.
- Remove obsolete implementation-coupled tests only after equivalent behavioural coverage exists at the new seam.
- Tests should survive internal refactors and assert observable outcomes, not implementation structure.
