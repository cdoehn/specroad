"""Behavior of complete/partial dependency selection; no presentation or IO oracles."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
import unittest

from specroad.graph.boundaries import BoundaryReference, boundary_for_relation
from specroad.graph.closure_inputs import artifact_node as A, resource_node as R
from specroad.graph.scope_closure import resolve_scope_closure
from specroad.graph.scope_inputs import ScopeResource
from specroad.graph.strong_closure import resolve_strong_closure
from specroad.model.attachments import AttachmentDescriptor
from specroad.model.canonical import canonical_json_sha256
from specroad.model.errors import ModelError
from support.boundary import selection
from support.closure import observe, source, subject
from support.relations import artifact, aid, edge, rid
from support.scopes import inputs


def pair(kind='duplicates'):
    return inputs(artifact(relations=[edge(kind, aid(number=2))]), artifact(number=2))


class ScopeClosureTests(unittest.TestCase):
    def run_closure(self, inventory, identities=None, policy='partial', **options):
        seeds = selection(inventory, [aid()] if identities is None else identities, policy=policy)
        return resolve_scope_closure(seeds, observe(inventory, **options))

    def test_partial_records_all_seven_boundary_fields(self):
        inventory = pair()
        result = self.run_closure(inventory)
        self.assertEqual(result.artifact_ids, (aid(),))
        self.assertEqual(result.boundary_references[0].data, {
            'source_id': aid(), 'relation_id': rid(), 'relation_type': 'duplicates',
            'target_id': aid(number=2), 'target_type': 'requirement',
            'reason': 'boundary_policy_partial',
            'origin_target_sha256': canonical_json_sha256(inventory.records[1].data)})

    def test_closed_includes_weak_target_without_boundary(self):
        result = self.run_closure(pair(), policy='closed')
        self.assertEqual(set(result.artifact_ids), {aid(), aid(number=2)})
        self.assertEqual(result.boundary_references, ())

    def test_conflict_with_other_type_is_a_valid_boundary(self):
        inventory = inputs(artifact(relations=[edge('conflicts_with', aid('risk'))]), artifact('risk'))
        self.assertEqual(self.run_closure(inventory).boundary_references[0].data['target_type'], 'risk')

    def test_closed_continues_through_weak_and_strong_edges(self):
        inventory = inputs(artifact(relations=[edge('duplicates', aid(number=2))]),
            artifact(number=2, relations=[edge('depends_on', aid(number=3), number=2)]),
            artifact(number=3, relations=[edge('conflicts_with', aid(number=4), number=3)]), artifact(number=4))
        self.assertEqual(self.run_closure(inventory, policy='closed').artifact_ids,
                         tuple(aid(number=n) for n in range(1, 5)))

    def test_partial_does_not_expand_omitted_targets_outgoing_relations(self):
        inventory = inputs(artifact(relations=[edge('duplicates', aid(number=2))]),
            artifact(number=2, relations=[edge('depends_on', aid(number=3), number=2)]), artifact(number=3))
        result = self.run_closure(inventory)
        self.assertEqual(result.artifact_ids, (aid(),))
        self.assertEqual(len(result.boundary_references), 1)

    def test_closed_cycle_terminates_with_single_visits(self):
        inventory = inputs(artifact(relations=[edge('conflicts_with', aid(number=2))]),
            artifact(number=2, relations=[edge('depends_on', aid(), number=2)]))
        result = self.run_closure(inventory, policy='closed')
        self.assertEqual(set(result.artifact_ids), {aid(), aid(number=2)})
        self.assertEqual(len(result.processing_order), 2)

    def test_internal_weak_target_does_not_create_boundary(self):
        result = self.run_closure(pair(), identities=[aid(), aid(number=2)])
        self.assertEqual(result.boundary_references, ())

    def test_later_strong_reachability_makes_weak_edge_internal(self):
        inventory = inputs(artifact(relations=[edge('duplicates', aid(number=2)),
            edge('depends_on', aid(number=3), number=2)]), artifact(number=2),
            artifact(number=3, relations=[edge('depends_on', aid(number=2), number=3)]))
        result = self.run_closure(inventory)
        self.assertEqual(len(result.artifact_ids), 3)
        self.assertEqual(result.boundary_references, ())

    def test_distinct_edges_to_same_omitted_target_keep_both_ids(self):
        inventory = inputs(artifact(relations=[edge('duplicates', aid(number=3))]),
            artifact(number=2, relations=[edge('conflicts_with', aid(number=3), number=2)]), artifact(number=3))
        result = self.run_closure(inventory, identities=[aid(), aid(number=2)])
        self.assertEqual([b.data['relation_id'] for b in result.boundary_references], [rid(), rid(2)])

    def test_boundary_order_is_independent_of_input_relation_order(self):
        edges = [edge('duplicates', aid(number=3), number=2), edge('duplicates', aid(number=2))]
        one = inputs(artifact(relations=edges), artifact(number=2), artifact(number=3))
        two = inputs(artifact(number=3), artifact(number=2), artifact(relations=list(reversed(edges))))
        self.assertEqual(self.run_closure(one).boundary_references, self.run_closure(two).boundary_references)

    def test_empty_selection_is_empty(self):
        result = self.run_closure(pair(), identities=[])
        self.assertEqual((result.artifact_ids, result.resource_ids, result.boundary_references), ((), (), ()))

    def test_project_scope_has_no_artificial_boundaries_between_included_nodes(self):
        inventory = pair()
        seeds = selection(inventory, kind='project')
        result = resolve_scope_closure(seeds, observe(inventory))
        self.assertEqual(len(result.artifact_ids), 2)
        self.assertEqual(result.boundary_references, ())

    def test_closed_includes_resources_used_by_weak_target(self):
        resource = ScopeResource('rule:r', 'rule', 'a'*64, '1')
        inventory = inputs(artifact(relations=[edge('duplicates', aid(number=2))]), artifact(number=2), resources=[resource])
        result = self.run_closure(inventory, policy='closed', uses={A(aid(number=2)): [R(resource.resource_id)]})
        self.assertEqual(result.resource_ids, (resource.resource_id,))

    def test_current_review_of_partial_edge_is_still_mandatory(self):
        review = source('relation_review', relation_id=rid())
        inventory = inputs(artifact(relations=[edge('duplicates', aid(number=2))]), artifact(number=2), review)
        result = self.run_closure(inventory, reviews={rid(): [review['id']]})
        self.assertIn(review['id'], result.artifact_ids)
        self.assertNotIn(aid(number=2), result.artifact_ids)

    def test_closed_evidence_target_includes_subject_and_attachment(self):
        attachment = AttachmentDescriptor('attachments/raw.bin', 'application/octet-stream', 5, 'a'*64)
        resource = ScopeResource('attachment:raw', 'attachment', 'a'*64)
        evidence = source('evidence', subjects=[subject(aid(number=2))], attachments=[attachment.data])
        inventory = inputs(artifact(relations=[edge('conflicts_with', evidence['id'])]),
            evidence, artifact(number=2), resources=[resource])
        result = self.run_closure(inventory, policy='closed', attachments={resource.resource_id: attachment})
        self.assertEqual(len(result.artifact_ids), 3)
        self.assertEqual(result.attachments, (attachment,))

    def test_retired_weak_targets_are_included_when_closed(self):
        inventory = inputs(artifact(relations=[edge('duplicates', aid(number=2))]), artifact(number=2, maturity='retired'))
        self.assertIn(aid(number=2), self.run_closure(inventory, policy='closed').artifact_ids)

    def test_unreachable_weak_sources_do_not_contribute_boundaries(self):
        inventory = inputs(artifact(), artifact(number=2, relations=[edge('duplicates', aid(number=3))]), artifact(number=3))
        self.assertEqual(self.run_closure(inventory).boundary_references, ())

    def test_reverse_relations_are_not_fabricated(self):
        result = self.run_closure(pair(), identities=[aid(number=2)], policy='closed')
        self.assertEqual(result.artifact_ids, (aid(number=2),))

    def test_original_strong_only_api_keeps_weak_edges_pending(self):
        inventory = pair(); seeds = selection(inventory, [aid()], policy='closed'); bindings = observe(inventory)
        old = resolve_strong_closure(seeds, bindings)
        self.assertEqual(old.artifact_ids, (aid(),))
        self.assertFalse(old.closure_complete)
        self.assertEqual(len(resolve_scope_closure(seeds, bindings).artifact_ids), 2)

    def test_boundary_factory_rejects_strong_relation(self):
        inventory = inputs(artifact(relations=[edge('depends_on', aid(number=2))]), artifact(number=2))
        with self.assertRaises(ModelError):
            boundary_for_relation(inventory.records[0].relations[0], inventory.records[1])

    def test_boundary_factory_rejects_wrong_target_record(self):
        inventory = inputs(artifact(relations=[edge('duplicates', aid(number=2))]), artifact(number=2), artifact(number=3))
        with self.assertRaises(ModelError):
            boundary_for_relation(inventory.records[0].relations[0], inventory.records[2])

    def test_missing_origin_target_is_error_even_for_partial(self):
        with self.assertRaises(ModelError):
            inputs(artifact(relations=[edge('duplicates', aid(number=2))]))

    def test_boundary_requires_real_relation_id_and_hash(self):
        data = self.run_closure(pair()).boundary_references[0].data
        for field in ('relation_id', 'origin_target_sha256'):
            bad = deepcopy(data); del bad[field]
            with self.assertRaises(ModelError): BoundaryReference(bad)

    def test_boundary_rejects_malformed_hash_and_unknown_fields(self):
        data = self.run_closure(pair()).boundary_references[0].data
        for changes in ({'origin_target_sha256': 'a'*63}, {'origin_target_sha256': 'A'*64}, {'unexpected': True}):
            with self.assertRaises(ModelError): BoundaryReference({**data, **changes})

    def test_boundary_rejects_mismatched_type_and_project(self):
        data = self.run_closure(pair()).boundary_references[0].data
        for changes in ({'target_type': 'risk'}, {'target_id': aid(number=2, project='AB')}, {'target_type': 'unknown'}):
            with self.assertRaises(ModelError): BoundaryReference({**data, **changes})

    def test_boundary_rejects_self_reference_and_empty_reason(self):
        data = self.run_closure(pair()).boundary_references[0].data
        for changes in ({'target_id': aid()}, {'reason': ' '}, {'reason': '\ud800'}):
            with self.assertRaises(ModelError): BoundaryReference({**data, **changes})

    def test_boundary_value_is_owned_and_immutable(self):
        data = self.run_closure(pair()).boundary_references[0].data
        boundary = BoundaryReference(data); original = boundary.data
        data['reason'] = 'changed'; boundary.data['reason'] = 'another'
        self.assertEqual(boundary.data, original)
        with self.assertRaises(FrozenInstanceError): boundary._encoded = b'{}'

    def test_result_data_mutation_does_not_change_observation(self):
        result = self.run_closure(pair()); original = result.observation_sha256
        result.data['boundary_references'][0]['reason'] = 'changed'
        self.assertEqual(result.observation_sha256, original)
        self.assertTrue(result.closure_complete)
        self.assertFalse(result.atomic_snapshot)
        self.assertEqual(result.validation_scope, 'closure_over_supplied_bindings')

    def test_input_original_bytes_stay_unchanged(self):
        inventory = pair(); original = tuple(record.source_bytes for record in inventory.records)
        self.run_closure(inventory); self.run_closure(inventory, policy='closed')
        self.assertEqual(tuple(record.source_bytes for record in inventory.records), original)

    def test_origin_hash_binds_full_target_including_revision(self):
        before = self.run_closure(pair()).boundary_references[0]
        inventory = inputs(artifact(relations=[edge('duplicates', aid(number=2))]), artifact(number=2, revision=2))
        after = self.run_closure(inventory).boundary_references[0]
        self.assertNotEqual(before.data['origin_target_sha256'], after.data['origin_target_sha256'])
