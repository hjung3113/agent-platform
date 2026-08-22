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
    "reserved_cost": 0,
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
        duplicate_a = make_ref("r1", "d1", contract_kind="decision")
        duplicate_b = make_ref("r1", "d1", contract_kind="contract")
        pack = compile_(contract_refs=(duplicate_a, duplicate_b))
        self.assertEqual(len(pack.units), 5)

    def test_conflicting_contract_ref_raises(self) -> None:
        ref_a = make_ref("r1", "d1")
        ref_b = make_ref("r1", "d2")
        with self.assertRaises(ConflictingContractRefError):
            compile_(contract_refs=(ref_a, ref_b))
        with self.assertRaises(ConflictingContractRefError):
            compile_(contract_refs=(ref_b, ref_a))


class ContextCompilerBudgetTest(unittest.TestCase):
    def test_budget_exceeded_required_alone(self) -> None:
        required_cost = compile_().required_cost
        with patch("execution.context_compiler.CONTEXT_BUDGET_MAX", required_cost - 1):
            with self.assertRaises(CONTEXT_BUDGET_EXCEEDED):
                compile_()

    def test_budget_exceeded_required_plus_reserved(self) -> None:
        required_cost = compile_().required_cost
        reserved = 100
        # passes when budget covers required + reserved
        with patch("execution.context_compiler.CONTEXT_BUDGET_MAX", required_cost + reserved):
            compile_(reserved_cost=reserved)
        # raises when budget sits strictly between required and required + reserved
        with patch("execution.context_compiler.CONTEXT_BUDGET_MAX", required_cost + reserved - 1):
            with self.assertRaises(CONTEXT_BUDGET_EXCEEDED):
                compile_(reserved_cost=reserved)


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
