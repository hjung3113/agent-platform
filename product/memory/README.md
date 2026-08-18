# Memory

This directory does not duplicate authority documents.

- `derived/` is regenerable and non-authoritative.

Operational run state lives outside the checkout.
Durable design decisions live in specs/ADRs/contracts. During the build, specs/ADRs are
authored in `../../docs/` (see `../../authority-map.yaml`); machine
contracts live in `../contracts/` and are not copied into a second memory store.
