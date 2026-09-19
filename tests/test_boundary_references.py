"""Untrusted boundary declarations must exactly cover absent weak relation targets."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
import unittest

from specroad.graph.boundaries import BoundaryReference
from specroad.graph.boundary_validation import validate_boundary_references
from specroad.graph.relations import SourceRelations
from specroad.graph.scope_closure import resolve_scope_closure
from specroad.graph.scope_descriptors import ScopeDescriptor
from specroad.model.canonical import canonical_json_sha256
from specroad.model.errors import ModelError
from support.artifacts import artifact_bytes
from support.boundary import selection
from support.closure import observe
from support.relations import artifact, aid, edge, rid, external
from support.scopes import inputs, descriptor


class BoundaryValidationTests(unittest.TestCase):
    def setUp(self):
        self.inventory = inputs(artifact(relations=[edge('duplicates', aid(number=2))]), artifact(number=2))
        self.seeds = selection(self.inventory, [aid()])
        self.result = resolve_scope_closure(self.seeds, observe(self.inventory))
        self.local = [self.inventory.records[0]]
        self.declarations = [item.data for item in self.result.boundary_references]

    def validate(self, declarations=None, *, origin=None, local=None, descriptor_value=None):
        return validate_boundary_references(self.local if local is None else local,
            self.declarations if declarations is None else declarations,
            descriptor=self.seeds.descriptor if descriptor_value is None else descriptor_value,
            origin_sources=origin)

    def test_exact_declaration_allows_only_missing_weak_target(self):
        result = self.validate()
        self.assertEqual(result.boundary_references, self.result.boundary_references)
        self.assertEqual(result.local_relations, ())
        self.assertFalse(result.origin_hashes_verified)
        self.assertEqual(result.validation_scope, 'partial_relation_bindings_only')

    def test_matching_origin_bytes_verify_hash_without_authenticating_origin_root(self):
        result = self.validate(origin=self.inventory.records)
        self.assertTrue(result.origin_hashes_verified)

    def test_omitted_declaration_fails(self):
        with self.assertRaises(ModelError) as error: self.validate([])
        self.assertEqual(error.exception.reason, 'boundary_reference_missing')

    def test_duplicate_declarations_fail_even_if_identical(self):
        with self.assertRaises(ModelError) as error: self.validate(self.declarations * 2)
        self.assertEqual(error.exception.reason, 'duplicate_boundary_reference')

    def test_conflicting_duplicate_hashes_fail(self):
        bad = {**self.declarations[0], 'origin_target_sha256': 'b'*64}
        with self.assertRaises(ModelError): self.validate([self.declarations[0], bad])

    def test_missing_relation_id_fails(self):
        bad = deepcopy(self.declarations); del bad[0]['relation_id']
        with self.assertRaises(ModelError): self.validate(bad)

    def test_wrong_relation_id_cannot_replace_missing_declaration(self):
        with self.assertRaises(ModelError): self.validate([{**self.declarations[0], 'relation_id': rid(2)}])

    def test_wrong_target_id_cannot_replace_missing_declaration(self):
        with self.assertRaises(ModelError): self.validate([{**self.declarations[0], 'target_id': aid(number=3)}])

    def test_wrong_source_cannot_claim_another_artifacts_edge(self):
        with self.assertRaises(ModelError): self.validate([{**self.declarations[0], 'source_id': aid(number=3)}])

    def test_other_weak_type_is_not_an_exact_match(self):
        with self.assertRaises(ModelError) as error:
            self.validate([{**self.declarations[0], 'relation_type': 'conflicts_with'}])
        self.assertEqual(error.exception.reason, 'boundary_reference_mismatch')

    def test_unknown_relation_type_is_rejected(self):
        with self.assertRaises(ModelError): self.validate([{**self.declarations[0], 'relation_type': 'superseded_by'}])

    def test_missing_strong_target_cannot_use_weak_boundary(self):
        strong = SourceRelations(artifact_bytes(artifact(relations=[edge('depends_on', aid(number=2))])))
        with self.assertRaises(ModelError) as error: self.validate(local=[strong])
        self.assertEqual(error.exception.reason, 'missing_relation_target')

    def test_missing_strong_target_fails_without_any_declaration(self):
        strong = SourceRelations(artifact_bytes(artifact(relations=[edge('depends_on', aid(number=2))])))
        with self.assertRaises(ModelError): self.validate([], local=[strong])

    def test_even_matching_strong_origin_hash_does_not_authorize_boundary(self):
        with self.assertRaises(ModelError): self.validate([{**self.declarations[0], 'relation_type': 'depends_on'}], origin=self.inventory.records)

    def test_closed_policy_forbids_declarations(self):
        closed = ScopeDescriptor(descriptor('explicit', {'artifact_ids': [aid()], 'resource_ids': []}))
        with self.assertRaises(ModelError): self.validate(descriptor_value=closed)

    def test_closed_policy_requires_weak_target_locally(self):
        closed = ScopeDescriptor(descriptor('explicit', {'artifact_ids': [aid()], 'resource_ids': []}))
        with self.assertRaises(ModelError): self.validate([], descriptor_value=closed)

    def test_local_weak_target_requires_no_boundary(self):
        result = self.validate([], local=self.inventory.records)
        self.assertEqual(len(result.local_relations), 1)
        self.assertEqual(result.boundary_references, ())

    def test_declaration_for_local_target_is_rejected(self):
        with self.assertRaises(ModelError) as error: self.validate(local=self.inventory.records)
        self.assertEqual(error.exception.reason, 'boundary_target_already_in_scope')

    def test_stray_declaration_is_not_silently_dropped(self):
        stray = {**self.declarations[0], 'relation_id': rid(2), 'target_id': aid(number=3)}
        with self.assertRaises(ModelError) as error: self.validate([*self.declarations, stray])
        self.assertEqual(error.exception.reason, 'unexpected_boundary_reference')

    def test_wrong_origin_target_hash_fails(self):
        with self.assertRaises(ModelError) as error:
            self.validate([{**self.declarations[0], 'origin_target_sha256': 'b'*64}], origin=self.inventory.records)
        self.assertEqual(error.exception.reason, 'boundary_origin_target_mismatch')

    def test_old_hash_is_not_accepted_after_origin_revision_changes(self):
        changed = inputs(artifact(relations=[edge('duplicates', aid(number=2))]), artifact(number=2, revision=2))
        with self.assertRaises(ModelError): self.validate(origin=changed.records)

    def test_altered_local_source_fails_origin_check(self):
        changed = SourceRelations(artifact_bytes(artifact(title='changed', relations=[edge('duplicates', aid(number=2))])))
        with self.assertRaises(ModelError) as error: self.validate(local=[changed], origin=self.inventory.records)
        self.assertEqual(error.exception.reason, 'boundary_origin_source_mismatch')

    def test_missing_origin_records_fail_not_fallback_to_hash_shape(self):
        with self.assertRaises(ModelError): self.validate(origin=[])
        with self.assertRaises(ModelError): self.validate(origin=self.local)

    def test_hash_shape_without_origin_is_explicitly_not_verification(self):
        result = self.validate([{**self.declarations[0], 'origin_target_sha256': 'b'*64}])
        self.assertFalse(result.origin_hashes_verified)

    def test_formatting_of_origin_does_not_change_canonical_target_hash(self):
        import json
        origin = [SourceRelations(json.dumps(record.data, indent=7).encode()) for record in self.inventory.records]
        self.assertTrue(self.validate(origin=origin).origin_hashes_verified)

    def test_unordered_declarations_are_canonically_returned(self):
        inventory = inputs(artifact(relations=[edge('duplicates', aid(number=2)), edge('conflicts_with', aid(number=3), number=2)]),
                           artifact(number=2), artifact(number=3))
        seeds = selection(inventory, [aid()]); result = resolve_scope_closure(seeds, observe(inventory))
        check = validate_boundary_references([inventory.records[0]], tuple(reversed(result.boundary_references)),
                                             descriptor=seeds.descriptor, origin_sources=inventory.records)
        self.assertEqual(check.boundary_references, result.boundary_references)

    def test_duplicate_source_id_is_rejected(self):
        with self.assertRaises(ModelError): self.validate(local=self.local*2)

    def test_duplicate_relation_id_across_sources_is_rejected(self):
        other = SourceRelations(artifact_bytes(artifact(number=3, relations=[edge('duplicates', aid(number=2))])))
        with self.assertRaises(ModelError) as error: self.validate(local=[*self.local, other])
        self.assertEqual(error.exception.reason, 'duplicate_relation_id')

    def test_duplicate_external_identity_across_sources_is_rejected(self):
        one = SourceRelations(artifact_bytes(artifact(relations=[edge('duplicates', aid(number=2), external_identities=[external()])])))
        two = SourceRelations(artifact_bytes(artifact(number=3, relations=[edge('duplicates', aid(number=2), number=2, external_identities=[external()])])))
        with self.assertRaises(ModelError) as error: self.validate(local=[one, two])
        self.assertEqual(error.exception.reason, 'duplicate_external_relation_identity')

    def test_type_matrix_is_checked_for_omitted_target(self):
        local = SourceRelations(artifact_bytes(artifact(relations=[edge('duplicates', aid('risk'))])))
        declaration = {**self.declarations[0], 'target_id': aid('risk'), 'target_type': 'risk'}
        with self.assertRaises(ModelError): self.validate([declaration], local=[local])

    def test_mixed_project_sources_are_rejected(self):
        other = SourceRelations(artifact_bytes(artifact(number=3, project='AB')))
        with self.assertRaises(ModelError): self.validate(local=[*self.local, other])

    def test_non_record_sources_and_non_sequence_declarations_are_rejected(self):
        for bad in (None, {}, 'data', b'bytes', [object()]):
            with self.assertRaises(ModelError): self.validate(local=bad if bad is not None else [None])
        for bad in ({}, 'data', b'bytes', 42):
            with self.assertRaises(ModelError): self.validate(bad)

    def test_invalid_descriptor_is_rejected(self):
        with self.assertRaises(ModelError): self.validate(descriptor_value={})

    def test_validation_does_not_mutate_inputs(self):
        before = deepcopy(self.declarations); bytes_before = [record.source_bytes for record in self.inventory.records]
        result = self.validate(origin=self.inventory.records)
        self.declarations[0]['reason'] = 'modified'; result.boundary_references[0].data['reason'] = 'other'
        self.assertEqual(result.boundary_references[0].data, before[0])
        self.assertEqual([record.source_bytes for record in self.inventory.records], bytes_before)
        with self.assertRaises(FrozenInstanceError): result.origin_hashes_verified = False

    def test_legacy_artifact_target_is_supported_without_new_legacy_id_creation(self):
        one = artifact(id='SR-REQ-0001', id_scheme='legacy-sequential-v1', relations=[edge('duplicates', 'SR-REQ-0002')])
        two = artifact(id='SR-REQ-0002', id_scheme='legacy-sequential-v1')
        inventory = inputs(one, two); seeds = selection(inventory, ['SR-REQ-0001'])
        result = resolve_scope_closure(seeds, observe(inventory))
        checked = validate_boundary_references([inventory.records[0]], result.boundary_references,
                                               descriptor=seeds.descriptor, origin_sources=inventory.records)
        self.assertTrue(checked.origin_hashes_verified)
