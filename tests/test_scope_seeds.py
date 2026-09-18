"""Seed membership, selector contracts and exact input bindings; no presentation."""
from dataclasses import FrozenInstanceError
import unittest

from specroad.graph.scope_descriptors import ScopeDescriptor
from specroad.graph.scope_inputs import ScopeResource, ScopeSeedInputs
from specroad.graph.scope_seeds import QuerySeedPage, resolve_scope_seeds
from specroad.model.errors import ModelError
from support.relations import artifact, aid, edge
from support.scopes import descriptor, query, inputs


def select(value, inventory, **options):
    return resolve_scope_seeds(ScopeDescriptor(value), inventory, **options)


class ScopeSeedTests(unittest.TestCase):
    def test_specification_excludes_both_control_types(self):
        inventory = inputs(artifact(), artifact('proposal'), artifact('baseline'))
        self.assertEqual(select(descriptor(), inventory).artifact_ids, (aid(),))

    def test_project_includes_controls_with_explicit_archive_inventory(self):
        archive = ScopeResource('archive:one', 'archive', 'a' * 64)
        inventory = inputs(artifact(), artifact('proposal'), artifact('baseline'), resources=[archive],
                           archive_bindings={aid('baseline'): ['archive:one']})
        result = select(descriptor('project'), inventory)
        self.assertEqual(set(result.artifact_ids), {aid(), aid('proposal'), aid('baseline')})
        self.assertEqual(result.resource_ids, ('archive:one',))

    def test_project_never_assumes_missing_baseline_inventory_empty(self):
        with self.assertRaises(ModelError): select(descriptor('project'), inputs(artifact('baseline')))

    def test_specification_uses_only_active_profiles_rules_mappings(self):
        active = [ScopeResource(kind + ':one@1', kind, 'a'*64, '1', True) for kind in ('profile','rule','mapping')]
        inactive = ScopeResource('profile:off@1', 'profile', 'b'*64, '1', False)
        result = select(descriptor(), inputs(artifact(), resources=active + [inactive]))
        self.assertEqual(set(result.resource_ids), {r.resource_id for r in active})
        self.assertIsNotNone(result.configuration_sha256)

    def test_project_uses_inactive_current_resources_too(self):
        resource = ScopeResource('profile:off@1','profile','b'*64,'1')
        self.assertEqual(select(descriptor('project'), inputs(resources=[resource])).resource_ids, (resource.resource_id,))

    def test_non_normative_operational_resources_rejected(self):
        for kind in ('cache', 'lock', 'journal', 'receipt', 'generated'):
            with self.subTest(kind=kind), self.assertRaises(ModelError): ScopeResource('x', kind, 'a'*64)

    def test_document_starts_only_at_document_before_contains_closure(self):
        doc = artifact('document', relations=[edge('contains', aid('section'))])
        result = select(descriptor('document', {'document_id': aid('document')}), inputs(doc, artifact('section')))
        self.assertEqual(result.artifact_ids, (aid('document'),)); self.assertFalse(result.closure_complete)

    def test_release_uses_incoming_planning_memberships(self):
        release = artifact('release')
        milestone = artifact('milestone', relations=[edge('part_of', release['id'], number=1)])
        requirement = artifact(relations=[edge('scheduled_for', milestone['id'], number=2)])
        task = artifact('task', relations=[edge('part_of', release['id'], number=3)])
        outsider = artifact(number=99)
        result = select(descriptor('release', {'release_id': release['id']}), inputs(task, outsider, requirement, milestone, release))
        self.assertEqual(set(result.artifact_ids), {release['id'],milestone['id'],requirement['id'],task['id']})

    def test_release_does_not_expand_requirement_dependencies(self):
        release = artifact('release'); other = artifact(number=2)
        scheduled = artifact(relations=[edge('scheduled_for',release['id']), edge('depends_on',other['id'],number=2)])
        result = select(descriptor('release', {'release_id': release['id']}), inputs(release,scheduled,other))
        self.assertNotIn(other['id'],result.artifact_ids)

    def test_explicit_keeps_exact_two_membership_sets(self):
        resource = ScopeResource('resource:x','attachment','c'*64)
        result = select(descriptor('explicit',{'artifact_ids':[aid()], 'resource_ids':['resource:x']}),
                        inputs(artifact(),artifact(number=2),resources=[resource]))
        self.assertEqual(result.artifact_ids,(aid(),));self.assertEqual(result.resource_ids,('resource:x',))
        self.assertIsNone(result.configuration_sha256)

    def test_empty_explicit_set_is_valid(self):
        result = select(descriptor('explicit', {'artifact_ids':[],'resource_ids':[]}), inputs(artifact()))
        self.assertEqual(result.artifact_ids,());self.assertEqual(result.resource_ids,())

    def test_missing_explicit_resource_rejected(self):
        with self.assertRaises(ModelError): select(descriptor('explicit',{'artifact_ids':[],'resource_ids':['absent']}),inputs())

    def test_unknown_document_or_release_is_not_an_empty_success(self):
        for kind in ('document','release'):
            with self.subTest(kind=kind), self.assertRaises(ModelError):
                select(descriptor(kind,{kind+'_id':aid(kind)}),inputs())

    def test_wrong_typed_selector_rejected(self):
        with self.assertRaises(ModelError): ScopeDescriptor(descriptor('release',{'release_id':aid('document')}))

    def test_unknown_top_level_and_selector_fields_rejected(self):
        for value in (descriptor(extra=True), descriptor(selector={'hidden':True})):
            with self.assertRaises(ModelError): ScopeDescriptor(value)

    def test_missing_version_is_not_filled(self):
        value=descriptor();del value['scope_version']
        with self.assertRaises(ModelError):ScopeDescriptor(value)

    def test_unknown_versions_and_boundary_modes_rejected(self):
        for field,value in [('scope_version','scope-v2'),('closure_profile','all'),('boundary_policy','best-effort')]:
            with self.subTest(field=field),self.assertRaises(ModelError):ScopeDescriptor(descriptor(**{field:value}))

    def test_descriptor_is_immutable_and_returns_owned_data(self):
        raw=descriptor();value=ScopeDescriptor(raw);raw['selector']['x']=1
        data=value.data;data['selector']['y']=2
        self.assertEqual(value.data['selector'],{})
        with self.assertRaises(FrozenInstanceError):value._encoded=b'changed'

    def test_descriptor_hash_ignores_object_key_order(self):
        raw=descriptor();self.assertEqual(ScopeDescriptor(raw).sha256,ScopeDescriptor(dict(reversed(list(raw.items())))).sha256)

    def test_descriptor_hash_includes_boundary_policy(self):
        self.assertNotEqual(ScopeDescriptor(descriptor()).sha256,ScopeDescriptor(descriptor(boundary_policy='partial')).sha256)

    def test_seed_order_and_inventory_binding_ignore_source_enumeration_order(self):
        values=[artifact(number=n) for n in (6,2,4)]
        left,right=inputs(*values),inputs(*reversed(values))
        self.assertEqual(left.fingerprint,right.fingerprint)
        self.assertEqual(select(descriptor(),left),select(descriptor(),right))

    def test_retired_and_rejected_seeds_are_not_dropped(self):
        inventory=inputs(artifact(maturity='retired'),artifact(number=2,maturity='rejected'))
        self.assertEqual(len(select(descriptor(),inventory).artifact_ids),2)

    def test_duplicate_artifact_inputs_fail(self):
        with self.assertRaises(ModelError):inputs(artifact(),artifact())

    def test_unconfigured_query_requires_actual_bound_page(self):
        with self.assertRaises(ModelError):select(descriptor('query',{'query':query()}),inputs())

    def test_query_preserves_page_order_without_repagination(self):
        desc=ScopeDescriptor(descriptor('query',{'query':query(offset=1,limit=2)}));inventory=inputs(*(artifact(number=n) for n in (1,2,3)))
        page=QuerySeedPage(desc,inventory,[aid(number=3),aid(number=1)],total=3)
        result=resolve_scope_seeds(desc,inventory,query_page=page)
        self.assertEqual(result.artifact_ids,(aid(number=3),aid(number=1)))
        self.assertEqual(result.canonical_artifact_ids,tuple(sorted(result.artifact_ids)))

    def test_query_limit_zero_has_no_items(self):
        desc=ScopeDescriptor(descriptor('query',{'query':query(limit=0)}));inventory=inputs(artifact())
        page=QuerySeedPage(desc,inventory,[],total=1)
        self.assertEqual(resolve_scope_seeds(desc,inventory,query_page=page).artifact_ids,())

    def test_query_page_from_changed_source_rejected(self):
        desc=ScopeDescriptor(descriptor('query',{'query':query()}));a=inputs(artifact());b=inputs(artifact(title='changed'))
        page=QuerySeedPage(desc,a,[aid()],total=1)
        with self.assertRaises(ModelError):resolve_scope_seeds(desc,b,query_page=page)

    def test_query_page_from_other_selector_rejected(self):
        desc=ScopeDescriptor(descriptor('query',{'query':query()}));inventory=inputs(artifact())
        page=QuerySeedPage(desc,inventory,[aid()],total=1)
        other=ScopeDescriptor(descriptor('query',{'query':query(limit=1)}))
        with self.assertRaises(ModelError):resolve_scope_seeds(other,inventory,query_page=page)

    def test_query_page_missing_results_rejected(self):
        desc=ScopeDescriptor(descriptor('query',{'query':query()}))
        with self.assertRaises(ModelError):QuerySeedPage(desc,inputs(artifact()),[],total=1)

    def test_query_materializes_pagination_and_other_defaults(self):
        for field in query():
            raw=query();del raw[field]
            with self.subTest(field=field),self.assertRaises(ModelError):ScopeDescriptor(descriptor('query',{'query':raw}))

    def test_query_expression_binds_content_not_file_path(self):
        raw=query(srx_filters=[{'path':'/tmp/filter.json'}])
        with self.assertRaises(ModelError):ScopeDescriptor(descriptor('query',{'query':raw}))

    def test_seed_objects_do_not_claim_full_closure_or_project_approval(self):
        inventory=inputs();result=select(descriptor(),inventory)
        self.assertEqual(inventory.validation_scope,'supplied_seed_inventory_only')
        self.assertEqual(result.validation_scope,'seed_selection_only');self.assertFalse(result.closure_complete)

    def test_configured_scope_does_not_silently_ignore_filter(self):
        inventory=inputs(artifact('configuration'),artifact())
        with self.assertRaises(ModelError):select(descriptor(configuration_id=aid('configuration')),inventory)

    def test_inputs_do_not_mutate_raw_source_records(self):
        raw=artifact();original=repr(raw);inventory=inputs(raw);select(descriptor(),inventory)
        self.assertEqual(repr(raw),original)
