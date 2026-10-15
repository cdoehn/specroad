"""Fixed-point oracles, stale bindings, missing providers and portability."""
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from specroad.graph.closure_inputs import ClosureBindings, ClosureNode, artifact_node as A, resource_node as R
from specroad.graph.scope_descriptors import ScopeDescriptor
from specroad.graph.scope_inputs import ScopeResource
from specroad.graph.scope_seeds import QuerySeedPage, ScopeSeeds, resolve_scope_seeds
from specroad.graph.strong_closure import resolve_strong_closure, require_strong_closure_current
from specroad.model.attachments import AttachmentDescriptor
from specroad.model.canonical import canonical_json_sha256
from specroad.model.errors import ModelError
from support.closure import source, observe, selected, subject, slot
from support.relations import artifact, aid, edge, rid
from support.scopes import inputs, descriptor, query
from support.portable import build_distribution


def attachment_fixture(**changes):
    values = dict(path='attachments/a.bin', media_type='application/octet-stream', size=3, sha256='a'*64)
    values.update(changes)
    observed = AttachmentDescriptor(**values)
    resource = ScopeResource('attachment:one', 'attachment', observed.sha256)
    evidence = source('evidence', subjects=[subject(aid())], attachments=[observed.data])
    inventory = inputs(evidence, artifact(), resources=[resource])
    return inventory, observed, evidence


class StrongClosureRightTests(unittest.TestCase):
    def test_all_fifteen_strong_relation_types_have_actual_reachability(self):
        pairs = [('addresses','requirement','goal'), ('refines','requirement','requirement'),
                 ('derived_from','requirement','source'), ('depends_on','requirement','requirement'),
                 ('constrains','requirement','component'), ('allocated_to','requirement','interface'),
                 ('implemented_by','requirement','task'), ('verified_by','requirement','test'),
                 ('produces','test','evidence'), ('mitigates','requirement','risk'),
                 ('scheduled_for','requirement','release'), ('part_of','task','release'),
                 ('supersedes','requirement','requirement'), ('contains','document','section'),
                 ('references','source','requirement')]
        for kind, source_type, target_type in pairs:
            with self.subTest(kind=kind):
                first = source(source_type, relations=[edge(kind, aid(target_type,2))])
                last = source(target_type,2, **({'subjects':[subject(first['id'])]} if target_type=='evidence' else {}))
                inventory = inputs(first,last)
                result = resolve_strong_closure(selected(inventory,[first['id']]),observe(inventory))
                self.assertEqual(set(result.artifact_ids),{first['id'],last['id']})

    def test_exhaustive_three_node_graphs_match_independent_fixed_point(self):
        edges = [(a,b) for a in range(3) for b in range(3) if a!=b]
        for mask in range(1 << len(edges)):
            pairs = [pair for i,pair in enumerate(edges) if mask & (1 << i)]
            raw = [artifact(number=a+1, relations=[edge('depends_on',aid(number=b+1),number=i+1)
                    for i,(left,b) in enumerate(pairs) if left==a]) for a in range(3)]
            inventory = inputs(*raw); bindings = observe(inventory)
            for seed in range(3):
                reached = {seed}
                while True:
                    expanded = reached | {b for a,b in pairs if a in reached}
                    if expanded == reached: break
                    reached = expanded
                result = resolve_strong_closure(selected(inventory,[aid(number=seed+1)]),bindings)
                self.assertEqual(set(result.artifact_ids),{aid(number=n+1) for n in reached})
                self.assertEqual(len(result.processing_order),len(reached))

    def test_deep_chain_does_not_depend_on_python_recursion_limit(self):
        length = 1400
        inventory = inputs(*(artifact(number=n, relations=([edge('depends_on',aid(number=n+1),number=n)] if n<length else []))
                             for n in range(1,length+1)))
        result = resolve_strong_closure(selected(inventory,[aid()]),observe(inventory))
        self.assertEqual(len(result.artifact_ids),length)
        self.assertEqual(len(result.processing_order),length)

    def test_wide_frontier_is_not_cut_at_an_output_limit(self):
        count = 275
        inventory = inputs(artifact(relations=[edge('depends_on',aid(number=n),number=n) for n in range(2,count+1)]),
                           *(artifact(number=n) for n in range(2,count+1)))
        result=resolve_strong_closure(selected(inventory,[aid()]),observe(inventory))
        self.assertEqual(len(result.artifact_ids),count)

    def test_source_and_binding_enumeration_order_do_not_change_result(self):
        a,b = ScopeResource('rule:a','rule','a'*64,'1'),ScopeResource('rule:b','rule','b'*64,'2')
        one,two = artifact(),artifact(number=2)
        left,right = inputs(one,two,resources=[a,b]), inputs(two,one,resources=[b,a])
        x=observe(left,uses={A(aid()):[R(a.resource_id),R(b.resource_id)]})
        y=observe(right,uses={A(aid()):[R(b.resource_id),R(a.resource_id)]})
        first=resolve_strong_closure(selected(left,[aid()]),x)
        last=resolve_strong_closure(selected(right,[aid()]),y)
        self.assertEqual(first,last);self.assertEqual(first.observation_sha256,last.observation_sha256)

    def test_frontier_and_resource_order_use_utf8_not_locale(self):
        names=['\U00010000','\ue000','é','a']
        resources=[ScopeResource(name,'rule','a'*64,'1') for name in names]
        inventory=inputs(resources=resources)
        result=resolve_strong_closure(selected(inventory,resource_ids=names),observe(inventory))
        expected=tuple(sorted(names,key=lambda text:text.encode('utf-8')))
        self.assertEqual(result.resource_ids,expected)
        self.assertEqual(tuple(node.identity for node in result.processing_order),expected)

    def test_tagged_namespaces_do_not_conflate_artifact_and_resource(self):
        inventory=inputs(artifact(),resources=[ScopeResource(aid(),'rule','a'*64,'1')])
        result=resolve_strong_closure(selected(inventory,[aid()],[aid()]),observe(inventory))
        self.assertEqual(len(result.processing_order),2)
        self.assertEqual({member.node.kind for member in result.members},{'artifact','resource'})

    def test_member_content_hashes_and_resource_versions_are_preserved(self):
        raw=artifact(); resource=ScopeResource('rule:a','rule','a'*64,'2')
        inventory=inputs(raw,resources=[resource])
        result=resolve_strong_closure(selected(inventory,[aid()],[resource.resource_id]),observe(inventory))
        by_node={member.node:member for member in result.members}
        self.assertEqual(by_node[A(aid())].sha256,canonical_json_sha256(raw))
        self.assertEqual(by_node[R(resource.resource_id)].sha256,resource.sha256)
        self.assertEqual(by_node[R(resource.resource_id)].version,'2')

    def test_same_current_observations_revalidate_without_mutation(self):
        inventory=inputs(artifact()); seeds=selected(inventory,[aid()]); bindings=observe(inventory)
        old=resolve_strong_closure(seeds,bindings)
        self.assertIsNone(require_strong_closure_current(old,seeds,bindings))

    def test_changed_resource_bytes_invalidate_old_result(self):
        old=inputs(resources=[ScopeResource('r','rule','a'*64,'1')]);new=inputs(resources=[ScopeResource('r','rule','b'*64,'1')])
        result=resolve_strong_closure(selected(old,resource_ids=['r']),observe(old))
        with self.assertRaises(ModelError):require_strong_closure_current(result,selected(new,resource_ids=['r']),observe(new))

    def test_changed_resource_version_invalidate_old_result(self):
        old=inputs(resources=[ScopeResource('r','rule','a'*64,'1')]);new=inputs(resources=[ScopeResource('r','rule','a'*64,'2')])
        result=resolve_strong_closure(selected(old,resource_ids=['r']),observe(old))
        with self.assertRaises(ModelError):require_strong_closure_current(result,selected(new,resource_ids=['r']),observe(new))

    def test_changed_usage_observation_invalidate_old_result(self):
        inventory=inputs(artifact(),resources=[ScopeResource('r','rule','a'*64,'1')]);seeds=selected(inventory,[aid()])
        old=resolve_strong_closure(seeds,observe(inventory))
        new=observe(inventory,uses={A(aid()):[R('r')]})
        with self.assertRaises(ModelError):require_strong_closure_current(old,seeds,new)

    def test_changed_current_review_selection_invalidates_old_result(self):
        review=source('relation_review',relation_id=rid())
        inventory=inputs(artifact(relations=[edge('refines',aid(number=2))]),artifact(number=2),review)
        seeds=selected(inventory,[aid()]);old=resolve_strong_closure(seeds,observe(inventory))
        with self.assertRaises(ModelError):require_strong_closure_current(old,seeds,observe(inventory,reviews={rid():[review['id']]}))

    def test_recheck_does_not_fallback_when_current_source_missing(self):
        inventory=inputs(artifact());seeds=selected(inventory,[aid()]);old=resolve_strong_closure(seeds,observe(inventory))
        with self.assertRaises(ModelError):require_strong_closure_current(old,seeds,observe(inputs()))

    def test_forged_membership_is_detected_by_recomputation(self):
        inventory=inputs(artifact());seeds=selected(inventory,[aid()]);binding=observe(inventory)
        old=resolve_strong_closure(seeds,binding)
        with self.assertRaises(ModelError):require_strong_closure_current(replace(old,artifact_ids=()),seeds,binding)

    def test_forged_explicit_seed_subset_is_not_accepted(self):
        inventory=inputs(artifact(),artifact(number=2));seeds=selected(inventory,[aid(),aid(number=2)])
        narrowed=replace(seeds,artifact_ids=(aid(),))
        with self.assertRaises(ModelError):resolve_strong_closure(narrowed,observe(inventory))

    def test_query_page_order_is_retained_but_dependencies_are_canonical(self):
        inventory=inputs(artifact(relations=[edge('depends_on',aid(number=2))]),artifact(number=2),artifact(number=3))
        desc=ScopeDescriptor(descriptor('query',{'query':query(limit=2)}));page=QuerySeedPage(desc,inventory,[aid(number=3),aid()],total=3)
        seeds=resolve_scope_seeds(desc,inventory,query_page=page)
        result=resolve_strong_closure(seeds,observe(inventory),query_page=page)
        self.assertEqual(result.seeds.artifact_ids,(aid(number=3),aid()))
        self.assertEqual(result.artifact_ids,tuple(aid(number=n) for n in (1,2,3)))

    def test_query_without_bound_page_is_not_treated_as_trusted_selection(self):
        inventory=inputs(artifact());desc=ScopeDescriptor(descriptor('query',{'query':query()}))
        seeds=ScopeSeeds(desc,inventory.fingerprint,(aid(),),(),None)
        with self.assertRaises(ModelError):resolve_strong_closure(seeds,observe(inventory))

    def test_stale_query_page_is_not_reused(self):
        old=inputs(artifact());new=inputs(artifact(title='changed'));desc=ScopeDescriptor(descriptor('query',{'query':query()}))
        page=QuerySeedPage(desc,old,[aid()],total=1)
        seeds=ScopeSeeds(desc,new.fingerprint,(aid(),),(),None)
        with self.assertRaises(ModelError):resolve_strong_closure(seeds,observe(new),query_page=page)

    def test_configuration_filter_is_not_silently_dropped(self):
        from support.records import record_value
        inventory=inputs(artifact(),record_value('configuration', id=aid('configuration')));desc=ScopeDescriptor(descriptor(configuration_id=aid('configuration')))
        seeds=ScopeSeeds(desc,inventory.fingerprint,(aid(),),(),None)
        with self.assertRaises(ModelError) as raised:resolve_strong_closure(seeds,observe(inventory))
        self.assertEqual(raised.exception.reason,'closure_seed_selection_mismatch')

    def test_missing_subject_rejected_for_closed_and_partial_policies(self):
        evidence=source('evidence',subjects=[subject(aid())]);inventory=inputs(evidence)
        for policy in ('closed','partial'):
            desc=ScopeDescriptor(descriptor('explicit',{'artifact_ids':[evidence['id']],'resource_ids':[]},boundary_policy=policy))
            with self.subTest(policy=policy),self.assertRaises(ModelError):
                resolve_strong_closure(resolve_scope_seeds(desc,inventory),observe(inventory))

    def test_missing_slot_target_is_not_an_unbound_manual_slot(self):
        contract=source('verification',evidence_slots=[slot(aid('test'))]);inventory=inputs(contract)
        with self.assertRaises(ModelError):resolve_strong_closure(selected(inventory,[contract['id']]),observe(inventory))

    def test_slot_target_must_be_a_test_not_an_artifact_label(self):
        contract=source('verification',evidence_slots=[slot(aid())]);inventory=inputs(contract,artifact())
        with self.assertRaises(ModelError):resolve_strong_closure(selected(inventory,[contract['id']]),observe(inventory))

    def test_multiple_slots_can_share_one_test(self):
        contract=source('verification',evidence_slots=[slot(aid('test'),'one'),slot(aid('test'),'two')]);inventory=inputs(contract,artifact('test'))
        result=resolve_strong_closure(selected(inventory,[contract['id']]),observe(inventory))
        self.assertEqual(len(result.artifact_ids),2)

    def test_duplicate_slot_check_ids_are_rejected(self):
        contract=source('verification',evidence_slots=[slot(),slot()]);inventory=inputs(contract)
        with self.assertRaises(ModelError):resolve_strong_closure(selected(inventory,[contract['id']]),observe(inventory))

    def test_malformed_slot_and_subject_fields_are_not_ignored(self):
        cases=[source('verification',evidence_slots=None),source('verification',evidence_slots=[]),
               source('verification',evidence_slots=[{'test_id':None}]), source('verification',evidence_slots=[slot(check_id='')]),
               source('evidence',subjects=[]),source('evidence',subjects=[dict(subject(aid()),revision=True)]),
               source('evidence',subjects=[dict(subject(aid()),artifact_sha256='x')])]
        for number,value in enumerate(cases):
            with self.subTest(case=number),self.assertRaises(ModelError):
                inventory=inputs(value,artifact());resolve_strong_closure(selected(inventory,[value['id']]),observe(inventory))

    def test_duplicate_subjects_are_rejected(self):
        evidence=source('evidence',subjects=[subject(aid()),subject(aid())]);inventory=inputs(evidence,artifact())
        with self.assertRaises(ModelError):resolve_strong_closure(selected(inventory,[evidence['id']]),observe(inventory))

    def test_review_for_a_different_relation_is_rejected(self):
        review=source('relation_review',relation_id=rid(99))
        inventory=inputs(artifact(relations=[edge('refines',aid(number=2))]),artifact(number=2),review)
        with self.assertRaises(ModelError):observe(inventory,reviews={rid():[review['id']]})

    def test_non_review_artifact_cannot_be_a_current_review(self):
        inventory=inputs(artifact(relations=[edge('refines',aid(number=2))]),artifact(number=2))
        with self.assertRaises(ModelError):observe(inventory,reviews={rid():[aid()]})

    def test_malformed_current_review_fields_are_rejected(self):
        review=source('relation_review',relation_id=rid());del review['source_context_sha256']
        inventory=inputs(artifact(relations=[edge('refines',aid(number=2))]),artifact(number=2),review)
        with self.assertRaises(ModelError):observe(inventory,reviews={rid():[review['id']]})

    def test_current_review_dependencies_are_transitive(self):
        review=source('relation_review',relation_id=rid());resource=ScopeResource('review-rule','rule','a'*64,'1')
        inventory=inputs(artifact(relations=[edge('depends_on',aid(number=2))]),artifact(number=2),review,resources=[resource])
        result=resolve_strong_closure(selected(inventory,[aid()]),observe(inventory,reviews={rid():[review['id']]},uses={A(review['id']):[R(resource.resource_id)]}))
        self.assertIn(resource.resource_id,result.resource_ids)

    def test_unreached_relation_does_not_pull_in_its_review(self):
        review=source('relation_review',relation_id=rid());inventory=inputs(artifact(),artifact(number=2,relations=[edge('depends_on',aid(number=3))]),artifact(number=3),review)
        result=resolve_strong_closure(selected(inventory,[aid()]),observe(inventory,reviews={rid():[review['id']]}))
        self.assertNotIn(review['id'],result.artifact_ids)

    def test_attachment_size_and_media_type_must_match_observation(self):
        inventory,observed,evidence=attachment_fixture()
        for changed in (replace(observed,size=4),replace(observed,media_type='text/plain')):
            with self.subTest(size=changed.size,media_type=changed.media_type),self.assertRaises(ModelError):
                resolve_strong_closure(selected(inventory,[evidence['id']]),observe(inventory,attachments={'attachment:one':changed}))

    def test_attachment_hash_must_match_resource_binding(self):
        inventory,observed,evidence=attachment_fixture()
        with self.assertRaises(ModelError):observe(inventory,attachments={'attachment:one':replace(observed,sha256='b'*64)})

    def test_missing_attachment_observation_is_not_success(self):
        inventory,observed,evidence=attachment_fixture()
        with self.assertRaises(ModelError):resolve_strong_closure(selected(inventory,[evidence['id']]),observe(inventory))

    def test_explicit_attachment_seed_still_requires_descriptor(self):
        inventory=inputs(resources=[ScopeResource('a','attachment','a'*64)])
        with self.assertRaises(ModelError):resolve_strong_closure(selected(inventory,resource_ids=['a']),observe(inventory))

    def test_shared_attachment_is_deduplicated_across_evidences(self):
        inventory,observed,evidence=attachment_fixture();other=source('evidence',2,subjects=[subject(aid())],attachments=[observed.data])
        inventory=inputs(evidence,other,artifact(),resources=inventory.resources)
        result=resolve_strong_closure(selected(inventory,[evidence['id'],other['id']]),observe(inventory,attachments={'attachment:one':observed}))
        self.assertEqual(result.attachments,(observed,))

    def test_duplicate_attachment_in_one_evidence_is_rejected(self):
        inventory,observed,evidence=attachment_fixture();evidence['attachments'].append(observed.data)
        inventory=inputs(evidence,artifact(),resources=inventory.resources)
        with self.assertRaises(ModelError):resolve_strong_closure(selected(inventory,[evidence['id']]),observe(inventory,attachments={'attachment:one':observed}))

    def test_case_colliding_attachment_paths_are_rejected(self):
        first=AttachmentDescriptor('attachments/A.bin','application/octet-stream',3,'a'*64);last=replace(first,path='attachments/a.bin')
        inventory=inputs(resources=[ScopeResource('a','attachment','a'*64),ScopeResource('b','attachment','a'*64)])
        with self.assertRaises(ModelError):observe(inventory,attachments={'a':first,'b':last})

    def test_attachment_order_is_project_relative_path_not_resource_alias(self):
        first=AttachmentDescriptor('attachments/z.bin','application/octet-stream',3,'a'*64);last=replace(first,path='attachments/a.bin')
        inventory=inputs(resources=[ScopeResource('a','attachment','a'*64),ScopeResource('z','attachment','a'*64)])
        result=resolve_strong_closure(selected(inventory,resource_ids=['a','z']),observe(inventory,attachments={'a':first,'z':last}))
        self.assertEqual(result.attachments,(last,first))

    def test_baseline_archive_binding_is_required_after_transitive_reach(self):
        first=artifact('source',relations=[edge('references',aid('baseline'))]);baseline=source('baseline');inventory=inputs(first,baseline)
        with self.assertRaises(ModelError):resolve_strong_closure(selected(inventory,[first['id']]),observe(inventory))

    def test_archive_resource_can_require_other_normative_resources(self):
        baseline=source('baseline');archive=ScopeResource('archive','archive','a'*64);rule=ScopeResource('rule','rule','b'*64,'1')
        inventory=inputs(baseline,resources=[archive,rule],archive_bindings={baseline['id']:['archive']})
        result=resolve_strong_closure(selected(inventory,[baseline['id']]),observe(inventory,uses={R('archive'):[R('rule')]}))
        self.assertEqual(set(result.resource_ids),{'archive','rule'})

    def test_unused_observation_can_be_absent_without_expanding_unreachable_nodes(self):
        inventory=inputs(artifact(),artifact(number=2))
        binding=ClosureBindings(inventory,uses={A(aid()):()},current_reviews={})
        self.assertEqual(resolve_strong_closure(selected(inventory,[aid()]),binding).artifact_ids,(aid(),))

    def test_duplicate_usage_and_duplicate_review_observations_fail(self):
        resource=ScopeResource('r','rule','a'*64,'1');inventory=inputs(artifact(),resources=[resource])
        with self.assertRaises(ModelError):observe(inventory,uses={A(aid()):[R('r'),R('r')]})
        review=source('relation_review',relation_id=rid());inventory=inputs(artifact(relations=[edge('refines',aid(number=2))]),artifact(number=2),review)
        with self.assertRaises(ModelError):observe(inventory,reviews={rid():[review['id'],review['id']]})

    def test_node_and_binding_types_are_checked_without_string_conversion(self):
        class Foreign:
            def __str__(self):raise AssertionError('conversion must not run')
        for value in (Foreign(),None,[],3):
            with self.subTest(type=type(value).__name__),self.assertRaises(ModelError):ClosureNode('resource',value)
        with self.assertRaises(ModelError):ClosureNode('file','/tmp/outside')
        with self.assertRaises(ModelError):ClosureBindings(inputs(),uses=[],current_reviews={})

    def test_observation_document_does_not_expose_or_mutate_source_bytes(self):
        raw=artifact(title='private source text');inventory=inputs(raw);binding=observe(inventory);seeds=selected(inventory,[aid()])
        result=resolve_strong_closure(seeds,binding);data=result.data;before=result.observation_sha256
        data['members'][0]['sha256']='0'*64;data['descriptor']['selector']['artifact_ids'].clear()
        self.assertEqual(result.observation_sha256,before)
        self.assertNotIn('private source text',json.dumps(result.data))
        self.assertEqual(inventory.records[0].data,raw)

    def test_multiple_dependencies_and_current_reviews_do_not_change_original_bytes(self):
        review=source('relation_review',relation_id=rid());inventory=inputs(artifact(relations=[edge('depends_on',aid(number=2))]),artifact(number=2),review)
        before=tuple(record.source_bytes for record in inventory.records);binding=observe(inventory,reviews={rid():[review['id']]})
        resolve_strong_closure(selected(inventory,[aid()]),binding)
        self.assertEqual(tuple(record.source_bytes for record in inventory.records),before)

    def test_locale_and_timezone_do_not_change_closure_membership_or_observation(self):
        import os
        inventory=inputs(artifact());binding=observe(inventory);seeds=selected(inventory,[aid()])
        reference=resolve_strong_closure(seeds,binding).observation_sha256
        with patch.dict(os.environ,{'LANG':'tr_TR.UTF-8','LC_ALL':'ar_EG.UTF-8','TZ':'Pacific/Auckland'}):
            self.assertEqual(resolve_strong_closure(seeds,binding).observation_sha256,reference)

    def test_recorded_weak_edge_is_not_falsely_called_a_boundary(self):
        inventory=inputs(artifact(relations=[edge('duplicates',aid(number=2))]),artifact(number=2))
        result=resolve_strong_closure(selected(inventory,[aid()]),observe(inventory))
        self.assertFalse(result.data['closure_complete'])
        self.assertNotIn('boundary_references',result.data)
        self.assertEqual(result.pending_weak_relations,((aid(),rid(),aid(number=2)),))

    def test_portable_module_and_zipapp_execute_real_strong_closure(self):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory);built=base/'built';build_distribution(built);moved=base/'moved';built.rename(moved)
            code='''
import sys
sys.path.insert(0,sys.argv[1])
from specroad.graph.scope_inputs import ScopeSeedInputs,ScopeResource
from specroad.graph.closure_inputs import ClosureBindings,resource_node
from specroad.graph.scope_descriptors import ScopeDescriptor
from specroad.graph.scope_seeds import resolve_scope_seeds
from specroad.graph.strong_closure import resolve_strong_closure
from specroad.model.configuration import ProjectConfiguration
import json
inventory=ScopeSeedInputs(ProjectConfiguration(json.loads(sys.argv[2])),[],[ScopeResource('p','profile','a'*64,'1'),ScopeResource('r','rule','b'*64,'2')])
desc=ScopeDescriptor({'scope_version':'scope-v1','scope_kind':'explicit','selector':{'artifact_ids':[],'resource_ids':['p']},'configuration_id':None,'closure_profile':'core-closure-v1','boundary_policy':'closed'})
binding=ClosureBindings(inventory,uses={resource_node('p'):(resource_node('r'),),resource_node('r'):()},current_reviews={})
result=resolve_strong_closure(resolve_scope_seeds(desc,inventory),binding)
assert result.resource_ids==('p','r') and not result.closure_complete
'''
            from support.model import configuration_value
            for distribution in (moved/'module',moved/'specroad.pyz'):
                proc=subprocess.run([sys.executable,'-I','-S','-B','-c',code,str(distribution),json.dumps(configuration_value())],
                                    stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,check=False)
                self.assertEqual(proc.returncode,0,proc.stderr.decode())
