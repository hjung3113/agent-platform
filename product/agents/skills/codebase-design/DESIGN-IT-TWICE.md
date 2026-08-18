# Design It Twice

When alternative interfaces are worth exploring, produce several genuinely different designs before committing to one. Based on Ousterhout's "Design It Twice" idea.

## Process

1. **Frame the problem space.** State constraints, dependency categories, authority/security boundaries, and a rough non-prescriptive sketch.
2. **Generate 3+ independent designs.** Use parallel independent agents when the runtime supports them; otherwise run separated design passes without letting the first proposal silently become the default. Give each pass a different constraint: minimal interface, flexibility, common-caller ergonomics, or ports/adapters where applicable.
3. **Compare.** Contrast depth, locality, seam placement, authority preservation, and testability. Recommend one design or a justified hybrid.

Each design should state its interface, usage example, hidden implementation, dependency strategy, and trade-offs.
