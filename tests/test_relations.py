"""Relation data contracts, not textual output or documentation."""

import json
from copy import deepcopy
from dataclasses import FrozenInstanceError
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from specroad.graph.relations import Relation, SourceRelations
from specroad.graph.relation_types import CORE_RELATION_TYPES
from specroad.model.errors import ModelError
from specroad.model.identity_values import artifact_identity
from specroad.storage.relations import read_source_relations
from specroad.storage.project import ProjectSource
from support.artifacts import artifact_bytes
from support.model import configuration_file, put
from support.relations import aid, rid, edge, artifact, external


class RelationWorkTests(unittest.TestCase):
    def test_complete_relation_retains_external_identity_and_extensions(self):
        data = edge(external_identities=[external(external_revision="007")],
                    extensions={"vendor.a": {"opaque": [None, False, 0.25, "e\u0301", "東京", "\0"]}})
        source = SourceRelations(artifact_bytes(artifact(relations=[data])))
        self.assertEqual(source.relations[0].data, data)
        self.assertEqual(source.relations[0].source, source.identity)

    def test_every_stored_core_type_is_loadable_without_claiming_matrix_validity(self):
        expected = {"addresses", "refines", "derived_from", "depends_on", "conflicts_with", "constrains",
                    "allocated_to", "implemented_by", "verified_by", "produces", "mitigates",
                    "scheduled_for", "part_of", "supersedes", "duplicates", "contains", "references"}
        self.assertEqual(set(CORE_RELATION_TYPES), expected)
        for kind in sorted(expected):
            with self.subTest(kind=kind):
                value = SourceRelations(artifact_bytes(artifact(relations=[edge(kind)])))
                self.assertEqual(value.relations[0].type, kind)
                self.assertEqual(value.validation_scope, "relation_fields_only")

    def test_required_fields_are_not_filled_with_defaults(self):
        for key in ("relation_id", "id_scheme", "type", "target", "external_identities", "extensions"):
            data = edge(); data.pop(key)
            with self.subTest(key=key), self.assertRaises(ModelError):
                SourceRelations(artifact_bytes(artifact(relations=[data])))

    def test_no_missing_identity_allocation_or_clock_read(self):
        with patch("secrets.token_bytes", side_effect=AssertionError("entropy must not be read")):
            for data in (edge(), dict(edge(), id_scheme="derived128-v1")):
                self.assertEqual(SourceRelations(artifact_bytes(artifact(relations=[data]))).relations[0].data, data)

    def test_original_artifact_bytes_are_kept(self):
        value = artifact(relations=[edge()]); raw = json.dumps(value, indent=3, ensure_ascii=True).encode() + b"\n"
        source = SourceRelations(raw)
        self.assertEqual(source.source_bytes, raw)
        self.assertEqual(source.data, value)

    def test_relation_owns_input_and_returned_data(self):
        data = edge(extensions={"a.b": [1]}); identity = artifact_identity(artifact())
        value = Relation(identity, data); data["extensions"]["a.b"].append(2)
        exposed = value.data; exposed["extensions"]["a.b"].clear()
        self.assertEqual(value.data["extensions"], {"a.b": [1]})
        with self.assertRaises(FrozenInstanceError): value.source = identity

    def test_source_collection_owns_every_record(self):
        source = SourceRelations(artifact_bytes(artifact(relations=[edge()])))
        source.data["relations"].clear()
        self.assertEqual(len(source.relations), 1)
        with self.assertRaises(FrozenInstanceError): source.relations = ()

    def test_ids_do_not_depend_on_relation_order(self):
        data = [edge(number=8), edge(number=3)]
        first = SourceRelations(artifact_bytes(artifact(relations=data)))
        second = SourceRelations(artifact_bytes(artifact(relations=list(reversed(data)))))
        self.assertEqual({r.identity.id for r in first.relations}, {rid(8), rid(3)})
        self.assertEqual({r.key for r in first.relations}, {r.key for r in second.relations})

    def test_duplicate_relation_identity_rejected(self):
        with self.assertRaises(ModelError) as caught:
            SourceRelations(artifact_bytes(artifact(relations=[edge(), edge(target=aid(number=3))])))
        self.assertEqual(caught.exception.reason, "duplicate_relation_id")

    def test_inverse_or_unknown_types_cannot_be_stored(self):
        for kind in ("superseded_by", "parent_of", "REFINES", "", None, [], True):
            with self.subTest(kind=repr(kind)), self.assertRaises(ModelError):
                SourceRelations(artifact_bytes(artifact(relations=[edge(type=kind)])))

    def test_target_is_artifact_identity_not_path_url_or_display_id(self):
        for target in ("REQ-10", "https://example.invalid/id", "spec/requirements/a.json", "../secret",
                       "REL-" + "0" * 26, "sr-REQ-0001", None, True, {}):
            with self.subTest(target=repr(target)), self.assertRaises(ModelError):
                SourceRelations(artifact_bytes(artifact(relations=[edge(target=aid(), **{}) | {"target": target}])) )

    def test_legacy_target_identity_is_retained(self):
        value = SourceRelations(artifact_bytes(artifact(relations=[edge(target="SR-REQ-0010")])))
        self.assertEqual(value.relations[0].target, "SR-REQ-0010")

    def test_optional_rationale_and_audit_data_are_preserved(self):
        data = edge(rationale="理由", created_at="2026-01-01T00:00:00.123Z",
                    created_by={"actor_type": "tool", "actor_id": "fixture"})
        self.assertEqual(SourceRelations(artifact_bytes(artifact(relations=[data]))).relations[0].data, data)

    def test_empty_relations_are_valid(self):
        source = SourceRelations(artifact_bytes(artifact()))
        self.assertEqual(source.relations, ())

    def test_contains_position_zero_is_valid(self):
        source = SourceRelations(artifact_bytes(artifact("document", relations=[edge("contains", aid("section"))])))
        self.assertEqual(source.relations[0].data["position"], 0)

    def test_invalid_positions_are_rejected(self):
        for position in (None, -1, 1.5, True, "0"):
            with self.subTest(position=repr(position)), self.assertRaises(ModelError):
                Relation(artifact_identity(artifact()), edge("contains", position=position))
        with self.assertRaises(ModelError): Relation(artifact_identity(artifact()), edge(position=0))

    def test_bad_namespace_is_rejected(self):
        with self.assertRaises(ModelError): Relation(artifact_identity(artifact()), edge(extensions={"plain": 1}))

    def test_external_keys_are_required_and_case_sensitive(self):
        for name in ("source_system", "source_document", "external_id"):
            data = external(); data.pop(name)
            with self.subTest(name=name), self.assertRaises(ModelError):
                Relation(artifact_identity(artifact()), edge(external_identities=[data]))
        records = [external(external_id="A"), external(external_id="a")]
        self.assertEqual(Relation(artifact_identity(artifact()), edge(external_identities=records)).data["external_identities"], records)

    def test_duplicate_external_key_cannot_be_hidden_by_revision(self):
        with self.assertRaises(ModelError):
            Relation(artifact_identity(artifact()), edge(external_identities=[external(external_revision="1"), external(external_revision="2")]))

    def test_full_import_binding_is_retained_not_verified(self):
        record = external(mapping_id="reqif@1", last_imported_projection_sha256="1" * 64,
                          last_source_projection_sha256="2" * 64, last_source_payload_sha256="3" * 64,
                          imported_at="2026-01-01T00:00:00Z")
        result = Relation(artifact_identity(artifact()), edge(external_identities=[record]))
        self.assertEqual(result.data["external_identities"], [record])

    def test_partial_import_binding_rejected(self):
        with self.assertRaises(ModelError):
            Relation(artifact_identity(artifact()), edge(external_identities=[external(mapping_id="reqif@1")]))

    def test_cyclic_and_foreign_data_never_runs_conversion_hooks(self):
        class Foreign:
            def __str__(self): raise AssertionError("conversion hook")
        data = edge(extensions={"a.b": Foreign()})
        with self.assertRaises(ModelError): Relation(artifact_identity(artifact()), data)
        data = edge(); data["extensions"]["a.b"] = data
        with self.assertRaises(ModelError): Relation(artifact_identity(artifact()), data)

    def test_passive_paths_and_commands_do_not_read_files_or_execute(self):
        data = edge(external_identities=[external(source_document="file:///private/secret")],
                    extensions={"plugin.code": {"command": "touch sentinel", "$ref": "https://example.invalid/schema"}})
        with patch("builtins.open", side_effect=AssertionError("unexpected file")), patch("subprocess.run", side_effect=AssertionError("execution")):
            result = Relation(artifact_identity(artifact()), data)
        self.assertEqual(result.data, data)

    def test_unknown_top_level_fields_rejected(self):
        with self.assertRaises(ModelError): Relation(artifact_identity(artifact()), edge(source="other"))

    def test_reader_preserves_files_and_path_binding(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); configuration_file(root)
            value = artifact(relations=[edge()]); raw = artifact_bytes(value)
            name = artifact_identity(value).path; put(root, name, raw)
            before = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}
            result = read_source_relations(ProjectSource(root), name)
            self.assertEqual(result.source_bytes, raw)
            self.assertEqual(result.identity.id, value["id"])
            self.assertEqual(before, {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()})

    def test_reader_error_reports_path_and_relation_index(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); configuration_file(root)
            value = artifact(relations=[edge(type="superseded_by")]); name = artifact_identity(value).path
            put(root, name, artifact_bytes(value))
            with self.assertRaises(ModelError) as caught: read_source_relations(ProjectSource(root), name)
            self.assertEqual(caught.exception.path, name)
            self.assertEqual(caught.exception.pointer, "/relations/0/type")
