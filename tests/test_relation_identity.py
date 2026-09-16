"""Behavior of random relation allocation; no probabilistic uniqueness oracle."""

import unittest
from dataclasses import FrozenInstanceError
from unittest.mock import patch

from specroad.model.errors import ModelError
from specroad.model.identity_tokens import encode128
from specroad.model.relation_identity import (
    RelationIdentity, RelationInventory, RelationAllocation, relation_identity,
    allocate_relation_identity,
)


def rid(number):
    return "REL-" + encode128(number.to_bytes(16, "big"))


def inventory(**changes):
    values = dict(current_ids=[], archived_ids=[], reserved_ids=[])
    values.update(changes)
    return RelationInventory(**values)


class RelationIdentityTests(unittest.TestCase):
    def test_equal_relation_contents_get_independent_identities(self):
        content = {"type": "refines", "target": "SR-REQ-0001", "extensions": {}}
        with patch("specroad.model.relation_identity.secrets.token_bytes", side_effect=[bytes(16), (1).to_bytes(16, "big")]) as entropy:
            first = allocate_relation_identity(inventory())
            second = allocate_relation_identity(first.inventory)
        a = dict(content, **first.identity.as_fields())
        b = dict(content, **second.identity.as_fields())
        self.assertEqual(a["target"], b["target"])
        self.assertNotEqual(a["relation_id"], b["relation_id"])
        self.assertEqual(entropy.call_args_list, [unittest.mock.call(16)] * 2)
        self.assertNotIn("relation_id", content)

    def test_all_128_random_bits_and_canonical_format_are_preserved(self):
        with patch("specroad.model.relation_identity.secrets.token_bytes", return_value=b"\xff" * 16):
            result = allocate_relation_identity(inventory())
        self.assertEqual(result.identity.relation_id, "REL-7" + "Z" * 25)
        self.assertEqual(result.identity.id_scheme, "random128-v1")

    def test_current_collision_is_retried(self):
        old = inventory(current_ids=[rid(0)])
        with patch("specroad.model.relation_identity.secrets.token_bytes", side_effect=[bytes(16), (1).to_bytes(16, "big")]):
            result = allocate_relation_identity(old)
        self.assertEqual(result.identity.id, rid(1))
        self.assertFalse(old.reserved_ids)

    def test_archived_identity_is_not_reused(self):
        old = inventory(archived_ids=[rid(0)])
        with patch("specroad.model.relation_identity.secrets.token_bytes", side_effect=[bytes(16), (1).to_bytes(16, "big")]):
            result = allocate_relation_identity(old)
        self.assertEqual(result.identity.id, rid(1))
        self.assertEqual(result.inventory.archived_ids, frozenset({rid(0)}))

    def test_reserved_identity_is_not_reused(self):
        old = inventory(reserved_ids=[rid(0)])
        with patch("specroad.model.relation_identity.secrets.token_bytes", side_effect=[bytes(16), (1).to_bytes(16, "big")]):
            result = allocate_relation_identity(old)
        self.assertEqual(result.inventory.reserved_ids, frozenset({rid(0), rid(1)}))

    def test_migrated_scheme_is_readable_not_regularly_reservable(self):
        value = relation_identity({"relation_id": rid(0), "id_scheme": "derived128-v1"})
        self.assertEqual(value.id, rid(0))
        with self.assertRaises(ModelError): inventory().reserve(value)

    def test_artifact_prefixes_and_legacy_numbers_are_not_relation_ids(self):
        for value in ("SR-REL-0001", "REL-0001", "SR-REL-" + "0" * 26, "rel-" + "0" * 26, "REL-8" + "0" * 25):
            with self.subTest(value=value), self.assertRaises(ModelError): RelationIdentity(value, "random128-v1")

    def test_reader_requires_both_identity_fields(self):
        for value in ({}, {"relation_id": rid(0)}, {"id_scheme": "random128-v1"}, None, [], True):
            with self.subTest(value=repr(value)), self.assertRaises(ModelError): relation_identity(value)

    def test_endpoint_fields_do_not_influence_identity_reading(self):
        value = {"relation_id": rid(0), "id_scheme": "random128-v1", "target": "SR-REQ-0001", "position": 3}
        first = relation_identity(value)
        value.update(target="SR-REQ-0002", position=999)
        self.assertEqual(relation_identity(value), first)

    def test_unknown_schemes_are_rejected(self):
        for scheme in ("legacy-sequential-v1", "sha256", None, [], True):
            with self.subTest(scheme=repr(scheme)), self.assertRaises(ModelError): RelationIdentity(rid(0), scheme)

    def test_inventory_owns_its_inputs(self):
        current = [rid(0)]; old = inventory(current_ids=current); current.clear()
        self.assertEqual(old.current_ids, frozenset({rid(0)}))
        with self.assertRaises(FrozenInstanceError): old.current_ids = frozenset()

    def test_duplicate_current_ids_are_rejected(self):
        with self.assertRaises(ModelError) as caught: inventory(current_ids=[rid(0), rid(0)])
        self.assertEqual(caught.exception.reason, "duplicate_relation_id")

    def test_entropy_error_preserves_reservations(self):
        old = inventory(reserved_ids=[rid(2)])
        with patch("specroad.model.relation_identity.secrets.token_bytes", side_effect=OSError("private")):
            with self.assertRaises(ModelError) as caught: allocate_relation_identity(old)
        self.assertEqual(caught.exception.reason, "entropy_unavailable")
        self.assertEqual(old.reserved_ids, frozenset({rid(2)}))

    def test_invalid_entropy_size_is_not_reserved(self):
        old = inventory()
        with patch("specroad.model.relation_identity.secrets.token_bytes", return_value=bytes(15)):
            with self.assertRaises(ModelError): allocate_relation_identity(old)
        self.assertFalse(old.reserved_ids)

    def test_forged_reservation_result_is_rejected(self):
        value = RelationIdentity(rid(0), "random128-v1")
        with self.assertRaises(ModelError): RelationAllocation(value, inventory())

    def test_fields_return_independent_objects(self):
        value = RelationIdentity(rid(0), "random128-v1")
        fields = value.as_fields(); fields["relation_id"] = rid(1)
        self.assertEqual(value.as_fields()["relation_id"], rid(0))
