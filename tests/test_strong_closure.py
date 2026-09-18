"""Strong fixed-point membership and mandatory passive bindings, no UI or docs."""
from dataclasses import FrozenInstanceError
from unittest.mock import patch
import unittest

from specroad.graph.closure_inputs import ClosureBindings, artifact_node as A, resource_node as R
from specroad.graph.scope_inputs import ScopeResource
from specroad.graph.strong_closure import resolve_strong_closure
from specroad.model.attachments import AttachmentDescriptor
from specroad.model.errors import ModelError
from support.closure import source, observe, selected, subject, slot
from support.relations import artifact, aid, edge, rid
from support.scopes import inputs, descriptor


class StrongClosureTests(unittest.TestCase):
    def test_transitive_dependencies_include_all_required_targets(self):
        inventory = inputs(artifact(relations=[edge('depends_on', aid(number=2))]),
                           artifact(number=2, relations=[edge('refines', aid(number=3), number=2)]),
                           artifact(number=3), artifact(number=4))
        result = resolve_strong_closure(selected(inventory, [aid()]), observe(inventory))
        self.assertEqual(result.artifact_ids, tuple(aid(number=n) for n in (1, 2, 3)))

    def test_seed_with_no_dependencies_is_preserved(self):
        inventory = inputs(artifact())
        self.assertEqual(resolve_strong_closure(selected(inventory, [aid()]), observe(inventory)).artifact_ids, (aid(),))

    def test_empty_seed_has_empty_fixed_point(self):
        inventory = inputs(artifact())
        result = resolve_strong_closure(selected(inventory), observe(inventory))
        self.assertEqual((result.artifact_ids, result.resource_ids, result.processing_order), ((), (), ()))

    def test_converging_dependency_paths_do_not_duplicate_targets(self):
        inventory = inputs(artifact(relations=[edge('depends_on', aid(number=2)), edge('refines', aid(number=3), number=2)]),
                           artifact(number=2, relations=[edge('refines', aid(number=4), number=3)]),
                           artifact(number=3, relations=[edge('depends_on', aid(number=4), number=4)]), artifact(number=4))
        result = resolve_strong_closure(selected(inventory, [aid()]), observe(inventory))
        self.assertEqual(len(result.artifact_ids), 4)
        self.assertEqual(len(result.processing_order), 4)

    def test_depends_on_cycle_terminates_without_discarding_members(self):
        inventory = inputs(artifact(relations=[edge('depends_on', aid(number=2))]),
                           artifact(number=2, relations=[edge('depends_on', aid(), number=2)]))
        result = resolve_strong_closure(selected(inventory, [aid()]), observe(inventory))
        self.assertEqual(set(result.artifact_ids), {aid(), aid(number=2)})
        self.assertEqual(len(result.processing_order), 2)

    def test_unreachable_nodes_are_not_added(self):
        inventory = inputs(*(artifact(number=n) for n in range(1, 5)))
        result = resolve_strong_closure(selected(inventory, [aid(number=2)]), observe(inventory))
        self.assertEqual(result.artifact_ids, (aid(number=2),))

    def test_rejected_and_retired_targets_are_not_filtered_out(self):
        inventory = inputs(artifact(relations=[edge('depends_on', aid(number=2)), edge('refines', aid(number=3), number=2)]),
                           artifact(number=2, maturity='retired'), artifact(number=3, maturity='rejected'))
        self.assertEqual(len(resolve_strong_closure(selected(inventory, [aid()]), observe(inventory)).artifact_ids), 3)

    def test_contains_expands_document_sections_and_blocks(self):
        inventory = inputs(artifact('document', relations=[edge('contains', aid('section'))]),
                           artifact('section', relations=[edge('contains', aid('content_block'), number=2)]), artifact('content_block'))
        seeds = selected(inventory, kind='document', selector={'document_id': aid('document')})
        result = resolve_strong_closure(seeds, observe(inventory))
        self.assertEqual(set(result.artifact_ids), {aid('document'), aid('section'), aid('content_block')})

    def test_weak_edges_are_exposed_as_unresolved_not_strongly_followed(self):
        inventory = inputs(artifact(relations=[edge('conflicts_with', aid(number=2))]), artifact(number=2))
        result = resolve_strong_closure(selected(inventory, [aid()]), observe(inventory))
        self.assertEqual(result.artifact_ids, (aid(),))
        self.assertEqual(result.pending_weak_relations, ((aid(), rid(), aid(number=2)),))
        self.assertFalse(result.closure_complete)

    def test_used_profiles_rules_and_mappings_expand_transitively(self):
        resources = [ScopeResource('profile:p@1', 'profile', 'a'*64, '1'),
                     ScopeResource('rule:r@2', 'rule', 'b'*64, '2'), ScopeResource('mapping:m@3', 'mapping', 'c'*64, '3')]
        inventory = inputs(artifact(), resources=resources)
        uses = {A(aid()): [R(resources[0].resource_id)], R(resources[0].resource_id): [R(resources[1].resource_id)],
                R(resources[1].resource_id): [R(resources[2].resource_id)]}
        result = resolve_strong_closure(selected(inventory, [aid()]), observe(inventory, uses=uses))
        self.assertEqual(set(result.resource_ids), {resource.resource_id for resource in resources})

    def test_inactive_but_used_resource_is_still_required(self):
        resource = ScopeResource('profile:p@1', 'profile', 'a'*64, '1', False)
        inventory = inputs(artifact(), resources=[resource])
        result = resolve_strong_closure(selected(inventory, [aid()]), observe(inventory, uses={A(aid()): [R(resource.resource_id)]}))
        self.assertEqual(result.resource_ids, (resource.resource_id,))

    def test_shared_resource_is_included_once(self):
        resource = ScopeResource('rule:r@1', 'rule', 'a'*64, '1')
        inventory = inputs(artifact(), artifact(number=2), resources=[resource])
        result = resolve_strong_closure(selected(inventory, [aid(), aid(number=2)]),
            observe(inventory, uses={A(aid()): [R(resource.resource_id)], A(aid(number=2)): [R(resource.resource_id)]}))
        self.assertEqual(result.resource_ids, (resource.resource_id,))

    def test_resource_cycles_reach_a_finite_fixed_point(self):
        a, b = [ScopeResource('profile:'+name, 'profile', 'a'*64, '1') for name in ('a', 'b')]
        inventory = inputs(resources=[a, b])
        result = resolve_strong_closure(selected(inventory, resource_ids=[a.resource_id]),
            observe(inventory, uses={R(a.resource_id): [R(b.resource_id)], R(b.resource_id): [R(a.resource_id)]}))
        self.assertEqual(result.resource_ids, (a.resource_id, b.resource_id))

    def test_evidence_subjects_are_mandatory_dependencies(self):
        evidence = source('evidence', subjects=[subject(aid())])
        inventory = inputs(evidence, artifact())
        result = resolve_strong_closure(selected(inventory, [evidence['id']]), observe(inventory))
        self.assertEqual(set(result.artifact_ids), {aid(), evidence['id']})

    def test_historical_evidence_hash_does_not_discard_subject(self):
        evidence = source('evidence', subjects=[subject(aid())])
        inventory = inputs(evidence, artifact(revision=17))
        self.assertIn(aid(), resolve_strong_closure(selected(inventory, [evidence['id']]), observe(inventory)).artifact_ids)

    def test_contract_slot_includes_test_and_its_strong_dependencies(self):
        contract = source('verification', evidence_slots=[slot(aid('test'))])
        test = artifact('test', relations=[edge('references', aid())])
        inventory = inputs(contract, test, artifact())
        result = resolve_strong_closure(selected(inventory, [contract['id']]), observe(inventory))
        self.assertEqual(set(result.artifact_ids), {contract['id'], test['id'], aid()})

    def test_manual_slot_without_test_does_not_invent_one(self):
        contract = source('verification', evidence_slots=[slot()]); inventory = inputs(contract)
        result = resolve_strong_closure(selected(inventory, [contract['id']]), observe(inventory))
        self.assertEqual(result.artifact_ids, (contract['id'],))

    def test_current_reviews_selected_for_contained_relation_are_included(self):
        review = source('relation_review', relation_id=rid())
        inventory = inputs(artifact(relations=[edge('depends_on', aid(number=2))]), artifact(number=2), review)
        result = resolve_strong_closure(selected(inventory, [aid()]), observe(inventory, reviews={rid(): [review['id']]}))
        self.assertIn(review['id'], result.artifact_ids)

    def test_persisted_review_not_selected_current_is_not_implicitly_added(self):
        review = source('relation_review', relation_id=rid())
        inventory = inputs(artifact(relations=[edge('depends_on', aid(number=2))]), artifact(number=2), review)
        result = resolve_strong_closure(selected(inventory, [aid()]), observe(inventory))
        self.assertNotIn(review['id'], result.artifact_ids)

    def test_referenced_attachment_uses_exact_observed_descriptor(self):
        attachment = AttachmentDescriptor('attachments/proof.bin', 'application/octet-stream', 4, 'a'*64)
        resource = ScopeResource('attachment:proof', 'attachment', 'a'*64)
        evidence = source('evidence', subjects=[subject(aid())], attachments=[attachment.data])
        inventory = inputs(evidence, artifact(), resources=[resource])
        result = resolve_strong_closure(selected(inventory, [evidence['id']]),
                                       observe(inventory, attachments={resource.resource_id: attachment}))
        self.assertEqual(result.attachments, (attachment,)); self.assertEqual(result.resource_ids, (resource.resource_id,))

    def test_baseline_in_project_requires_bound_archive_objects(self):
        archive = ScopeResource('archive:object', 'archive', 'c'*64)
        baseline = source('baseline')
        inventory = inputs(baseline, resources=[archive], archive_bindings={baseline['id']: [archive.resource_id]})
        result = resolve_strong_closure(selected(inventory, [baseline['id']]), observe(inventory))
        self.assertEqual(result.resource_ids, (archive.resource_id,))

    def test_specification_control_reached_by_strong_edge_is_not_silent_success(self):
        inventory = inputs(artifact('content_block', relations=[edge('references', aid('proposal'))]), artifact('proposal'))
        with self.assertRaises(ModelError) as raised:
            resolve_strong_closure(selected(inventory, kind='specification'), observe(inventory))
        self.assertEqual(raised.exception.reason, 'scope_control_dependency')

    def test_missing_usage_observation_is_not_assumed_empty(self):
        inventory = inputs(artifact())
        with self.assertRaises(ModelError) as raised:
            resolve_strong_closure(selected(inventory, [aid()]), ClosureBindings(inventory, uses={}, current_reviews={}))
        self.assertEqual(raised.exception.reason, 'closure_usage_observation_missing')

    def test_missing_review_observation_is_not_assumed_no_current_reviews(self):
        inventory = inputs(artifact(relations=[edge('depends_on', aid(number=2))]), artifact(number=2))
        binding = ClosureBindings(inventory, uses={A(aid()): (), A(aid(number=2)): ()}, current_reviews={})
        with self.assertRaises(ModelError) as raised: resolve_strong_closure(selected(inventory, [aid()]), binding)
        self.assertEqual(raised.exception.reason, 'closure_review_observation_missing')

    def test_missing_transitive_resource_is_rejected(self):
        inventory = inputs(artifact())
        with self.assertRaises(ModelError): observe(inventory, uses={A(aid()): [R('not-present')]})

    def test_missing_evidence_subject_fails_instead_of_partial_result(self):
        evidence = source('evidence', subjects=[subject(aid())]); inventory = inputs(evidence)
        with self.assertRaises(ModelError) as raised: resolve_strong_closure(selected(inventory, [evidence['id']]), observe(inventory))
        self.assertEqual(raised.exception.reason, 'closure_bound_artifact_missing')

    def test_changed_inventory_invalidates_previous_seeds(self):
        old, new = inputs(artifact()), inputs(artifact(title='changed'))
        with self.assertRaises(ModelError) as raised: resolve_strong_closure(selected(old, [aid()]), observe(new))
        self.assertEqual(raised.exception.reason, 'stale_closure_seed_inputs')

    def test_binding_observations_are_owned_and_immutable(self):
        resource = ScopeResource('r', 'rule', 'a'*64, '1'); inventory = inputs(artifact(), resources=[resource])
        targets = [R('r')]; binding = observe(inventory, uses={A(aid()): targets}); fingerprint = binding.fingerprint
        targets.clear()
        self.assertEqual(binding.uses[A(aid())], (R('r'),)); self.assertEqual(binding.fingerprint, fingerprint)
        with self.assertRaises(TypeError): binding.uses[A(aid())] = ()
        with self.assertRaises(FrozenInstanceError): binding.fingerprint = '0'*64

    def test_extension_strings_are_not_interpreted_as_links_or_code(self):
        inventory = inputs(artifact(extensions={'org.example': {'subjects': [aid(number=99)], 'path': '/tmp/secret', 'shell': 'false'}}))
        binding = observe(inventory); seeds = selected(inventory, [aid()])
        with patch('builtins.open', side_effect=AssertionError('no filesystem loading')):
            result = resolve_strong_closure(seeds, binding)
        self.assertEqual(result.artifact_ids, (aid(),)); self.assertEqual(result.resource_ids, ())

    def test_no_full_scope_approval_or_atomic_snapshot_is_claimed(self):
        inventory = inputs(artifact()); result = resolve_strong_closure(selected(inventory, [aid()]), observe(inventory))
        self.assertTrue(result.strong_closure_complete); self.assertFalse(result.closure_complete)
        self.assertFalse(result.atomic_snapshot)
        self.assertEqual(result.validation_scope, 'strong_closure_over_supplied_bindings')
        self.assertEqual(result.seeds.inputs_sha256, inventory.fingerprint)
