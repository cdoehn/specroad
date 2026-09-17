"""Portable semantic roots and actual file bindings, never human presentation."""

from dataclasses import FrozenInstanceError
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest

from specroad.model.configuration import ProjectConfiguration
from specroad.model.errors import ModelError
from specroad.model.hashes import canonical_json_sha256
from specroad.model.model_manifest import (ManifestResource, ProjectReadBinding,
                                          assemble_model_manifest)
from specroad.model.semantic_configuration import semantic_configuration
from specroad.storage.model_root import (capture_model_inputs, check_model_inputs_current,
                                        prepare_model_root)
from specroad.storage.project import ProjectSource
from support.artifacts import artifact_bytes, common_artifact
from support.model import configuration_file, configuration_value, put
from support.portable import files_under
from test_resource_inventory import descriptor


def scope(ids=(), resources=(), *, kind="explicit", policy="closed"):
    return {"scope_version": "scope-v1", "scope_kind": kind,
            "selector": {"artifact_ids": sorted(ids), "resource_ids": sorted(resources)} if kind == "explicit" else {},
            "configuration_id": None, "closure_profile": "core-closure-v1", "boundary_policy": policy}


def fixture(root, *, token="0", **overrides):
    configuration_file(root, **overrides)
    value = common_artifact(id="SR-GOAL-" + token * 26)
    path = "spec/goals/" + value["id"] + ".json"
    put(root, path, artifact_bytes(value))
    return path, value


class ModelRootWorkTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path, self.value = fixture(self.root)
        self.source = ProjectSource(self.root)

    def build(self, *, source=None, paths=None, descriptor_value=None, **kw):
        return prepare_model_root(source or self.source, paths or [self.path],
                                  scope_descriptor=descriptor_value or scope([self.value["id"]]),
                                  effective_profile=kw.pop("effective_profile", {}), **kw)

    def test_model_root_is_sha256_of_canonical_manifest(self):
        result = self.build()
        self.assertEqual(result.sha256, sha256(result.canonical_bytes).hexdigest())
        self.assertEqual(result.sha256, canonical_json_sha256(result.data))

    def test_same_snapshot_under_another_root_has_same_hash(self):
        other = self.root / "relocated"; other.mkdir(); fixture(other)
        self.assertEqual(self.build().sha256, self.build(source=ProjectSource(other)).sha256)

    def test_configuration_identity_is_bound(self):
        other = self.root / "foreign"; other.mkdir(); fixture(other, project_id="different")
        self.assertNotEqual(self.build().sha256, self.build(source=ProjectSource(other)).sha256)

    def test_wrong_expected_project_is_rejected(self):
        with self.assertRaises(ModelError): ProjectSource(self.root, expected_project_id="different")

    def test_original_byte_formatting_does_not_change_root(self):
        before = self.build().sha256
        put(self.root, self.path, json.dumps(self.value, sort_keys=True, indent=4).encode())
        self.assertEqual(self.build().sha256, before)

    def test_artifact_content_changes_root(self):
        before = self.build().sha256
        put(self.root, self.path, artifact_bytes({**self.value, "title": "Other"}))
        self.assertNotEqual(self.build().sha256, before)

    def test_audit_field_changes_are_not_stripped(self):
        before = self.build().sha256
        put(self.root, self.path, artifact_bytes({**self.value, "revision": 2}))
        self.assertNotEqual(self.build().sha256, before)

    def test_scope_descriptor_changes_are_bound(self):
        a = self.build(); b = self.build(descriptor_value=scope(kind="project"))
        self.assertNotEqual(a.scope_sha256, b.scope_sha256)
        self.assertNotEqual(a.sha256, b.sha256)

    def test_profile_projection_changes_are_bound(self):
        a = self.build(); b = self.build(effective_profile={"required_fields": ["rationale"]})
        self.assertNotEqual(a.sha256, b.sha256)
        self.assertNotEqual(a.scope_sha256, b.scope_sha256)

    def test_explicit_empty_profile_is_required_not_invented(self):
        with self.assertRaises(ModelError): self.build(effective_profile=None)

    def test_artifact_order_is_independent_of_path_input_order(self):
        other = common_artifact(id="SR-GOAL-" + "1" * 26)
        path = "spec/goals/" + other["id"] + ".json"; put(self.root, path, artifact_bytes(other))
        a = self.build(paths=[path, self.path]); b = self.build(paths=[self.path, path])
        self.assertEqual(a.sha256, b.sha256)
        self.assertEqual([r["id"] for r in a.data["artifacts"]], sorted([self.value["id"], other["id"]]))

    def test_required_seed_missing_is_not_a_partial_success(self):
        with self.assertRaises(ModelError): self.build(descriptor_value=scope(["SR-GOAL-" + "1"*26]))

    def test_no_implicit_scan_of_unselected_artifact(self):
        before = self.build().sha256
        other = common_artifact(id="SR-GOAL-" + "1" * 26)
        put(self.root, "spec/goals/" + other["id"] + ".json", artifact_bytes(other))
        self.assertEqual(self.build().sha256, before)
        self.assertFalse(self.build().closure_verified)

    def test_included_attachment_hashes_actual_bytes(self):
        item = descriptor(content=b"abc"); put(self.root, item.path, b"abc")
        result = self.build(attachments=(item,))
        self.assertEqual(result.data["attachments"], [{"kind":"attachment", **item.data}])
        put(self.root, item.path, b"def")
        with self.assertRaises(ModelError): self.build(attachments=(item,))

    def test_attachment_media_and_relative_path_are_bound(self):
        a=descriptor("attachments/a",b"abc","text/plain"); b=descriptor("attachments/b",b"abc","text/plain")
        put(self.root,a.path,b"abc"); put(self.root,b.path,b"abc")
        h=self.build(attachments=(a,)).sha256
        self.assertNotEqual(h,self.build(attachments=(b,)).sha256)
        c=descriptor(a.path,b"abc","application/octet-stream")
        self.assertNotEqual(h,self.build(attachments=(c,)).sha256)

    def test_resource_identity_version_and_content_are_bound(self):
        value={"schema_version":"0.2.0","profile_id":"core","profile_version":"0.2.0","rules":[]}
        put(self.root,"profiles/core.json",artifact_bytes(value))
        a=self.build(paths=[self.path,"profiles/core.json"])
        put(self.root,"profiles/core.json",artifact_bytes({**value,"profile_version":"0.3.0"}))
        self.assertNotEqual(a.sha256,self.build(paths=[self.path,"profiles/core.json"]).sha256)

    def test_missing_resource_identity_is_not_guessed_from_filename(self):
        put(self.root,"rules/named-1.0.0.json",b'{"schema_version":"0.2.0"}')
        with self.assertRaises(ModelError): self.build(paths=[self.path,"rules/named-1.0.0.json"])

    def test_missing_selected_file_fails_entire_capture(self):
        with self.assertRaises(FileNotFoundError): self.build(paths=[self.path,"rules/missing.json"])

    def test_foreign_root_resources_cannot_be_merged(self):
        captured=capture_model_inputs(self.source,[self.path])
        other=self.root/"other";other.mkdir();fixture(other)
        foreign=capture_model_inputs(ProjectSource(other),[self.path])
        with self.assertRaises(ModelError):
            assemble_model_manifest(self.source.configuration,captured.binding,foreign.resources,
                                    scope_descriptor=scope(),effective_profile={})

    def test_freshness_check_rejects_identical_bytes_from_other_root(self):
        captured=capture_model_inputs(self.source,[self.path])
        other=self.root/"other";other.mkdir();fixture(other)
        with self.assertRaises(ModelError):check_model_inputs_current(ProjectSource(other),captured)

    def test_freshness_check_is_byte_sensitive_even_when_root_is_not(self):
        captured=capture_model_inputs(self.source,[self.path]); before=self.build().sha256
        put(self.root,self.path,json.dumps(self.value,indent=2).encode())
        with self.assertRaises(ModelError):check_model_inputs_current(self.source,captured)
        self.assertEqual(before,self.build().sha256)

    def test_configuration_is_never_hashed_a_second_time_as_raw_bytes(self):
        self.assertEqual(self.build().sha256,self.build(paths=[self.path,"specroad.json"]).sha256)

    def test_semantic_configuration_removes_display_and_soft_targets(self):
        a=ProjectConfiguration(configuration_value())
        b=ProjectConfiguration(configuration_value(default_locale="ja",generated_path="views",
                              resource_limits={"model_bytes":10,"query_result_count":3}))
        self.assertEqual(semantic_configuration(a),semantic_configuration(b))

    def test_semantic_configuration_keeps_hard_limits(self):
        a=ProjectConfiguration(configuration_value(resource_limits={"artifact_file_bytes":1}))
        b=ProjectConfiguration(configuration_value(resource_limits={"artifact_file_bytes":2}))
        self.assertNotEqual(semantic_configuration(a),semantic_configuration(b))

    def test_numeric_precision_and_query_defaults_are_materialized(self):
        a=ProjectConfiguration(configuration_value())
        b=ProjectConfiguration(configuration_value(resource_limits={"query_default_limit":100},
                              srx_policy={"numeric_policy_version":"srx-decimal-v1","decimal_precision":34}))
        self.assertEqual(semantic_configuration(a),semantic_configuration(b))

    def test_unknown_limits_require_classification_not_silent_exclusion(self):
        with self.assertRaises(ModelError):semantic_configuration(ProjectConfiguration(configuration_value(resource_limits={"guess":1})))

    def test_proposal_cannot_be_hashed_as_specification_resource(self):
        value=common_artifact("proposal","PROP"); from specroad.model.paths import artifact_path
        path=artifact_path("proposal",value["id"],"SR");put(self.root,path,artifact_bytes(value))
        with self.assertRaises(ModelError):self.build(paths=[path],descriptor_value=scope(kind="specification"))

    def test_hash_is_not_a_closure_profile_or_write_proof(self):
        result=self.build()
        self.assertEqual(result.validation_scope,"manifest_inputs_only")
        self.assertFalse(result.closure_verified)
        self.assertFalse(result.profile_composition_verified)
        self.assertFalse(result.atomic_snapshot)

    def test_owned_values_and_original_files_are_preserved(self):
        before=files_under(self.root); result=self.build(); value=result.data;value["artifacts"].clear()
        self.assertEqual(len(result.data["artifacts"]),1)
        self.assertEqual(before,files_under(self.root))
        with self.assertRaises(FrozenInstanceError):result._encoded=b"{}"

    def test_duplicate_members_are_not_silently_deduplicated(self):
        captured=capture_model_inputs(self.source,[self.path])
        with self.assertRaises(ModelError):
            assemble_model_manifest(self.source.configuration,captured.binding,captured.resources*2,
                                    scope_descriptor=scope(),effective_profile={})
