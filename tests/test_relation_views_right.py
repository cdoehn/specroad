"""Symmetry adversarial cases, stable IDs and safe in-memory projections."""
import copy
from pathlib import Path
import tempfile
import unittest

from specroad.graph.references import ResolvedRelation, validate_relation_references
from specroad.graph.relations import Relation, require_relation_keys_unchanged
from specroad.graph.symmetry import (canonical_relation, canonical_relations, require_canonical_reorder,
                                    RelationView, RelationViews)
from specroad.model.errors import ModelError
from support.relations import aid, artifact, edge, external, rid
from support.portable import build_distribution
from support.processes import run_python
from test_relation_views import pair, records


class RelationViewsRightTests(unittest.TestCase):
    def test_only_exact_canonical_reorder_is_allowed(self):
        old = validate_relation_references(pair(reverse=True)).relations[0]
        new = canonical_relation(old)
        require_canonical_reorder(old, new)
        self.assertEqual(new.relation.identity.id, old.relation.identity.id)

    def test_generic_update_guard_still_rejects_source_relocation(self):
        old = validate_relation_references(pair(reverse=True)).relations[0]
        with self.assertRaises(ModelError) as caught:
            require_relation_keys_unchanged(old.relation, canonical_relation(old).relation)
        self.assertEqual(caught.exception.reason, "relation_source_immutable")

    def test_reorder_cannot_exchange_relation_id(self):
        old = validate_relation_references(pair(reverse=True)).relations[0]; new = canonical_relation(old)
        changed = dict(new.relation.data, relation_id=rid(9))
        forged = ResolvedRelation(Relation(new.source, changed), new.source, new.target)
        with self.assertRaises(ModelError): require_canonical_reorder(old, forged)

    def test_reorder_cannot_change_metadata(self):
        old = validate_relation_references(pair(reverse=True)).relations[0]; new = canonical_relation(old)
        for changed in ({"rationale": "new"}, {"extensions": {"example.flag": True}}, {"external_identities": [external()]}):
            forged = ResolvedRelation(Relation(new.source, dict(new.relation.data, **changed)), new.source, new.target)
            with self.subTest(changed=repr(changed)), self.assertRaises(ModelError): require_canonical_reorder(old, forged)

    def test_boolean_and_integer_metadata_are_not_equal(self):
        old = validate_relation_references(pair(reverse=True, extensions={"example.flag": True})).relations[0]
        new = canonical_relation(old)
        forged = ResolvedRelation(Relation(new.source, dict(new.relation.data, extensions={"example.flag": 1})), new.source, new.target)
        with self.assertRaises(ModelError): require_canonical_reorder(old, forged)

    def test_semantically_equal_metadata_key_order_is_not_a_change(self):
        old = validate_relation_references(pair(reverse=True, extensions={"example.data": {"a":1,"b":2}})).relations[0]
        new = canonical_relation(old); data = new.relation.data; data["extensions"]["example.data"]={"b":2,"a":1}
        proposed = ResolvedRelation(Relation(new.source, data), new.source, new.target)
        require_canonical_reorder(old, proposed)

    def test_reorder_cannot_switch_symmetric_relation_type(self):
        old = validate_relation_references(pair(reverse=True)).relations[0]; new = canonical_relation(old)
        forged = ResolvedRelation(Relation(new.source, dict(new.relation.data, type="duplicates")), new.source, new.target)
        with self.assertRaises(ModelError): require_canonical_reorder(old, forged)

    def test_reorder_cannot_relabel_id_scheme(self):
        old = validate_relation_references(pair(reverse=True)).relations[0]; new = canonical_relation(old)
        forged = ResolvedRelation(Relation(new.source, dict(new.relation.data, id_scheme="derived128-v1")), new.source, new.target)
        with self.assertRaises(ModelError): require_canonical_reorder(old, forged)

    def test_migration_relation_id_survives_canonical_preparation(self):
        old = validate_relation_references(pair(reverse=True, id_scheme="derived128-v1")).relations[0]
        new = canonical_relation(old); require_canonical_reorder(old, new)
        self.assertEqual(old.relation.identity, new.relation.identity)
        self.assertEqual(new.relation.data["id_scheme"], "derived128-v1")

    def test_legacy_artifact_ids_use_literal_lexicographic_order(self):
        a=artifact(id="SR-REQ-0090", id_scheme="legacy-sequential-v1", relations=[edge("duplicates", "SR-REQ-0002")])
        b=artifact(number=2,id="SR-REQ-0002",id_scheme="legacy-sequential-v1")
        result=canonical_relations(validate_relation_references(records(a,b)))[0]
        self.assertEqual(result.source.id,"SR-REQ-0002"); self.assertEqual(result.target.id,"SR-REQ-0090")
        self.assertEqual(result.relation.identity.id,rid())

    def test_cross_type_conflicts_sort_entire_ids_not_array_position(self):
        refs=validate_relation_references(pair(reverse=True, source_kind="task", target_kind="goal"))
        result=canonical_relations(refs)[0]
        self.assertLess(result.source.id,result.target.id)
        self.assertEqual({result.source.artifact_type,result.target.artifact_type},{"task","goal"})

    def test_reverse_copies_with_different_metadata_are_not_merged(self):
        a=artifact(relations=[edge("conflicts_with",aid(number=2),1,rationale="one")])
        b=artifact(number=2,relations=[edge("conflicts_with",aid(),2,rationale="two")])
        values=records(a,b); before=[v.source_bytes for v in values]
        with self.assertRaises(ModelError) as caught: canonical_relations(validate_relation_references(values))
        self.assertEqual(caught.exception.reason,"duplicate_symmetric_relation")
        self.assertEqual([v.source_bytes for v in values],before)

    def test_opposite_directed_dependencies_are_not_inverse_copies(self):
        a=artifact(relations=[edge("depends_on",aid(number=2),1)])
        b=artifact(number=2,relations=[edge("depends_on",aid(),2)])
        views=RelationViews(validate_relation_references(records(a,b)))
        found=views.for_artifact(aid()); self.assertEqual(len(found),2)
        self.assertEqual({v.inverse for v in found},{True,False})
        self.assertEqual(len(views.stored_relations),2)

    def test_relation_id_and_metadata_do_not_change_on_array_reordering(self):
        a=artifact(relations=[edge("duplicates",aid(number=2),2,rationale="a"),edge("conflicts_with",aid(number=2),1,rationale="b")])
        one=RelationViews(validate_relation_references(records(a,artifact(number=2))))
        a["relations"].reverse()
        two=RelationViews(validate_relation_references(records(artifact(number=2),a)))
        self.assertEqual(one.stored_relations,two.stored_relations)
        self.assertEqual(one.for_artifact(aid(number=2)),two.for_artifact(aid(number=2)))

    def test_aliases_and_external_ids_never_change_canonical_orientation(self):
        a=artifact(display_id="ZZZ",relations=[edge("duplicates",aid(number=2),external_identities=[external()])])
        b=artifact(number=2,display_id="AAA")
        views=RelationViews(validate_relation_references(records(a,b)))
        self.assertEqual(views.stored_relations[0].source.id,aid())
        with self.assertRaises(ModelError):views.for_artifact("AAA")

    def test_missing_targets_are_not_synthesized_for_inverse_views(self):
        with self.assertRaises(ModelError):
            RelationViews(validate_relation_references(records(artifact(relations=[edge("supersedes")]))))

    def test_source_bytes_are_preserved_after_repeated_queries(self):
        values=pair();before=[v.source_bytes for v in values]
        views=RelationViews(validate_relation_references(values))
        for _ in range(10):
            for value in values:views.for_artifact(value.identity.id)
        self.assertEqual([v.source_bytes for v in values],before)

    def test_projection_cannot_be_used_as_a_normative_relation(self):
        values=pair("supersedes");views=RelationViews(validate_relation_references(values))
        view=views.for_artifact(values[1].identity.id)[0]
        with self.assertRaises(ModelError):Relation(values[1].identity,view)
        with self.assertRaises(ModelError):canonical_relation(view)

    def test_view_flags_are_not_falsely_claimed_as_graph_approval(self):
        views=RelationViews(validate_relation_references(pair()))
        self.assertEqual(views.validation_scope,"canonical_relations_and_views_only")
        self.assertTrue(all(not v.normative for source in views.sources for v in views.for_artifact(source.id)))

    def test_wrong_reorder_value_types_rejected(self):
        old=validate_relation_references(pair()).relations[0]
        for invalid in (None,{},[],"edge",old.relation):
            with self.subTest(value=repr(invalid)):
                with self.assertRaises(ModelError):require_canonical_reorder(old,invalid)
                with self.assertRaises(ModelError):require_canonical_reorder(invalid,old)

    def test_distinct_isolated_instances_do_not_share_query_state(self):
        values=pair();one=RelationViews(validate_relation_references(values))
        empty=RelationViews(validate_relation_references(records(artifact())))
        self.assertEqual(empty.for_artifact(aid()),())
        self.assertEqual(len(one.for_artifact(aid())),1)

    def test_inverse_projection_works_in_moved_module_and_zipapp(self):
        raw=[v.source_bytes for v in pair("supersedes")]
        body=("from specroad.graph.relations import SourceRelations\n"
              "from specroad.graph.references import validate_relation_references\n"
              "from specroad.graph.symmetry import RelationViews\n"
              "r=[SourceRelations(x) for x in "+repr(raw)+"]\n"
              "v=RelationViews(validate_relation_references(r)).for_artifact(r[1].identity.id)[0]\n"
              "assert v.type=='superseded_by' and v.inverse and not v.normative\n")
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);out=root/'built';build_distribution(out);moved=root/'moved';out.rename(moved)
            for source in (moved/'module',moved/'specroad.pyz'):
                code="import sys;sys.path.insert(0,"+repr(str(source))+");\n"+body
                result=run_python(['-I','-S','-B','-c',code],root)
                self.assertEqual(result.returncode,0,result.stderr.decode())
