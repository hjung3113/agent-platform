# Protocol Versioning and Migration — Draft

Compatibility semantics are fixed before protocol v1 so later schema work cannot redefine replay or historical meaning.

## Version identity and interpretation

- every authoritative record carries an explicit `protocol_version` and contract `schema_version`
- those versions are immutable parts of the record's interpretation context
- canonical contract meaning is selected by the record's declared versions, never by the currently installed runtime or adapter
- readers dispatch to an exact supported version; there is no fallback to a "latest" reader
- unknown or unsupported versions fail closed with a typed rejection
- runtime and adapter semantic identity is captured by a Runtime Capability Profile that includes runtime version, adapter version, effective configuration identity, tool/action mapping identity, and capability probe result
- any Runtime Capability Profile identity change makes prior capability admission stale; execution under the changed profile requires re-admission even when protocol and runtime family names are unchanged
- artifact identity uses one protocol-defined canonical representation and digest algorithm
- semantically irrelevant serialization differences must not create implementation-specific identity
- canonicalization rules cover field ordering/omission, path representation, text/newline normalization where applicable, and which metadata is excluded from content identity
- the schema/protocol version participating in canonical interpretation is unambiguous and validated before digest comparison
- producers and validators must compute the same digest for the same canonical artifact

## Compatibility policy

Compatibility is explicit, directional, and contract-specific.

- exact-version handoffs still require normal schema, identity, digest, authority, and lineage checks
- mixed-version parent/child handoffs are rejected unless an explicit compatibility rule permits that exact relationship
- the compatibility registry is keyed by relationship plus parent contract/version and child contract/version; absence of an entry means incompatible
- a compatibility entry either permits direct interpretation or names an explicit migration rule; compatibility is never inferred from matching major versions, field similarity, adapter support, runtime support, or Runtime Capability Profile compatibility
- every admitted cross-version relationship records the compatibility or migration rule identity/version used for admission so replay does not depend on a later registry revision
- published compatibility and migration rule versions are immutable; corrections create successor rule versions rather than changing historical semantics
- adapter compatibility is not protocol compatibility

Protocol v1 starts with only the compatibility relationships explicitly declared for v1. Protocol v2 is incompatible by default until each allowed v1/v2 relationship and required migration rule is deliberately registered.

## Replay policy

Authoritative history is replayed in its recorded versions by default.

- replay never rewrites an old authoritative artifact into the current version
- replay selects the version-specific reader for each authoritative artifact and uses the historical compatibility/migration rule recorded on cross-version edges
- current adapter/runtime behavior cannot reinterpret an existing contract version during replay
- deterministic replay of a retained lineage must remain possible without depending on a mutable "current" compatibility decision
- a protocol/schema reader cannot be retired while any retained authoritative artifact reachable from a retained run, decision, receipt, or verification lineage requires that reader
- reader retirement therefore follows artifact reachability and retention, not deployment age alone

A replay may additionally build a migrated projection for current tooling, but that projection is derived and cannot replace or redefine the original authoritative lineage.

## Migration semantics

- writers never mutate an older immutable artifact "into" a new version
- migrations produce successor records or derived projections with provenance
- an authoritative migration successor binds the source identity, source digest, source protocol/schema versions, target protocol/schema versions, and migration rule identity/version
- the source artifact remains retained according to normal authority/lineage retention rules
- migration of one artifact does not implicitly authorize mixed-version descendants; every cross-version edge must still be covered by an explicit compatibility or migration rule
- migration cannot retroactively change the meaning, admission result, or ordering of an already published historical run

## Runtime and adapter boundary

- Runtime Capability Profile admission determines whether a runtime/adapter may execute an Attempt; it does not determine protocol compatibility or canonical contract meaning
- adapters may translate harness-neutral actions to native runtime operations, but may not rename, default, coerce, or reinterpret canonical fields contrary to the selected protocol/schema version
- a runtime or adapter update that requires different contract meaning requires a new protocol/schema or explicit compatibility/migration rule; it cannot silently change an existing version
- runtime/adapter/profile identities remain execution provenance and capability bindings, not substitutes for protocol/schema versioning

## Retention invariant

Retention policy and compatibility support are coupled: if an authoritative artifact is retained for audit or replay, the readers and immutable rule definitions required to interpret every reachable authoritative edge must also remain available.

Exact storage duration may remain an operational policy, but removing the final reader/rule needed by retained authoritative history is forbidden.
