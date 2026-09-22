"""Passive metadata behavior, with no presentation or documentation oracles."""

import builtins
import json
import unittest
from copy import deepcopy
from unittest.mock import patch

from specroad.model.artifact_schemas import validate_common_fields, artifact_common_schema
from specroad.model.configuration import ProjectConfiguration
from specroad.model.errors import ModelError
from specroad.model._schema import validate_builtin
from specroad.storage.metadata import ArtifactMetadata, serialize_common_artifact
from specroad.storage.json_syntax import parse_json_object
from specroad.storage.domain_artifact import DomainArtifact
from specroad.storage.record_artifact import RecordArtifact
from support.artifacts import common_artifact, artifact_bytes
from support.domain import domain_value
from support.records import record_value
from support.model import configuration_value


def provenance(**changes):
    value = {"locator": "manual:meeting/2026-09-15", "captured_at": "2026-09-15T10:00:00Z",
             "excerpt": "Änderung: 東京 / بيانات"}
    value.update(changes)
    return value


class MetadataTests(unittest.TestCase):
    def test_unknown_extensions_survive_load_and_serialize(self):
        extra = {"example.custom": {"opaque": [None, False, 2, 0.125, "é\n東京"], "$ref": "remote:not-followed"}}
        value = common_artifact(extensions=extra)
        raw = serialize_common_artifact(value)
        self.assertEqual(parse_json_object(raw), value)
        self.assertEqual(ArtifactMetadata.from_bytes(raw).data["extensions"], extra)

    def test_metadata_projection_detaches_inputs_and_outputs(self):
        value = common_artifact(extensions={"vendor.data": {"a": [1]}})
        resource = ArtifactMetadata(value)
        value["extensions"]["vendor.data"]["a"].append(2)
        exposed = resource.data; exposed["extensions"].clear()
        self.assertEqual(resource.data, {"extensions": {"vendor.data": {"a": [1]}}})

    def test_display_id_is_optional_and_preserved(self):
        value = common_artifact(display_id="REQ-1")
        self.assertEqual(ArtifactMetadata(value).data["display_id"], "REQ-1")
        self.assertNotIn("display_id", ArtifactMetadata(common_artifact()).data)
        self.assertEqual(parse_json_object(serialize_common_artifact(value))["id"], value["id"])

    def test_domain_reader_preserves_display_id(self):
        value = domain_value("requirement", display_id="SR-REQ-0018")
        self.assertEqual(DomainArtifact(artifact_bytes(value)).data, value)

    def test_record_reader_preserves_display_id(self):
        value = record_value("source", display_id="SOURCE A")
        self.assertEqual(RecordArtifact(artifact_bytes(value)).data, value)

    def test_locator_provenance_retained(self):
        value = common_artifact(provenance=[provenance()])
        self.assertEqual(ArtifactMetadata.from_bytes(serialize_common_artifact(value)).data["provenance"], value["provenance"])

    def test_source_and_hash_provenance_retained(self):
        data = {"source_id": "SR-SRC-" + "0" * 26, "captured_at": "2026-01-01T00:00:00Z", "content_sha256": "a" * 64}
        value = common_artifact(provenance=[data])
        self.assertEqual(ArtifactMetadata(value).data["provenance"], [data])

    def test_provenance_needs_source_or_locator(self):
        value = provenance(); del value["locator"]
        with self.assertRaises(ModelError): validate_common_fields(common_artifact(provenance=[value]))

    def test_provenance_needs_excerpt_or_hash(self):
        value = provenance(); del value["excerpt"]
        with self.assertRaises(ModelError): validate_common_fields(common_artifact(provenance=[value]))

    def test_provenance_needs_timestamp(self):
        value = provenance(); del value["captured_at"]
        with self.assertRaises(ModelError): validate_common_fields(common_artifact(provenance=[value]))

    def test_empty_provenance_record_is_not_evidence(self):
        with self.assertRaises(ModelError): validate_common_fields(common_artifact(provenance=[{}]))

    def test_rejects_missing_namespace(self):
        with self.assertRaises(ModelError): validate_common_fields(common_artifact(extensions={"plain": 1}))

    def test_rejects_empty_namespace_components(self):
        for key in (".name", "vendor.", "vendor..name"):
            with self.subTest(key=key), self.assertRaises(ModelError):
                validate_common_fields(common_artifact(extensions={key: 1}))

    def test_project_extensions_use_same_namespace_contract(self):
        value = configuration_value(); value["extensions"] = {"vendor.flag": True}
        self.assertEqual(ProjectConfiguration(value).data["extensions"], value["extensions"])
        value["extensions"] = {"flag": True}
        with self.assertRaises(ModelError): ProjectConfiguration(value)

    def test_relation_extensions_are_inert_namespaced_data(self):
        value = common_artifact(relations=[{"extensions": {"vendor.info": {"x": [None]}}}])
        self.assertEqual(parse_json_object(serialize_common_artifact(value)), value)
        value["relations"][0]["extensions"] = {"bad": True}
        with self.assertRaises(ModelError): validate_common_fields(value)

    def test_schema_resource_enforces_metadata_contract(self):
        value = common_artifact(extensions={"bad": 1})
        with self.assertRaises(ModelError): validate_builtin(value, artifact_common_schema("goal"))

    def test_cyclic_metadata_is_rejected(self):
        value = common_artifact(); value["extensions"]["vendor.cycle"] = value
        with self.assertRaises(ModelError): serialize_common_artifact(value)

    def test_unknown_namespace_does_not_import_or_execute(self):
        value = common_artifact(extensions={"uninstalled.plugin": {"entrypoint": "os.system", "command": "raise"}})
        with patch.object(builtins, "__import__", side_effect=AssertionError("unexpected import")), patch.object(builtins, "open", side_effect=AssertionError("unexpected file")):
            result = ArtifactMetadata(value).data
            raw = serialize_common_artifact(value)
        self.assertEqual(result["extensions"], value["extensions"])
        self.assertEqual(parse_json_object(raw), value)


class MetadataRightTests(unittest.TestCase):
    def test_deep_extensions_preserve_all_values(self):
        tree = {"e\u0301": [False, None, -0.0, "\0", "😀", 9007199254740994]}
        for _ in range(150): tree = {"items": [tree]}
        value = common_artifact(extensions={"org.example.data": tree})
        self.assertEqual(parse_json_object(serialize_common_artifact(value)), value)

    def test_namespaces_preserve_unicode_and_do_not_normalize(self):
        value = common_artifact(extensions={"anbieter.ä": 1, "anbieter.a\u0308": 2, "供应商.数据": False})
        self.assertEqual(ArtifactMetadata(value).data["extensions"], value["extensions"])

    def test_whitespace_and_control_in_namespaces_rejected(self):
        for key in ("a. b", "a.b\n", "a.\0b", "a.\x7fb", "a.\tb", "a.\u2003b"):
            with self.subTest(key=repr(key)), self.assertRaises(ModelError):
                validate_common_fields(common_artifact(extensions={key: 1}))

    def test_provenance_preserves_both_alternatives_and_extensions(self):
        data = provenance(source_id="SR-SRC-0001", content_sha256="1" * 64,
                          extensions={"vendor.audit": {"unknown": [None, 0, False]}})
        value = common_artifact(provenance=[data, deepcopy(data)])
        raw = serialize_common_artifact(value)
        self.assertEqual(ArtifactMetadata.from_bytes(raw).data["provenance"], value["provenance"])

    def test_provenance_hash_and_time_contracts_reject_invalid_values(self):
        for values in ({"content_sha256": "F" * 64}, {"content_sha256": "f" * 63},
                       {"captured_at": "2026-02-30T00:00:00Z"}, {"captured_at": "2026-01-01T12:00:00+02:00"},
                       {"source_id": "SR-REQ-0001"}, {"excerpt": ""}):
            with self.subTest(value=repr(values)), self.assertRaises(ModelError):
                validate_common_fields(common_artifact(provenance=[provenance(**values)]))

    def test_provenance_unknown_fields_must_use_extensions(self):
        with self.assertRaises(ModelError):
            validate_common_fields(common_artifact(provenance=[provenance(custom="x")]))
        validate_common_fields(common_artifact(provenance=[provenance(extensions={"vendor.custom": "x"})]))

    def test_display_id_rejects_nonstrings_empty_and_null(self):
        for value in (None, 0, False, {}, [], "", "\t", "label\0"):
            with self.subTest(value=repr(value)), self.assertRaises(ModelError):
                validate_common_fields(common_artifact(display_id=value))

    def test_label_change_never_changes_path_or_identity(self):
        from specroad.model.paths import artifact_path
        from specroad.storage.metadata import resolve_artifact_reference
        value = common_artifact(display_id="A")
        before = artifact_path("goal", value["id"], "SR")
        value["display_id"] = "renamed"
        resolved = resolve_artifact_reference(value["id"], [value], id_prefix="SR")
        self.assertEqual(resolved["id"], value["id"])
        self.assertEqual(artifact_path("goal", resolved["id"], "SR"), before)

    def test_display_id_cannot_resolve_an_artifact(self):
        from specroad.storage.metadata import resolve_artifact_reference
        value = common_artifact(display_id="SR-GOAL-0001")
        with self.assertRaises(ModelError) as caught:
            resolve_artifact_reference(value["display_id"], [value], id_prefix="SR")
        self.assertEqual(caught.exception.reason, "display_id_is_not_identity")

    def test_duplicate_labels_do_not_merge_artifacts(self):
        from specroad.storage.metadata import resolve_artifact_reference
        one = common_artifact(display_id="same")
        two = common_artifact(id="SR-GOAL-" + "0" * 25 + "1", display_id="same")
        for value in (one, two):
            self.assertEqual(resolve_artifact_reference(value["id"], [one, two], id_prefix="SR"), value)

    def test_actual_id_wins_over_another_artifact_label(self):
        from specroad.storage.metadata import resolve_artifact_reference
        one = common_artifact()
        two = common_artifact(id="SR-GOAL-" + "0" * 25 + "1", display_id=one["id"])
        self.assertEqual(resolve_artifact_reference(one["id"], [two, one], id_prefix="SR"), one)

    def test_resolver_rejects_duplicate_actual_ids(self):
        from specroad.storage.metadata import resolve_artifact_reference
        one = common_artifact()
        with self.assertRaises(ModelError) as caught:
            resolve_artifact_reference(one["id"], [one, deepcopy(one)], id_prefix="SR")
        self.assertEqual(caught.exception.reason, "duplicate_artifact_id")

    def test_resolver_rejects_foreign_project(self):
        from specroad.storage.metadata import resolve_artifact_reference
        value = common_artifact(id="OTHER-GOAL-" + "0" * 26)
        with self.assertRaises(ModelError): resolve_artifact_reference(value["id"], [value], id_prefix="SR")

    def test_resolver_checks_full_inventory_and_returns_detached_data(self):
        from specroad.storage.metadata import resolve_artifact_reference
        value = common_artifact(extensions={"vendor.data": [1]})
        with self.assertRaises(ModelError): resolve_artifact_reference(value["id"], [value, {}], id_prefix="SR")
        result = resolve_artifact_reference(value["id"], [value], id_prefix="SR")
        result["extensions"]["vendor.data"].append(2)
        self.assertEqual(value["extensions"]["vendor.data"], [1])

    def test_invalid_reference_and_inventory_rejected(self):
        from specroad.storage.metadata import resolve_artifact_reference
        for value in (None, 1, False, {}, [], ""):
            with self.subTest(value=repr(value)), self.assertRaises(ModelError):
                resolve_artifact_reference(value, [], id_prefix="SR")
        for value in (None, 1, False, {}, "abc", b"abc"):
            with self.subTest(value=repr(value)), self.assertRaises(ModelError):
                resolve_artifact_reference("SR-GOAL-0001", value, id_prefix="SR")

    def test_unknown_reference_is_not_guessed(self):
        from specroad.storage.metadata import resolve_artifact_reference
        with self.assertRaises(ModelError) as caught:
            resolve_artifact_reference("SR-GOAL-0001", [common_artifact()], id_prefix="SR")
        self.assertEqual(caught.exception.reason, "artifact_not_found")

    def test_schema_objects_are_detached(self):
        from specroad.model.metadata import metadata_schemas
        one = metadata_schemas(); one["extensions"].clear()
        self.assertTrue(metadata_schemas()["extensions"])
        with self.assertRaises(ModelError): validate_common_fields(common_artifact(extensions={"bad": 1}))

    def test_failed_serialization_does_not_change_input(self):
        value = common_artifact(provenance=[provenance(content_sha256="invalid")])
        before = deepcopy(value)
        with self.assertRaises(ModelError): serialize_common_artifact(value)
        self.assertEqual(value, before)
