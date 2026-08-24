from __future__ import annotations

import dataclasses
import inspect
import json
import unittest
from pathlib import Path
from typing import Any

from kernel import protocol, protocol_v1
from kernel.canonical import canonical_json_bytes, content_digest
from kernel.protocol import (
    ProtocolRejectionCode,
    RecordRef,
    read_candidate,
    read_published_record,
    verify_binding,
)
from kernel.protocol_v1 import (
    RequestV1,
    WorkflowRevisionV1,
    request_v1_content_digest,
    workflow_revision_v1_content_digest,
)

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "protocol" / "v1"
GOLDEN_REQUEST_RECORD_ID = "rec-request-0001"


def load_fixture(name: str) -> Any:
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


def golden_request_envelope() -> dict:
    return load_fixture("request.json")


def golden_workflow_envelope() -> dict:
    return load_fixture("workflow-revision.json")


def golden_digests() -> dict:
    return load_fixture("golden-digests.json")


def golden_request_digest() -> str:
    return golden_digests()["request"]["content_digest"]


def read_golden_request():
    return read_candidate(golden_request_envelope())


def read_golden_workflow():
    return read_candidate(golden_workflow_envelope())


def reverse_key_order(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: reverse_key_order(value[key]) for key in reversed(list(value))}
    if isinstance(value, list):
        return [reverse_key_order(item) for item in value]
    return value


class GoldenVectorTests(unittest.TestCase):
    def test_golden_request_bytes_and_digest_are_fixed(self) -> None:
        result = read_golden_request()
        self.assertTrue(result.ok, result.reason)
        golden = golden_digests()["request"]
        self.assertEqual(
            canonical_json_bytes(result.value.envelope.to_content_value()),
            golden["canonical_json"].encode("utf-8"),
        )
        self.assertEqual(result.value.envelope.content_digest(), golden["content_digest"])
        self.assertTrue(protocol.is_content_digest(golden["content_digest"]))

    def test_golden_workflow_revision_bytes_and_digest_are_fixed(self) -> None:
        result = read_golden_workflow()
        self.assertTrue(result.ok, result.reason)
        golden = golden_digests()["workflow_revision"]
        self.assertEqual(
            canonical_json_bytes(result.value.envelope.to_content_value()),
            golden["canonical_json"].encode("utf-8"),
        )
        self.assertEqual(result.value.envelope.content_digest(), golden["content_digest"])

    def test_golden_workflow_binds_golden_request_digest(self) -> None:
        revision = read_golden_workflow().value.value
        self.assertEqual(revision.request.content_digest, golden_request_digest())

    def test_key_insertion_order_does_not_change_identity(self) -> None:
        for envelope in (golden_request_envelope(), golden_workflow_envelope()):
            original = read_candidate(envelope)
            self.assertTrue(original.ok, original.reason)
            reordered = reverse_key_order(envelope)
            reordered = {
                "payload": reordered["payload"],
                "schema_version": reordered["schema_version"],
                "protocol_version": reordered["protocol_version"],
                "contract_kind": reordered["contract_kind"],
            }
            other = read_candidate(reordered)
            self.assertTrue(other.ok, other.reason)
            self.assertEqual(
                other.value.envelope.content_digest(),
                original.value.envelope.content_digest(),
            )
            self.assertEqual(
                other.value.envelope.to_content_value(),
                original.value.envelope.to_content_value(),
            )

    def test_array_order_remains_meaningful(self) -> None:
        request = read_golden_request().value.value
        swapped_scope = RequestV1(
            objective=request.objective,
            scope=tuple(reversed(request.scope)),
            acceptance_criteria=request.acceptance_criteria,
        )
        swapped_criteria = RequestV1(
            objective=request.objective,
            scope=request.scope,
            acceptance_criteria=tuple(reversed(request.acceptance_criteria)),
        )
        base = request_v1_content_digest(request)
        self.assertNotEqual(base, request_v1_content_digest(swapped_scope))
        self.assertNotEqual(base, request_v1_content_digest(swapped_criteria))

    def test_identity_changes_when_semantic_fields_or_binding_change(self) -> None:
        request = read_golden_request().value.value
        base = request_v1_content_digest(request)
        changed_fields = (
            RequestV1(
                objective=request.objective + " (amended)",
                scope=request.scope,
                acceptance_criteria=request.acceptance_criteria,
            ),
            RequestV1(
                objective=request.objective,
                scope=request.scope + ("docs/plans/active/m1-authoritative-publication.md",),
                acceptance_criteria=request.acceptance_criteria,
            ),
            RequestV1(
                objective=request.objective,
                scope=request.scope,
                acceptance_criteria=request.acceptance_criteria + ("One more gate",),
            ),
        )
        for changed in changed_fields:
            self.assertNotEqual(base, request_v1_content_digest(changed))

        revision = read_golden_workflow().value.value
        revision_base = workflow_revision_v1_content_digest(revision)
        substituted_id = WorkflowRevisionV1(
            request=RecordRef(
                revision.request.contract_kind,
                "rec-request-9999",
                revision.request.content_digest,
            ),
            tasks=revision.tasks,
        )
        substituted_digest = WorkflowRevisionV1(
            request=RecordRef(
                revision.request.contract_kind,
                revision.request.record_id,
                "sha256:agent-platform-json-v1:" + "e" * 64,
            ),
            tasks=revision.tasks,
        )
        self.assertNotEqual(
            revision_base, workflow_revision_v1_content_digest(substituted_id)
        )
        self.assertNotEqual(
            revision_base, workflow_revision_v1_content_digest(substituted_digest)
        )

    def test_identity_changes_when_version_or_kind_change(self) -> None:
        content = read_golden_request().value.envelope.to_content_value()
        base = content_digest(content)
        for version_field in ("protocol_version", "schema_version"):
            bumped = dict(content)
            bumped[version_field] = content[version_field] + 1
            self.assertNotEqual(base, content_digest(bumped), version_field)
        other_kind = dict(content)
        other_kind["contract_kind"] = "workflow_revision"
        self.assertNotEqual(base, content_digest(other_kind))

    def test_declared_published_digest_must_equal_recomputed_content_digest(self) -> None:
        record = {
            "record_id": GOLDEN_REQUEST_RECORD_ID,
            "content_digest": golden_request_digest(),
            **golden_request_envelope(),
        }
        result = read_published_record(record)
        self.assertTrue(result.ok, result.reason)
        self.assertEqual(result.value.content_digest, golden_request_digest())
        forged = {
            "record_id": GOLDEN_REQUEST_RECORD_ID,
            "content_digest": golden_request_digest(),
            **golden_request_envelope(),
        }
        forged["payload"]["objective"] += " (forged)"
        self.assertEqual(
            read_published_record(forged).rejection_code,
            ProtocolRejectionCode.CONTENT_DIGEST_MISMATCH,
        )


class StaleSubstitutedBindingTests(unittest.TestCase):
    def expected_parent(self) -> RecordRef:
        return RecordRef(
            contract_kind="request",
            record_id=GOLDEN_REQUEST_RECORD_ID,
            content_digest=golden_request_digest(),
        )

    def read_substituted_revision(self, request_ref: dict):
        envelope = golden_workflow_envelope()
        envelope["payload"]["request"] = request_ref
        result = read_candidate(envelope)
        self.assertTrue(result.ok, result.reason)
        return result.value.value

    def test_exact_golden_binding_verifies(self) -> None:
        revision = read_golden_workflow().value.value
        result = verify_binding(revision.request, self.expected_parent())
        self.assertTrue(result.ok, result.reason)
        self.assertEqual(result.value, revision.request)

    def test_wrong_request_record_id_rejects_against_expected_parent(self) -> None:
        revision = self.read_substituted_revision(
            {
                "contract_kind": "request",
                "record_id": "rec-request-0002",
                "content_digest": golden_request_digest(),
            }
        )
        result = verify_binding(revision.request, self.expected_parent())
        self.assertEqual(result.rejection_code, ProtocolRejectionCode.BINDING_MISMATCH)

    def test_stale_request_digest_rejects(self) -> None:
        earlier = read_golden_request().value.value
        stale_digest = request_v1_content_digest(
            RequestV1(
                objective=earlier.objective + " (earlier revision)",
                scope=earlier.scope,
                acceptance_criteria=earlier.acceptance_criteria,
            )
        )
        self.assertTrue(protocol.is_content_digest(stale_digest))
        revision = self.read_substituted_revision(
            {
                "contract_kind": "request",
                "record_id": GOLDEN_REQUEST_RECORD_ID,
                "content_digest": stale_digest,
            }
        )
        result = verify_binding(revision.request, self.expected_parent())
        self.assertEqual(result.rejection_code, ProtocolRejectionCode.BINDING_MISMATCH)

    def test_substituted_semantically_similar_parent_rejects(self) -> None:
        original = read_golden_request().value.value
        similar = request_v1_content_digest(
            RequestV1(
                objective=original.objective,
                scope=original.scope + ("docs/plans/active/m2.md",),
                acceptance_criteria=original.acceptance_criteria,
            )
        )
        revision = self.read_substituted_revision(
            {
                "contract_kind": "request",
                "record_id": GOLDEN_REQUEST_RECORD_ID,
                "content_digest": similar,
            }
        )
        self.assertNotEqual(similar, golden_request_digest())
        result = verify_binding(revision.request, self.expected_parent())
        self.assertEqual(result.rejection_code, ProtocolRejectionCode.BINDING_MISMATCH)
        self.assertNotEqual(result.rejection_code, None)


class ForgedPublicationMetadataTests(unittest.TestCase):
    def published_record(self, *, record_id: str, declared_digest: str) -> dict:
        return {
            "record_id": record_id,
            "content_digest": declared_digest,
            **golden_request_envelope(),
        }

    def test_published_record_with_incorrect_declared_digest_rejects(self) -> None:
        record = self.published_record(
            record_id=GOLDEN_REQUEST_RECORD_ID,
            declared_digest="sha256:agent-platform-json-v1:" + "e" * 64,
        )
        self.assertEqual(
            read_published_record(record).rejection_code,
            ProtocolRejectionCode.CONTENT_DIGEST_MISMATCH,
        )

    def test_parsing_a_candidate_produces_no_record_id_or_authority_flag(self) -> None:
        parsed = read_golden_request().value
        self.assertEqual(
            {field.name for field in dataclasses.fields(parsed.envelope)},
            {"contract_kind", "protocol_version", "schema_version", "payload"},
        )
        self.assertEqual(
            {field.name for field in dataclasses.fields(parsed.value)},
            {"objective", "scope", "acceptance_criteria"},
        )
        for obj in (parsed.envelope, parsed.value):
            for forbidden in ("record_id", "published", "authoritative"):
                self.assertFalse(hasattr(obj, forbidden), forbidden)

    def test_parsing_published_shape_does_not_mutate_state_or_input(self) -> None:
        record = self.published_record(
            record_id=GOLDEN_REQUEST_RECORD_ID,
            declared_digest=golden_request_digest(),
        )
        snapshot = json.loads(json.dumps(record))
        readers_before = dict(protocol._READERS)
        first = read_published_record(record)
        second = read_published_record(snapshot)
        self.assertTrue(first.ok, first.reason)
        self.assertEqual(first, second)
        self.assertEqual(record, snapshot)
        self.assertEqual(protocol._READERS, readers_before)
        self.assertEqual(
            {field.name for field in dataclasses.fields(first.value)},
            {"record_id", "content_digest", "envelope", "value"},
        )

    def test_no_kernel_publication_api_is_exposed(self) -> None:
        for module in (protocol, protocol_v1):
            for name in (
                "publish",
                "publish_record",
                "admit",
                "admission",
                "commit",
                "store",
                "write",
                "append",
            ):
                self.assertFalse(hasattr(module, name), f"{module.__name__}.{name}")

    def test_canonical_looking_path_is_never_admission_semantics(self) -> None:
        for module in (protocol, protocol_v1):
            for name, member in inspect.getmembers(module, inspect.isfunction):
                for parameter in inspect.signature(member).parameters:
                    self.assertNotIn(
                        parameter,
                        {"path", "filename", "file_path", "filepath"},
                        f"{module.__name__}.{name}",
                    )
        self.assertEqual(
            read_candidate(FIXTURES_DIR / "request.json").rejection_code,
            ProtocolRejectionCode.MALFORMED_ENVELOPE,
        )
        canonical_named = self.published_record(
            record_id="records/request/0001/canonical.json",
            declared_digest="sha256:agent-platform-json-v1:" + "0" * 64,
        )
        self.assertEqual(
            read_published_record(canonical_named).rejection_code,
            ProtocolRejectionCode.CONTENT_DIGEST_MISMATCH,
        )
        authentic = self.published_record(
            record_id="records/request/0001/canonical.json",
            declared_digest=golden_request_digest(),
        )
        result = read_published_record(authentic)
        self.assertTrue(result.ok, result.reason)
        self.assertEqual(result.value.record_id, "records/request/0001/canonical.json")


class FixtureBoundaryTests(unittest.TestCase):
    def test_production_source_never_references_fixture_paths(self) -> None:
        src_root = Path(__file__).resolve().parents[2] / "src"
        self.assertTrue(src_root.is_dir())
        offenders = []
        for source in sorted(src_root.rglob("*.py")):
            text = source.read_text(encoding="utf-8")
            for needle in ("tests/fixtures", "fixtures/protocol"):
                if needle in text:
                    offenders.append(f"{source.relative_to(src_root)}:{needle}")
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
