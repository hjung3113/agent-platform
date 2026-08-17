# Recovery and Release

Recovery must reconstruct from authoritative records, not agent chat.

Release pipeline:
verified snapshot -> release authorization -> release precondition validation -> release action -> release receipt.

Release authorization is valid only for the exact verified snapshot, intended external effect, target identity, and expected pre-release target state recorded in the authorization lineage.
Immediately before push/PR/merge/deploy or another external effect, the release path revalidates those bindings and fails closed if the verified snapshot, target ref, or expected target state changed.

Release Receipt records the actual external-effect target and released content identity. That identity must remain traceable to the Verification and Release Authorization that permitted it.

Push/PR/merge/deploy are distinct external effects and may require separate approval policy.
Verified readiness never implies release authorization by itself.
