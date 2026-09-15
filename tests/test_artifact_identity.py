"""Identity values and allocation, not random-statistical or output tests."""

import unittest
from dataclasses import FrozenInstanceError
from unittest.mock import patch

from specroad.model.identities import (ArtifactIdentity, IdentityInventory,
    allocate_artifact_identity, encode128, decode128)
from specroad.model.artifact_types import artifact_types
from specroad.model.errors import ModelError
from support.artifacts import common_artifact


def inventory(**changes):
    data = {"id_prefix": "SR", "current_ids": [], "archived_ids": [], "reserved_ids": []}
    data.update(changes)
    return IdentityInventory(**data)


def gid(number):
    return "SR-GOAL-" + encode128(number.to_bytes(16, "big"))


class ArtifactIdentityTests(unittest.TestCase):
    def test_codec_exact_extreme_vectors(self):
        self.assertEqual(encode128(bytes(16)), "0" * 26)
        self.assertEqual(encode128(b"\xff" * 16), "7" + "Z" * 25)
        self.assertEqual(decode128("0" * 25 + "1"), bytes(15) + b"\x01")

    def test_codec_preserves_every_input_bit(self):
        for bit in range(128):
            value = (1 << bit).to_bytes(16, "big")
            self.assertEqual(decode128(encode128(value)), value)

    def test_token_aliases_case_overflow_and_length_rejected(self):
        for token in ("8" + "0" * 25, "0" * 25 + "I", "0" * 25 + "O", "0" * 25 + "L",
                      "0" * 25 + "U", "0" * 25 + "z", "0" * 25, "0" * 27, "0" * 26 + "\n", ""):
            with self.subTest(token=token), self.assertRaises(ModelError): decode128(token)

    def test_codec_requires_exact_sixteen_bytes(self):
        for value in (None, 16, "0" * 16, bytearray(16), bytes(15), bytes(17)):
            with self.subTest(value=repr(value)), self.assertRaises(ModelError): encode128(value)

    def test_all_registered_types_allocate_matching_paths(self):
        with patch("specroad.model.identities.secrets.token_bytes", return_value=bytes(16)) as entropy:
            for definition in artifact_types():
                value = allocate_artifact_identity(definition.artifact_type, inventory()).identity
                self.assertEqual(value.id, "SR-" + definition.prefix + "-" + "0" * 26)
                self.assertEqual(value.path, "spec/" + definition.directory + "/" + value.id + ".json")
                self.assertEqual(value.id_scheme, "random128-v1")
                self.assertEqual(len(value.id.rsplit("-", 1)[1]), 26)
            self.assertEqual(entropy.call_count, 28)
            entropy.assert_called_with(16)

    def test_secure_standard_library_random_source_is_used(self):
        with patch("specroad.model.identities.secrets.token_bytes", return_value=b"\xff" * 16) as entropy:
            value = allocate_artifact_identity("goal", inventory())
        entropy.assert_called_once_with(16)
        self.assertEqual(value.identity.id, "SR-GOAL-7" + "Z" * 25)

    def test_current_collision_is_retried_without_input_mutation(self):
        state = inventory(current_ids=[gid(0)])
        with patch("specroad.model.identities.secrets.token_bytes", side_effect=[bytes(16), (1).to_bytes(16, "big")]):
            value = allocate_artifact_identity("goal", state)
        self.assertEqual(value.identity.id, gid(1))
        self.assertEqual(state.reserved_ids, frozenset())
        self.assertEqual(value.inventory.reserved_ids, frozenset({gid(1)}))

    def test_archived_collision_is_not_reused(self):
        state = inventory(archived_ids=[gid(0)])
        with patch("specroad.model.identities.secrets.token_bytes", side_effect=[bytes(16), (2).to_bytes(16, "big")]):
            value = allocate_artifact_identity("goal", state)
        self.assertEqual(value.identity.id, gid(2))
        self.assertEqual(value.inventory.archived_ids, state.archived_ids)

    def test_reserved_collision_is_not_reused(self):
        state = inventory(reserved_ids=[gid(0)])
        with patch("specroad.model.identities.secrets.token_bytes", side_effect=[bytes(16), (3).to_bytes(16, "big")]):
            value = allocate_artifact_identity("goal", state)
        self.assertEqual(value.identity.id, gid(3))
        self.assertEqual(value.inventory.reserved_ids, frozenset({gid(0), gid(3)}))

    def test_inventory_is_detached_from_mutable_inputs(self):
        live = [gid(0)]; state = inventory(current_ids=live); live.clear()
        self.assertEqual(state.current_ids, frozenset({gid(0)}))
        with self.assertRaises(FrozenInstanceError): state.id_prefix = "XX"

    def test_legacy_ids_are_readable_but_not_generated(self):
        value = ArtifactIdentity("SR-GOAL-0001", "legacy-sequential-v1", "goal", "SR")
        self.assertEqual(value.path, "spec/goals/SR-GOAL-0001.json")
        with self.assertRaises(ModelError): inventory().reserve(value)
        with patch("specroad.model.identities.secrets.token_bytes", return_value=bytes(16)):
            self.assertEqual(allocate_artifact_identity("goal", inventory()).identity.id_scheme, "random128-v1")

    def test_identity_scheme_cannot_disagree_with_token(self):
        for id, scheme in (("SR-GOAL-0001", "random128-v1"), (gid(0), "legacy-sequential-v1"), (gid(0), "derived128-v1")):
            with self.subTest(scheme=scheme), self.assertRaises(ModelError): ArtifactIdentity(id, scheme, "goal", "SR")

    def test_invalid_project_and_type_are_rejected(self):
        for prefix in ("a", "a-b", "SR_", "", "TOOLONGGG", None):
            with self.subTest(prefix=str(prefix)), self.assertRaises(ModelError): inventory(id_prefix=prefix)
        with patch("specroad.model.identities.secrets.token_bytes", side_effect=AssertionError("must not run")):
            with self.assertRaises(ModelError): allocate_artifact_identity("new-plugin", inventory())

    def test_foreign_or_unknown_inventory_ids_rejected(self):
        for value in ("OTHER-GOAL-0001", "SR-UNKNOWN-0001", "label", False, "SR-GOAL-8" + "0" * 25):
            with self.subTest(value=str(value)), self.assertRaises(ModelError): inventory(current_ids=[value])

    def test_new_identity_value_is_immutable(self):
        with patch("specroad.model.identities.secrets.token_bytes", return_value=bytes(16)):
            allocated = allocate_artifact_identity("goal", inventory())
        with self.assertRaises(FrozenInstanceError): allocated.identity.id = gid(1)
        with self.assertRaises(FrozenInstanceError): allocated.inventory = inventory()

    def test_entropy_failure_leaves_inventory_unchanged(self):
        state = inventory(reserved_ids=[gid(4)])
        with patch("specroad.model.identities.secrets.token_bytes", side_effect=OSError("private entropy data")):
            with self.assertRaises(ModelError) as caught: allocate_artifact_identity("goal", state)
        self.assertEqual(caught.exception.reason, "entropy_unavailable")
        self.assertEqual(state.reserved_ids, frozenset({gid(4)}))

    def test_invalid_entropy_bytes_fail_without_reserving(self):
        state = inventory()
        with patch("specroad.model.identities.secrets.token_bytes", return_value=bytes(15)):
            with self.assertRaises(ModelError): allocate_artifact_identity("goal", state)
        self.assertFalse(state.reserved_ids)

    def test_reservation_rejects_an_already_used_id(self):
        value = ArtifactIdentity(gid(0), "random128-v1", "goal", "SR")
        with self.assertRaises(ModelError): inventory(current_ids=[gid(0)]).reserve(value)
