"""Normative edge identity and inverse data semantics, not visual output."""
from dataclasses import FrozenInstanceError
import copy
import unittest
from unittest.mock import patch

from specroad.graph.references import validate_relation_references
from specroad.graph.relations import SourceRelations, Relation
from specroad.graph.symmetry import (canonical_relation, canonical_relations,
                                    require_canonical_relations, RelationView, RelationViews)
from specroad.model.errors import ModelError
from support.artifacts import artifact_bytes
from support.relations import aid, artifact, edge, external, rid


def records(*values):
    return [SourceRelations(artifact_bytes(value)) for value in values]


def pair(kind="conflicts_with", *, reverse=False, source_kind="requirement", target_kind="requirement", **metadata):
    source = artifact(source_kind, 1)
    target = artifact(target_kind, 2)
    # Respect canonical order also for differing type prefixes.
    source, target = sorted((source, target), key=lambda value: value["id"], reverse=reverse)
    source["relations"] = [edge(kind, target["id"], **metadata)]
    return records(source, target)


class RelationViewsWorkTests(unittest.TestCase):
    def test_conflict_is_visible_from_both_endpoints_once(self):
        values = pair(); refs = validate_relation_references(values); views = RelationViews(refs)
        a, b = values[0].identity.id, values[1].identity.id
        self.assertEqual(len(views.stored_relations), 1)
        self.assertEqual(views.for_artifact(a)[0].target.id, b)
        self.assertEqual(views.for_artifact(b)[0].target.id, a)
        self.assertEqual(views.for_artifact(a)[0].relation_id, views.for_artifact(b)[0].relation_id)

    def test_duplicate_relation_has_the_same_symmetric_semantics(self):
        values = pair("duplicates"); views = RelationViews(validate_relation_references(values))
        for value in values:
            found = views.for_artifact(value.identity.id)
            self.assertEqual(len(found), 1); self.assertEqual(found[0].type, "duplicates")

    def test_canonicalization_preserves_identity_and_metadata(self):
        values = pair(reverse=True, rationale="because", external_identities=[external()],
                      extensions={"example.value": {"script": "do not run"}},
                      created_at="2026-09-17T10:00:00Z", created_by={"actor_type":"human","actor_id":"test"})
        original = validate_relation_references(values).relations[0]
        result = canonical_relation(original)
        self.assertLess(result.source.id, result.target.id)
        self.assertEqual(result.relation.identity, original.relation.identity)
        old, new = original.relation.data, result.relation.data
        old.pop("target"); new.pop("target"); self.assertEqual(old, new)
        self.assertEqual(result.source, original.target); self.assertEqual(result.target, original.source)

    def test_directional_relation_is_not_reversed(self):
        refs = validate_relation_references(pair("refines", reverse=True))
        self.assertEqual(canonical_relations(refs), refs.relations)

    def test_canonicalization_is_idempotent(self):
        value = canonical_relations(validate_relation_references(pair(reverse=True)))[0]
        self.assertEqual(canonical_relation(value), value)

    def test_read_views_reject_noncanonical_storage_not_silently_fix(self):
        with self.assertRaises(ModelError) as caught:
            RelationViews(validate_relation_references(pair(reverse=True)))
        self.assertEqual(caught.exception.reason, "noncanonical_symmetric_relation")

    def test_twice_stored_symmetric_pair_is_rejected(self):
        a = artifact(number=1, relations=[edge("conflicts_with", aid(number=2), 1)])
        b = artifact(number=2, relations=[edge("conflicts_with", aid(number=1), 2)])
        with self.assertRaises(ModelError) as caught:
            canonical_relations(validate_relation_references(records(a, b)))
        self.assertEqual(caught.exception.reason, "duplicate_symmetric_relation")

    def test_same_direction_duplicate_is_also_rejected(self):
        a = artifact(relations=[edge("duplicates", aid(number=2), 1), edge("duplicates", aid(number=2), 2)])
        with self.assertRaises(ModelError):
            canonical_relations(validate_relation_references(records(a, artifact(number=2))))

    def test_conflicts_and_duplicates_between_same_pair_remain_distinct(self):
        a = artifact(relations=[edge("duplicates", aid(number=2), 1), edge("conflicts_with", aid(number=2), 2)])
        views = RelationViews(validate_relation_references(records(a, artifact(number=2))))
        self.assertEqual({v.type for v in views.for_artifact(a["id"])}, {"conflicts_with", "duplicates"})

    def test_superseded_by_is_computed_not_stored(self):
        values = pair("supersedes"); refs = validate_relation_references(values)
        incoming = RelationViews(refs).for_artifact(values[1].identity.id)[0]
        self.assertEqual(incoming.type, "superseded_by"); self.assertTrue(incoming.inverse)
        self.assertEqual(incoming.stored.relation.type, "supersedes"); self.assertFalse(incoming.normative)
        with self.assertRaises(ModelError): Relation(values[1].identity, edge("superseded_by"))

    def test_incoming_refinement_is_not_misrepresented_as_normative_reverse(self):
        values = pair("refines"); view = RelationViews(validate_relation_references(values)).for_artifact(values[1].identity.id)[0]
        self.assertEqual(view.type, "refines"); self.assertTrue(view.inverse)
        self.assertEqual(view.stored.source.id, values[0].identity.id)
        self.assertFalse(view.normative)

    def test_explicit_directions_match_physical_storage(self):
        values = pair(); views = RelationViews(validate_relation_references(values))
        a, b = [v.identity.id for v in values]
        self.assertEqual(views.for_artifact(a, direction="incoming"), ())
        self.assertEqual(views.for_artifact(b, direction="outgoing"), ())
        self.assertEqual(len(views.for_artifact(a, direction="outgoing")), 1)
        self.assertEqual(len(views.for_artifact(b, direction="incoming")), 1)

    def test_unknown_artifact_not_resolved_via_display_label(self):
        views = RelationViews(validate_relation_references(records(artifact(display_id="human"))))
        for name in ("human", aid(number=99), None, 1):
            with self.subTest(name=repr(name)), self.assertRaises(ModelError): views.for_artifact(name)

    def test_empty_model_has_no_normative_or_computed_edges(self):
        refs = validate_relation_references([])
        self.assertEqual(canonical_relations(refs), ())
        self.assertEqual(RelationViews(refs).stored_relations, ())

    def test_isolated_artifact_has_empty_views(self):
        value = artifact(); views = RelationViews(validate_relation_references(records(value)))
        self.assertEqual(views.for_artifact(value["id"]), ())

    def test_invalid_direction_is_not_silently_defaulted(self):
        views = RelationViews(validate_relation_references(pair()))
        for direction in ("reverse", "", None, [], True):
            with self.subTest(direction=repr(direction)), self.assertRaises(ModelError):
                views.for_artifact(aid(), direction=direction)

    def test_views_cannot_be_modified(self):
        views = RelationViews(validate_relation_references(pair()))
        with self.assertRaises(FrozenInstanceError): views.stored_relations = ()
        with self.assertRaises(FrozenInstanceError): views.for_artifact(aid())[0].inverse = True

    def test_inputs_and_original_bytes_are_untouched(self):
        values = pair(reverse=True); before = [v.source_bytes for v in values]
        refs = validate_relation_references(values); canonical_relations(refs)
        self.assertEqual([v.source_bytes for v in values], before)
        self.assertGreater(refs.relations[0].source.id, refs.relations[0].target.id)

    def test_projection_does_not_read_files_or_spawn_processes(self):
        refs = validate_relation_references(pair())
        with patch("builtins.open", side_effect=AssertionError("file")), patch("subprocess.run", side_effect=AssertionError("process")):
            canonical_relations(refs); result = RelationViews(refs).for_artifact(aid())
        self.assertEqual(len(result), 1)

    def test_wrong_input_types_are_controlled_model_errors(self):
        for value in (None, [], {}, "value"):
            with self.subTest(value=repr(value)):
                for function in (canonical_relation, canonical_relations, require_canonical_relations, RelationViews):
                    with self.assertRaises(ModelError): function(value)

    def test_boolean_direction_flag_is_required(self):
        edge_value = validate_relation_references(pair()).relations[0]
        for value in (0, 1, "inverse", None):
            with self.subTest(value=repr(value)), self.assertRaises(ModelError): RelationView(edge_value, value)

    def test_record_order_does_not_change_view_order(self):
        a = artifact(relations=[edge("duplicates", aid(number=2), 1), edge("conflicts_with", aid(number=3), 2)])
        values = records(a, artifact(number=2), artifact(number=3))
        one = RelationViews(validate_relation_references(values)); two = RelationViews(validate_relation_references(reversed(values)))
        self.assertEqual(one.for_artifact(a["id"]), two.for_artifact(a["id"]))
