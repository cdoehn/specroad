"""Cycle, inverse, completeness, stable BFS and nested-context regressions."""
import copy
import itertools
import json
import os
from pathlib import Path
import tempfile
from concurrent.futures import ThreadPoolExecutor
import unittest
from unittest.mock import patch
from specroad.srx import (LoadedGraph, EvaluationContext, SrxProgram, SrxError, evaluate)
from specroad.srx import fields
from specroad.graph.relations import SourceRelations
from support.srx import roots, literal, binary, field, expression_document, quantifier
from support.srx_graph import (artifact, edge, aid, records, graph, call, count, incoming, has, reach, chain)
from support.artifacts import artifact_bytes
from support.portable import build_distribution
from support.processes import run_python


class SrxGraphRightTests(unittest.TestCase):
    def test_cycle_with_no_match_terminates(self):
        values = chain(); values[2]['relations'] = [edge('depends_on', aid(number=1), number=3)]
        self.assertIs(call(reach(aid(number=4), depth=100000), values), False)

    def test_cycle_does_not_visit_a_node_twice(self):
        values = chain(); values[2]['relations'] = [edge('depends_on', aid(number=1), number=3)]
        seen = []; original = fields.resolve_tokens
        def probe(value, tokens, **kwargs):
            if tokens == ('id',): seen.append(value['id'])
            return original(value, tokens, **kwargs)
        with patch.object(fields, 'resolve_tokens', side_effect=probe):
            self.assertIs(call(reach(aid(number=9), depth=100), values), False)
        self.assertEqual(seen, [aid(number=n) for n in (1,2,3)])

    def test_diamond_uses_shortest_depth(self):
        values = [artifact(number=1, relations=[edge('depends_on', aid(number=2), number=1),
                                              edge('depends_on', aid(number=4), number=2)]),
                  artifact(number=2, relations=[edge('depends_on', aid(number=3), number=3)]),
                  artifact(number=3, relations=[edge('depends_on', aid(number=5), number=4)]),
                  artifact(number=4, relations=[edge('depends_on', aid(number=5), number=5)]),
                  artifact(number=5)]
        self.assertIs(call(reach(aid(number=5), depth=2), values), True)

    def test_bfs_visits_whole_level_before_next_level(self):
        values = chain(); values[0]['relations'].append(edge('depends_on', aid(number=4), number=4))
        values.append(artifact(number=4)); seen=[]; original=fields.resolve_tokens
        def probe(value,tokens,**kwargs):
            if tokens == ('id',): seen.append(value['id'])
            return original(value,tokens,**kwargs)
        with patch.object(fields,'resolve_tokens',side_effect=probe):
            self.assertIs(call(reach(aid(number=9),depth=3),values),False)
        self.assertEqual(seen,[aid(number=n) for n in (1,2,4,3)])

    def test_neighbours_sorted_by_type_then_target_id(self):
        values = [artifact(number=1, relations=[edge('refines',aid(number=2),number=1),
                  edge('depends_on',aid(number=4),number=2),edge('depends_on',aid(number=3),number=3)])]
        values += [artifact(number=n) for n in (2,3,4)]
        seen=[]; original=fields.resolve_tokens
        def probe(value,tokens,**kwargs):
            if tokens == ('id',): seen.append(value['id'])
            return original(value,tokens,**kwargs)
        with patch.object(fields,'resolve_tokens',side_effect=probe):
            self.assertIs(call(reach(aid(number=9),depth=1),values),False)
        self.assertEqual(seen,[aid(number=n) for n in (1,3,4,2)])

    def test_source_and_edge_permutation_does_not_change_result(self):
        values=chain();values[0]['relations'].append(edge('refines',aid(number=3),number=3))
        for order in itertools.permutations(values):
            self.assertIs(call(reach(aid(number=3),depth=2),list(order),list(order).index(values[0])),True)

    def test_duplicate_edges_to_same_target_count_separately(self):
        values=chain();values[0]['relations'].append(edge('depends_on',aid(number=2),number=4))
        self.assertEqual(call(count(),values),2)
        self.assertEqual(call(incoming(),values,1),2)

    def test_multiple_edges_enqueue_target_only_once(self):
        values=chain();values[0]['relations'].append(edge('refines',aid(number=2),number=4))
        seen=[];original=fields.resolve_tokens
        def probe(value,tokens,**kwargs):
            if tokens == ('id',): seen.append(value['id'])
            return original(value,tokens,**kwargs)
        with patch.object(fields,'resolve_tokens',side_effect=probe):call(reach(aid(number=9),depth=2),values)
        self.assertEqual(seen,[aid(number=n) for n in (1,2,3)])

    def test_incoming_named_inverse_is_not_lost(self):
        values=[artifact(number=1,relations=[edge('supersedes',aid(number=2))]),artifact(number=2)]
        for kind in ('superseded_by','supersedes'):
            self.assertIs(call(reach(aid(number=1),direction='incoming',types=[kind]),values,1),True)
        self.assertEqual(call(incoming(['superseded_by','supersedes']),values,1),1)
        self.assertEqual(call(count(['superseded_by']),values),0)

    def test_symmetric_inverse_retains_single_relation(self):
        for kind in ('conflicts_with','duplicates'):
            values=[artifact(number=1,relations=[edge(kind,aid(number=2))]),artifact(number=2)]
            self.assertIs(call(reach(aid(number=1),direction='incoming',types=[kind]),values,1),True)
            self.assertEqual(call(count([kind],direction='both'),values,1),1)

    def test_opposite_duplicate_symmetric_storage_is_invalid(self):
        values=[artifact(number=1,relations=[edge('conflicts_with',aid(number=2))]),
                artifact(number=2,relations=[edge('conflicts_with',aid(number=1),number=2)])]
        with self.assertRaises(SrxError):graph(values)

    def test_stored_inverse_type_is_not_accepted(self):
        value=artifact(number=1,relations=[edge('superseded_by',aid(number=2))])
        # SourceRelations rejects this before it can become a graph input.
        from specroad.model.errors import ModelError
        with self.assertRaises(ModelError):records([value,artifact(number=2)])

    def test_full_loaded_incoming_set_exceeds_display_limit(self):
        values=[artifact(number=1)] + [artifact(number=n,relations=[edge('depends_on',aid(number=1),number=n)])
                                      for n in range(2,153)]
        self.assertEqual(call(incoming(),values),151)

    def test_readonly_empty_relations_root_cannot_truncate_real_index(self):
        values=chain()
        self.assertEqual(call(incoming(),values,1,extra_roots={'relations':{'incoming':[],'complete':True}}),1)

    def test_duplicate_source_id_is_invalid(self):
        with self.assertRaises(SrxError) as error:graph([*chain(),chain()[0]])
        self.assertEqual(error.exception.actual,'duplicate_artifact_id')

    def test_duplicate_relation_id_is_invalid(self):
        values=chain();values[1]['relations'][0]['relation_id']=values[0]['relations'][0]['relation_id']
        with self.assertRaises(SrxError) as error:graph(values)
        self.assertEqual(error.exception.actual,'duplicate_relation_id')

    def test_loaded_model_and_context_cannot_mix_project_instances_by_prefix(self):
        values=chain();values.append(artifact(number=1,project='OTHER'))
        with self.assertRaises(SrxError):graph(values)

    def test_foreign_source_collection_is_not_iterated(self):
        calls=[]
        class Evil:
            def __iter__(self):calls.append('iter');return iter(())
        with self.assertRaises(SrxError):LoadedGraph(Evil(),rule_id='foreign')
        self.assertEqual(calls,[])

    def test_callback_is_not_an_evaluation_graph(self):
        calls=[]
        def fetch():calls.append('fetch');return graph(chain())
        with self.assertRaises(SrxError):EvaluationContext(roots(),rule_id='foreign',graph=fetch)
        self.assertEqual(calls,[])

    def test_source_subclasses_cannot_inject_loaders(self):
        calls=[]
        class Evil(SourceRelations):
            @property
            def source_bytes(self):calls.append('get');raise AssertionError()
        with self.assertRaises(SrxError):LoadedGraph([object.__new__(Evil)],rule_id='foreign')
        self.assertEqual(calls,[])

    def test_graph_data_as_json_literal_is_never_executed(self):
        node={'op':'has_relation','direction':'bad','types':'unknown'}
        self.assertEqual(call(literal(node),chain()),node)

    def test_first_predicate_error_stops_search(self):
        values=chain();values[0]['extensions']={'org.example':{'ok':False}}
        values[1]['extensions']={'org.example':{'ok':'invalid'}}
        values[2]['extensions']={'org.example':{'ok':True}}
        with self.assertRaises(SrxError) as error:call(reach(depth=2,where=field('/extensions/org.example/ok')),values)
        self.assertEqual(error.exception.expected,'boolean')

    def test_first_witness_finishes_before_unneeded_runtime_error(self):
        values=chain();values[0]['extensions']={'org.example':{'ok':True}}
        self.assertIs(call(reach(depth=100,where=field('/extensions/org.example/ok')),values),True)

    def test_beyond_depth_predicate_is_not_executed(self):
        values=chain();values[0]['extensions']={'org.example':{'ok':False}}
        self.assertIs(call(reach(depth=0,where=field('/extensions/org.example/ok')),values),False)

    def test_nested_reachable_starts_at_candidate_not_outer_root(self):
        inner=reach(aid(number=1),depth=0)
        node=reach(depth=2,where={'op':'and','args':[binary('eq',field('/id'),literal(aid(number=2))),inner]})
        self.assertIs(call(node,chain()),False)

    def test_nested_reachable_finds_incoming_target(self):
        inner=reach(aid(number=1),depth=1,direction='incoming')
        node=reach(depth=1,where={'op':'and','args':[binary('eq',field('/id'),literal(aid(number=2))),inner]})
        self.assertIs(call(node,chain()),True)

    def test_graph_operator_in_predicate_uses_candidate(self):
        node=reach(depth=1,where=binary('eq',incoming(),literal(1)))
        self.assertIs(call(node,chain()),True)

    def test_roots_restored_after_reachable_and_quantifier(self):
        node={'op':'and','args':[reach(aid(number=3),depth=2),
                binary('eq',field('/id'),literal(aid(number=1))),binary('eq',count(),literal(1))]}
        self.assertIs(call(node,chain()),True)
        node=quantifier('all',literal([aid(number=2),aid(number=3)]),{'op':'and','args':[
            reach(depth=2,where=binary('eq',field('/id'),field('','item'))),
            binary('eq',field('/id'),literal(aid(number=1)))]})
        self.assertIs(call(node,chain()),True)

    def test_nested_quantifier_inside_reachable_restores_candidate(self):
        pred={'op':'and','args':[quantifier('all',literal([True]),field('','item')),
                               binary('eq',field('/id'),literal(aid(number=2)))]}
        self.assertIs(call(reach(depth=1,where=pred),chain()),True)

    def test_deep_nested_graph_search_avoids_recursive_ast_calls(self):
        node=literal(True)
        for _ in range(1100):node=reach(depth=0,where=node)
        self.assertIs(call(node,[artifact()]),True)

    def test_long_chain_has_no_recursive_traversal(self):
        length=1200
        values=[artifact(number=n,relations=[edge('depends_on',aid(number=n+1),number=n)] if n<length else [])
                for n in range(1,length+1)]
        self.assertIs(call(reach(aid(number=length),depth=length-1),values),True)
        self.assertIs(call(reach(aid(number=length),depth=length-2),values),False)

    def test_exhaustive_three_node_models_against_independent_bounded_sets(self):
        pairs=[(a,b) for a in range(1,4) for b in range(1,4) if a!=b]
        programs={(direction,depth,target):SrxProgram(expression_document(reach(aid(number=target),depth=depth,direction=direction)),rule_id='oracle')
                  for direction in ('outgoing','incoming','both') for depth in range(4) for target in range(1,4)}
        for mask in range(64):
            edges=[pair for bit,pair in enumerate(pairs) if mask & (1<<bit)]
            values=[artifact(number=n,relations=[edge('depends_on',aid(number=b),number=k+1)
                        for k,(a,b) in enumerate(edges) if a==n]) for n in range(1,4)]
            loaded=graph(values)
            for start in range(1,4):
                context=EvaluationContext(roots(values[start-1]),rule_id='oracle',graph=loaded)
                for direction in ('outgoing','incoming','both'):
                    selected=set(edges if direction=='outgoing' else [(b,a) for a,b in edges] if direction=='incoming' else edges+[(b,a) for a,b in edges])
                    visited={start}
                    for depth in range(4):
                        for target in range(1,4):
                            self.assertIs(evaluate(programs[direction,depth,target],context),target in visited)
                        visited |= {b for a,b in selected if a in visited}

    def test_independent_threaded_evaluation(self):
        values=chain();loaded=graph(values)
        contexts=[EvaluationContext(roots(value),graph=loaded,rule_id='thread') for value in values]
        program=SrxProgram(expression_document(incoming()),rule_id='thread')
        with ThreadPoolExecutor(max_workers=3) as executor:
            results=list(executor.map(lambda n:evaluate(program,contexts[n]),[0,1,2]*10))
        self.assertEqual(results,[0,1,1]*10)

    def test_error_leaves_same_context_reusable(self):
        values=chain();context=EvaluationContext(roots(values[0]),graph=graph(values),rule_id='reuse')
        broken=SrxProgram(expression_document(reach(where=literal(None))),rule_id='reuse')
        valid=SrxProgram(expression_document(reach(aid(number=3),depth=2)),rule_id='reuse')
        diagnostics=[]
        for _ in range(2):
            with self.assertRaises(SrxError) as error:evaluate(broken,context)
            diagnostics.append(error.exception.diagnostic())
            self.assertIs(evaluate(valid,context),True)
        self.assertEqual(diagnostics[0],diagnostics[1])

    def test_graph_evaluation_does_not_open_files_or_read_environment(self):
        values=chain();context=EvaluationContext(roots(values[0]),graph=graph(values),rule_id='offline')
        program=SrxProgram(expression_document(reach(aid(number=3),depth=2)),rule_id='offline')
        with patch('builtins.open',side_effect=AssertionError('I/O')),patch.object(os,'getenv',side_effect=AssertionError('host')):
            self.assertIs(evaluate(program,context),True)

    def test_invalid_incoming_options_and_duplicate_types_fail(self):
        node=incoming();node['direction']='incoming'
        with self.assertRaises(SrxError):call(node,chain())
        with self.assertRaises(SrxError):call(count(['depends_on','depends_on']),chain())

    def test_unknown_predicate_operator_is_rejected_even_depth_zero(self):
        with self.assertRaises(SrxError):call(reach(depth=0,where={'op':'unknown'}),chain())

    def test_portable_module_and_zipapp_evaluate_loaded_graph(self):
        values=chain()
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);output=root/'build';build_distribution(output);moved=root/'moved';output.rename(moved)
            code='''
import json
from specroad.graph.relations import SourceRelations
from specroad.srx import LoadedGraph,EvaluationContext,SrxProgram,evaluate
values=json.loads(%r)
sources=[SourceRelations(json.dumps(x).encode()) for x in values]
g=LoadedGraph(sources,rule_id='portable')
c=EvaluationContext({'artifact':values[1],'configuration':None,'project':{},'relations':[]},graph=g,rule_id='portable')
p=SrxProgram({'language':'srx','version':'1.0','expression':{'op':'incoming_count','types':['depends_on']}},rule_id='portable')
assert evaluate(p,c)==1
''' % json.dumps(values)
            for source in (moved/'module',moved/'specroad.pyz'):
                prefix='import sys;sys.path.insert(0,'+repr(str(source))+');\n'
                result=run_python(['-I','-S','-B','-c',prefix+code],root)
                self.assertEqual(result.returncode,0,result.stderr.decode())
