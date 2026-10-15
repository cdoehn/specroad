"""Permanent scope exclusions: membership, errors and unchanged source values."""
from copy import deepcopy
import unittest

from specroad.graph.closure_inputs import ClosureBindings, artifact_node as A
from specroad.graph.scope_admission import (
    ScopeControlDependencyError, excludes_control_artifacts, require_artifact_admissible)
from specroad.graph.scope_closure import resolve_scope_closure
from specroad.graph.scope_descriptors import ScopeDescriptor
from specroad.graph.scope_inputs import ScopeResource
from specroad.graph.scope_seeds import resolve_scope_seeds
from specroad.graph.strong_closure import resolve_strong_closure
from specroad.model.canonical import canonical_json_sha256
from specroad.model.errors import ModelError
from specroad.model.identity_values import artifact_identity
from support.boundary import selection
from support.closure import observe, source, subject
from support.relations import artifact, aid, edge, rid
from support.scopes import inputs, descriptor


def referenced_control(kind='proposal'):
    return inputs(artifact('content_block', relations=[edge('references', aid(kind))]), artifact(kind))


def spec_closure(inventory, policy='closed', **options):
    return resolve_scope_closure(selection(inventory, kind='specification', policy=policy),
                                 observe(inventory, **options))


class ScopeControlTests(unittest.TestCase):
    def assert_control(self, operation, source_id, target_id, relation_id=None, pointer=None):
        with self.assertRaises(ScopeControlDependencyError) as raised:
            operation()
        error = raised.exception
        self.assertIsInstance(error, ModelError)
        self.assertEqual(error.code, 'SRV140')
        self.assertEqual(error.reason, 'scope_control_dependency')
        self.assertEqual(error.exit_code, 3)
        data = error.diagnostic()
        self.assertEqual(data['source_id'], source_id)
        self.assertEqual(data['target_id'], target_id)
        self.assertEqual(data['relation_id'], relation_id)
        self.assertEqual(data['severity'], 'error')
        if pointer is not None:
            self.assertEqual(data['pointer'], pointer)
        return error

    def test_control_artifacts_remain_excluded_from_seeds_and_members(self):
        result = spec_closure(inputs(artifact(), artifact('proposal'), artifact('baseline')))
        self.assertEqual(result.artifact_ids, (aid(),))
        self.assertEqual(result.seeds.artifact_ids, (aid(),))

    def test_control_only_inventory_has_no_specification_members(self):
        self.assertEqual(spec_closure(inputs(artifact('proposal'), artifact('baseline'))).members, ())

    def test_adding_unreferenced_controls_does_not_change_selected_values(self):
        first = spec_closure(inputs(artifact()))
        second = spec_closure(inputs(artifact(), artifact('proposal'), artifact('baseline')))
        self.assertEqual(first.members, second.members)
        self.assertEqual(first.boundary_references, second.boundary_references)
        # Inventory observations intentionally bind the full supplied input.
        self.assertNotEqual(first.bindings_sha256, second.bindings_sha256)

    def test_editing_unreferenced_control_does_not_change_member_hashes(self):
        before = spec_closure(inputs(artifact(), artifact('proposal', revision=1)))
        after = spec_closure(inputs(artifact(), artifact('proposal', revision=2, title='Changed control')))
        self.assertEqual(before.members, after.members)

    def test_free_text_mention_of_control_is_not_a_relation(self):
        value = artifact(statement='See ' + aid('proposal'), title=aid('baseline'))
        self.assertEqual(spec_closure(inputs(value)).artifact_ids, (aid(),))

    def test_extension_target_text_is_not_a_relation(self):
        value = artifact(extensions={'example.data': {'target': aid('proposal'), 'type': 'references'}})
        self.assertEqual(spec_closure(inputs(value)).artifact_ids, (aid(),))

    def test_direct_proposal_reference_has_complete_diagnostic(self):
        self.assert_control(lambda: spec_closure(referenced_control()),
                            aid('content_block'), aid('proposal'), rid(), '/relations/0/target')

    def test_direct_baseline_reference_is_denied_before_archive_requirements(self):
        self.assert_control(lambda: spec_closure(referenced_control('baseline')),
                            aid('content_block'), aid('baseline'), rid(), '/relations/0/target')

    def test_partial_policy_does_not_downgrade_strong_control_dependency(self):
        self.assert_control(lambda: spec_closure(referenced_control(), 'partial'),
                            aid('content_block'), aid('proposal'), rid())

    def test_strong_only_api_uses_same_control_gate(self):
        inventory = referenced_control()
        self.assert_control(lambda: resolve_strong_closure(
            selection(inventory, kind='specification'), observe(inventory)),
            aid('content_block'), aid('proposal'), rid())

    def test_closed_weak_control_dependency_is_denied(self):
        inventory = inputs(artifact(relations=[edge('conflicts_with', aid('proposal'))]), artifact('proposal'))
        self.assert_control(lambda: spec_closure(inventory), aid(), aid('proposal'), rid())

    def test_partial_weak_control_dependency_retains_boundary(self):
        inventory = inputs(artifact(relations=[edge('conflicts_with', aid('proposal'))]), artifact('proposal'))
        result = spec_closure(inventory, 'partial')
        self.assertEqual(result.artifact_ids, (aid(),))
        self.assertEqual(result.boundary_references[0].data['target_type'], 'proposal')
        self.assertEqual(result.boundary_references[0].data['origin_target_sha256'],
                         canonical_json_sha256(inventory.records[0].data))

    def test_evidence_subject_proposal_has_field_pointer(self):
        value = source('evidence', subjects=[subject(aid('proposal'))], attachments=[])
        inventory = inputs(value, artifact('proposal'))
        self.assert_control(lambda: spec_closure(inventory), value['id'], aid('proposal'),
                            pointer='/subjects/0/artifact_id')

    def test_evidence_subject_baseline_has_field_pointer(self):
        value = source('evidence', subjects=[subject(aid('baseline'))], attachments=[])
        self.assert_control(lambda: spec_closure(inputs(value, artifact('baseline'))),
                            value['id'], aid('baseline'), pointer='/subjects/0/artifact_id')

    def test_second_evidence_subject_has_original_index(self):
        value = source('evidence', subjects=[subject(aid()), subject(aid('proposal'))], attachments=[])
        self.assert_control(lambda: spec_closure(inputs(value, artifact(), artifact('proposal'))),
                            value['id'], aid('proposal'), pointer='/subjects/1/artifact_id')

    def test_project_scope_may_include_same_reference(self):
        inventory = referenced_control()
        result = resolve_scope_closure(selection(inventory, kind='project'), observe(inventory))
        self.assertEqual(set(result.artifact_ids), {aid('content_block'), aid('proposal')})

    def test_document_scope_may_include_same_reference_transitively(self):
        inventory = inputs(
            artifact('document', relations=[edge('contains', aid('section'), number=1)]),
            artifact('section', relations=[edge('contains', aid('content_block'), number=2)]),
            artifact('content_block', relations=[edge('references', aid('proposal'), number=3)]),
            artifact('proposal'))
        seeds = selection(inventory, kind='document', selector={'document_id': aid('document')})
        self.assertIn(aid('proposal'), resolve_scope_closure(seeds, observe(inventory)).artifact_ids)

    def test_explicit_scope_may_select_control(self):
        inventory = inputs(artifact('proposal'))
        self.assertEqual(resolve_scope_closure(selection(inventory, [aid('proposal')]), observe(inventory)).artifact_ids,
                         (aid('proposal'),))

    def test_project_baseline_retains_archive_dependencies(self):
        archive = ScopeResource('archive:a', 'archive', 'a'*64)
        inventory = inputs(artifact('baseline'), resources=[archive],
                           archive_bindings={aid('baseline'): ['archive:a']})
        result = resolve_scope_closure(selection(inventory, kind='project'), observe(inventory))
        self.assertEqual(result.resource_ids, ('archive:a',))

    def test_rejected_control_is_still_excluded(self):
        value = artifact('proposal', maturity='rejected')
        self.assertEqual(spec_closure(inputs(artifact(), value)).artifact_ids, (aid(),))

    def test_retired_control_is_not_allowed_as_dependency(self):
        inventory = inputs(artifact('content_block', relations=[edge('references', aid('baseline'))]),
                           artifact('baseline', maturity='retired'))
        self.assert_control(lambda: spec_closure(inventory), aid('content_block'), aid('baseline'), rid())

    def test_excluded_control_needs_no_usage_observation(self):
        inventory = inputs(artifact(), artifact('proposal'))
        binding = ClosureBindings(inventory, uses={A(aid()): ()}, current_reviews={})
        self.assertEqual(resolve_scope_closure(selection(inventory, kind='specification'), binding).artifact_ids, (aid(),))

    def test_referenced_control_is_denied_before_reading_its_uses(self):
        inventory = referenced_control()
        binding = ClosureBindings(inventory, uses={A(aid('content_block')): ()}, current_reviews={rid(): ()})
        self.assert_control(lambda: resolve_scope_closure(selection(inventory, kind='specification'), binding),
                            aid('content_block'), aid('proposal'), rid())

    def test_error_does_not_mutate_source_bytes(self):
        inventory = referenced_control()
        before = [(item.source_bytes, item.data) for item in inventory.records]
        self.assert_control(lambda: spec_closure(inventory), aid('content_block'), aid('proposal'), rid())
        self.assertEqual(before, [(item.source_bytes, item.data) for item in inventory.records])

    def test_diagnostic_returns_independent_data(self):
        error = self.assert_control(lambda: spec_closure(referenced_control()), aid('content_block'), aid('proposal'), rid())
        changed = error.diagnostic(); changed['target_id'] = 'changed'
        self.assertEqual(error.diagnostic()['target_id'], aid('proposal'))

    def test_configuration_wrapper_preserves_specification_exclusions(self):
        wrapped = ScopeDescriptor(descriptor('configuration', {'base_scope_descriptor': descriptor()},
                                             configuration_id=aid('configuration')))
        self.assertTrue(excludes_control_artifacts(wrapped))
        self.assert_control(lambda: require_artifact_admissible(wrapped, artifact_identity(artifact('proposal')),
                            source_id=aid('content_block'), pointer='/binding/target'),
                            aid('content_block'), aid('proposal'), pointer='/binding/target')

    def test_configuration_wrapper_does_not_impose_specification_on_project(self):
        wrapped = ScopeDescriptor(descriptor('configuration', {'base_scope_descriptor': descriptor('project')},
                                             configuration_id=aid('configuration')))
        self.assertFalse(excludes_control_artifacts(wrapped))
        require_artifact_admissible(wrapped, artifact_identity(artifact('proposal')))

    def test_unresolved_configuration_still_fails_closed(self):
        inventory = inputs(artifact(), artifact('configuration'))
        desc = ScopeDescriptor(descriptor(configuration_id=aid('configuration')))
        with self.assertRaises(ModelError) as raised:
            resolve_scope_seeds(desc, inventory)
        self.assertEqual(raised.exception.reason, 'missing_field')
