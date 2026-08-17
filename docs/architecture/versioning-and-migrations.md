# Protocol Versioning and Migration — Draft

This is intentionally incomplete until protocol v1 exists.

Rules already fixed:
- every authoritative record carries an explicit schema/protocol version
- unknown future versions fail closed
- writers never mutate an older immutable artifact "into" a new version
- migrations produce successor records/projections with provenance
- adapter compatibility is not protocol compatibility
- runtime update cannot silently change canonical contract meaning
- runtime and adapter semantic identity is captured by a Runtime Capability Profile that includes runtime version, adapter version, effective configuration identity, tool/action mapping identity, and capability probe result
- any Runtime Capability Profile identity change makes prior capability admission stale; execution under the changed profile requires re-admission even when protocol and runtime family names are unchanged
- artifact identity uses one protocol-defined canonical representation and digest algorithm
- semantically irrelevant serialization differences must not create implementation-specific identity
- canonicalization rules cover field ordering/omission, path representation, text/newline normalization where applicable, and which metadata is excluded from content identity
- the schema/protocol version participating in canonical interpretation is unambiguous and validated before digest comparison
- producers and validators must compute the same digest for the same canonical artifact
- mixed-version parent/child handoffs are rejected unless an explicit compatibility or migration rule permits them

Open before v2:
- whether old runs are replayed by versioned readers or migrated into a new store
- retention window for old readers
- exact mixed-version compatibility matrix once protocol v1/v2 schemas exist
