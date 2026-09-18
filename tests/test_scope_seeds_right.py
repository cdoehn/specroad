"""Boundary, ordering, fresh-source and portability behavior for scope seeds."""
from pathlib import Path
from unittest.mock import patch
import itertools
import tempfile
import unittest

from specroad.graph.scope_descriptors import ScopeDescriptor
from specroad.graph.scope_inputs import ScopeResource
from specroad.graph.scope_seeds import QuerySeedPage, resolve_scope_seeds
from specroad.model.canonical import canonical_json_sha256
from specroad.model.errors import ModelError
from specroad.model.paths import artifact_path
from specroad.storage.project import ProjectSource
from specroad.storage.scope_seeds import read_artifact_scope_seeds
from support.artifacts import artifact_bytes
from support.model import configuration_file, configuration_value, put
from support.relations import artifact, aid, edge
from support.scopes import descriptor, query, inputs
from support.portable import files_under


def wrap(base=None, **changes):
    return descriptor('configuration', {'base_scope_descriptor': descriptor() if base is None else base},
                      configuration_id=aid('configuration'), **changes)


def save(root, value):
    return put(root, artifact_path(value['artifact_type'], value['id'], 'SR'), artifact_bytes(value))


class ScopeRightTests(unittest.TestCase):
    def test_configuration_wrapper_contains_one_unbound_base(self):
        value=ScopeDescriptor(wrap());self.assertEqual(value.data['selector']['base_scope_descriptor'],descriptor())

    def test_configuration_wrapper_without_id_is_rejected(self):
        raw=wrap();raw['configuration_id']=None
        with self.assertRaises(ModelError):ScopeDescriptor(raw)

    def test_recursive_configuration_wrapper_is_rejected(self):
        with self.assertRaises(ModelError):ScopeDescriptor(wrap(wrap()))

    def test_already_configured_inner_scope_is_rejected(self):
        with self.assertRaises(ModelError):ScopeDescriptor(wrap(descriptor(configuration_id=aid('configuration'))))

    def test_configuration_wrapper_does_not_invent_applicability_results(self):
        with self.assertRaises(ModelError):resolve_scope_seeds(ScopeDescriptor(wrap()),inputs(artifact('configuration'),artifact()))

    def test_configured_descriptor_requires_existing_config(self):
        with self.assertRaises(ModelError):resolve_scope_seeds(ScopeDescriptor(descriptor(configuration_id=aid('configuration'))),inputs(artifact()))

    def test_wrapper_unknown_selector_fields_fail(self):
        value=wrap();value['selector']['extra']=True
        with self.assertRaises(ModelError):ScopeDescriptor(value)

    def test_explicit_duplicate_or_unsorted_artifact_ids_fail(self):
        for names in ([aid(),aid()],[aid(number=2),aid()]):
            with self.subTest(names=','.join(names)),self.assertRaises(ModelError):ScopeDescriptor(descriptor('explicit',{'artifact_ids':names,'resource_ids':[]}))

    def test_explicit_duplicate_or_unsorted_resource_ids_fail(self):
        for names in (['same','same'],['z','a']):
            with self.subTest(names=','.join(names)),self.assertRaises(ModelError):ScopeDescriptor(descriptor('explicit',{'artifact_ids':[],'resource_ids':names}))

    def test_resource_order_is_utf8_not_locale_or_utf16(self):
        ids=['\U00010000','\ue000','é','a'];ordered=sorted(ids,key=lambda v:v.encode('utf-8'))
        resources=[ScopeResource(name,'attachment','a'*64) for name in ids]
        result=resolve_scope_seeds(ScopeDescriptor(descriptor('explicit',{'artifact_ids':[],'resource_ids':ordered})),inputs(resources=resources))
        self.assertEqual(result.resource_ids,tuple(ordered))

    def test_duplicate_resources_are_rejected_even_with_same_bytes(self):
        one=ScopeResource('x','attachment','a'*64)
        with self.assertRaises(ModelError):inputs(resources=[one,one])

    def test_missing_archive_binding_resource_is_rejected(self):
        with self.assertRaises(ModelError):inputs(artifact('baseline'),archive_bindings={aid('baseline'):['missing']})

    def test_missing_archive_binding_owner_is_rejected(self):
        with self.assertRaises(ModelError):inputs(archive_bindings={aid('baseline'):[]})

    def test_unreferenced_archive_is_not_part_of_project_seeds(self):
        resource=ScopeResource('unreferenced','archive','a'*64)
        result=resolve_scope_seeds(ScopeDescriptor(descriptor('project')),inputs(artifact(),resources=[resource]))
        self.assertEqual(result.resource_ids,())

    def test_mutating_archive_argument_does_not_mutate_inventory(self):
        raw={aid('baseline'):[]};inventory=inputs(artifact('baseline'),archive_bindings=raw);binding=inventory.fingerprint
        raw[aid('baseline')].append('foreign')
        self.assertEqual(inventory.archive_bindings[aid('baseline')],());self.assertEqual(inventory.fingerprint,binding)

    def test_mixed_project_prefixes_are_rejected(self):
        with self.assertRaises(ModelError):inputs(artifact(project='XX'))

    def test_missing_graph_target_is_not_silently_ignored(self):
        with self.assertRaises(ModelError):inputs(artifact(relations=[edge(target=aid(number=2))]))

    def test_release_membership_deduplicates_multiple_paths(self):
        release=artifact('release');milestone=artifact('milestone',relations=[edge('part_of',release['id'])])
        task=artifact('task',relations=[edge('scheduled_for',release['id'],number=2),edge('part_of',milestone['id'],number=3)])
        result=resolve_scope_seeds(ScopeDescriptor(descriptor('release',{'release_id':release['id']})),inputs(task,release,milestone))
        self.assertEqual(len(result.artifact_ids),3)

    def test_release_isolated_from_other_release_membership(self):
        a,b=artifact('release'),artifact('release',number=2)
        task=artifact('task',relations=[edge('part_of',b['id'])])
        result=resolve_scope_seeds(ScopeDescriptor(descriptor('release',{'release_id':a['id']})),inputs(a,b,task))
        self.assertEqual(result.artifact_ids,(a['id'],))

    def test_all_small_input_permutations_have_identical_selection(self):
        a=artifact('release');b=artifact('milestone',relations=[edge('part_of',a['id'])]);c=artifact(relations=[edge('scheduled_for',b['id'],number=2)])
        desc=ScopeDescriptor(descriptor('release',{'release_id':a['id']}));results=[resolve_scope_seeds(desc,inputs(*values)) for values in itertools.permutations([a,b,c])]
        self.assertTrue(all(value==results[0] for value in results))

    def test_all_small_release_assignment_graphs_match_independent_expected_sets(self):
        release=artifact('release');other=artifact('release',number=2)
        for flags in itertools.product((False,True),repeat=3):
            values=[release,other];expected={release['id']}
            for number,belongs in enumerate(flags,1):
                item=artifact('task',number=number,relations=[edge('scheduled_for',release['id'] if belongs else other['id'],number=number)])
                values.append(item)
                if belongs:expected.add(item['id'])
            result=resolve_scope_seeds(ScopeDescriptor(descriptor('release',{'release_id':release['id']})),inputs(*values))
            self.assertEqual(set(result.artifact_ids),expected)

    def test_query_page_duplicate_or_foreign_id_is_rejected(self):
        desc=ScopeDescriptor(descriptor('query',{'query':query()}));inventory=inputs(artifact(),artifact(number=2))
        for ids in ([aid(),aid()],[aid(number=3)]):
            with self.assertRaises(ModelError):QuerySeedPage(desc,inventory,ids,total=len(ids))

    def test_query_page_offset_beyond_total_is_valid_empty(self):
        desc=ScopeDescriptor(descriptor('query',{'query':query(offset=20)}));inventory=inputs(artifact())
        page=QuerySeedPage(desc,inventory,[],total=1)
        self.assertEqual(resolve_scope_seeds(desc,inventory,query_page=page).artifact_ids,())

    def test_query_more_than_default_hundred_not_clipped(self):
        inventory=inputs(*(artifact(number=i) for i in range(1,134)))
        desc=ScopeDescriptor(descriptor('query',{'query':query(offset=1,limit=131)}));ids=[aid(number=i) for i in range(132,1,-1)]
        page=QuerySeedPage(desc,inventory,ids,total=133)
        self.assertEqual(resolve_scope_seeds(desc,inventory,query_page=page).artifact_ids,tuple(ids))

    def test_query_changed_resource_bytes_make_page_stale(self):
        desc=ScopeDescriptor(descriptor('query',{'query':query()}));a=inputs(artifact(),resources=[ScopeResource('x','attachment','a'*64)]);b=inputs(artifact(),resources=[ScopeResource('x','attachment','b'*64)])
        with self.assertRaises(ModelError):resolve_scope_seeds(desc,b,query_page=QuerySeedPage(desc,a,[aid()],total=1))

    def test_query_changed_project_id_makes_page_stale(self):
        desc=ScopeDescriptor(descriptor('query',{'query':query()}));a=inputs(artifact());b=inputs(artifact(),configuration=configuration_value(project_id='other'))
        with self.assertRaises(ModelError):resolve_scope_seeds(desc,b,query_page=QuerySeedPage(desc,a,[aid()],total=1))

    def test_query_non_integer_negative_or_boolean_pagination_is_rejected(self):
        for name in ('limit','offset'):
            for value in (-1,True,1.5,'1',None):
                with self.subTest(name=name,value=str(value)),self.assertRaises(ModelError):ScopeDescriptor(descriptor('query',{'query':query(**{name:value})}))

    def test_query_expression_hash_is_verified_but_expression_not_executed(self):
        expression={'op':'literal','value':True};operand={'expression':expression,'sha256':canonical_json_sha256(expression)}
        value=ScopeDescriptor(descriptor('query',{'query':query(srx_filters=[operand])}))
        self.assertEqual(value.data['selector']['query']['srx_filters'][0],operand)
        operand['sha256']='0'*64
        with self.assertRaises(ModelError):ScopeDescriptor(descriptor('query',{'query':query(srx_filters=[operand])}))

    def test_query_evaluation_path_is_not_loaded(self):
        with self.assertRaises(ModelError):ScopeDescriptor(descriptor('query',{'query':query(evaluation='/tmp/evaluation.json')}))

    def test_query_unknown_filters_and_sort_keys_fail(self):
        for changes in ({'filters':{'unknown':['x']}},{'sort':[{'key':'not-a-field','direction':'asc'}]}):
            with self.assertRaises(ModelError):ScopeDescriptor(descriptor('query',{'query':query(**changes)}))

    def test_query_select_and_sort_order_remains_bound(self):
        left=query(select=['/title','/id']);right=query(select=['/id','/title'])
        self.assertNotEqual(ScopeDescriptor(descriptor('query',{'query':left})).sha256,ScopeDescriptor(descriptor('query',{'query':right})).sha256)

    def test_noncanonical_json_and_cycles_rejected(self):
        a=descriptor();a['selector']['cycle']=a
        for raw in (a,descriptor(selector={'bad':float('nan')}),descriptor(selector={'bad':'\ud800'})):
            with self.assertRaises(ModelError):ScopeDescriptor(raw)

    def test_foreign_conversion_hooks_are_not_called(self):
        class Foreign:
            def __str__(self):raise AssertionError('hook must not run')
        with self.assertRaises(ModelError):ScopeDescriptor(descriptor(selector={'foreign':Foreign()}))


class ScopeStorageTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        configuration_file(self.root)

    def test_release_reader_finds_incoming_unselected_sources_and_preserves_bytes(self):
        release=artifact('release');save(self.root,release)
        task=artifact('task',relations=[edge('part_of',release['id'])]);save(self.root,task)
        before=files_under(self.root)
        result=read_artifact_scope_seeds(ProjectSource(self.root),ScopeDescriptor(descriptor('release',{'release_id':release['id']})))
        self.assertEqual(set(result.selection.artifact_ids),{release['id'],task['id']});self.assertEqual(result.source_count,2)
        self.assertEqual(files_under(self.root),before);self.assertFalse(result.atomic_snapshot)

    def test_new_source_between_calls_is_not_hidden_by_prior_result(self):
        release=artifact('release');save(self.root,release);source=ProjectSource(self.root)
        desc=ScopeDescriptor(descriptor('release',{'release_id':release['id']}));old=read_artifact_scope_seeds(source,desc)
        save(self.root,artifact('task',relations=[edge('part_of',release['id'])]))
        new=read_artifact_scope_seeds(source,desc)
        self.assertNotEqual(old.binding,new.binding);self.assertEqual(len(new.selection.artifact_ids),2)

    def test_source_mutation_during_selection_is_rejected(self):
        import specroad.storage.scope_seeds as module
        doc=artifact('document');path=save(self.root,doc);source=ProjectSource(self.root);original=module.resolve_scope_seeds
        def mutate(*args,**kwargs):
            result=original(*args,**kwargs);changed=dict(doc,title='changed');path.write_bytes(artifact_bytes(changed));return result
        with patch.object(module,'resolve_scope_seeds',side_effect=mutate),self.assertRaises(ModelError):
            read_artifact_scope_seeds(source,ScopeDescriptor(descriptor('document',{'document_id':doc['id']})))

    def test_corrupt_unselected_source_does_not_produce_partial_success(self):
        doc=artifact('document');save(self.root,doc);put(self.root,'spec/requirements/bad.json',b'{broken')
        with self.assertRaises(ModelError):read_artifact_scope_seeds(ProjectSource(self.root),ScopeDescriptor(descriptor('document',{'document_id':doc['id']})))

    def test_project_scope_is_not_reduced_to_artifacts_by_specialized_reader(self):
        with self.assertRaises(ModelError):read_artifact_scope_seeds(ProjectSource(self.root),ScopeDescriptor(descriptor('project')))

    def test_explicit_resource_request_is_not_silently_ignored(self):
        desc=ScopeDescriptor(descriptor('explicit',{'artifact_ids':[],'resource_ids':['profile:x']}))
        with self.assertRaises(ModelError):read_artifact_scope_seeds(ProjectSource(self.root),desc)

    def test_local_read_binding_distinguishes_project_copies(self):
        doc=artifact('document');save(self.root,doc);desc=ScopeDescriptor(descriptor('document',{'document_id':doc['id']}))
        other=self.root/'copy';other.mkdir();configuration_file(other);save(other,doc)
        left=read_artifact_scope_seeds(ProjectSource(self.root),desc);right=read_artifact_scope_seeds(ProjectSource(other),desc)
        self.assertEqual(left.selection,right.selection);self.assertNotEqual(left.binding.source_root,right.binding.source_root)

    def test_portable_module_and_zipapp_provide_scope_selection(self):
        import subprocess
        import sys
        from support.portable import build_distribution
        doc=artifact('document');save(self.root,doc)
        with tempfile.TemporaryDirectory() as directory:
            built=Path(directory)/'built';build_distribution(built);moved=Path(directory)/'moved';built.rename(moved)
            for distribution in (moved/'module',moved/'specroad.pyz'):
                code='''import sys
sys.path.insert(0,sys.argv[1])
from specroad.storage.project import ProjectSource
from specroad.graph.scope_descriptors import ScopeDescriptor
from specroad.storage.scope_seeds import read_artifact_scope_seeds
value={'scope_version':'scope-v1','scope_kind':'document','selector':{'document_id':sys.argv[3]},'configuration_id':None,'closure_profile':'core-closure-v1','boundary_policy':'closed'}
result=read_artifact_scope_seeds(ProjectSource(sys.argv[2]),ScopeDescriptor(value))
assert result.selection.artifact_ids==(sys.argv[3],) and not result.atomic_snapshot
'''
                run=subprocess.run([sys.executable,'-I','-S','-B','-c',code,str(distribution),str(self.root),doc['id']],
                                   stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,check=False)
                self.assertEqual(run.returncode,0,run.stderr.decode())

    def test_deep_query_values_are_preserved_without_truncation(self):
        expression={'op':'literal','value':True}
        for _ in range(150):expression={'value':expression}
        raw=descriptor('query',{'query':query(srx_filters=[{'expression':expression,'sha256':canonical_json_sha256(expression)}])})
        value=ScopeDescriptor(raw).data['selector']['query']['srx_filters'][0]['expression']
        for _ in range(150):value=value['value']
        self.assertEqual(value,{'op':'literal','value':True})

    def test_unavailable_json_decoder_yields_controlled_model_error(self):
        import specroad.graph.scope_descriptors as module
        with patch.object(module.json,'loads',side_effect=RecursionError),self.assertRaises(ModelError):
            ScopeDescriptor(descriptor())

    def test_seed_result_rejects_missing_input_binding(self):
        from specroad.graph.scope_seeds import ScopeSeeds
        with self.assertRaises(ModelError):ScopeSeeds(ScopeDescriptor(descriptor()),None,(),(),None)
