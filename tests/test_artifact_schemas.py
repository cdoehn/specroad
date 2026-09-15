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


class ArtifactSchemaRightTests(unittest.TestCase):
    def test_id_prefix_is_bound_for_each_of_the_28_types(self):
        for kind, prefix in EXPECTED:
            with self.subTest(kind=kind):
                with self.assertRaises(ModelError):
                    validate_common_fields(common_artifact(kind, prefix, id="SR-WRONG-" + "0" * 26))

    def test_random_identity_alphabet_length_and_first_character(self):
        for token in ("0" * 25, "0" * 27, "8" + "0" * 25, "0" * 25 + "I", "0" * 25 + "O",
                      "0" * 25 + "U", "0" * 25 + "L", "0" * 25 + "a", "0" * 26 + "\n"):
            with self.subTest(token=token), self.assertRaises(ModelError):
                validate_common_fields(common_artifact(id="SR-GOAL-" + token))
        validate_common_fields(common_artifact(id="SR-GOAL-7" + "Z" * 25))

    def test_valid_legacy_ids_are_readable_but_not_minted(self):
        for kind, prefix in EXPECTED:
            with self.subTest(kind=kind):
                resource = CommonArtifact(artifact_bytes(common_artifact(kind, prefix,
                    id="SR-" + prefix + "-0123", id_scheme="legacy-sequential-v1")))
                self.assertEqual(resource.id, "SR-" + prefix + "-0123")
                self.assertEqual(resource.validation_scope, "common_fields_only")

    def test_identity_scheme_cannot_be_swapped_without_changing_identity(self):
        for values in ({"id": "SR-GOAL-0001"}, {"id_scheme": "legacy-sequential-v1"},
                       {"id_scheme": "derived128-v1"}, {"id": "sr-GOAL-" + "0" * 26}):
            with self.subTest(values=str(values)), self.assertRaises(ModelError):
                validate_common_fields(common_artifact(**values))

    def test_artifact_project_prefix_grammar(self):
        for prefix in ("A", "1A", "ABCDEFGHI", "aB", "AB-", "../AB", "AB\n"):
            with self.subTest(prefix=prefix), self.assertRaises(ModelError):
                validate_common_fields(common_artifact(id=prefix + "-GOAL-" + "0" * 26))
        for prefix in ("AA", "A1", "ABCDEFGH"):
            validate_common_fields(common_artifact(id=prefix + "-GOAL-" + "0" * 26))

    def test_bad_identity_types_are_controlled_model_errors(self):
        for value in (None, True, [], {}, 12):
            with self.subTest(value=str(value)), self.assertRaises(ModelError):
                validate_common_fields(common_artifact(id=value))

    def test_utc_timestamp_forms_preserve_the_input_bytes(self):
        for timestamp in ("2024-02-29T10:30:59Z", "2024-02-29t10:30:59z",
                          "2024-02-29T10:30:59.123456789Z", "2024-02-29T10:30:59+00:00",
                          "2016-12-31T23:59:60Z"):
            with self.subTest(timestamp=timestamp):
                raw = artifact_bytes(common_artifact(created_at=timestamp, updated_at=timestamp))
                resource = CommonArtifact(raw)
                self.assertEqual(resource.source_bytes, raw)
                self.assertEqual(resource.common_fields["created_at"], timestamp)

    def test_bad_calendar_and_non_utc_timestamps_are_rejected(self):
        for timestamp in ("2023-02-29T00:00:00Z", "2024-13-01T00:00:00Z", "0000-01-01T00:00:00Z",
                          "2024-01-01T24:00:00Z", "2024-01-01T00:60:00Z", "2024-01-01T00:00:61Z",
                          "2024-01-01T00:00:60Z", "2024-01-01T00:00:00", "2024-01-01T00:00:00-00:00",
                          "2024-01-01T00:00:00+01:00", "2024-01-01T00:00:00.Z", "2024-01-01T00:00:00Z\n"):
            for field in ("created_at", "updated_at"):
                with self.subTest(timestamp=timestamp, field=field), self.assertRaises(ModelError) as caught:
                    validate_common_fields(common_artifact(**{field: timestamp}))
                self.assertEqual(caught.exception.pointer, "/" + field)

    def test_actor_discriminators_and_ids_are_checked(self):
        for value in ({"actor_type": "robot", "actor_id": "a"}, {"actor_type": True, "actor_id": "a"},
                      {"actor_type": "human", "actor_id": " "}, {"actor_type": "human", "actor_id": 5},
                      {"actor_type": "human", "actor_id": "x", "run_shell": "ignored?"}):
            with self.subTest(value=str(value)), self.assertRaises(ModelError):
                validate_common_fields(common_artifact(created_by=value))
        for kind in ("human", "ai", "ci", "tool"):
            validate_common_fields(common_artifact(created_by={"actor_type": kind, "actor_id": "actor"}))

    def test_nested_actor_error_reports_exact_json_pointer_without_value(self):
        secret = "SECRET_ACTOR_TYPE"
        with self.assertRaises(ModelError) as caught:
            CommonArtifact(artifact_bytes(common_artifact(updated_by={"actor_type": secret, "actor_id": "a"})), path="owned.json")
        self.assertEqual(caught.exception.pointer, "/updated_by/actor_type")
        self.assertNotIn(secret, json.dumps(caught.exception.diagnostic()))

    def test_required_text_cannot_be_blank_or_contain_nul(self):
        for field in ("title", "language", "owner"):
            for bad in ("", " \t\n", "A\0B"):
                with self.subTest(field=field, bad=repr(bad)), self.assertRaises(ModelError):
                    validate_common_fields(common_artifact(**{field: bad}))

    def test_json_integer_semantics_do_not_confuse_booleans_and_integers(self):
        validate_common_fields(common_artifact(revision=1.0))
        for value in (False, True, 0.0, 2.5, -1, "1"):
            with self.subTest(value=repr(value)), self.assertRaises(ModelError):
                validate_common_fields(common_artifact(revision=value))

    def test_optional_common_fields_are_checked_without_modifying_input(self):
        value = common_artifact(owner={"actor_type": "human", "actor_id": "owner"},
                                tags=["a", "b"], provenance=[{"locator": "manual:example", "captured_at": "2026-01-01T00:00:00Z", "excerpt": "source text"}], external_identities=[{}],
                                applicability={"op": "literal", "value": True}, text_direction="auto")
        before = artifact_bytes(value); validate_common_fields(value)
        self.assertEqual(artifact_bytes(value), before)
        for field, bad in (("owner", []), ("applicability", []), ("provenance", "x"),
                           ("provenance", [1]), ("external_identities", {}), ("external_identities", ["x"])):
            with self.subTest(field=field, value=str(bad)), self.assertRaises(ModelError):
                validate_common_fields(common_artifact(**{field: bad}))

    def test_json_only_input_boundary_catches_non_json_values_and_cycles(self):
        for bad in (set(), object(), float("nan"), float("inf"), b"x", "\ud800"):
            with self.subTest(value=str(type(bad))), self.assertRaises(ModelError):
                validate_common_fields(common_artifact(extensions={"org.example": bad}))
        value = common_artifact(); value["extensions"]["cycle"] = value
        with self.assertRaises(ModelError) as caught: validate_common_fields(value)
        self.assertEqual(caught.exception.reason, "unsupported_json_nesting")

    def test_invalid_common_input_objects_are_not_coerced(self):
        for value in (None, False, [], "{}", b"{}", 1):
            with self.subTest(value=str(value)), self.assertRaises(ModelError): validate_common_fields(value)

    def test_common_validation_has_no_graph_or_approval_side_effect(self):
        value = common_artifact(maturity="approved", statement="type-specific content")
        raw = artifact_bytes(value); result = CommonArtifact(raw)
        self.assertEqual(result.validation_scope, "common_fields_only")
        self.assertEqual(result.common_fields["maturity"], "approved")
        self.assertNotIn("statement", result.common_fields)
        self.assertEqual(raw, result.source_bytes)

    def test_schema_resources_work_after_relocating_portable_distributions(self):
        import subprocess
        import sys
        from support.portable import build_distribution
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); repository = Path(__file__).resolve().parents[1]
            module, archive = build_distribution(root / "build", repository / "src")
            target = root / "relocated"; (root / "build").rename(target)
            for location in (target / "module", target / "specroad.pyz"):
                code = ("import sys,json;sys.path.insert(0,sys.argv[1]);"
                        "from specroad.model.artifact_schemas import artifact_types,artifact_common_schema;"
                        "from specroad.storage.artifact_common import CommonArtifact;"
                        "r=CommonArtifact(sys.argv[2].encode());"
                        "assert len(artifact_types())==28;assert r.validation_scope=='common_fields_only';"
                        "assert artifact_common_schema('goal')['properties']['revision']['minimum']==1")
                result = subprocess.run([sys.executable, "-I", "-S", "-B", "-c", code, str(location),
                                         artifact_bytes(common_artifact()).decode()], cwd=root,
                                        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                self.assertEqual(result.returncode, 0, result.stderr.decode())

    def test_read_rejects_a_symlink_without_touching_target(self):
        from specroad.security import SafetyViolation
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); configuration_file(root)
            value = common_artifact(); name = artifact_path("goal", value["id"], "SR")
            target = put(root, "outside.json", artifact_bytes(value))
            link = root / name; link.parent.mkdir(parents=True); link.symlink_to(target)
            with self.assertRaises(SafetyViolation): read_common_artifact(ProjectSource(root), name)
            self.assertEqual(target.read_bytes(), artifact_bytes(value))

    def test_schema_mutations_cannot_disable_id_and_time_validation(self):
        schema = artifact_common_schema("goal"); schema["anyOf"].clear(); schema["$defs"]["utc"].clear()
        for bad in ({"id": "arbitrary"}, {"updated_at": "yesterday"}):
            with self.subTest(value=str(bad)), self.assertRaises(ModelError):
                validate_common_fields(common_artifact(**bad))

    def test_supplied_bytes_are_not_changed_by_plain_json_schema_validation(self):
        value = common_artifact(revision=1.0, title="e\u0301 文字", extensions={"org.example": {"x": 0.1}})
        raw = (" \n" + json.dumps(value, ensure_ascii=True, indent=3) + "\n").encode()
        self.assertEqual(CommonArtifact(raw).source_bytes, raw)

    def test_invalid_schema_version_and_kind_have_stable_failure_pointers(self):
        for values, pointer in (({"schema_version": "future"}, "/schema_version"),
                                ({"artifact_type": "unknown"}, "/artifact_type")):
            with self.subTest(values=str(values)), self.assertRaises(ModelError) as caught:
                validate_common_fields(common_artifact(**values))
            self.assertEqual(caught.exception.pointer, pointer)

    def test_existing_closed_json_reader_still_rejects_unknown_full_fields(self):
        from specroad.storage.json_reader import JsonResource, ResourceSchema
        from specroad.model.paths import PathClass
        schema = ResourceSchema("minimal", PathClass.ARTIFACT, {"schema_version"}, {"schema_version"})
        with self.assertRaises(ModelError) as caught:
            JsonResource(b'{"schema_version":"0.2.0","unknown":true}', schema)
        self.assertEqual(caught.exception.reason, "unknown_field")

    def test_unsupported_schema_assertions_are_never_silently_ignored(self):
        from specroad.model._schema import validate_builtin
        for schema in ({"type": "unknown"}, {"properties": {"unused": {"format": "custom"}}},
                       {"anyOf": [True, {"patternProperties": {}}]}):
            with self.subTest(schema=str(schema)):
                with self.assertRaises(ValueError):
                    validate_builtin({}, schema)

    def test_schema_references_are_local_acyclic_and_never_resolved_externally(self):
        from specroad.model._schema import validate_builtin
        for reference in ("https://example.invalid/schema", "file:///etc/passwd", "#/$defs/missing"):
            with self.subTest(reference=reference):
                with self.assertRaises(ValueError):
                    validate_builtin({}, {"properties": {"unused": {"$ref": reference}}})
        with self.assertRaises(ValueError):
            validate_builtin({}, {"$defs": {"loop": {"$ref": "#/$defs/loop"}},
                                  "$ref": "#/$defs/loop"})

    def test_same_schema_accepts_json_integers_but_not_python_boolean_equality(self):
        from specroad.model._schema import validate_builtin
        validate_builtin(1.0, {"type": "integer", "const": 1})
        for value in (True, False, "1", None):
            with self.subTest(value=value):
                with self.assertRaises(ModelError):
                    validate_builtin(value, {"const": 1})
        with self.assertRaises(ModelError):
            validate_builtin({"items": [True]}, {"const": {"items": [1]}})
