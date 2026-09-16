"""Exact-byte history observations, with explicit unresolved/conflict outcomes."""

from dataclasses import replace
from hashlib import sha256
import unittest

from specroad.model.errors import ModelError
from specroad.model.identity_history import (
    HistoryOrigin, HistoryObservation, HistoryComparison, compare_histories,
    require_same_history,
)
from specroad.model.identity_values import artifact_identity
from specroad.model.relation_identity import RelationIdentity
from specroad.storage.history_observation import observe_artifact_history, observe_relation_history
from support.artifacts import common_artifact, artifact_bytes
from test_identity_history import observation


class IdentityHistoryRightTests(unittest.TestCase):
    def test_origin_event_distinguishes_independent_creation_in_one_namespace(self):
        first = observation(); other = replace(first, origin=replace(first.origin, creation_event="creation-2"))
        self.assertEqual(compare_histories(first, other), HistoryComparison.IDENTITY_CONFLICT)
        with self.assertRaises(ModelError) as caught: require_same_history(first, other)
        self.assertEqual(caught.exception.reason, "identity_conflict")

    def test_unresolved_provenance_is_not_treated_as_compatible(self):
        with self.assertRaises(ModelError) as caught: require_same_history(observation(origin=None), observation())
        self.assertEqual(caught.exception.reason, "identity_history_unresolved")

    def test_precondition_accepts_copies_and_history_not_new_identities(self):
        self.assertEqual(require_same_history(observation(), observation()), HistoryComparison.IDENTICAL_COPY)
        self.assertEqual(require_same_history(observation(), observation(content_sha256="b"*64)), HistoryComparison.SAME_HISTORY)
        new = artifact_identity(common_artifact(id="SR-GOAL-" + "1"*26))
        with self.assertRaises(ModelError): require_same_history(observation(), observation(identity=new, origin=None))

    def test_different_namespaces_with_same_event_are_not_equivalent(self):
        first=observation(); other=replace(first, origin=replace(first.origin, namespace="history-B"))
        self.assertEqual(compare_histories(first, other), HistoryComparison.IDENTITY_CONFLICT)

    def test_artifact_observation_is_bound_to_exact_bytes_and_identity(self):
        value=common_artifact(); raw=artifact_bytes(value)
        result=observe_artifact_history(raw, origin=observation().origin)
        self.assertEqual(result.identity, artifact_identity(value))
        self.assertEqual(result.content_sha256, sha256(raw).hexdigest())
        value["title"]="changed"
        self.assertEqual(result.content_sha256, sha256(raw).hexdigest())

    def test_representation_difference_is_not_reported_as_byteidentical_copy(self):
        raw=artifact_bytes(common_artifact())
        a=observe_artifact_history(raw, origin=observation().origin)
        b=observe_artifact_history(raw+b"\n", origin=observation().origin)
        self.assertEqual(compare_histories(a,b), HistoryComparison.SAME_HISTORY)

    def test_equal_audit_metadata_does_not_establish_history(self):
        raw=artifact_bytes(common_artifact())
        self.assertEqual(compare_histories(observe_artifact_history(raw), observe_artifact_history(raw)), HistoryComparison.UNRESOLVED)

    def test_spoofed_display_id_never_binds_an_origin(self):
        value=common_artifact(display_id="other")
        with self.assertRaises(ModelError): observe_artifact_history(artifact_bytes(value), origin=HistoryOrigin("other","h","e"))

    def test_relation_observation_binds_source_and_bytes(self):
        identity=RelationIdentity("REL-"+"0"*26,"random128-v1")
        raw=artifact_bytes(dict(identity.as_fields(), type="refines", target="SR-REQ-0001"))
        result=observe_relation_history(raw, source=observation().identity, origin=HistoryOrigin(identity.id,"h","e"))
        self.assertEqual(result.identity, identity)
        self.assertEqual(result.source, observation().identity)
        self.assertEqual(result.content_sha256,sha256(raw).hexdigest())

    def test_relation_history_requires_real_source_identity_not_label(self):
        raw=artifact_bytes(RelationIdentity("REL-"+"0"*26,"random128-v1").as_fields())
        for source in (None, "SR-GOAL-0001", True, {}, []):
            with self.subTest(source=repr(source)), self.assertRaises(ModelError): observe_relation_history(raw, source=source)

    def test_malformed_json_is_not_an_observation(self):
        for raw in (b'[]', b'{} garbage', b'{"id":1,"id":2}', b'\xff', "{}"):
            with self.subTest(raw=repr(raw)), self.assertRaises(ModelError): observe_artifact_history(raw)

    def test_partial_or_invalid_origins_are_rejected(self):
        for bad in (None, True, "", " \t", "secret\0x", "\ud800"):
            with self.subTest(bad=repr(bad)), self.assertRaises(ModelError): HistoryOrigin(observation().identity.id,"namespace",bad)

    def test_hash_must_be_complete_lowercase_sha256(self):
        for bad in ("a"*63, "A"*64, "a"*64+"\n", None, 1):
            with self.subTest(bad=repr(bad)), self.assertRaises(ModelError): observation(content_sha256=bad)

    def test_artifact_observation_cannot_carry_a_relation_source(self):
        with self.assertRaises(ModelError): observation(source=observation().identity)

    def test_plain_objects_are_not_trusted_origin_bindings(self):
        with self.assertRaises(ModelError): observation(origin={"subject_id":observation().identity.id,"namespace":"h","creation_event":"e"})
        with self.assertRaises(ModelError): compare_histories({}, observation())

    def test_comparison_is_symmetric_and_leaves_inputs_unchanged(self):
        first=observation()
        values=(observation(), observation(content_sha256="b"*64), observation(origin=None),
                replace(first, origin=replace(first.origin, creation_event="other")))
        before=(first,values)
        for other in values:
            self.assertEqual(compare_histories(first,other),compare_histories(other,first))
        self.assertEqual((first,values),before)
