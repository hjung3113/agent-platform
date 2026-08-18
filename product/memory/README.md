# Memory

This directory does not duplicate authority documents.

- `derived/` is regenerable and non-authoritative.

Operational run state lives outside the checkout.
Durable design decisions live in specs/ADRs/contracts. During the build, specs/ADRs are
authored in `../../dev-env/docs/` (see `../../dev-env/authority-map.yaml`); machine
contracts live in `../contracts/` and are not copied into a second memory store.
