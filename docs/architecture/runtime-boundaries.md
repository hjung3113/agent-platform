# Runtime and Transport Boundaries

Independent axes:
- runtime
- role
- model/effort
- transport
- workspace isolation

The same role may run on different runtimes only after capability admission.
Transport liveness is not correctness.
Adapter configuration may narrow core policy but cannot silently widen it.

Harness-agnostic skills use a canonical action vocabulary; adapters map those actions to native tools. Portability means preservation of canonical action semantics, not merely successful invocation.

## Capability admission

Before any side effect, the Host must resolve an immutable **Runtime Capability Profile** for the selected runtime/adapter/configuration. The profile is bound to the Attempt Packet and records:
- runtime and adapter identity/version
- effective configuration identity
- supported canonical actions and required semantic guarantees
- effective permission/tool envelope after runtime defaults are applied
- unsupported, partially supported, or extension-only behavior
- cancellation/reconciliation guarantees relevant to the attempt

Admission compares the Attempt Packet's required capabilities against that exact profile. `unsupported`, `unknown`, or `partial` does not satisfy a required capability unless the packet explicitly admits a named degraded mode. Capability probing is therefore semantic and fail-closed; binary presence or command acceptance is insufficient.

## Semantic preservation

For every canonical action, its contract defines the observable effect, permission boundary, success/failure meaning, and evidence obligations that runtimes must preserve. An adapter may translate syntax, invocation shape, or native tool names, but may not reinterpret these semantics.

Runtime-specific features remain explicit extensions. They must not be smuggled into a canonical action or force the canonical vocabulary toward a lowest-common-denominator abstraction. A workflow requiring an extension declares it as a capability requirement and is admitted only to compatible profiles.

## Permission preservation

The effective runtime permission set must be equal to or narrower than the admitted execution envelope after all runtime defaults, inherited configuration, tool aliases, and adapter mappings are resolved. Any mapping that would widen filesystem, network, process, credential, approval-bypass, or external-effect authority fails admission rather than relying on runtime defaults.

## Fallback and degradation

No adapter may silently substitute a different runtime, model, transport, workspace mode, action, permission mode, or failure behavior. Fallback requires an explicit successor Attempt or a degraded mode already named in the admitted packet. The fallback target is capability-admitted independently and receives its own bound Runtime Capability Profile.

## Drift control

Runtime or adapter upgrades may change native behavior without changing the canonical protocol. Therefore capability admission and downstream evidence bind the exact Runtime Capability Profile identity, not only a runtime family name. If an upgrade, configuration change, tool mapping change, or probe result changes the profile identity, prior admission is stale and execution must be re-admitted.

Workspace Snapshot identity and Runtime Capability Profile identity are independent bindings: the former fixes effective workspace content/state; the latter fixes execution semantics and permissions.
