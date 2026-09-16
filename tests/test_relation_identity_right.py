"""Invalid identity, reservation and partial-schema contracts fail closed."""

import json
import unittest
from unittest.mock import patch

from specroad.model.errors import ModelError
from specroad.model.artifact_schemas import validate_common_fields
from specroad.model.relation_identity import (
    RelationIdentity, RelationInventory, RelationAllocation, relation_identity,
    allocate_relation_identity, require_relation_identity_unchanged,
)
from specroad.storage.artifact_common import CommonArtifact
from support.artifacts import artifact_bytes, common_artifact
from test_relation_identity import rid, inventory


class RelationIdentityRightTests(unittest.TestCase):
    def test_collisions_across_all_pools_are_retried(self):
        before = inventory(current_ids=[rid(0)], archived_ids=[rid(1)], reserved_ids=[rid(2)])
        with patch("specroad.model.relation_identity.secrets.token_bytes", side_effect=[i.to_bytes(16,"big") for i in range(4)]) as source:
            after = allocate_relation_identity(before)
        self.assertEqual(source.call_count, 4)
        self.assertEqual(after.identity.id, rid(3))
        self.assertEqual(before.reserved_ids, frozenset({rid(2)}))

    def test_entropy_error_after_collision_has_no_partial_reservation(self):
        before = inventory(current_ids=[rid(0)])
        with patch("specroad.model.relation_identity.secrets.token_bytes", side_effect=[bytes(16), OSError("private")]):
            with self.assertRaises(ModelError): allocate_relation_identity(before)
        self.assertFalse(before.reserved_ids)

    def test_inventory_rejects_unknown_ids_and_bad_containers(self):
        for value in (None, "REL-0001", {rid(0): 1}, 42):
            with self.subTest(value=repr(value)), self.assertRaises(ModelError): inventory(current_ids=value)
        for value in (None, True, rid(0) + "\n", "REL-" + "I" * 26, "SR-REQ-0001"):
            with self.subTest(value=repr(value)), self.assertRaises(ModelError): inventory(current_ids=[value])

    def test_invalid_inventory_does_not_consume_entropy(self):
        with patch("specroad.model.relation_identity.secrets.token_bytes", side_effect=AssertionError("entropy must not run")):
            with self.assertRaises(ModelError): allocate_relation_identity({})

    def test_derived_identity_cannot_be_forged_as_new_allocation(self):
        value = RelationIdentity(rid(0), "derived128-v1")
        with self.assertRaises(ModelError): RelationAllocation(value, inventory(reserved_ids=[rid(0)]))

    def test_existing_current_or_archived_identity_cannot_be_new_allocation(self):
        value = RelationIdentity(rid(0), "random128-v1")
        for state in (inventory(current_ids=[rid(0)], reserved_ids=[rid(0)]), inventory(archived_ids=[rid(0)], reserved_ids=[rid(0)])):
            with self.assertRaises(ModelError): RelationAllocation(value, state)

    def test_regular_update_cannot_change_id(self):
        before = RelationIdentity(rid(0), "random128-v1").as_fields()
        after = dict(before, relation_id=rid(1))
        with self.assertRaises(ModelError) as caught: require_relation_identity_unchanged(before, after)
        self.assertEqual(caught.exception.reason, "relation_identity_immutable")

    def test_regular_update_cannot_change_scheme(self):
        before = RelationIdentity(rid(0), "derived128-v1").as_fields()
        with self.assertRaises(ModelError): require_relation_identity_unchanged(before, dict(before, id_scheme="random128-v1"))

    def test_normal_fields_do_not_become_identity_fields(self):
        before = dict(RelationIdentity(rid(0), "random128-v1").as_fields(), target="SR-GOAL-0001")
        require_relation_identity_unchanged(before, dict(before, target="SR-GOAL-0002"))
        self.assertEqual(before["target"], "SR-GOAL-0001")

    def test_common_layer_validates_present_relation_ids(self):
        value = common_artifact(relations=[{"relation_id": rid(0), "id_scheme":"random128-v1"}])
        validate_common_fields(value)
        for bad in ("REL-0001", "REL-8" + "0" * 25, True, [], "x"):
            value["relations"][0]["relation_id"] = bad
            with self.subTest(bad=repr(bad)), self.assertRaises(ModelError): validate_common_fields(value)

    def test_relation_identity_fields_are_an_all_or_none_partial_projection(self):
        validate_common_fields(common_artifact(relations=[{}]))
        for item in ({"relation_id":rid(0)}, {"id_scheme":"random128-v1"}):
            with self.assertRaises(ModelError): validate_common_fields(common_artifact(relations=[item]))

    def test_reader_preserves_derived_ids_without_claiming_migration(self):
        raw = artifact_bytes(common_artifact(relations=[{"relation_id":rid(0), "id_scheme":"derived128-v1"}]))
        resource = CommonArtifact(raw)
        self.assertEqual(resource.source_bytes, raw)
        self.assertEqual(resource.validation_scope, "common_fields_only")

    def test_bad_relation_does_not_change_original_bytes(self):
        raw = artifact_bytes(common_artifact(relations=[{"relation_id":"private", "id_scheme":"random128-v1"}]))
        copy = bytes(raw)
        with self.assertRaises(ModelError) as caught: CommonArtifact(raw, path="test.json")
        self.assertEqual(raw, copy)
        self.assertEqual(caught.exception.path, "test.json")
        self.assertNotIn("private", json.dumps(caught.exception.diagnostic()))

    def test_zero_and_maximum_relation_tokens_roundtrip(self):
        for number in (0, 1, 2**127, 2**128 - 1):
            value = RelationIdentity(rid(number), "random128-v1")
            self.assertEqual(relation_identity(value.as_fields()), value)
