# Commands

Commands are thin entry points only.

A command should:
1. resolve user intent / namespace,
2. invoke one canonical skill or workflow,
3. pass arguments,
4. avoid duplicating workflow logic.

This follows ECC's migration toward skills as durable units, Superpowers' thin
command wrappers, and GSD's namespace-router strategy.
