# Context Compiler

Deterministic attempt-context subsystem.

Responsibilities:
- resolve authority precedence
- select task/lineage-relevant sources
- verify source identity/digests
- enforce context budget
- detect merge/context conflicts
- produce immutable Context Pack and Attempt Packet inputs

It does not summarize arbitrary chat as authority and is not an LLM persona.
Optional model-produced summaries may be inputs only when provenance-linked and explicitly non-authoritative.
