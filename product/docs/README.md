# Documentation Map (Product Tree)

`product/` ships as the harness. Its `docs/` therefore holds only what belongs with the
shipped artifact: operating guidance and empty templates for the doc kinds a harness user
might eventually publish alongside it.

- `docs/operations/` — operating guidance for running/deploying the harness (authoritative).
- `docs/product/`, `docs/specs/`, `docs/adr/`, `docs/architecture/` — template-only
  placeholders (`README.md` + `TEMPLATE.md`). No live content.
- `contracts/` — executable representation of supported contracts (authoritative).
- `memory/derived/` — regenerable indexes (non-authoritative).

All content about *building this platform* — normative specs, accepted ADRs, architecture
docs, product vision/scope, research, reviews, delivery plans — lives outside the product
tree in `../../docs/`. See the root `AGENTS.md` for that authority map.
