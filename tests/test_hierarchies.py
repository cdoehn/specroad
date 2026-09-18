"""Per-type hierarchy and document composition contracts; no rendering tests."""
import unittest
from unittest.mock import patch

from specroad.graph.references import validate_relation_references
from specroad.graph.hierarchies import (HIERARCHY_RELATION_TYPES, validate_hierarchies,
                                      ordered_children, contains_position_key)
from specroad.model.errors import ModelError
from support.relations import aid, artifact, edge, rid
from test_relation_views import records


def hierarchy(kind="refines", pairs=((1,2),(2,3)), *, isolated=()):
    artifact_kind = {"part_of":"component", "contains":"section"}.get(kind,"requirement")
    values={number:artifact(artifact_kind,number) for pair in pairs for number in pair}
    for number in isolated: values[number]=artifact(artifact_kind,number)
    for number,(source,target) in enumerate(pairs,1):
        values[source]["relations"].append(edge(kind,aid(artifact_kind,target),number))
    return records(*[values[number] for number in sorted(values)])


def document_fixture(positions):
    doc=artifact("document",1)
    targets={}
    for number,(target,position) in enumerate(positions,1):
        targets[target]=artifact("section",target)
        doc["relations"].append(edge("contains",aid("section",target),number,position=position))
    return records(doc,*targets.values())


class HierarchyWorkTests(unittest.TestCase):
    def test_empty_input_is_acyclic(self):
        result=validate_hierarchies(validate_relation_references([]))
        self.assertEqual(result.source_count,0);self.assertEqual(result.relation_count,0)

    def test_isolated_sources_are_accepted(self):
        result=validate_hierarchies(validate_relation_references(hierarchy(pairs=(),isolated=(1,2))))
        self.assertEqual(result.source_count,2)

    def test_each_protected_hierarchy_accepts_a_chain(self):
        for kind in HIERARCHY_RELATION_TYPES:
            with self.subTest(kind=kind):
                result=validate_hierarchies(validate_relation_references(hierarchy(kind)))
                self.assertEqual(result.relation_count,2)

    def test_each_protected_hierarchy_rejects_two_node_cycle(self):
        for kind in HIERARCHY_RELATION_TYPES:
            with self.subTest(kind=kind),self.assertRaises(ModelError) as caught:
                validate_hierarchies(validate_relation_references(hierarchy(kind,((1,2),(2,1)))))
            self.assertEqual(caught.exception.reason,"relation_hierarchy_cycle")

    def test_three_node_cycle_is_rejected(self):
        with self.assertRaises(ModelError):
            validate_hierarchies(validate_relation_references(hierarchy(pairs=((1,2),(2,3),(3,1)))))

    def test_diamond_is_not_a_directed_cycle(self):
        result=validate_hierarchies(validate_relation_references(hierarchy(pairs=((1,2),(1,3),(2,4),(3,4)))))
        self.assertEqual(result.relation_count,4)

    def test_multiple_relations_to_same_target_do_not_fake_cycle(self):
        result=validate_hierarchies(validate_relation_references(hierarchy(pairs=((1,2),(1,2)))))
        self.assertEqual(result.relation_count,2)

    def test_dependency_cycle_is_not_subject_to_hierarchy_prohibition(self):
        result=validate_hierarchies(validate_relation_references(hierarchy("depends_on",((1,2),(2,1)))))
        self.assertEqual(result.relation_count,2)

    def test_different_hierarchy_types_are_not_union_checked(self):
        a=artifact(relations=[edge("refines",aid(number=2),1)])
        b=artifact(number=2,relations=[edge("supersedes",aid(),2)])
        result=validate_hierarchies(validate_relation_references(records(a,b)))
        self.assertEqual(result.relation_count,2)

    def test_self_relation_rejected_before_traversal(self):
        for kind in ("refines","supersedes","depends_on"):
            with self.subTest(kind=kind),self.assertRaises(ModelError) as caught:
                validate_hierarchies(validate_relation_references(hierarchy(kind,((1,1),))))
            self.assertEqual(caught.exception.reason,"self_relation_forbidden")

    def test_missing_target_is_not_ignored_as_a_leaf(self):
        with self.assertRaises(ModelError) as caught:
            validate_hierarchies(validate_relation_references(records(artifact(relations=[edge()]))))
        self.assertEqual(caught.exception.reason,"missing_relation_target")

    def test_hierarchy_validation_changes_no_original_records(self):
        values=hierarchy();before=[v.source_bytes for v in values]
        validate_hierarchies(validate_relation_references(values))
        self.assertEqual([v.source_bytes for v in values],before)

    def test_position_zero_is_valid(self):
        refs=validate_relation_references(document_fixture([(1,0)]))
        child=ordered_children(refs,aid("document"))[0]
        self.assertEqual(contains_position_key(child),(0,aid("section"),rid()))

    def test_children_sort_by_numeric_position_not_relation_array(self):
        refs=validate_relation_references(document_fixture([(1,10),(2,2),(3,0)]))
        self.assertEqual([e.target.id for e in ordered_children(refs,aid("document"))],
                         [aid("section",3),aid("section",2),aid("section",1)])

    def test_equal_positions_sort_by_target_id(self):
        refs=validate_relation_references(document_fixture([(3,0),(1,0),(2,0)]))
        self.assertEqual([e.target.id for e in ordered_children(refs,aid("document"))],
                         [aid("section",1),aid("section",2),aid("section",3)])

    def test_equal_target_and_position_sort_by_relation_id(self):
        values=document_fixture([(1,0),(1,0)]);doc=values[0].data;doc["relations"].reverse()
        refs=validate_relation_references(records(doc,values[1].data))
        self.assertEqual([e.relation.identity.id for e in ordered_children(refs,aid("document"))],[rid(1),rid(2)])

    def test_section_children_include_content_blocks(self):
        section=artifact("section",relations=[edge("contains",aid("content_block"),1)])
        refs=validate_relation_references(records(section,artifact("content_block")))
        self.assertEqual(ordered_children(refs,aid("section"))[0].target.artifact_type,"content_block")

    def test_non_contains_edges_are_not_document_children(self):
        first=artifact("document",relations=[edge("supersedes",aid("document",2),1)])
        refs=validate_relation_references(records(first,artifact("document",2)))
        self.assertEqual(ordered_children(refs,aid("document")),())

    def test_empty_document_has_no_children(self):
        refs=validate_relation_references(records(artifact("document")))
        self.assertEqual(ordered_children(refs,aid("document")),())

    def test_wrong_parent_kind_and_unknown_parent_fail(self):
        refs=validate_relation_references(records(artifact()))
        for name in (aid(),aid("document"),None,[],1):
            with self.subTest(name=repr(name)),self.assertRaises(ModelError):ordered_children(refs,name)

    def test_operations_require_resolved_inputs(self):
        for value in (None,[],{},"graph"):
            with self.subTest(value=repr(value)):
                with self.assertRaises(ModelError):validate_hierarchies(value)
                with self.assertRaises(ModelError):ordered_children(value,aid("document"))
                with self.assertRaises(ModelError):contains_position_key(value)

    def test_no_files_or_processes_used_in_hierarchy_or_order_operations(self):
        refs=validate_relation_references(document_fixture([(1,0)]))
        with patch("builtins.open",side_effect=AssertionError("file")),patch("subprocess.run",side_effect=AssertionError("process")):
            result=validate_hierarchies(refs);children=ordered_children(refs,aid("document"))
        self.assertEqual(result.validation_scope,"hierarchies_only");self.assertEqual(len(children),1)
