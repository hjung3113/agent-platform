# Claude Runtime Adapter

Maps runtime-neutral actions to claude primitives.

Owns:
- binary/config resolution
- supported role/mode capabilities
- command/tool mapping
- runtime observations
- cancellation/reconciliation semantics

Does not own workflow truth, acceptance, or completion.
