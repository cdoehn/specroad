"""Behavior of versioned schema resources and common-field reads, not UI/doc tests."""

from dataclasses import FrozenInstanceError
import json
from pathlib import Path
import tempfile
import unittest

from specroad.model.artifact_schemas import (artifact_types, artifact_type,
    artifact_common_schema, validate_common_fields, COMMON_REQUIRED)
from specroad.model.errors import ModelError
from specroad.model.paths import artifact_path
from specroad.storage import ProjectSource
from specroad.storage.artifact_common import CommonArtifact, read_common_artifact
from support.artifacts import common_artifact, artifact_bytes
from support.model import configuration_file, put

# Fixed expected data contract, not a mirror derived from the implementation.
EXPECTED = (
    ("goal", "GOAL"), ("need", "NEED"), ("capability", "CAP"), ("requirement", "REQ"),
    ("scenario", "SCN"), ("decision", "DEC"), ("risk", "RISK"), ("assumption", "ASM"),
    ("component", "COMP"), ("interface", "IFC"), ("source", "SRC"), ("verification", "VER"),
    ("test", "TEST"), ("evidence", "EVD"), ("release", "REL"), ("milestone", "MS"),
    ("task", "TASK"), ("term", "TERM"), ("proposal", "PROP"), ("baseline", "BASE"),
    ("issue", "ISSUE"), ("document", "DOC"), ("section", "SEC"), ("content_block", "BLOCK"),
    ("view", "VIEW"), ("code_ref", "CODE"), ("relation_review", "RREV"), ("configuration", "CFG"),
)


class ArtifactSchemaWorkTests(unittest.TestCase):
    def test_all_28_types_have_distinct_versioned_schema_and_prefix(self):
        entries = artifact_types()
        self.assertEqual(tuple((entry.artifact_type, entry.prefix) for entry in entries), EXPECTED)
        self.assertEqual(len({entry.schema_id for entry in entries}), 28)
        self.assertEqual(len({entry.prefix for entry in entries}), 28)
        for entry in entries:
            self.assertEqual(entry.schema_version, "0.2.0")
            schema = artifact_common_schema(entry.artifact_type)
            self.assertEqual(schema["$id"], entry.schema_id)
            self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
            self.assertEqual(json.loads(json.dumps(schema)), schema)

    def test_minimal_common_fields_for_every_type(self):
        for kind, prefix in EXPECTED:
            with self.subTest(kind=kind):
                raw = artifact_bytes(common_artifact(kind, prefix))
                resource = CommonArtifact(raw)
                self.assertEqual(resource.artifact_type, kind)
                self.assertEqual(resource.source_bytes, raw)
                self.assertEqual(resource.validation_scope, "common_fields_only")

    def test_all_common_required_fields_are_required_for_every_type(self):
        required = ("schema_version", "id", "id_scheme", "artifact_type", "title", "maturity",
                    "revision", "created_at", "updated_at", "created_by", "updated_by", "relations", "extensions")
        self.assertEqual(set(COMMON_REQUIRED), set(required))
        for kind, prefix in EXPECTED:
            for name in required:
                with self.subTest(kind=kind, field=name):
                    value = common_artifact(kind, prefix); value.pop(name)
                    with self.assertRaises(ModelError): CommonArtifact(artifact_bytes(value))

    def test_unknown_types_are_not_silently_registered(self):
        for kind in ("unknown", "Goal", "", [], {}, True, None):
            with self.subTest(kind=str(kind)):
                with self.assertRaises(ModelError) as caught: artifact_type(kind)
                self.assertEqual(caught.exception.reason, "unknown_artifact_type")

    def test_unsupported_schema_versions_are_explicit(self):
        for version in ("0.1.0", "0.2.1", "1.0.0", "v0.2.0", None, True, [], {}):
            with self.subTest(version=str(version)):
                with self.assertRaises(ModelError) as caught: artifact_common_schema("goal", version)
                self.assertEqual(caught.exception.highest_supported, "0.2.0")
                with self.assertRaises(ModelError): CommonArtifact(artifact_bytes(common_artifact(schema_version=version)))

    def test_language_required_only_for_declared_common_language_types(self):
        for kind, prefix in EXPECTED:
            value = common_artifact(kind, prefix); value.pop("language", None)
            with self.subTest(kind=kind):
                if kind in ("requirement", "document", "term"):
                    with self.assertRaises(ModelError): validate_common_fields(value)
                else:
                    validate_common_fields(value)

    def test_registry_entries_cannot_be_mutated(self):
        item = artifact_type("goal")
        with self.assertRaises(FrozenInstanceError): item.prefix = "EVIL"
        self.assertEqual(artifact_type("goal").prefix, "GOAL")

    def test_schema_results_do_not_mutate_the_next_schema_or_validator(self):
        schema = artifact_common_schema("goal")
        schema["required"].clear(); schema["properties"]["revision"]["minimum"] = -10
        schema["$defs"]["actor"]["required"].clear()
        with self.assertRaises(ModelError): validate_common_fields(common_artifact(revision=0))
        self.assertIn("revision", artifact_common_schema("goal")["required"])

    def test_common_projection_owns_data_and_does_not_claim_full_validation(self):
        value = common_artifact(statement={"later": "type-specific validation"})
        raw = artifact_bytes(value); resource = CommonArtifact(raw)
        self.assertNotIn("statement", resource.common_fields)
        data = resource.common_fields; data["created_by"]["actor_id"] = "other"
        self.assertEqual(resource.common_fields["created_by"]["actor_id"], "test-author")
        self.assertEqual(resource.source_bytes, raw)
        with self.assertRaises(FrozenInstanceError): resource.source_bytes = b'{}'

    def test_invalid_common_shapes_have_structured_failure(self):
        for name, bad in (("title", 4), ("title", ""), ("revision", True), ("revision", 0),
                          ("revision", 1.5), ("created_by", "human"), ("created_by", {}),
                          ("relations", {}), ("relations", ["id"]), ("extensions", []),
                          ("maturity", "passed"), ("tags", [1]), ("text_direction", "diagonal")):
            with self.subTest(field=name, value=str(bad)):
                with self.assertRaises(ModelError) as caught:
                    CommonArtifact(artifact_bytes(common_artifact(**{name: bad})), path="input.json")
                self.assertEqual(caught.exception.path, "input.json")
                self.assertTrue(caught.exception.pointer.startswith("/" + name))

    def test_expected_type_cannot_disagree_with_document(self):
        with self.assertRaises(ModelError) as caught:
            CommonArtifact(artifact_bytes(common_artifact()), expected_type="requirement")
        self.assertEqual(caught.exception.reason, "artifact_type_mismatch")

    def test_read_bound_artifact_preserves_original_file(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); configuration_file(root)
            value = common_artifact(statement="Later schema layer")
            name = artifact_path("goal", value["id"], "SR"); raw = artifact_bytes(value)
            path = put(root, name, raw); source = ProjectSource(root)
            before = sorted(str(item.relative_to(root)) for item in root.rglob("*"))
            resource = read_common_artifact(source, name)
            self.assertEqual(resource.id, value["id"])
            self.assertEqual(resource.source_bytes, path.read_bytes())
            self.assertEqual(before, sorted(str(item.relative_to(root)) for item in root.rglob("*")))

    def test_file_identity_and_project_identity_are_bound(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); configuration_file(root); source = ProjectSource(root)
            name = "spec/goals/SR-GOAL-" + "0" * 26 + ".json"
            for value in (common_artifact(id="SR-GOAL-" + "1" * 26),
                          common_artifact("need", "NEED"), common_artifact(id="XX-GOAL-" + "0" * 26)):
                with self.subTest(identity=value["id"]):
                    put(root, name, artifact_bytes(value))
                    with self.assertRaises(ModelError): read_common_artifact(source, name)

    def test_read_rejects_generated_files_and_stale_configuration(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); configuration_file(root); source = ProjectSource(root)
            put(root, "generated/x.json", artifact_bytes(common_artifact()))
            with self.assertRaises(ModelError): read_common_artifact(source, "generated/x.json")
            value = common_artifact(); name = artifact_path("goal", value["id"], "SR")
            put(root, name, artifact_bytes(value)); configuration_file(root, project_name="Changed")
            with self.assertRaises(ModelError): read_common_artifact(source, name)

    def test_invalid_read_leaves_project_byte_identical(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); configuration_file(root)
            name = "spec/goals/SR-GOAL-" + "0" * 26 + ".json"
            path = put(root, name, artifact_bytes(common_artifact(revision=0)))
            source = ProjectSource(root); before = path.read_bytes()
            with self.assertRaises(ModelError): read_common_artifact(source, name)
            self.assertEqual(path.read_bytes(), before)
            self.assertFalse((root / ".specroad").exists())

    def test_strict_json_boundary_is_not_weakened_by_common_reader(self):
        for raw in (b'{} {}', b'[]', b'{"x":1,"x":2}', b'\xef\xbb\xbf{}'):
            with self.subTest(raw=repr(raw)), self.assertRaises(ModelError): CommonArtifact(raw)
