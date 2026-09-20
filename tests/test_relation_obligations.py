"""Behavior-only relation minima and review-context contracts (Appendix J)."""
from copy import deepcopy
import json
import unittest

from specroad.graph.relations import SourceRelations, Relation
from specroad.graph.relation_obligations import RelationObligations
from specroad.graph.review_contexts import (EndpointReviewContext, RelationReviewContext,
                                            relation_content_sha256)
from specroad.model.canonical import canonical_json_sha256
from specroad.model.errors import ModelError
from support.artifacts import artifact_bytes
from support.relations import artifact, aid, edge, rid


def sources(*values):
    return tuple(SourceRelations(artifact_bytes(value)) for value in values)


def satisfied_fixture():
    return sources(artifact(maturity='approved', relations=[
        edge('addresses', aid('goal'), 1), edge('verified_by', aid('test'), 2)]),
        artifact('goal'), artifact('test'))


class ObligationWorkTests(unittest.TestCase):
    def test_approved_requirement_needs_origin_and_verification(self):
        result = RelationObligations(sources(artifact(maturity='approved')))
        self.assertFalse(result.requirements_satisfied)
        self.assertTrue(result.has_errors)
        self.assertEqual({x['rule_id'] for x in result.diagnostics},
                         {'core:requirement-origin', 'core:requirement-verification'})
        self.assertEqual([x['actual'] for x in result.diagnostics], [0, 0])

    def test_each_origin_alternative_is_accepted(self):
        for kind, target_type in [('derived_from', 'source'), ('refines', 'need'), ('addresses', 'goal')]:
            with self.subTest(kind=kind):
                records = sources(artifact(maturity='approved', relations=[
                    edge(kind, aid(target_type), 1), edge('verified_by', aid('test'), 2)]),
                    artifact(target_type), artifact('test'))
                self.assertTrue(RelationObligations(records).requirements_satisfied)

    def test_test_and_verification_are_valid_verification_targets(self):
        for kind in ('test', 'verification'):
            with self.subTest(kind=kind):
                records = sources(artifact(maturity='approved', relations=[
                    edge('addresses', aid('goal'), 1), edge('verified_by', aid(kind), 2)]),
                    artifact('goal'), artifact(kind))
                self.assertTrue(RelationObligations(records).requirements_satisfied)

    def test_satisfied_minima_do_not_grant_approval_or_review(self):
        result = RelationObligations(satisfied_fixture())
        self.assertTrue(result.requirements_satisfied)
        self.assertEqual(result.diagnostics, ())
        self.assertFalse(result.approval_granted)
        self.assertFalse(result.review_status_checked)
        self.assertFalse(result.profile_composition_checked)

    def test_nonapproved_requirement_does_not_get_approval_minima(self):
        for maturity in ('draft', 'proposed', 'rejected', 'retired'):
            with self.subTest(maturity=maturity):
                result = RelationObligations(sources(artifact(maturity=maturity)))
                self.assertEqual(result.checks, ())

    def test_other_artifact_is_not_mistaken_for_requirement(self):
        result = RelationObligations(sources(artifact('goal', maturity='approved')))
        self.assertEqual(result.checks, ())

    def test_incoming_origin_is_not_outgoing_origin(self):
        records = sources(artifact(maturity='approved'),
            artifact(number=2, relations=[edge('refines', aid())]))
        self.assertEqual(len(RelationObligations(records).diagnostics), 2)

    def test_provenance_text_does_not_replace_relation(self):
        result = RelationObligations(sources(artifact(maturity='approved',
            rationale='Source exists', statement='Must work', priority='must',
            provenance=[{'locator': 'urn:test:source', 'captured_at': '2026-01-01T00:00:00Z',
                         'excerpt': 'test source'}])))
        self.assertFalse(result.requirements_satisfied)

    def test_waiver_status_does_not_disable_relation_gate(self):
        result = RelationObligations(sources(artifact(maturity='approved',
                                                     verification_plan_status='waived')))
        self.assertEqual(len(result.diagnostics), 2)

    def test_missing_target_is_error_not_satisfied_minimum(self):
        with self.assertRaises(ModelError) as caught:
            RelationObligations(sources(artifact(maturity='approved', relations=[edge()])))
        self.assertEqual(caught.exception.reason, 'missing_relation_target')

    def test_invalid_matrix_is_error(self):
        records = sources(artifact(maturity='approved', relations=[edge('verified_by', aid('goal'))]),
                          artifact('goal'))
        with self.assertRaises(ModelError): RelationObligations(records)

    def test_duplicate_source_identity_is_error(self):
        with self.assertRaises(ModelError): RelationObligations(sources(artifact(), artifact()))

    def test_self_relation_is_error(self):
        with self.assertRaises(ModelError):
            RelationObligations(sources(artifact(relations=[edge('refines', aid())])))

    def test_input_order_does_not_change_results(self):
        records = satisfied_fixture()
        a, b = RelationObligations(records), RelationObligations(reversed(records))
        self.assertEqual(a.checks, b.checks)
        self.assertEqual(a.input_sha256, b.input_sha256)

    def test_empty_input_is_explicit_empty_result_not_project_approval(self):
        result = RelationObligations(())
        self.assertEqual(result.checks, ())
        self.assertFalse(result.approval_granted)

    def test_original_sources_are_not_changed(self):
        records = satisfied_fixture(); original = [record.source_bytes for record in records]
        result = RelationObligations(records)
        self.assertEqual(original, [record.source_bytes for record in records])
        self.assertEqual(result.checks[0].relation_ids, (rid(1),))
        self.assertEqual(result.checks[1].relation_ids, (rid(2),))


class ContextWorkTests(unittest.TestCase):
    def test_endpoint_context_is_exact_canonical_projection(self):
        source = sources(artifact(title='A', statement='Keep this', owner='reviewer'))[0]
        excluded = {'revision', 'created_at', 'created_by', 'updated_at', 'updated_by',
                    'maturity', 'relations', 'tags'}
        expected = {k: v for k, v in source.data.items() if k not in excluded}
        context = EndpointReviewContext(source)
        self.assertEqual(context.context_sha256, canonical_json_sha256(expected))
        self.assertEqual(context.artifact_sha256, canonical_json_sha256(source.data))
        self.assertEqual(context.algorithm, 'relation_context_hash-v1')

    def test_lifecycle_change_does_not_change_review_context(self):
        a, b = sources(artifact(maturity='draft'), artifact(maturity='approved'))
        self.assertEqual(EndpointReviewContext(a).context_sha256, EndpointReviewContext(b).context_sha256)
        self.assertNotEqual(EndpointReviewContext(a).artifact_sha256, EndpointReviewContext(b).artifact_sha256)

    def test_content_change_changes_context(self):
        a, b = sources(artifact(statement='A'), artifact(statement='B'))
        self.assertNotEqual(EndpointReviewContext(a).context_sha256, EndpointReviewContext(b).context_sha256)

    def test_other_relations_do_not_change_endpoint_context(self):
        a, b = sources(artifact(), artifact(relations=[edge()]))
        self.assertEqual(EndpointReviewContext(a).context_sha256, EndpointReviewContext(b).context_sha256)

    def test_nested_status_and_audit_keys_remain_bound(self):
        a, b = sources(artifact(extensions={'example.org:content': {'maturity': 'A'}}),
                       artifact(extensions={'example.org:content': {'maturity': 'B'}}))
        self.assertNotEqual(EndpointReviewContext(a).context_sha256, EndpointReviewContext(b).context_sha256)

    def test_relation_hash_excludes_only_creation_audit(self):
        a, b = sources(artifact(relations=[edge()]), artifact(relations=[edge(
            created_at='2026-01-01T00:00:00Z', created_by={'actor_type':'human','actor_id':'one'})]))
        self.assertEqual(relation_content_sha256(a.relations[0]), relation_content_sha256(b.relations[0]))
        changed = sources(artifact(relations=[edge(rationale='changed')]))[0]
        self.assertNotEqual(relation_content_sha256(a.relations[0]), relation_content_sha256(changed.relations[0]))

    def test_binding_contains_both_full_hashes_and_context_hashes(self):
        a, b = sources(artifact(relations=[edge()]), artifact(number=2))
        binding = RelationReviewContext(a.relations[0], a, b)
        self.assertEqual(binding.source.artifact_id, a.identity.id)
        self.assertEqual(binding.target.artifact_id, b.identity.id)
        self.assertEqual(binding.source.revision, 1)
        self.assertEqual(binding.relation_id, rid())
        self.assertFalse(binding.review_selected)

    def test_endpoint_mismatch_rejected(self):
        a, b = sources(artifact(relations=[edge()]), artifact(number=3))
        with self.assertRaises(ModelError): RelationReviewContext(a.relations[0], a, b)

    def test_detached_relation_not_accepted_as_stored(self):
        a, b = sources(artifact(), artifact(number=2))
        with self.assertRaises(ModelError) as caught:
            RelationReviewContext(Relation(a.identity, edge()), a, b)
        self.assertEqual(caught.exception.reason, 'review_relation_not_in_source')

    def test_changed_relation_argument_not_accepted_as_stored(self):
        a, b = sources(artifact(relations=[edge()]), artifact(number=2))
        with self.assertRaises(ModelError):
            RelationReviewContext(Relation(a.identity, edge(rationale='different')), a, b)

    def test_projection_copy_does_not_mutate_context(self):
        record = sources(artifact(extensions={'example.org:data': {'x': [1]}}))[0]
        context = EndpointReviewContext(record); before = context.context_sha256
        context.projection['extensions']['example.org:data']['x'].append(2)
        self.assertEqual(before, context.context_sha256)
        self.assertEqual(context.projection['extensions']['example.org:data']['x'], [1])

    def test_formatting_is_not_context_or_full_value_change(self):
        data = artifact(title='日本語')
        a = SourceRelations(json.dumps(data, ensure_ascii=False, indent=2).encode())
        b = SourceRelations(json.dumps(data, sort_keys=True, ensure_ascii=True).encode())
        self.assertNotEqual(a.source_bytes, b.source_bytes)
        self.assertEqual(EndpointReviewContext(a), EndpointReviewContext(b))

    def test_invalid_input_has_controlled_error(self):
        for bad in (None, {}, [], b'{}'):
            with self.subTest(kind=type(bad).__name__):
                with self.assertRaises(ModelError): EndpointReviewContext(bad)
                with self.assertRaises(ModelError): relation_content_sha256(bad)
