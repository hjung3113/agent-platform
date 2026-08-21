from __future__ import annotations

import tempfile
import unittest
from dataclasses import fields
from pathlib import Path

from execution.redaction import RedactionResult, RedactionStatus, scan_for_retention
from kernel.admission import AdmissionStatus, AttemptRequest, admit_attempt
from kernel.canonical import content_digest
from kernel.runtime_capability import (
    Capability,
    CapabilityStatus,
    PermissionEnvelope,
    RuntimeCapabilityProfile,
)

AWS_CANARY = "AKIAABCDEFGHIJKLMNOP"
PEM_CANARY = (
    "-----BEGIN RSA PRIVATE KEY-----\n"
    "ZmFrZS1wZW0tYm9keQ==\n"
    "-----END RSA PRIVATE KEY-----"
)
HIGH_ENTROPY_CANARY = "token=synthetic-token-123456"
ORDINARY_TEXT = "the quick brown fox jumps over the lazy dog"


def make_profile() -> RuntimeCapabilityProfile:
    return RuntimeCapabilityProfile(
        runtime="opencode@1.2.3",
        adapter="opencode-adapter@0.4.0",
        config_identity=content_digest({"config": "baseline"}),
        tool_mapping_identity=content_digest({"tool_mapping": "baseline"}),
        permission_envelope=PermissionEnvelope(),
        capabilities=(Capability("file.read", CapabilityStatus.SUPPORTED),),
    )


class RedactionTests(unittest.TestCase):
    def assert_fixture_not_in_result(
        self, fixture: str, result: RedactionResult
    ) -> None:
        self.assertNotIn(fixture, repr(result))
        self.assertNotIn(fixture, str(result))
        for field in fields(result):
            value = getattr(result, field.name)
            self.assertNotIn(fixture, repr(value))
            self.assertNotIn(fixture, str(value))

    def test_aws_key_canary_is_blocked_without_raw_fixture_in_result(self) -> None:
        result = scan_for_retention(AWS_CANARY)

        self.assertEqual(result.status, RedactionStatus.BLOCKED.value)
        self.assertIn("aws_access_key", result.reasons)
        self.assert_fixture_not_in_result(AWS_CANARY, result)

    def test_pem_canary_is_blocked_without_raw_fixture_in_result(self) -> None:
        result = scan_for_retention(PEM_CANARY)

        self.assertEqual(result.status, RedactionStatus.BLOCKED.value)
        self.assertIn("pem_private_key", result.reasons)
        self.assert_fixture_not_in_result(PEM_CANARY, result)

    def test_labeled_high_entropy_canary_is_blocked_without_raw_fixture_in_result(
        self,
    ) -> None:
        result = scan_for_retention(HIGH_ENTROPY_CANARY)

        self.assertEqual(result.status, RedactionStatus.BLOCKED.value)
        self.assertIn("high_entropy_token", result.reasons)
        self.assert_fixture_not_in_result(HIGH_ENTROPY_CANARY, result)

    def test_ordinary_text_is_passed(self) -> None:
        result = scan_for_retention(ORDINARY_TEXT)

        self.assertEqual(result.status, RedactionStatus.PASSED.value)
        self.assertEqual(result.reasons, ())

    def test_none_is_unknown(self) -> None:
        result = scan_for_retention(None)

        self.assertEqual(result.status, RedactionStatus.UNKNOWN.value)
        self.assertEqual(result.reasons, ())

    def test_blocked_redaction_status_blocks_retained_evidence_at_admission(self) -> None:
        redaction_status = scan_for_retention(AWS_CANARY).status

        with tempfile.TemporaryDirectory() as directory:
            result = admit_attempt(
                AttemptRequest(
                    Path(directory),
                    make_profile(),
                    retain_evidence=True,
                    redaction_status=redaction_status,
                )
            )

        self.assertEqual(result.status, AdmissionStatus.BLOCKED)
        self.assertEqual(result.reason, "redaction_not_proven")

    def test_unknown_redaction_status_blocks_retained_evidence_at_admission(self) -> None:
        redaction_status = scan_for_retention(None).status

        with tempfile.TemporaryDirectory() as directory:
            result = admit_attempt(
                AttemptRequest(
                    Path(directory),
                    make_profile(),
                    retain_evidence=True,
                    redaction_status=redaction_status,
                )
            )

        self.assertEqual(result.status, AdmissionStatus.BLOCKED)
        self.assertEqual(result.reason, "redaction_not_proven")


if __name__ == "__main__":
    unittest.main()
