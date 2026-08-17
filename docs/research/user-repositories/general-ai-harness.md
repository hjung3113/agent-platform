# general-ai-harness

Status: ADAPT

Evidence:
- `README.md`: contract-driven local-first one-shot harness; sandbox outside checkout; host-owned receipt.
- `docs/design/THIN_MVP_GRILL.md`: deliberately rejects speculative adapter/registry/state-machine seams
  until a second consumer proves the need.
- `docs/design/GENERAL_AI_HARNESS_REPORT.md`: long-term RunSpec -> Admission -> isolated execution ->
  Evidence -> Gate -> Result model.

Adopt:
- deterministic host gate/receipt authority
- product/development environment separation
- fail-closed admission
- "deep seam, minimum mechanism" design discipline

Do not blindly adopt:
- one-shot SHA-only MVP limitations
- premature generalized control-plane mechanisms from the older long-range report

Target:
`src/kernel`, `src/execution`, product principles, Spec 03/05/06.
