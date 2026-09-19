"""Adversarial and boundary coverage of the pure comparison contracts."""
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from specroad.graph.comparison import (ComparisonInputs, field_diff, compare_artifacts,
                                      direct_impact, compare_duration_bounds)
from specroad.graph.scope_hash import fingerprint_scope
from specroad.graph.scope_closure import resolve_scope_closure
from specroad.graph.scope_descriptors import ScopeDescriptor
from specroad.graph.scope_seeds import resolve_scope_seeds
from specroad.graph.scope_inputs import ScopeResource
from specroad.graph.scope_query_page import QuerySeedPage
from specroad.graph.relations import SourceRelations
from specroad.graph.strong_closure import resolve_strong_closure
from specroad.model.canonical import canonical_json_sha256
from specroad.model.configuration import ProjectConfiguration
from specroad.model.model_manifest import ManifestResource, ProjectReadBinding
from specroad.model.errors import ModelError
from specroad.model.attachments import AttachmentDescriptor
from support.artifacts import artifact_bytes
from support.relations import artifact, aid, edge, rid
from support.scopes import inputs, descriptor, query
from support.closure import observe, selected, source, subject
from support.model import configuration_value
from support.portable import build_distribution
from support.processes import run_python, run_core
from test_scope_comparison import snapshot, resolved, fingerprint


class ScopeComparisonRightTests(unittest.TestCase):
    def call(self, inventory, *, closure=None, dependencies=None, cfg=None,
             binding=None, resources=None, profile=None, kind='explicit', query_page=None):
        if closure is None:
            closure, dependencies = resolved(inventory, kind=kind)
        return fingerprint_scope(cfg or ProjectConfiguration(configuration_value()),
            binding or ProjectReadBinding('sample', '/test', (1, 2)), closure, dependencies,
            effective_profile={} if profile is None else profile,
            resource_records=resources, query_page=query_page)

    def test_stale_closure_does_not_produce_a_hash(self):
        inventory=inputs(artifact()); closure, bindings=resolved(inventory)
        other=inputs(artifact(title='New'))
        with self.assertRaises(ModelError): self.call(other, closure=closure, dependencies=observe(other))

    def test_tampered_closure_member_is_not_trusted(self):
        inventory=inputs(artifact()); closure, bindings=resolved(inventory)
        bad=replace(closure, members=(replace(closure.members[0], sha256='a'*64),))
        with self.assertRaises(ModelError): self.call(inventory, closure=bad, dependencies=bindings)

    def test_tampered_selected_set_is_not_trusted(self):
        inventory=inputs(artifact()); closure, bindings=resolved(inventory)
        with self.assertRaises(ModelError):
            self.call(inventory, closure=replace(closure, artifact_ids=()), dependencies=bindings)

    def test_strong_only_result_is_not_a_complete_scope(self):
        inventory=inputs(artifact()); closure, bindings=resolved(inventory)
        with self.assertRaises(ModelError):
            self.call(inventory, closure=resolve_strong_closure(closure.seeds, bindings), dependencies=bindings)

    def test_wrong_project_binding_rejected(self):
        with self.assertRaises(ModelError):
            self.call(inputs(artifact()), binding=ProjectReadBinding('other','/test',(1,2)))

    def test_semantic_configuration_mismatch_rejected(self):
        cfg=ProjectConfiguration(configuration_value(validation_policy={'fail_on':'warning'}))
        with self.assertRaises(ModelError): self.call(inputs(artifact()), cfg=cfg)

    def test_foreign_profile_project_rejected(self):
        with self.assertRaises(ModelError): self.call(inputs(artifact()), profile={'project_id':'other'})

    def test_missing_resource_metadata_rejected(self):
        inventory=inputs(artifact(), resources=[ScopeResource('p','profile','a'*64,'1',True)])
        with self.assertRaises(ModelError): self.call(inventory, kind='project')

    def test_extra_resource_metadata_rejected(self):
        with self.assertRaises(ModelError): self.call(inputs(artifact()), resources={'extra':None})

    def test_mismatched_resource_hash_rejected(self):
        inventory=inputs(artifact(), resources=[ScopeResource('p','profile','a'*64,'1',True)])
        binding=ProjectReadBinding('sample','/test',(1,2))
        record=ManifestResource(binding,{'kind':'profile','id':'p','version':'1','sha256':'b'*64})
        with self.assertRaises(ModelError): self.call(inventory, kind='project', resources={'p':record})

    def test_mismatched_resource_version_rejected(self):
        inventory=inputs(artifact(), resources=[ScopeResource('p','profile','a'*64,'1',True)])
        binding=ProjectReadBinding('sample','/test',(1,2))
        record=ManifestResource(binding,{'kind':'profile','id':'p','version':'2','sha256':'a'*64})
        with self.assertRaises(ModelError): self.call(inventory, kind='project', resources={'p':record})

    def test_copied_project_resource_binding_rejected(self):
        inventory=inputs(artifact(), resources=[ScopeResource('p','profile','a'*64,'1',True)])
        binding=ProjectReadBinding('sample','/copy',(1,3))
        record=ManifestResource(binding,{'kind':'profile','id':'p','version':'1','sha256':'a'*64})
        with self.assertRaises(ModelError): self.call(inventory, kind='project', resources={'p':record})

    def test_opaque_resource_aliases_cannot_duplicate_canonical_identity(self):
        rs=[ScopeResource(i,'rule','a'*64,'1',True) for i in ('r1','r2')]
        inventory=inputs(artifact(), resources=rs); binding=ProjectReadBinding('sample','/test',(1,2))
        record=ManifestResource(binding,{'kind':'rule','id':'r','version':'1','sha256':'a'*64})
        with self.assertRaises(ModelError): self.call(inventory, kind='project', resources={'r1':record,'r2':record})

    def test_selected_attachment_binds_size_media_type_and_bytes(self):
        def make(media, size):
            att=AttachmentDescriptor('attachments/e.bin', media, size, 'a'*64)
            inv=inputs(source('evidence', subjects=[subject(aid())], attachments=[att.data]), artifact(),
                       resources=[ScopeResource('binary','attachment','a'*64)])
            deps=observe(inv,attachments={'binary':att})
            seeds=selected(inv,kind='project');closure=resolve_scope_closure(seeds,deps)
            return self.call(inv,closure=closure,dependencies=deps)
        a=make('application/octet-stream',5)
        self.assertEqual(a.data['attachments'][0]['size'],5)
        self.assertNotEqual(a.scope_sha256,make('text/plain',5).scope_sha256)
        self.assertNotEqual(a.scope_sha256,make('application/octet-stream',6).scope_sha256)

    def test_document_descriptor_is_hashed_without_downgrading_to_project(self):
        inventory=inputs(artifact('document'))
        desc=ScopeDescriptor(descriptor('document', {'document_id':aid('document')}))
        seeds=resolve_scope_seeds(desc,inventory);deps=observe(inventory)
        result=self.call(inventory,closure=resolve_scope_closure(seeds,deps),dependencies=deps)
        self.assertEqual(result.data['scope_descriptor'],desc.data)

    def test_release_scope_keeps_its_selector(self):
        inventory=inputs(artifact('release'))
        desc=ScopeDescriptor(descriptor('release', {'release_id':aid('release')}))
        seeds=resolve_scope_seeds(desc,inventory);deps=observe(inventory)
        result=self.call(inventory,closure=resolve_scope_closure(seeds,deps),dependencies=deps)
        self.assertEqual(result.data['scope_descriptor'],desc.data)

    def test_specification_control_exclusion_still_blocks_hash(self):
        with self.assertRaises(ModelError):
            fingerprint(inputs(artifact(relations=[edge('references',aid('proposal'))]), artifact('proposal')),
                        kind='specification')

    def test_scope_hash_ignores_locale_environment(self):
        inventory=inputs(artifact())
        with patch.dict(os.environ,{'LANG':'ja_JP.UTF-8','TZ':'Pacific/Honolulu'}):a=fingerprint(inventory).sha256
        with patch.dict(os.environ,{'LANG':'C','TZ':'Europe/Berlin'}):b=fingerprint(inventory).sha256
        self.assertEqual(a,b)

    def test_boundary_tampering_is_rejected(self):
        inv=inputs(artifact(relations=[edge('duplicates',aid(number=2))]), artifact(number=2))
        closure,deps=resolved(inv,policy='partial')
        with self.assertRaises(ModelError):self.call(inv,closure=replace(closure,boundary_references=()),dependencies=deps)

    def test_duplicate_input_ids_are_rejected(self):
        with self.assertRaises(ModelError):snapshot(artifact(),artifact())

    def test_foreign_input_objects_are_not_executed(self):
        class Foreign:
            def __iter__(self):raise AssertionError('must not be converted')
        with self.assertRaises(ModelError):field_diff({'x':Foreign()},{})

    def test_cyclic_values_are_controlled_errors(self):
        value={};value['cycle']=value
        with self.assertRaises(ModelError):field_diff(value,{})

    def test_nonfinite_values_are_rejected(self):
        for value in (float('nan'),float('inf'),float('-inf')):
            with self.subTest(value=str(value)):
                with self.assertRaises(ModelError):field_diff({'v':value},{'v':0})

    def test_invalid_unicode_is_rejected(self):
        with self.assertRaises(ModelError):field_diff({'x':'\ud800'},{})

    def test_empty_json_pointer_key_is_preserved(self):
        self.assertEqual(field_diff({'':1},{'':2}).data['changes'][0]['pointer'],'/')

    def test_unicode_normalization_is_not_automatic(self):
        self.assertTrue(field_diff({'statement':'é'},{'statement':'e\u0301'}).data['changed'])

    def test_retirement_diff_is_not_deletion(self):
        result=compare_artifacts(snapshot(artifact()),snapshot(artifact(maturity='retired'))).data['changes'][0]
        self.assertEqual(result['change_kind'],'retired')
        self.assertIn('status_changed',result['categories'])
        self.assertIsNotNone(result['after_sha256'])

    def test_added_artifact_root_presence_is_explicit(self):
        item=compare_artifacts(snapshot(),snapshot(artifact())).data['changes'][0]['fields'][0]
        self.assertEqual(item['operation'],'add');self.assertFalse(item['before_present'])

    def test_removed_artifact_root_presence_is_explicit(self):
        item=compare_artifacts(snapshot(artifact()),snapshot()).data['changes'][0]['fields'][0]
        self.assertEqual(item['operation'],'remove');self.assertFalse(item['after_present'])

    def test_structured_field_categories(self):
        cases={'thresholds':([{'value':1}],[{'value':2}],'threshold_changed'),
               'exceptions':(['a'],['b'],'exception_changed'),
               'applicability':({'x':False},{'x':True},'scope_changed'),
               'verification_plan_status':('not_planned','planned','verification_changed'),
               'revision':(1,2,'audit_changed'),
               'relations':([], [edge()], 'relation_changed')}
        for name,(before,after,expected) in cases.items():
            with self.subTest(field=name):
                changes=field_diff({name:before},{name:after}).data['changes']
                self.assertEqual({c['category'] for c in changes},{expected})

    def test_ambiguous_timing_structure_does_not_claim_tightening(self):
        result=field_diff({'timing':{'value':10}},{'timing':{'value':5}}).data
        self.assertEqual({c['category'] for c in result['changes']},{'timing_changed'})

    def test_unstructured_timing_prose_remains_text(self):
        result=field_diff({'timing':'within ten seconds'},{'timing':'within five seconds'}).data
        self.assertEqual(result['changes'][0]['category'],'text_changed')

    def test_exception_text_not_interpreted_as_numerical_threshold(self):
        result=field_diff({'statement':'except above 10'},{'statement':'except above 20'}).data
        self.assertEqual(result['changes'][0]['category'],'text_changed')

    def test_document_contains_position_change_is_structural(self):
        a=artifact('document',relations=[edge('contains',aid('section'),position=0)])
        b=artifact('document',relations=[edge('contains',aid('section'),position=1)])
        change=compare_artifacts(snapshot(a),snapshot(b)).data['changes'][0]
        self.assertIn('document_structure_changed',change['categories'])
        self.assertIn('relation_changed',change['categories'])

    def test_code_ref_field_change_is_classified(self):
        a=artifact('code_ref',path='src/old.py');b=artifact('code_ref',path='src/new.py')
        change=compare_artifacts(snapshot(a),snapshot(b)).data['changes'][0]
        self.assertIn('code_reference_changed',change['categories'])

    def test_evidence_status_is_not_fabricated_from_bytes(self):
        a=artifact('evidence',attachments=[]);b=artifact('evidence',attachments=[{'sha256':'a'*64}])
        change=compare_artifacts(snapshot(a),snapshot(b)).data['changes'][0]
        self.assertNotIn('evidence_stale',change['categories'])

    def test_strict_upper_duration_bound_is_tightened(self):
        result=compare_duration_bounds({'value':10,'unit':'ms'},{'value':5,'unit':'ms'},bound='maximum').data
        self.assertEqual(result['category'],'timing_tightened')

    def test_larger_upper_duration_bound_is_relaxed(self):
        self.assertEqual(compare_duration_bounds('PT1S','PT2S',bound='maximum').data['category'],'timing_relaxed')

    def test_larger_lower_duration_bound_is_tightened(self):
        self.assertEqual(compare_duration_bounds('PT1S','PT2S',bound='minimum').data['category'],'timing_tightened')

    def test_smaller_lower_duration_bound_is_relaxed(self):
        self.assertEqual(compare_duration_bounds('PT2S','PT1S',bound='minimum').data['category'],'timing_relaxed')

    def test_unit_conversion_can_be_equivalent(self):
        result=compare_duration_bounds({'value':1000,'unit':'ms'},'PT1S',bound='maximum').data
        self.assertEqual(result['category'],'timing_equivalent');self.assertEqual(result['order'],0)

    def test_duration_comparison_avoids_float_rounding(self):
        result=compare_duration_bounds('PT0.10000000000000001S','PT0.1S',bound='maximum').data
        self.assertEqual(result['category'],'timing_tightened')

    def test_calendar_durations_do_not_invent_fixed_seconds(self):
        result=compare_duration_bounds('P1M','P30D',bound='maximum').data
        self.assertFalse(result['comparable']);self.assertEqual(result['category'],'timing_changed')

    def test_valid_but_unconverted_units_are_not_rejected_as_invalid(self):
        result=compare_duration_bounds({'value':1,'unit':'mo'},{'value':1,'unit':'a'},bound='maximum').data
        self.assertFalse(result['comparable'])

    def test_duration_requires_explicit_bound_direction(self):
        with self.assertRaises(ModelError):compare_duration_bounds('PT1S','PT2S',bound='guess')

    def test_duration_invalid_values_are_rejected(self):
        for bad in (True,{'value':-1,'unit':'s'},'ten seconds',{'value':3,'unit':'furlong'}):
            with self.subTest(case=repr(bad)):
                with self.assertRaises(ModelError):compare_duration_bounds(bad,'PT2S',bound='maximum')

    def test_unchanged_duration_is_not_a_change(self):
        self.assertEqual(compare_duration_bounds('PT1S','PT1S',bound='maximum').data['category'],'unchanged')

    def test_large_incoming_set_is_not_truncated(self):
        inventory=inputs(artifact(),*[artifact(number=n,relations=[edge('depends_on',aid(),number=n)]) for n in range(2,153)])
        result=direct_impact(aid(),inventory.references).data
        self.assertEqual(len(result['groups'][0]['artifact_ids']),151)
        self.assertEqual(len(result['groups'][0]['connections']),151)

    def test_impact_cycles_stay_one_hop(self):
        inventory=inputs(artifact(relations=[edge('depends_on',aid(number=2))]),
            artifact(number=2,relations=[edge('depends_on',aid(),number=2)]))
        result=direct_impact(aid(),inventory.references).data
        self.assertEqual(len(result['groups'][0]['connections']),2)

    def test_impact_binds_supplied_relation_data(self):
        a=inputs(artifact(relations=[edge('depends_on',aid(number=2))]),artifact(number=2))
        b=inputs(artifact(relations=[edge('depends_on',aid(number=2),rationale='New')]),artifact(number=2))
        self.assertNotEqual(direct_impact(aid(),a.references).data['input_relations_sha256'],
                            direct_impact(aid(),b.references).data['input_relations_sha256'])

    def test_original_source_bytes_are_preserved(self):
        inventory=inputs(artifact(relations=[edge('depends_on',aid(number=2))]),artifact(number=2))
        saved=[r.source_bytes for r in inventory.records]
        fingerprint(inventory); direct_impact(aid(),inventory.references)
        compare_artifacts(ComparisonInputs('sample',inventory.records),snapshot(artifact()))
        self.assertEqual(saved,[r.source_bytes for r in inventory.records])

    def test_no_files_or_environment_are_touched(self):
        with tempfile.TemporaryDirectory() as temp:
            before=dict(os.environ);path=Path(temp)/'keep';path.write_bytes(b'unchanged')
            fingerprint(inputs(artifact()));field_diff({'x':1},{'x':2})
            self.assertEqual(list(Path(temp).iterdir()),[path]);self.assertEqual(path.read_bytes(),b'unchanged')
            self.assertEqual(dict(os.environ),before)

    def test_portable_module_and_zipapp_provide_same_data_primitives(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);build_distribution(root/'dist');(root/'dist').rename(root/'moved')
            paths=[root/'moved/module',root/'moved/specroad.pyz']
            # Consult actual distribution names, not a console-output snapshot.
            if not paths[1].exists():paths[1]=next((root/'moved').glob('*.pyz'))
            code="from specroad.graph.comparison import field_diff,compare_duration_bounds; from specroad.graph.scope_hash import fingerprint_scope; assert field_diff({'a':1},{'a':2}).data['changed']; assert compare_duration_bounds('PT2S','PT1S',bound='maximum').data['category']=='timing_tightened'"
            for path in paths:
                result=run_python(['-I','-S','-B','-c','import sys;sys.path.insert(0,'+repr(str(path))+');'+code],root)
                self.assertEqual(result.returncode,0,result.stderr.decode())

    def test_query_scope_preserves_bound_pagination(self):
        inv=inputs(artifact(),artifact(number=2));deps=observe(inv)
        desc=ScopeDescriptor(descriptor('query', {'query':query(offset=1,limit=1)}))
        page=QuerySeedPage(desc,inv,[aid(number=2)],total=2)
        seeds=resolve_scope_seeds(desc,inv,query_page=page)
        closure=resolve_scope_closure(seeds,deps,query_page=page)
        result=self.call(inv,closure=closure,dependencies=deps,query_page=page)
        self.assertEqual([a['id'] for a in result.data['artifacts']],[aid(number=2)])
        self.assertEqual(result.data['scope_descriptor'],desc.data)

    def test_query_scope_cannot_be_hashed_without_its_page(self):
        inv=inputs(artifact());deps=observe(inv)
        desc=ScopeDescriptor(descriptor('query', {'query':query(limit=1)}))
        page=QuerySeedPage(desc,inv,[aid()],total=1)
        seeds=resolve_scope_seeds(desc,inv,query_page=page)
        closure=resolve_scope_closure(seeds,deps,query_page=page)
        with self.assertRaises(ModelError):self.call(inv,closure=closure,dependencies=deps)

    def test_archived_model_is_not_replaced_by_archive_zip_digest(self):
        resource=ScopeResource('archive:one','archive','a'*64)
        inv=inputs(source('baseline'),resources=[resource],archive_bindings={aid('baseline'):['archive:one']})
        with self.assertRaises(ModelError) as error:
            self.call(inv,kind='project',resources={'archive:one':None})
        self.assertEqual(error.exception.reason,'scope_hash_archive_expansion_required')

    def test_empty_scope_has_real_hash_and_no_synthetic_members(self):
        inv=inputs();closure,deps=resolved(inv,identities=[])
        result=self.call(inv,closure=closure,dependencies=deps)
        self.assertEqual(result.data['artifacts'],[])
        self.assertEqual(len(result.scope_sha256),64)

    def test_timing_unit_is_structured_not_unstructured_prose(self):
        result=field_diff({'timing':{'value':1,'unit':'s'}},{'timing':{'value':1,'unit':'ms'}}).data
        self.assertEqual(result['changes'][0]['category'],'timing_changed')

    def test_wide_field_diff_has_no_pagination_truncation(self):
        before={str(i):0 for i in range(250)};after={str(i):1 for i in range(250)}
        self.assertEqual(len(field_diff(before,after).data['changes']),250)

    def test_structured_limit_change_has_no_unjustified_strictness(self):
        result=field_diff({'thresholds':[{'value':10}]},{'thresholds':[{'value':5}]}).data
        self.assertEqual(result['changes'][0]['category'],'threshold_changed')
        self.assertTrue(all(c['category'] not in ('timing_tightened','timing_relaxed')
                            for c in result['changes']))

    def test_nan_and_subclass_conversion_hooks_never_generate_results(self):
        class CustomInt(int):
            def __float__(self):raise AssertionError('foreign conversion')
        with self.assertRaises(ModelError):field_diff({'x':CustomInt(1)},{'x':2})

    def test_result_values_are_frozen(self):
        result=field_diff({'x':1},{'x':2})
        with self.assertRaises(FrozenInstanceError):result._encoded=b'{}'

    def test_deep_values_are_processed_or_rejected_explicitly(self):
        before={}; after={}; left=before; right=after
        for _ in range(1500):
            left['nested']={}; left=left['nested']
            right['nested']={}; right=right['nested']
        left['value']=1; right['value']=2
        try:
            result=field_diff(before,after).data
        except ModelError as error:
            self.assertEqual(error.reason,'comparison_nesting_not_supported')
        else:
            self.assertEqual(len(result['changes']),1)
            change=result['changes'][0]
            self.assertEqual(change['pointer'],'/nested'*1500+'/value')
            self.assertEqual((change['before'],change['after']),(1,2))

    def test_decoder_nesting_failure_becomes_controlled_model_error(self):
        with patch('json.loads',side_effect=RecursionError):
            with self.assertRaises(ModelError) as error:field_diff({'x':1},{'x':2})
        self.assertEqual(error.exception.reason,'comparison_nesting_not_supported')
