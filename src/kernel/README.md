# Kernel

Deterministic authority boundary.

Responsibilities:
- schema/admission validation
- durable ID assignment and digest binding
- publication of authoritative records
- run transition admission
- replay/projection
- idempotency and conflict checks
- commit-point ownership

Non-responsibilities:
- product design judgement
- implementation
- natural-language review
- model selection by intuition
