# Machine Contracts

This directory is the machine-enforceable protocol surface.

Normative rule: prose specs explain the contract; schemas and kernel code enforce it.

Candidate contract families:
- request
- approval / material decision
- workflow revision
- task
- context pack
- attempt packet
- runtime observation
- result
- review
- evidence
- finding
- receipt
- repository snapshot/admission
- release/promotion

Unknown fields and unsupported schema versions should fail closed at admission.
Do not let runtime adapters invent alternate contract shapes.
