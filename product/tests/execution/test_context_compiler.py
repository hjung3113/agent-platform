from __future__ import annotations

import itertools
import unittest
from unittest.mock import patch

from execution.context_compiler import (
    CONTEXT_BUDGET_EXCEEDED,
    ConflictingContractRefError,
    compile_context_pack,
)
from kernel.protocol import RecordRef


FIXED_ARGS = {
    "task_id": "t1",
    "task_objective": "do the thing",
    "task_acceptance_criteria": ("crit a", "crit b"),
    "workspace_snapshot_digest": "sha256:agent-platform-json-v1:deadbeef",
    "runtime_capability_profile_identity": "sha256:agent-platform-json-v1:cafef00d",
    "disclosure_identity": "disc1",
}


def make_ref(record_id: str, content_digest: str, contract_kind: str = "decision") -> RecordRef:
    return RecordRef(
        contract_kind=contract_kind,
        record_id=record_id,
        content_digest=content_digest,
    )


def compile_(**overrides):
    kwargs = dict(FIXED_ARGS)
    kwargs.update(overrides)
    return compile_context_pack(**kwargs)


def unit_identities(pack) -> tuple[str, ...]:
    return tuple(unit.source_identity for unit in pack.units)


class ContextCompilerDeterminismTest(unittest.TestCase):
    def test_deterministic_digest(self) -> None:
        self.assertEqual(compile_().digest, compile_().digest)

    def test_shuffle_order_empty_refs(self) -> None:
        digests = {compile_(contract_refs=()).digest for _ in range(2)}
        self.assertEqual(len(digests), 1)
        self.assertEqual(unit_identities(compile_(contract_refs=())), unit_identities(compile_(contract_refs=())))

    def test_shuffle_order_single_ref(self) -> None:
        ref = make_ref("r1", "d1")
        packs = [compile_(contract_refs=(ref,)) for _ in range(2)]
        self.assertEqual({p.digest for p in packs}, {packs[0].digest})
        self.assertEqual(unit_identities(packs[0]), unit_identities(packs[1]))

    def test_shuffle_order_true_duplicate_refs(self) -> None:
        ref = make_ref("r1", "d1")
        ref2 = make_ref("r2", "d2")
        digests = set()
        identities = set()
        for perm in itertools.permutations([ref, ref2, ref, ref2]):
            pack = compile_(contract_refs=perm)
            digests.add(pack.digest)
            identities.add(unit_identities(pack))
        self.assertEqual(len(digests), 1)
        self.assertEqual(len(identities), 1)


class ContextCompilerContractRefTest(unittest.TestCase):
    def test_dedup_true_duplicate(self) -> None:
        # Same (contract_kind, record_id, content_digest) triple twice ->
        # one unit. Same contract_kind is load-bearing here (PR #47 review
        # P1) — see test_different_contract_kind_same_record_id_not_deduped
        # for the case this must NOT collapse.
        duplicate_a = make_ref("r1", "d1", contract_kind="decision")
        duplicate_b = make_ref("r1", "d1", contract_kind="decision")
        pack = compile_(contract_refs=(duplicate_a, duplicate_b))
        self.assertEqual(len(pack.units), 5)

    def test_different_contract_kind_same_record_id_not_deduped(self) -> None:
        # Two refs sharing record_id AND content_digest but differing
        # contract_kind are different identities in different id spaces,
        # not duplicates of one thing and not a conflict either — both must
        # survive as distinct units (PR #47 review P1: record_id-only
        # grouping wrongly collapsed this pair).
        ref_a = make_ref("r1", "d1", contract_kind="decision")
        ref_b = make_ref("r1", "d1", contract_kind="contract")
        pack = compile_(contract_refs=(ref_a, ref_b))
        self.assertEqual(len(pack.units), 6)
        contract_ref_identities = [
            unit.source_identity for unit in pack.units if unit.scope == "contract_ref"
        ]
        self.assertEqual(
            set(contract_ref_identities),
            {"contract_ref:decision:r1", "contract_ref:contract:r1"},
        )

    def test_conflicting_contract_ref_raises(self) -> None:
        ref_a = make_ref("r1", "d1")
        ref_b = make_ref("r1", "d2")
        with self.assertRaises(ConflictingContractRefError):
            compile_(contract_refs=(ref_a, ref_b))
        with self.assertRaises(ConflictingContractRefError):
            compile_(contract_refs=(ref_b, ref_a))

    def test_different_contract_kind_same_record_id_different_digest_no_conflict(
        self,
    ) -> None:
        # Different contract_kind means different identity spaces, so a
        # differing content_digest under a different contract_kind is not
        # the same-ref-drifted-content case ConflictingContractRefError
        # exists to catch — it must compile cleanly as two distinct refs.
        ref_a = make_ref("r1", "d1", contract_kind="decision")
        ref_b = make_ref("r1", "d2", contract_kind="contract")
        pack = compile_(contract_refs=(ref_a, ref_b))
        self.assertEqual(len(pack.units), 6)


class ContextCompilerBudgetTest(unittest.TestCase):
    def test_budget_exceeded_required_alone(self) -> None:
        baseline = compile_()
        total = baseline.required_cost + baseline.optional_cost + baseline.reserved_cost
        with patch("execution.context_compiler.CONTEXT_BUDGET_MAX", total - 1):
            with self.assertRaises(CONTEXT_BUDGET_EXCEEDED):
                compile_()

    def test_budget_exceeded_required_plus_reserved(self) -> None:
        # reserved_cost is now computed internally from the real rendered
        # message (PR #47 review P1), so drive the boundary by adding
        # contract_refs (which grow reserved_cost's render-overhead
        # component) rather than by passing a reserved_cost override.
        baseline = compile_(contract_refs=())
        with_ref = compile_(contract_refs=(make_ref("r1", "d1"),))
        baseline_total = (
            baseline.required_cost + baseline.optional_cost + baseline.reserved_cost
        )
        with_ref_total = (
            with_ref.required_cost + with_ref.optional_cost + with_ref.reserved_cost
        )
        self.assertGreater(with_ref_total, baseline_total)
        # passes when budget covers the real total
        with patch("execution.context_compiler.CONTEXT_BUDGET_MAX", with_ref_total):
            compile_(contract_refs=(make_ref("r1", "d1"),))
        # raises when budget sits below the real total (even though it
        # covers required_cost alone) — proves required+reserved, not
        # required alone, is what's enforced
        with patch("execution.context_compiler.CONTEXT_BUDGET_MAX", with_ref_total - 1):
            with self.assertRaises(CONTEXT_BUDGET_EXCEEDED):
                compile_(contract_refs=(make_ref("r1", "d1"),))

    def test_budget_predicate_matches_real_rendered_message_size(self) -> None:
        # PR #47 review P1: the accounted total must equal the actual
        # rendered single-argv message size (plus the small fixed argv
        # allowance), not merely an under-count of unit content bytes.
        from execution.context_compiler import (
            RUN_MESSAGE_ENVELOPE_OVERHEAD_BYTES,
            render_context_pack,
        )

        pack = compile_(contract_refs=(make_ref("r1", "d1"),))
        rendered_bytes = len(render_context_pack(pack.units).encode("utf-8"))
        accounted_total = pack.required_cost + pack.optional_cost + pack.reserved_cost
        self.assertEqual(
            accounted_total, rendered_bytes + RUN_MESSAGE_ENVELOPE_OVERHEAD_BYTES
        )


class ContextCompilerUnitTest(unittest.TestCase):
    def test_estimated_cost_byte_length(self) -> None:
        pack = compile_()
        objective_units = [
            unit for unit in pack.units if unit.source_class == "control" and unit.scope == "task.objective"
        ]
        self.assertEqual(len(objective_units), 1)
        self.assertEqual(objective_units[0].estimated_cost, len("do the thing".encode("utf-8")))

    def test_all_units_required_and_control_derived_classes(self) -> None:
        pack = compile_(contract_refs=())
        self.assertEqual(
            [unit.source_class for unit in pack.units],
            ["control", "control", "derived", "derived"],
        )
        self.assertTrue(all(unit.requirement == "required" for unit in pack.units))


if __name__ == "__main__":
    unittest.main()
