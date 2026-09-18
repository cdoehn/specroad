"""Cycle witnesses, deep graphs, deterministic ordering and invalid positions."""
from dataclasses import FrozenInstanceError
from pathlib import Path
import tempfile
import unittest

from specroad.graph.hierarchies import (HierarchyCycleError, HIERARCHY_RELATION_TYPES,
                                       validate_hierarchies, ordered_children, contains_position_key)
from specroad.graph.references import validate_relation_references
from specroad.graph.relations import Relation
from specroad.model.errors import ModelError
from specroad.model.identity_values import artifact_identity
from support.relations import aid, artifact, edge, rid
from support.portable import build_distribution
from support.processes import run_python
from test_relation_views import records
from test_hierarchies import hierarchy, document_fixture


def cycle_error(refs):
    try:
        validate_hierarchies(refs)
    except HierarchyCycleError as error:
        return error
    raise AssertionError("Expected a real hierarchy cycle")


class HierarchyRightTests(unittest.TestCase):
    def test_witness_is_a_closed_path_of_existing_edges(self):
        refs=validate_relation_references(hierarchy(pairs=((1,2),(2,3),(3,1))))
        error=cycle_error(refs)
        self.assertEqual(error.artifact_ids,(aid(number=1),aid(number=2),aid(number=3),aid(number=1)))
        self.assertEqual(error.relation_ids,(rid(1),rid(2),rid(3)))
        self.assertEqual(error.relation_type,"refines")

    def test_cycle_witness_is_deterministic_under_source_and_relation_reordering(self):
        values=hierarchy(pairs=((1,2),(1,3),(2,4),(4,2),(3,1)))
        first=cycle_error(validate_relation_references(values)).diagnostic()
        changed=[]
        for record in reversed(values):
            value=record.data;value['relations'].reverse();changed.append(value)
        second=cycle_error(validate_relation_references(records(*changed))).diagnostic()
        self.assertEqual(first,second)

    def test_disconnected_cycle_is_not_hidden_by_valid_component(self):
        error=cycle_error(validate_relation_references(hierarchy(pairs=((1,2),(3,4),(4,3)),isolated=(8,))))
        self.assertEqual(set(error.artifact_ids),{aid(number=3),aid(number=4)})

    def test_inserting_then_removing_cycle_rechecks_current_data(self):
        validate_hierarchies(validate_relation_references(hierarchy()))
        cycle_error(validate_relation_references(hierarchy(pairs=((1,2),(2,3),(3,1)))))
        result=validate_hierarchies(validate_relation_references(hierarchy()))
        self.assertEqual(result.relation_count,2)

    def test_witness_rotation_preserves_directed_orientation(self):
        error=cycle_error(validate_relation_references(hierarchy(pairs=((1,5),(5,3),(3,4),(4,5)))))
        self.assertEqual(error.artifact_ids,(aid(number=3),aid(number=4),aid(number=5),aid(number=3)))
        self.assertEqual(error.relation_ids,(rid(3),rid(4),rid(2)))

    def test_multiple_cycle_types_choose_stable_type_order(self):
        a=artifact(relations=[edge('supersedes',aid(number=2),3),edge('refines',aid(number=2),1)])
        b=artifact(number=2,relations=[edge('supersedes',aid(),4),edge('refines',aid(),2)])
        error=cycle_error(validate_relation_references(records(a,b)))
        self.assertEqual(error.relation_type,'refines')

    def test_all_three_node_digraphs_match_independent_reachability_oracle(self):
        possible=[(s,t) for s in (1,2,3) for t in (1,2,3) if s!=t]
        for kind in HIERARCHY_RELATION_TYPES:
            for mask in range(1<<len(possible)):
                pairs=[pair for bit,pair in enumerate(possible) if mask & (1<<bit)]
                reachable={(s,t) for s,t in pairs}
                for middle in (1,2,3):
                    for source in (1,2,3):
                        for target in (1,2,3):
                            if (source,middle) in reachable and (middle,target) in reachable:reachable.add((source,target))
                expected=any((n,n) in reachable for n in (1,2,3))
                refs=validate_relation_references(hierarchy(kind,pairs,isolated=tuple(n for n in (1,2,3) if all(n not in p for p in pairs))))
                with self.subTest(kind=kind,mask=mask):
                    if expected:
                        error=cycle_error(refs)
                        lookup={e.relation.identity.id:(e.source.id,e.target.id) for e in refs.relations}
                        self.assertEqual(len(error.artifact_ids),len(error.relation_ids)+1)
                        for i,rel_id in enumerate(error.relation_ids):
                            self.assertEqual(lookup[rel_id],error.artifact_ids[i:i+2])
                    else:validate_hierarchies(refs)

    def test_deep_acyclic_hierarchy_does_not_require_recursive_stack(self):
        count=1250
        result=validate_hierarchies(validate_relation_references(hierarchy(pairs=tuple((n,n+1) for n in range(1,count)))))
        self.assertEqual(result.source_count,count)

    def test_deep_cycle_detected_without_recursion_limit_failure(self):
        count=1200;pairs=tuple((n,n+1) for n in range(1,count))+((count,1),)
        error=cycle_error(validate_relation_references(hierarchy(pairs=pairs)))
        self.assertEqual(len(error.relation_ids),count)
        self.assertEqual(error.artifact_ids[0],error.artifact_ids[-1])

    def test_cycle_error_contains_no_private_artifact_text(self):
        values=hierarchy(pairs=((1,2),(2,1)))
        changed=[dict(v.data,title='private source text never report') for v in values]
        error=cycle_error(validate_relation_references(records(*changed)))
        self.assertNotIn('private source text',str(error.diagnostic()))
        self.assertEqual(error.diagnostic()['reason'],'relation_hierarchy_cycle')

    def test_failure_leaves_original_bytes_and_ids_untouched(self):
        values=hierarchy('contains',((1,2),(2,1)))
        original=[v.source_bytes for v in values];cycle_error(validate_relation_references(values))
        self.assertEqual([v.source_bytes for v in values],original)

    def test_position_rejects_negative_boolean_fractional_and_string_values(self):
        for position in (-1,False,True,1.25,'0',None,[],{}):
            with self.subTest(position=repr(position)),self.assertRaises(ModelError):
                Relation(artifact_identity(artifact('section')),edge('contains',aid('section',2),position=position))

    def test_nonfinite_position_rejected_without_sorting(self):
        for position in (float('inf'),float('-inf'),float('nan')):
            with self.subTest(position=repr(position)),self.assertRaises(ModelError):
                Relation(artifact_identity(artifact('section')),edge('contains',aid('section',2),position=position))

    def test_contains_requires_an_explicit_position(self):
        value=edge('contains',aid('section',2));del value['position']
        with self.assertRaises(ModelError):Relation(artifact_identity(artifact('section')),value)

    def test_large_and_integer_valued_float_positions_keep_numeric_order(self):
        refs=validate_relation_references(document_fixture([(1,2**40),(2,2.0),(3,0.0)]))
        self.assertEqual([e.target.id for e in ordered_children(refs,aid('document'))],[aid('section',3),aid('section',2),aid('section',1)])

    def test_non_contains_position_key_is_rejected(self):
        refs=validate_relation_references(hierarchy())
        with self.assertRaises(ModelError):contains_position_key(refs.relations[0])

    def test_position_changes_never_change_relation_identity(self):
        before=document_fixture([(1,0)])[0].data;after=document_fixture([(1,20)])[0].data
        self.assertEqual(before['relations'][0]['relation_id'],after['relations'][0]['relation_id'])
        refs=validate_relation_references(records(after,artifact('section')))
        child=ordered_children(refs,aid('document'))[0]
        self.assertEqual(contains_position_key(child),(20,aid('section'),rid()))

    def test_ordering_ignores_display_labels(self):
        values=document_fixture([(2,0),(1,0)])
        changed=[dict(v.data,display_id='AAA' if v.identity.id==aid('section',2) else 'ZZZ') for v in values]
        result=ordered_children(validate_relation_references(records(*changed)),aid('document'))
        self.assertEqual([v.target.id for v in result],[aid('section'),aid('section',2)])

    def test_sorting_is_stable_when_both_input_orders_are_reversed(self):
        values=document_fixture([(3,1),(1,0),(2,0)])
        first=ordered_children(validate_relation_references(values),aid('document'))
        changed=[]
        for v in reversed(values):
            data=v.data;data['relations'].reverse();changed.append(data)
        second=ordered_children(validate_relation_references(records(*changed)),aid('document'))
        self.assertEqual(first,second)

    def test_ownership_and_full_document_approval_not_inferred(self):
        a=artifact('document',1,relations=[edge('contains',aid('section'),1)])
        b=artifact('document',2,relations=[edge('contains',aid('section'),2)])
        refs=validate_relation_references(records(a,b,artifact('section')))
        result=validate_hierarchies(refs)
        self.assertEqual(result.validation_scope,'hierarchies_only')
        self.assertEqual(len(ordered_children(refs,aid('document',1))),1)
        self.assertEqual(len(ordered_children(refs,aid('document',2))),1)

    def test_success_result_is_immutable(self):
        result=validate_hierarchies(validate_relation_references(hierarchy()))
        with self.assertRaises(FrozenInstanceError):result.relation_count=0

    def test_invalid_cycle_witness_cannot_be_a_report(self):
        refs=validate_relation_references(hierarchy())
        for kind,values in [('refines',refs.relations),('depends_on',refs.relations),('refines',()),('refines',(None,None))]:
            with self.subTest(kind=kind,count=len(values)),self.assertRaises(ModelError):HierarchyCycleError(kind,values)

    def test_repeated_parallel_edges_still_find_the_real_return_edge(self):
        error=cycle_error(validate_relation_references(hierarchy(pairs=((1,2),(1,2),(2,1)))))
        self.assertEqual(error.relation_ids,(rid(1),rid(3)))

    def test_moved_portable_build_detects_cycle_and_orders_positions(self):
        cyclic=[v.source_bytes for v in hierarchy(pairs=((1,2),(2,1)))]
        documents=[v.source_bytes for v in document_fixture([(1,4),(2,0)])]
        body=("from specroad.graph.relations import SourceRelations\n"
              "from specroad.graph.references import validate_relation_references as resolve\n"
              "from specroad.graph.hierarchies import validate_hierarchies,HierarchyCycleError,ordered_children\n"
              "try: validate_hierarchies(resolve([SourceRelations(x) for x in "+repr(cyclic)+"]))\n"
              "except HierarchyCycleError as e: assert len(e.relation_ids)==2\n"
              "else: raise AssertionError('missing cycle')\n"
              "d=resolve([SourceRelations(x) for x in "+repr(documents)+"])\n"
              "assert ordered_children(d,"+repr(aid('document'))+")[0].target.id=="+repr(aid('section',2))+"\n")
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);out=root/'build';build_distribution(out);moved=root/'moved';out.rename(moved)
            for source in (moved/'module',moved/'specroad.pyz'):
                code='import sys;sys.path.insert(0,'+repr(str(source))+');\n'+body
                result=run_python(['-I','-S','-B','-c',code],root)
                self.assertEqual(result.returncode,0,result.stderr.decode())
