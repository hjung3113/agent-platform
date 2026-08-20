from __future__ import annotations

import unittest

from execution import policy
from kernel.runtime_capability import PermissionEnvelope


class M3ExecutionPolicyTest(unittest.TestCase):
    def test_admitted_permissions_is_a_valid_permission_envelope(self) -> None:
        self.assertIsInstance(policy.M3_ADMITTED_PERMISSIONS, PermissionEnvelope)

    def test_admitted_permissions_denies_ungranted_categories(self) -> None:
        permissions = policy.M3_ADMITTED_PERMISSIONS
        self.assertEqual(permissions.network, ())
        self.assertEqual(permissions.external_effects, ())
        self.assertEqual(permissions.process, ())

    def test_required_capabilities_are_non_empty_strings(self) -> None:
        self.assertTrue(policy.M3_REQUIRED_CAPABILITIES)
        self.assertTrue(
            all(
                isinstance(capability, str) and capability
                for capability in policy.M3_REQUIRED_CAPABILITIES
            )
        )

    def test_policy_constants_are_stable_module_singletons(self) -> None:
        permissions = policy.M3_ADMITTED_PERMISSIONS
        capabilities = policy.M3_REQUIRED_CAPABILITIES

        self.assertIs(permissions, policy.M3_ADMITTED_PERMISSIONS)
        self.assertIs(capabilities, policy.M3_REQUIRED_CAPABILITIES)


if __name__ == "__main__":
    unittest.main()
