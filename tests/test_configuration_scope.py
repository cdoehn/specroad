"""Configured seed selection, dependency admission and semantic scope bindings."""
from dataclasses import replace
import unittest

from specroad.configurations import resolve_configuration
from specroad.graph.closure_inputs import artifact_node
from specroad.graph.scope_admission import ScopeConfigurationDependencyError, ScopeControlDependencyError
from specroad.graph.scope_closure import resolve_scope_closure
from specroad.graph.scope_descriptors import ScopeDescriptor
from specroad.graph.scope_hash import fingerprint_scope
from specroad.graph.scope_inputs import ScopeResource
from specroad.graph.scope_seeds import resolve_scope_seeds
from specroad.graph.strong_closure import resolve_strong_closure
from specroad.model.canonical import canonical_json_sha256
from specroad.model.configuration import ProjectConfiguration
from specroad.model.errors import ModelError
from specroad.model.model_manifest import ProjectReadBinding
from support.closure import observe
from support.model import configuration_value
from support.records import record_value
from support.relations import aid, artifact, edge, rid
from support.scopes import descriptor, inputs, query
from support.srx import binary, expression_document, field, literal


def configuration(number=1, **changes):
    return record_value('configuration', id=aid('configuration', number), name='Variant ' + str(number), **changes)


def condition(platform):
    return expression_document(binary('eq', field('/effective_values/platform', 'configuration'), literal(platform)))


def seeds(inventory, identities=None, *, kind='explicit', selector=None, policy='closed', wrapper=False,
          configuration_id=aid('configuration')):
    if selector is None:
        selector = {'artifact_ids': sorted([aid()] if identities is None else identities), 'resource_ids': []} if kind == 'explicit' else {}
    value = descriptor(kind, selector, boundary_policy=policy, configuration_id=configuration_id)
    if wrapper:
        base = descriptor(kind, selector, boundary_policy=policy)
        value = descriptor('configuration', {'base_scope_descriptor': base}, boundary_policy=policy,
                           configuration_id=configuration_id)
    return resolve_scope_seeds(ScopeDescriptor(value), inventory)


def fingerprint(inventory, *, project=None):
    selected = seeds(inventory)
    bindings = observe(inventory)
    closure = resolve_scope_closure(selected, bindings)
    config = ProjectConfiguration(configuration_value() if project is None else project)
    return fingerprint_scope(config, ProjectReadBinding(config.project_id, '/owned/synthetic', (1, 2)),
                             closure, bindings, effective_profile={})


class ConfigurationScopeWorkTests(unittest.TestCase):
    def test_explicit_seeds_include_unconditional_and_matching_artifacts(self):
        inventory = inputs(configuration(), artifact(), artifact(number=2, applicability=condition('linux')),
                           artifact(number=3, applicability=condition('windows')))
        self.assertEqual(seeds(inventory, [aid(), aid(number=2), aid(number=3)]).artifact_ids,
                         (aid(), aid(number=2)))

    def test_unselected_configuration_keeps_conditional_artifacts_as_potential_members(self):
        inventory = inputs(artifact(applicability=condition('windows')))
        self.assertEqual(seeds(inventory, configuration_id=None).artifact_ids, (aid(),))

    def test_parent_selection_is_applied_before_seeds(self):
        root = configuration()
        child = configuration(2, parent=root['id'], dimensions=[], selection={'platform': 'windows'})
        inventory = inputs(root, child, artifact(applicability=condition('windows')))
        self.assertEqual(seeds(inventory, configuration_id=child['id']).artifact_ids, (aid(),))

    def test_configuration_wrapper_filters_its_base_seeds(self):
        inventory = inputs(configuration(), artifact(applicability=condition('windows')),
                           artifact(number=2, applicability=condition('linux')))
        result = seeds(inventory, [aid(), aid(number=2)], wrapper=True)
        self.assertEqual(result.artifact_ids, (aid(number=2),))
        self.assertEqual(result.descriptor.scope_kind, 'configuration')

    def test_specification_keeps_permanent_control_exclusions(self):
        inventory = inputs(configuration(), artifact(), artifact('proposal'), artifact('baseline'),
                           artifact(number=2, applicability=condition('windows')))
        result = seeds(inventory, kind='specification')
        self.assertEqual(set(result.artifact_ids), {aid('configuration'), aid()})

    def test_specification_wrapper_keeps_permanent_control_exclusions(self):
        inventory = inputs(configuration(), artifact(), artifact('proposal'), artifact('baseline'))
        self.assertEqual(set(seeds(inventory, kind='specification', wrapper=True).artifact_ids),
                         {aid('configuration'), aid()})

    def test_excluded_project_baseline_does_not_require_or_add_its_archive(self):
        archive = ScopeResource('archive:one', 'archive', 'a' * 64)
        inventory = inputs(configuration(), artifact(), artifact('baseline', applicability=condition('windows')),
                           resources=[archive])
        result = seeds(inventory, kind='project')
        self.assertNotIn(aid('baseline'), result.artifact_ids)
        self.assertEqual(result.resource_ids, ())

    def test_selected_project_baseline_still_requires_archive_inventory(self):
        inventory = inputs(configuration(), artifact('baseline', applicability=condition('linux')))
        with self.assertRaises(ModelError) as caught:
            seeds(inventory, kind='project')
        self.assertEqual(caught.exception.reason, 'scope_baseline_archive_inventory_required')

    def test_excluded_document_seed_does_not_traverse_contains(self):
        document = artifact('document', applicability=condition('windows'),
                            relations=[edge('contains', aid('section'))])
        inventory = inputs(configuration(), document, artifact('section'))
        selected = seeds(inventory, kind='document', selector={'document_id': document['id']})
        self.assertEqual(selected.artifact_ids, ())
        result = resolve_scope_closure(selected, observe(inventory))
        self.assertEqual(result.artifact_ids, ())

    def test_release_candidates_are_filtered_before_closure(self):
        release = artifact('release')
        included = artifact(relations=[edge('scheduled_for', release['id'])], applicability=condition('linux'))
        excluded = artifact(number=2, relations=[edge('scheduled_for', release['id'], number=2)],
                            applicability=condition('windows'))
        inventory = inputs(configuration(), release, included, excluded)
        selected = seeds(inventory, kind='release', selector={'release_id': release['id']})
        self.assertEqual(set(selected.artifact_ids), {release['id'], included['id']})

    def test_applicable_strong_dependency_is_admitted(self):
        inventory = inputs(configuration(), artifact(relations=[edge('depends_on', aid(number=2))]),
                           artifact(number=2, applicability=condition('linux')))
        result = resolve_scope_closure(seeds(inventory), observe(inventory))
        self.assertEqual(result.artifact_ids, (aid(), aid(number=2)))

    def test_excluded_strong_target_is_a_configuration_error_for_both_policies(self):
        inventory = inputs(configuration(), artifact(relations=[edge('depends_on', aid(number=2))]),
                           artifact(number=2, applicability=condition('windows')))
        for policy in ('closed', 'partial'):
            with self.subTest(policy=policy), self.assertRaises(ScopeConfigurationDependencyError) as caught:
                resolve_scope_closure(seeds(inventory, policy=policy), observe(inventory))
            self.assertEqual(caught.exception.code, 'SRV141')
            self.assertEqual(caught.exception.exit_code, 3)
            self.assertEqual(caught.exception.source_id, aid())
            self.assertEqual(caught.exception.target_id, aid(number=2))
            self.assertEqual(caught.exception.relation_id, rid())
            self.assertEqual(caught.exception.configuration_id, aid('configuration'))

    def test_strong_only_walker_has_the_same_configuration_admission(self):
        inventory = inputs(configuration(), artifact(relations=[edge('depends_on', aid(number=2))]),
                           artifact(number=2, applicability=condition('windows')))
        with self.assertRaises(ScopeConfigurationDependencyError):
            resolve_strong_closure(seeds(inventory), observe(inventory))

    def test_excluded_evidence_subject_is_a_required_resource_error(self):
        from support.closure import subject
        evidence = record_value('evidence', id=aid('evidence'), subjects=[subject(aid())])
        inventory = inputs(configuration(), evidence, artifact(applicability=condition('windows')))
        with self.assertRaises(ScopeConfigurationDependencyError) as caught:
            resolve_scope_closure(seeds(inventory, [evidence['id']]), observe(inventory))
        self.assertEqual(caught.exception.source_id, evidence['id'])
        self.assertEqual(caught.exception.pointer, '/subjects/0/artifact_id')

    def test_permanent_control_dependency_guard_is_preserved(self):
        inventory = inputs(configuration(), artifact('content_block', relations=[edge('references', aid('proposal'))]),
                           artifact('proposal'))
        with self.assertRaises(ScopeControlDependencyError):
            resolve_scope_closure(seeds(inventory, kind='specification', wrapper=True), observe(inventory))

    def test_excluded_unused_artifact_requires_no_usage_observation(self):
        excluded = artifact(number=2, applicability=condition('windows'))
        inventory = inputs(configuration(), artifact(), excluded)
        binding = observe(inventory)
        from specroad.graph.closure_inputs import ClosureBindings
        uses = dict(binding.uses); del uses[artifact_node(excluded['id'])]
        binding = ClosureBindings(inventory, uses=uses, current_reviews=dict(binding.current_reviews))
        result = resolve_scope_closure(seeds(inventory, [aid(), excluded['id']]), binding)
        self.assertEqual(result.artifact_ids, (aid(),))

    def test_invalid_condition_is_not_an_excluded_seed(self):
        inventory = inputs(configuration(), artifact(applicability=expression_document(literal('false'))))
        with self.assertRaises(ModelError) as caught:
            seeds(inventory)
        self.assertEqual(caught.exception.reason, 'invalid_applicability')

    def test_missing_selected_configuration_is_not_an_empty_scope(self):
        with self.assertRaises(ModelError) as caught:
            seeds(inputs(artifact()))
        self.assertEqual(caught.exception.reason, 'scope_configuration_missing')

    def test_forged_seed_membership_cannot_restore_an_excluded_artifact(self):
        inventory = inputs(configuration(), artifact(applicability=condition('windows')))
        forged = replace(seeds(inventory), artifact_ids=(aid(),))
        with self.assertRaises(ModelError) as caught:
            resolve_scope_closure(forged, observe(inventory))
        self.assertEqual(caught.exception.reason, 'closure_seed_selection_mismatch')

    def test_forged_configuration_binding_is_recomputed(self):
        inventory = inputs(configuration(), artifact())
        forged = replace(seeds(inventory), configuration_sha256='a' * 64)
        with self.assertRaises(ModelError) as caught:
            resolve_scope_closure(forged, observe(inventory))
        self.assertEqual(caught.exception.reason, 'closure_seed_selection_mismatch')

    def test_scope_configuration_binding_includes_project_and_selected_chain(self):
        inventory = inputs(configuration(), artifact())
        selected = resolve_configuration(inventory.records, aid('configuration'))
        expected = canonical_json_sha256({'project_configuration_sha256': inventory.configuration_sha256,
                                          'selected_configuration_sha256': selected.sha256})
        self.assertEqual(seeds(inventory).configuration_sha256, expected)
        self.assertEqual(fingerprint(inventory).data['configuration_sha256'], expected)

    def test_scope_hash_changes_when_selected_configuration_revision_changes(self):
        self.assertNotEqual(fingerprint(inputs(configuration(), artifact())).sha256,
                            fingerprint(inputs(configuration(revision=2), artifact())).sha256)

    def test_scope_hash_binds_semantic_project_policy_with_selected_configuration(self):
        first = inputs(configuration(), artifact())
        changed = configuration_value(profiles=['safety@1.0.0'])
        second = inputs(configuration(), artifact(), configuration=changed)
        self.assertNotEqual(fingerprint(first).sha256, fingerprint(second, project=changed).sha256)

    def test_unselected_configuration_outside_explicit_scope_does_not_change_hash(self):
        first = inputs(configuration(), configuration(2), artifact())
        second = inputs(configuration(), configuration(2, revision=2), artifact())
        self.assertEqual(fingerprint(first).sha256, fingerprint(second).sha256)

    def test_reordering_supplied_sources_does_not_change_scope_hash(self):
        values = [configuration(), artifact()]
        self.assertEqual(fingerprint(inputs(*values)).sha256, fingerprint(inputs(*reversed(values))).sha256)

    def test_query_configuration_remains_explicitly_blocked_until_page_adapter_integration(self):
        inventory = inputs(configuration(), artifact())
        for wrapper in (False, True):
            with self.subTest(wrapper=wrapper), self.assertRaises(ModelError) as caught:
                seeds(inventory, kind='query', selector={'query': query()}, wrapper=wrapper)
            self.assertEqual(caught.exception.reason, 'configured_query_resolver_required')

    def test_resolution_preserves_all_original_artifact_bytes(self):
        inventory = inputs(configuration(), artifact())
        before = [record.source_bytes for record in inventory.records]
        resolve_scope_closure(seeds(inventory), observe(inventory))
        self.assertEqual([record.source_bytes for record in inventory.records], before)
