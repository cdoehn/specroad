"""Invalid and adversarial relation inputs, key updates and read freshness."""

import json
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from specroad.graph.relations import (Relation, SourceRelations, prepare_relation_update,
    require_relation_keys_unchanged, require_retained_relation_keys_unchanged)
from specroad.model.errors import ModelError
from specroad.model.identity_values import artifact_identity
from specroad.security import SafetyViolation
from specroad.storage.relations import read_source_relations
from specroad.storage.project import ProjectSource
from support.artifacts import artifact_bytes
from support.relations import aid, rid, artifact, edge, external
from support.model import configuration_file, put
from support.portable import build_distribution
import subprocess
import sys


def relation(**changes):
    return Relation(artifact_identity(artifact()), edge(**changes))


class RelationRightTests(unittest.TestCase):
    def test_each_identity_key_update_is_rejected_without_changing_input(self):
        previous = relation()
        for name, value in (("relation_id", rid(8)), ("id_scheme", "derived128-v1"),
                            ("type", "depends_on"), ("target", aid(number=8))):
            with self.subTest(name=name), self.assertRaises(ModelError) as caught:
                prepare_relation_update(previous, {name: value})
            self.assertEqual(caught.exception.reason, "relation_key_immutable")
            self.assertEqual(caught.exception.pointer, "/" + name)
        self.assertEqual(previous.data, edge())

    def test_full_replacement_guard_rejects_changed_keys(self):
        previous = relation()
        for name, value in (("relation_id", rid(8)), ("id_scheme", "derived128-v1"),
                            ("type", "depends_on"), ("target", aid(number=8))):
            with self.subTest(name=name), self.assertRaises(ModelError):
                require_relation_keys_unchanged(previous, relation(**{name: value}))

    def test_source_relocation_is_not_a_metadata_update(self):
        previous = relation(); other = Relation(artifact_identity(artifact(number=5)), edge())
        with self.assertRaises(ModelError) as caught: require_relation_keys_unchanged(previous, other)
        self.assertEqual(caught.exception.reason, "relation_source_immutable")

    def test_valid_metadata_update_preserves_keys(self):
        previous = relation(); changes = {"rationale": "reviewed", "external_identities": [external()],
                                         "extensions": {"vendor.review": [True, "é"]}}
        proposed = prepare_relation_update(previous, changes)
        self.assertEqual(previous.key, proposed.key)
        self.assertEqual(proposed.data, edge(**changes))
        self.assertEqual(previous.data, edge())

    def test_equal_key_repetition_is_valid(self):
        previous = relation(); proposed = prepare_relation_update(previous, previous.data)
        self.assertEqual(proposed.data, previous.data)
        require_relation_keys_unchanged(previous, proposed)

    def test_position_update_keeps_relation_identity(self):
        previous = Relation(artifact_identity(artifact("section")), edge("contains", aid("section", 5)))
        result = prepare_relation_update(previous, {"position": 12})
        self.assertEqual(result.identity, previous.identity)
        self.assertEqual(result.data["position"], 12)

    def test_metadata_mutation_does_not_alias_inputs(self):
        previous = relation(); changes = {"extensions": {"vendor.data": [1]}}
        result = prepare_relation_update(previous, changes); changes["extensions"]["vendor.data"].clear()
        result.data["extensions"].clear()
        self.assertEqual(result.data["extensions"], {"vendor.data": [1]})
        self.assertEqual(previous.data["extensions"], {})

    def test_invalid_metadata_update_rejected_without_partial_result(self):
        for changes in ({"extensions": {"bad": 1}}, {"external_identities": [external(), external()]},
                        {"created_at": "2026-02-30T00:00:00Z"}, {"rationale": None}, {"position": 2}):
            previous = relation()
            with self.subTest(changes=repr(changes)), self.assertRaises(ModelError): prepare_relation_update(previous, changes)
            self.assertEqual(previous.data, edge())

    def test_null_and_unrecognized_fields_cannot_delete_keys(self):
        for key in ("relation_id", "id_scheme", "type", "target"):
            with self.subTest(key=key), self.assertRaises(ModelError): prepare_relation_update(relation(), {key: None})
        for changes in ({"source": aid()}, {"delete": "relation_id"}, [], None):
            with self.subTest(changes=repr(changes)), self.assertRaises(ModelError): prepare_relation_update(relation(), changes)

    def test_source_revision_comparison_allows_reordering_and_metadata(self):
        a = artifact(relations=[edge(number=1), edge(number=2)])
        b = deepcopy(a); b["relations"].reverse(); b["relations"][0]["rationale"] = "new"
        require_retained_relation_keys_unchanged(SourceRelations(artifact_bytes(a)), SourceRelations(artifact_bytes(b)))

    def test_source_revision_comparison_rejects_retained_edge_retarget(self):
        a = artifact(relations=[edge(number=1), edge(number=2)])
        b = deepcopy(a); b["relations"][1]["target"] = aid(number=9)
        with self.assertRaises(ModelError) as caught:
            require_retained_relation_keys_unchanged(SourceRelations(artifact_bytes(a)), SourceRelations(artifact_bytes(b), path="source.json"))
        self.assertEqual(caught.exception.pointer, "/relations/1/target")
        self.assertEqual(caught.exception.path, "source.json")

    def test_new_edge_identity_is_not_misclassified_as_update(self):
        a = SourceRelations(artifact_bytes(artifact(relations=[edge(number=1)])))
        b = SourceRelations(artifact_bytes(artifact(relations=[edge(number=2, target=aid(number=8))])))
        require_retained_relation_keys_unchanged(a, b)
        self.assertEqual(a.relations[0].identity.id, rid(1))
        self.assertEqual(b.relations[0].identity.id, rid(2))
        self.assertEqual(b.validation_scope, "relation_fields_only")

    def test_bad_guard_argument_types_fail_closed(self):
        for value in (None, {}, [], edge()):
            with self.subTest(value=repr(value)), self.assertRaises(ModelError): require_relation_keys_unchanged(relation(), value)
            with self.subTest(value=repr(value)), self.assertRaises(ModelError): require_retained_relation_keys_unchanged(value, value)

    def test_import_binding_hashes_and_timestamp_are_checked(self):
        data = external(mapping_id="m", last_imported_projection_sha256="a"*64,
                        last_source_projection_sha256="b"*64, last_source_payload_sha256="c"*64,
                        imported_at="2026-01-01T00:00:00Z")
        for field, value in (("mapping_id", ""), ("last_source_projection_sha256", "F"*64),
                             ("last_source_payload_sha256", "f"*63), ("imported_at", "2026-01-01T00:00:00+00:00")):
            with self.subTest(field=field), self.assertRaises(ModelError): relation(external_identities=[dict(data, **{field: value})])

    def test_external_identity_class_and_nested_extensions_checked(self):
        for value in (None, {}, [None], [external(extensions={"plain": True})], [external(unknown=1)],
                      [external(external_revision=7)]):
            with self.subTest(value=repr(value)), self.assertRaises(ModelError): relation(external_identities=value)

    def test_external_revision_unicode_and_all_import_fields_roundtrip(self):
        data = external(source_document="供应商.reqif", external_id=" e\u0301 ", external_revision="007",
                        extensions={"anbieter.ä": [None, "\0", "😀"]})
        self.assertEqual(relation(external_identities=[data]).data["external_identities"], [data])

    def test_malformed_audit_values_rejected(self):
        for changes in ({"created_at": "2026-01-01T00:00:00z"}, {"created_by": "alice"},
                        {"created_by": {"actor_type": "human", "actor_id": ""}},
                        {"created_by": {"actor_type": "human", "actor_id": "A", "cmd": "run"}}):
            with self.subTest(changes=repr(changes)), self.assertRaises(ModelError): relation(**changes)

    def test_nonfinite_and_invalid_unicode_rejected(self):
        for value in (float("nan"), float("inf"), "\ud800", {2: "not string"}):
            with self.subTest(value=repr(value)), self.assertRaises(ModelError): relation(extensions={"a.b": value})

    def test_source_json_duplicate_keys_fail_before_relation_loading(self):
        raw = artifact_bytes(artifact(relations=[edge()])).replace(b'"type": "refines"', b'"type":"refines","type":"depends_on"')
        with self.assertRaises(ModelError): SourceRelations(raw)

    def test_source_kind_and_id_must_match(self):
        value = artifact(); value["artifact_type"] = "goal"
        with self.assertRaises(ModelError): SourceRelations(artifact_bytes(value))

    def test_invalid_source_identity_cannot_be_constructed_from_mapping(self):
        with self.assertRaises(ModelError): Relation(artifact_identity(artifact()).__dict__, edge())

    def test_invalid_source_bytes_rejected(self):
        for raw in (b"[]", b"null", b"{", b"{}", "{}"): 
            with self.subTest(raw=repr(raw)), self.assertRaises(ModelError): SourceRelations(raw)

    def test_observed_source_change_invalidates_read(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); configuration_file(root); value=artifact(relations=[edge()])
            name=artifact_identity(value).path; raw=artifact_bytes(value); put(root,name,raw)
            source=ProjectSource(root); original=source.read_normative; calls=[]
            def changed(path, **kwargs):
                data=original(path, **kwargs); calls.append(path)
                if len(calls)==1: put(root,name,raw+b" ")
                return data
            with patch.object(source, "read_normative", side_effect=changed):
                with self.assertRaises(ModelError) as caught: read_source_relations(source,name)
            self.assertEqual(caught.exception.reason, "relation_source_changed")
            self.assertEqual((root/name).read_bytes(),raw+b" ")

    def test_foreign_path_and_symbolic_link_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); configuration_file(root); value=artifact(relations=[edge()])
            name=artifact_identity(value).path; path=put(root,name,artifact_bytes(value))
            source=ProjectSource(root)
            with self.assertRaises((ModelError,SafetyViolation)): read_source_relations(source,"../secret")
            path.unlink(); path.symlink_to(root/"specroad.json")
            with self.assertRaises((ModelError,SafetyViolation)): read_source_relations(source,name)

    def test_reader_rejects_path_identity_mismatch_and_stale_configuration(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); configuration_file(root); value=artifact(relations=[edge()])
            name=artifact_identity(artifact(number=2)).path; put(root,name,artifact_bytes(value));source=ProjectSource(root)
            with self.assertRaises(ModelError): read_source_relations(source,name)
            configuration_file(root,project_name="changed")
            with self.assertRaises((ModelError,SafetyViolation)): read_source_relations(source,name)

    def test_portable_distribution_can_load_relations_without_dependencies(self):
        with tempfile.TemporaryDirectory() as folder:
            output=Path(folder)/"dist";build_distribution(output)
            shifted=Path(folder)/"relocated";output.rename(shifted)
            # A portable Core source is imported with site-packages disabled.
            code="import sys,json;sys.path.insert(0,sys.argv[1]);from specroad.graph.relations import SourceRelations;r=SourceRelations(bytes.fromhex(sys.argv[2]));print(json.dumps(r.relations[0].data))"
            value=artifact(relations=[edge()]);raw=artifact_bytes(value)
            module=next(p for p in shifted.rglob("__init__.py") if p.parent.name=="specroad").parent.parent
            for path in (module, next(shifted.rglob("*.pyz"))):
                run=subprocess.run([sys.executable,"-I","-S","-B","-c",code,str(path),raw.hex()],stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False)
                self.assertEqual(run.returncode,0,run.stderr)
                self.assertEqual(json.loads(run.stdout),edge())
