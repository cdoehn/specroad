"""Passive metadata behavior, with no presentation or documentation oracles."""

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
        with patch("builtins.__import__", side_effect=AssertionError("unexpected import")), patch("builtins.open", side_effect=AssertionError("unexpected file")):
            result = ArtifactMetadata(value).data
            raw = serialize_common_artifact(value)
        self.assertEqual(result["extensions"], value["extensions"])
        self.assertEqual(parse_json_object(raw), value)
