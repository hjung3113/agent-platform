# Protocol Versioning and Migration — Draft

This is intentionally incomplete until protocol v1 exists.

Rules already fixed:
- every authoritative record carries an explicit schema/protocol version
- unknown future versions fail closed
- writers never mutate an older immutable artifact "into" a new version
- migrations produce successor records/projections with provenance
- adapter compatibility is not protocol compatibility
- runtime update cannot silently change canonical contract meaning

Open before v2:
- whether old runs are replayed by versioned readers or migrated into a new store
- retention window for old readers
- mixed-version workflow/attempt compatibility
