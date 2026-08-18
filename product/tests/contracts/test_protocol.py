from __future__ import annotations

import unittest

from kernel import protocol
from kernel.canonical import content_digest
from kernel.protocol import (
    ContractKind,
    ProtocolRejectionCode,
    ReaderOutcome,
    read_candidate,
    read_published_record,
    register_reader,
)


def candidate_envelope(
    *,
    contract_kind: str = "request",
    protocol_version: int = 1,
    schema_version: int = 1,
    payload: object = None,
) -> dict:
    return {
        "contract_kind": contract_kind,
        "protocol_version": protocol_version,
        "schema_version": schema_version,
        "payload": payload,
    }


class RegistrySandbox(unittest.TestCase):
    """Keep reader registrations local to each test."""

    def setUp(self) -> None:
        saved = dict(protocol._READERS)
        self.addCleanup(self._restore, saved)

    @staticmethod
    def _restore(saved: dict) -> None:
        protocol._READERS.clear()
        protocol._READERS.update(saved)


class ExactDispatchTests(RegistrySandbox):
    def test_exact_key_dispatch_and_no_fallback(self) -> None:
        register_reader(
            ContractKind.WORKFLOW_REVISION,
            2,
            2,
            lambda payload: ReaderOutcome(value={"seen": payload}, canonical_payload=payload),
        )

        result = read_candidate(
            candidate_envelope(
                contract_kind="workflow_revision",
                protocol_version=2,
                schema_version=2,
                payload={"a": 1},
            )
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.value.value, {"seen": {"a": 1}})

        future_protocol = read_candidate(
            candidate_envelope(contract_kind="workflow_revision", protocol_version=3)
        )
        self.assertEqual(
            future_protocol.rejection_code,
            ProtocolRejectionCode.UNSUPPORTED_PROTOCOL_VERSION,
        )
        other_schema = read_candidate(
            candidate_envelope(
                contract_kind="workflow_revision",
                protocol_version=2,
                schema_version=3,
            )
        )
        self.assertEqual(
            other_schema.rejection_code,
            ProtocolRejectionCode.UNSUPPORTED_SCHEMA_VERSION,
        )

    def test_unknown_contract_kind_rejects(self) -> None:
        register_reader(
            ContractKind.WORKFLOW_REVISION,
            2,
            2,
            lambda payload: ReaderOutcome(value=payload, canonical_payload=payload),
        )

        result = read_candidate(candidate_envelope(contract_kind="decision"))
        self.assertEqual(
            result.rejection_code, ProtocolRejectionCode.UNKNOWN_CONTRACT_KIND
        )
        self.assertFalse(result.ok)

    def test_unsupported_protocol_version_rejects_without_fallback(self) -> None:
        register_reader(
            ContractKind.REQUEST,
            1,
            1,
            lambda payload: ReaderOutcome(value=payload, canonical_payload=payload),
        )

        result = read_candidate(candidate_envelope(protocol_version=2))
        self.assertEqual(
            result.rejection_code,
            ProtocolRejectionCode.UNSUPPORTED_PROTOCOL_VERSION,
        )

    def test_unsupported_schema_version_rejects_without_fallback(self) -> None:
        register_reader(
            ContractKind.REQUEST,
            1,
            1,
            lambda payload: ReaderOutcome(value=payload, canonical_payload=payload),
        )

        result = read_candidate(candidate_envelope(schema_version=2))
        self.assertEqual(
            result.rejection_code, ProtocolRejectionCode.UNSUPPORTED_SCHEMA_VERSION
        )


class CandidateEnvelopeTests(RegistrySandbox):
    def test_missing_envelope_key_rejects(self) -> None:
        envelope = candidate_envelope()
        del envelope["payload"]
        result = read_candidate(envelope)
        self.assertEqual(
            result.rejection_code, ProtocolRejectionCode.MALFORMED_ENVELOPE
        )

    def test_extra_envelope_key_rejects(self) -> None:
        envelope = candidate_envelope()
        envelope["extra"] = True
        result = read_candidate(envelope)
        self.assertEqual(
            result.rejection_code, ProtocolRejectionCode.MALFORMED_ENVELOPE
        )

    def test_non_object_envelope_rejects(self) -> None:
        result = read_candidate([candidate_envelope()])
        self.assertEqual(
            result.rejection_code, ProtocolRejectionCode.MALFORMED_ENVELOPE
        )

    def test_non_integer_versions_reject(self) -> None:
        for field in ("protocol_version", "schema_version"):
            envelope = candidate_envelope()
            envelope[field] = "1"
            result = read_candidate(envelope)
            self.assertEqual(
                result.rejection_code,
                ProtocolRejectionCode.MALFORMED_ENVELOPE,
                field,
            )
            envelope[field] = True
            self.assertEqual(
                read_candidate(envelope).rejection_code,
                ProtocolRejectionCode.MALFORMED_ENVELOPE,
                field,
            )

    def test_candidate_publication_only_fields_reject(self) -> None:
        for forbidden in ("record_id", "content_digest", "published", "authoritative"):
            envelope = candidate_envelope()
            envelope[forbidden] = "sha256:agent-platform-json-v1:" + "0" * 64
            result = read_candidate(envelope)
            self.assertEqual(
                result.rejection_code,
                ProtocolRejectionCode.MALFORMED_ENVELOPE,
                forbidden,
            )


class PublishedRecordTests(RegistrySandbox):
    def setUp(self) -> None:
        super().setUp()
        register_reader(
            ContractKind.WORKFLOW_REVISION,
            2,
            2,
            lambda payload: ReaderOutcome(value=payload, canonical_payload=payload),
        )

    def published_record(self, *, declared_digest: str) -> dict:
        envelope = candidate_envelope(
            contract_kind="workflow_revision",
            protocol_version=2,
            schema_version=2,
            payload={"task": {"task_id": "t-1"}},
        )
        content = {
            "contract_kind": envelope["contract_kind"],
            "protocol_version": envelope["protocol_version"],
            "schema_version": envelope["schema_version"],
            "payload": envelope["payload"],
        }
        return {
            "record_id": "rec-1",
            "content_digest": declared_digest,
            **envelope,
            "_computed": content_digest(content),
        }

    def test_valid_published_record_parses_and_binds_digest(self) -> None:
        record = self.published_record(declared_digest="")
        record["content_digest"] = record.pop("_computed")
        result = read_published_record(record)
        self.assertTrue(result.ok)
        self.assertEqual(result.value.content_digest, record["content_digest"])
        self.assertEqual(result.value.record_id, "rec-1")

    def test_declared_digest_mismatch_rejects(self) -> None:
        record = self.published_record(
            declared_digest="sha256:agent-platform-json-v1:" + "f" * 64
        )
        record.pop("_computed")
        result = read_published_record(record)
        self.assertEqual(
            result.rejection_code, ProtocolRejectionCode.CONTENT_DIGEST_MISMATCH
        )

    def test_malformed_declared_digest_rejects(self) -> None:
        record = self.published_record(declared_digest="not-a-digest")
        record.pop("_computed")
        self.assertEqual(
            read_published_record(record).rejection_code,
            ProtocolRejectionCode.MALFORMED_ENVELOPE,
        )

    def test_missing_or_extra_record_keys_reject(self) -> None:
        record = self.published_record(declared_digest="")
        record["content_digest"] = record.pop("_computed")
        del record["record_id"]
        self.assertEqual(
            read_published_record(record).rejection_code,
            ProtocolRejectionCode.MALFORMED_ENVELOPE,
        )
        record["published"] = True
        self.assertEqual(
            read_published_record(record).rejection_code,
            ProtocolRejectionCode.MALFORMED_ENVELOPE,
        )


class RecordRefTests(unittest.TestCase):
    def test_malformed_record_reference_rejects(self) -> None:
        from kernel.protocol import read_record_ref

        digest = "sha256:agent-platform-json-v1:" + "a" * 64
        valid = {
            "contract_kind": "request",
            "record_id": "rec-1",
            "content_digest": digest,
        }
        self.assertEqual(read_record_ref(valid).content_digest, digest)

        for bad in (
            "not-an-object",
            {**valid, "record_id": ""},
            {**valid, "content_digest": "sha256:wrong:" + "a" * 64},
            {**valid, "content_digest": digest[:-1]},
            {**valid, "extra": 1},
            {"contract_kind": "request", "record_id": "rec-1"},
        ):
            with self.assertRaises(
                protocol.ProtocolRejected,
                msg=repr(bad),
            ) as caught:
                read_record_ref(bad)
            self.assertEqual(
                caught.exception.code,
                ProtocolRejectionCode.MALFORMED_RECORD_REF,
            )

    def test_is_content_digest_shape(self) -> None:
        self.assertTrue(
            protocol.is_content_digest("sha256:agent-platform-json-v1:" + "0" * 64)
        )
        self.assertFalse(protocol.is_content_digest("sha256:md5:" + "0" * 64))
        self.assertFalse(protocol.is_content_digest(123))


if __name__ == "__main__":
    unittest.main()
