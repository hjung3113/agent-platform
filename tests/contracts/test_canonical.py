from __future__ import annotations

import unittest

from kernel import canonical


class CanonicalJsonTests(unittest.TestCase):
    def test_golden_vector(self) -> None:
        artifact = {
            "schema_version": 1,
            "subject": {"id": "workflow-7", "kind": "workflow_revision"},
            "accepted": True,
            "parents": ["request-2", "decision-3"],
            "note": "검증",
        }

        self.assertEqual(
            canonical.canonical_json_bytes(artifact),
            (
                '{"accepted":true,"note":"검증","parents":["request-2","decision-3"],'
                '"schema_version":1,"subject":{"id":"workflow-7","kind":"workflow_revision"}}'
            ).encode("utf-8"),
        )
        self.assertEqual(
            canonical.content_digest(artifact),
            "sha256:9ef2d6362d8228ecd6aa78be1d40a609b4b0d170fbae27b0f11963b5d345ec1e",
        )

    def test_object_insertion_order_does_not_change_identity(self) -> None:
        left = {"b": 2, "a": {"z": 1, "x": 0}}
        right = {"a": {"x": 0, "z": 1}, "b": 2}

        self.assertEqual(canonical.canonical_json_bytes(left), canonical.canonical_json_bytes(right))
        self.assertEqual(canonical.content_digest(left), canonical.content_digest(right))

    def test_array_order_changes_identity(self) -> None:
        self.assertNotEqual(
            canonical.content_digest({"parents": ["a", "b"]}),
            canonical.content_digest({"parents": ["b", "a"]}),
        )

    def test_floating_point_fails_closed(self) -> None:
        with self.assertRaises(canonical.CanonicalizationError):
            canonical.content_digest({"score": 1.5})

    def test_non_string_object_key_fails_closed(self) -> None:
        with self.assertRaises(canonical.CanonicalizationError):
            canonical.content_digest({1: "not-a-json-object-key"})

    def test_integer_outside_interoperable_range_fails_closed(self) -> None:
        with self.assertRaises(canonical.CanonicalizationError):
            canonical.content_digest({"sequence": canonical.MAX_SAFE_INTEGER + 1})

    def test_non_json_value_fails_closed(self) -> None:
        with self.assertRaises(canonical.CanonicalizationError):
            canonical.content_digest({"tags": {"a", "b"}})

    def test_invalid_unicode_fails_closed(self) -> None:
        with self.assertRaises(canonical.CanonicalizationError):
            canonical.content_digest({"bad": "\ud800"})


if __name__ == "__main__":
    unittest.main()
