"""Origin-aware comparisons are not automatic merge or authenticity decisions."""

import unittest
from dataclasses import FrozenInstanceError, replace

from specroad.model.errors import ModelError
from specroad.model.identity_values import artifact_identity
from specroad.model.relation_identity import RelationIdentity
from specroad.model.identity_history import (
    HistoryOrigin, HistoryObservation, HistoryComparison, compare_histories,
)
from support.artifacts import common_artifact


def observation(**changes):
    identity = artifact_identity(common_artifact())
    values = dict(identity=identity, content_sha256="a" * 64,
                  origin=HistoryOrigin(identity.id, "project-history-A", "creation-1"))
    values.update(changes)
    return HistoryObservation(**values)


class IdentityHistoryTests(unittest.TestCase):
    def test_identical_bound_copy_is_recognized(self):
        self.assertEqual(compare_histories(observation(), observation()), HistoryComparison.IDENTICAL_COPY)

    def test_changed_content_with_same_origin_is_same_history(self):
        self.assertEqual(compare_histories(observation(), observation(content_sha256="b" * 64)), HistoryComparison.SAME_HISTORY)

    def test_independent_origins_conflict_even_with_equal_content(self):
        first = observation()
        second = replace(first, origin=HistoryOrigin(first.identity.id, "other-history", "creation-1"))
        self.assertEqual(compare_histories(first, second), HistoryComparison.IDENTITY_CONFLICT)

    def test_equal_ids_and_bytes_without_origin_do_not_prove_a_copy(self):
        self.assertEqual(compare_histories(observation(origin=None), observation(origin=None)), HistoryComparison.UNRESOLVED)

    def test_one_missing_origin_remains_unresolved(self):
        self.assertEqual(compare_histories(observation(), observation(origin=None)), HistoryComparison.UNRESOLVED)

    def test_distinct_ids_are_not_joined_by_equal_hashes(self):
        new_id = artifact_identity(common_artifact(id="SR-GOAL-" + "1" * 26))
        self.assertEqual(compare_histories(observation(), observation(identity=new_id, origin=None)), HistoryComparison.DIFFERENT_IDENTITY)

    def test_origin_must_be_bound_to_observed_identity(self):
        with self.assertRaises(ModelError): observation(origin=HistoryOrigin("SR-GOAL-0001", "history", "create"))

    def test_observations_are_immutable(self):
        value = observation()
        with self.assertRaises(FrozenInstanceError): value.content_sha256 = "b" * 64
        with self.assertRaises(FrozenInstanceError): value.origin.creation_event = "another"

    def test_relation_copy_is_also_bound_to_source(self):
        identity = RelationIdentity("REL-" + "0" * 26, "random128-v1")
        origin = HistoryOrigin(identity.id, "history", "create")
        source = artifact_identity(common_artifact())
        left = HistoryObservation(identity, "a" * 64, origin, source)
        self.assertEqual(compare_histories(left, replace(left)), HistoryComparison.IDENTICAL_COPY)
        changed = replace(left, source=artifact_identity(common_artifact(id="SR-GOAL-0001", id_scheme="legacy-sequential-v1")))
        self.assertEqual(compare_histories(left, changed), HistoryComparison.SAME_HISTORY)

    def test_relation_scheme_disagreement_is_a_conflict(self):
        identity = RelationIdentity("REL-" + "0" * 26, "random128-v1")
        value = HistoryObservation(identity, "a" * 64, HistoryOrigin(identity.id, "h", "c"), observation().identity)
        self.assertEqual(compare_histories(value, replace(value, identity=RelationIdentity(identity.id, "derived128-v1"))), HistoryComparison.IDENTITY_CONFLICT)
