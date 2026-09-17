"""Typed relations and exact ID resolution; no output/doco assertions."""

import unittest
from dataclasses import FrozenInstanceError
from copy import deepcopy
from unittest.mock import patch

from specroad.graph.relations import SourceRelations
from specroad.graph.references import validate_relation_references, ResolvedRelation
from specroad.graph.relation_matrix import relation_pair_allowed, relation_rules
from specroad.model.errors import ModelError
from specroad.model.identity_values import artifact_identity
from support.artifacts import artifact_bytes
from support.relations import aid, artifact, edge


def record(value):
    return SourceRelations(artifact_bytes(value))


def linked(kind, source_type, target_type):
    target = artifact(target_type, number=2)
    source = artifact(source_type, relations=[edge(kind, target["id"])])
    return [record(source), record(target)]


class RelationReferenceWorkTests(unittest.TestCase):
    def test_requirement_refinement_points_from_detail_to_general(self):
        sources = linked("refines", "requirement", "requirement")
        result = validate_relation_references(sources)
        self.assertEqual(len(result.relations), 1)
        self.assertEqual(result.relations[0].source, sources[0].identity)
        self.assertEqual(result.relations[0].target, sources[1].identity)
        self.assertEqual(result.relations[0].relation.type, "refines")

    def test_requirement_dependency_is_not_refinement(self):
        result = validate_relation_references(linked("depends_on", "requirement", "requirement"))
        self.assertEqual(result.relations[0].relation.type, "depends_on")
        self.assertEqual(result.validation_scope, "relation_references_only")

    def test_one_accepted_pair_for_each_core_relation(self):
        cases = [("addresses","need","goal"), ("refines","requirement","need"),
                 ("derived_from","component","source"), ("depends_on","task","requirement"),
                 ("conflicts_with","evidence","goal"), ("constrains","decision","interface"),
                 ("allocated_to","requirement","component"), ("implemented_by","decision","code_ref"),
                 ("verified_by","task","test"), ("produces","test","evidence"),
                 ("mitigates","task","risk"), ("scheduled_for","task","milestone"),
                 ("part_of","milestone","release"), ("supersedes","evidence","evidence"),
                 ("duplicates","configuration","configuration"), ("contains","document","section"),
                 ("references","view","proposal")]
        for relation_type, source, target in cases:
            with self.subTest(kind=relation_type):
                result = validate_relation_references(linked(relation_type,source,target))
                self.assertEqual(result.relations[0].source.artifact_type,source)
                self.assertEqual(result.relations[0].target.artifact_type,target)

    def test_unlisted_pair_is_rejected_not_coerced(self):
        for relation_type,source,target in (("addresses","goal","need"), ("part_of","requirement","requirement"),
              ("contains","document","requirement"), ("references","requirement","goal"),
              ("derived_from","evidence","source"), ("verified_by","requirement","evidence")):
            with self.subTest(kind=relation_type,source=source,target=target), self.assertRaises(ModelError) as caught:
                validate_relation_references(linked(relation_type,source,target))
            self.assertEqual(caught.exception.reason,"relation_type_pair_forbidden")

    def test_self_links_rejected(self):
        for relation_type,kind in (("refines","requirement"),("depends_on","task"),("duplicates","goal"),
                                   ("supersedes","goal"),("conflicts_with","risk"),("contains","section")):
            value=artifact(kind,relations=[edge(relation_type,aid(kind))])
            with self.subTest(kind=relation_type), self.assertRaises(ModelError) as caught:
                validate_relation_references([record(value)])
            self.assertEqual(caught.exception.reason,"self_relation_forbidden")

    def test_absent_target_fails_closed(self):
        source = record(artifact(relations=[edge()]))
        with self.assertRaises(ModelError) as caught: validate_relation_references([source])
        self.assertEqual(caught.exception.reason,"missing_relation_target")

    def test_missing_non_owning_reference_is_still_an_error(self):
        source=record(artifact("view",relations=[edge("references",aid("goal"))]))
        with self.assertRaises(ModelError) as caught: validate_relation_references([source])
        self.assertEqual(caught.exception.reason,"missing_relation_target")

    def test_display_name_does_not_resolve_a_missing_target(self):
        source=record(artifact(relations=[edge(target="SR-REQ-0010")]))
        impostor=record(artifact(number=2, display_id="SR-REQ-0010"))
        with self.assertRaises(ModelError): validate_relation_references([source,impostor])

    def test_same_display_labels_do_not_mix_target_identities(self):
        sources=linked("depends_on","requirement","requirement")
        values=[dict(source.data,display_id="SAME") for source in sources]
        result=validate_relation_references([record(value) for value in values])
        self.assertEqual(result.relations[0].target.id,aid(number=2))

    def test_duplicate_artifact_id_is_an_error_even_for_equal_bytes(self):
        item=record(artifact())
        with self.assertRaises(ModelError) as caught: validate_relation_references([item,item])
        self.assertEqual(caught.exception.reason,"duplicate_artifact_id")

    def test_duplicate_relation_id_across_sources_rejected(self):
        a=record(artifact(number=1,relations=[edge(target=aid(number=3))]))
        b=record(artifact(number=2,relations=[edge(target=aid(number=3))]))
        with self.assertRaises(ModelError) as caught: validate_relation_references([a,b,record(artifact(number=3))])
        self.assertEqual(caught.exception.reason,"duplicate_relation_id")

    def test_mixed_project_prefixes_rejected(self):
        with self.assertRaises(ModelError) as caught:
            validate_relation_references([record(artifact()),record(artifact(project="ZZ"))])
        self.assertEqual(caught.exception.reason,"mixed_project_prefix")

    def test_order_changes_do_not_change_resolved_keys(self):
        source=record(artifact(relations=[edge(number=2),edge(number=1)]));target=record(artifact(number=2))
        a=validate_relation_references([source,target])
        changed=source.data;changed["relations"].reverse()
        b=validate_relation_references([target,record(changed)])
        self.assertEqual(a.sources,b.sources)
        self.assertEqual([r.relation.key for r in a.relations],[r.relation.key for r in b.relations])

    def test_empty_explicit_model_has_no_relations(self):
        result=validate_relation_references([])
        self.assertEqual(result.sources,());self.assertEqual(result.relations,())
        self.assertEqual(result.validation_scope,"relation_references_only")

    def test_result_is_immutable_and_does_not_expose_input_collections(self):
        sources=linked("refines","requirement","requirement");result=validate_relation_references(sources)
        sources.clear();result.relations[0].relation.data["extensions"].update({"a.b":1})
        self.assertEqual(len(result.sources),2);self.assertEqual(result.relations[0].relation.data["extensions"],{})
        with self.assertRaises(FrozenInstanceError): result.relations=()

    def test_wrong_input_types_fail_with_model_errors(self):
        for values in (None, "source", {}, [artifact()], [None], [artifact_identity(artifact())]):
            with self.subTest(values=repr(values)), self.assertRaises(ModelError): validate_relation_references(values)

    def test_query_rejects_unknown_type_not_wildcard(self):
        for args in (("unknown","goal","goal"),("superseded_by","goal","goal"),
                     ("duplicates","unknown","goal"),("conflicts_with","goal","unknown")):
            with self.subTest(args=repr(args)), self.assertRaises(ModelError): relation_pair_allowed(*args)

    def test_rules_cannot_be_mutated(self):
        rules=relation_rules("refines")
        self.assertEqual(len(rules),4)
        with self.assertRaises(FrozenInstanceError):rules[0].sources=frozenset()
        with self.assertRaises(AttributeError):rules[0].targets.add("source")

    def test_resolved_relation_rejects_forged_endpoint(self):
        sources=linked("refines","requirement","requirement");rel=sources[0].relations[0]
        with self.assertRaises(ModelError):ResolvedRelation(rel,sources[0].identity,artifact_identity(artifact(number=3)))

    def test_no_target_resolution_uses_files_or_processes(self):
        sources=linked("refines","requirement","need")
        with patch("builtins.open",side_effect=AssertionError("file opened")),patch("subprocess.run",side_effect=AssertionError("process started")):
            result=validate_relation_references(sources)
        self.assertEqual(len(result.relations),1)

    def test_same_type_requirement_for_supersedes_and_duplicates(self):
        for kind in ("supersedes","duplicates"):
            self.assertTrue(relation_pair_allowed(kind,"goal","goal"))
            self.assertFalse(relation_pair_allowed(kind,"goal","need"))
            with self.subTest(kind=kind), self.assertRaises(ModelError):validate_relation_references(linked(kind,"goal","need"))
