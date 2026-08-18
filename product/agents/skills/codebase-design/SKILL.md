---
name: codebase-design
description: Shared vocabulary for designing deep modules. Use when designing or improving a module interface, finding deepening opportunities, deciding where a seam goes, or making code more testable and navigable.
---

# Codebase Design

Design **deep modules**: a lot of behaviour behind a small interface, placed at a clean seam, testable through that interface. The aim is leverage for callers, locality for maintainers, and testability for everyone.

## Glossary

**Module** — anything with an interface and an implementation: a function, class, package, or tier-spanning slice.

**Interface** — everything a caller must know to use the module correctly: type surface, invariants, ordering constraints, error modes, required configuration, and relevant performance characteristics.

**Implementation** — what's inside a module.

**Depth** — leverage at the interface: how much behaviour callers can exercise per unit of interface they must learn.

**Seam** — a place where behaviour can be altered without editing the caller; the location at which a module's interface lives.

**Adapter** — a concrete thing that satisfies an interface at a seam.

**Leverage** — more capability per unit of interface learned.

**Locality** — change, bugs, knowledge, and verification concentrate in one place rather than spreading across callers.

## Principles

- **Depth is a property of the interface, not the implementation.**
- **The deletion test.** If deleting the module makes its complexity reappear across callers, it was earning its keep; if complexity simply disappears, it was likely pass-through.
- **The interface is the test surface.** Callers and tests cross the same seam.
- **One adapter means a hypothetical seam. Two adapters means a real one.** Do not introduce a seam unless something actually varies across it.
- Respect agent-platform's existing authority/security boundaries; deepening is not permission to collapse Kernel/Host or other deliberate trust boundaries.

## Designing for testability

1. Accept dependencies rather than creating hidden external dependencies.
2. Prefer returning explicit results over implicit side effects where the domain permits it.
3. Keep the external surface small and correctness-relevant invariants explicit.

## Going deeper

- See [DEEPENING.md](DEEPENING.md) for dependency categories and seam discipline.
- See [DESIGN-IT-TWICE.md](DESIGN-IT-TWICE.md) for exploring alternative interfaces.
