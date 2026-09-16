"""Audit value contracts and a pure revision-one factory, not write permission."""

import unittest
from dataclasses import FrozenInstanceError
from unittest.mock import patch

from specroad.model.audit import Actor, Revision, UtcTimestamp, actor, artifact_audit, new_artifact_audit
from specroad.model.artifact_types import artifact_types
from specroad.model.artifact_schemas import validate_common_fields
from specroad.model.errors import ModelError
from support.artifacts import common_artifact


class AuditTests(unittest.TestCase):
    def test_regular_creation_starts_at_one_with_complete_bound_actor_and_time(self):
        who=Actor("human","test-author"); when=UtcTimestamp("2026-09-16T00:00:00.123456789Z")
        value=new_artifact_audit(actor=who, planned_at=when)
        self.assertEqual(value.as_fields(), {"revision":1, "created_at":when.value,
            "created_by":who.as_fields(), "updated_at":when.value, "updated_by":who.as_fields()})

    def test_bound_inputs_do_not_read_wall_clock_or_environment(self):
        who=Actor("tool","test-tool"); when=UtcTimestamp("2026-01-01T00:00:00Z")
        with patch("time.time", side_effect=AssertionError("clock forbidden")), patch("os.getenv", side_effect=AssertionError("environment forbidden")):
            self.assertEqual(new_artifact_audit(actor=who,planned_at=when),new_artifact_audit(actor=who,planned_at=when))

    def test_all_actor_types_are_supported_without_authentication(self):
        for kind in ("human","ai","ci","tool"):
            self.assertEqual(actor({"actor_type":kind,"actor_id":"名 e\u0301"}),Actor(kind,"名 e\u0301"))

    def test_actor_data_is_not_a_mutable_alias(self):
        data={"actor_type":"human","actor_id":"A"}; value=actor(data); data["actor_id"]="B"
        self.assertEqual(value.actor_id,"A")
        output=value.as_fields();output["actor_id"]="C";self.assertEqual(value.actor_id,"A")

    def test_revision_accepts_positive_integer_json_values(self):
        for value in (1, 2, 10000, 1.0, 7.0):
            self.assertEqual(Revision(value).value,int(value))
            self.assertIs(type(Revision(value).value),int)

    def test_fractional_boolean_and_nonpositive_revisions_are_rejected(self):
        for value in (0, -1, True, False, 1.2, "1", None, float("nan"), float("inf")):
            with self.subTest(value=repr(value)), self.assertRaises(ModelError):Revision(value)

    def test_exact_fractional_seconds_are_retained_not_truncated(self):
        for text in ("2024-02-29T23:59:59Z","2024-02-29t23:59:59.00000000123456789Z"):
            self.assertEqual(UtcTimestamp(text).value,text)

    def test_utc_z_contract_rejects_offset_and_local_spelling(self):
        for text in ("2024-01-01T00:00:00+00:00","2024-01-01T00:00:00z","2024-01-01T00:00:00","2024-01-01T00:00:00-00:00"):
            with self.subTest(text=text),self.assertRaises(ModelError):UtcTimestamp(text)

    def test_invalid_calendar_date_is_rejected(self):
        for text in ("2023-02-29T00:00:00Z","0000-01-01T00:00:00Z","2024-01-01T24:00:00Z"):
            with self.subTest(text=text),self.assertRaises(ModelError):UtcTimestamp(text)

    def test_existing_audit_is_not_reset_to_revision_one(self):
        values=common_artifact(revision=7,updated_at="2026-02-01T00:00:00Z",updated_by={"actor_type":"ci","actor_id":"job-7"})
        result=artifact_audit(values)
        self.assertEqual(result.revision.value,7)
        self.assertEqual(result.updated_at.value,values["updated_at"])
        self.assertNotEqual(result.created_by,result.updated_by)

    def test_factory_metadata_applies_to_all_twenty_eight_common_envelopes(self):
        audit=new_artifact_audit(actor=Actor("human","a"),planned_at=UtcTimestamp("2026-01-01T00:00:00Z"))
        for item in artifact_types():
            value=common_artifact(item.artifact_type,item.prefix,**audit.as_fields())
            validate_common_fields(value)
            self.assertEqual(artifact_audit(value),audit)

    def test_audit_and_nested_values_are_immutable(self):
        value=new_artifact_audit(actor=Actor("human","a"),planned_at=UtcTimestamp("2026-01-01T00:00:00Z"))
        with self.assertRaises(FrozenInstanceError):value.revision=Revision(2)
        with self.assertRaises(FrozenInstanceError):value.created_by.actor_id="b"
        fields=value.as_fields();fields["created_by"]["actor_id"]="c"
        self.assertEqual(value.updated_by.actor_id,"a")

    def test_missing_bound_inputs_are_not_inferred(self):
        with self.assertRaises(TypeError):new_artifact_audit()
        with self.assertRaises(ModelError):new_artifact_audit(actor={},planned_at=UtcTimestamp("2026-01-01T00:00:00Z"))
        with self.assertRaises(ModelError):new_artifact_audit(actor=Actor("human","a"),planned_at="2026-01-01T00:00:00Z")

    def test_missing_audit_field_is_reported_at_its_pointer(self):
        for name in ("revision","created_at","created_by","updated_at","updated_by"):
            value=common_artifact();value.pop(name)
            with self.assertRaises(ModelError) as caught:artifact_audit(value)
            self.assertEqual(caught.exception.pointer,"/"+name)

    def test_incomplete_or_unknown_actor_data_is_not_accepted(self):
        for value in ({},{"actor_type":"human"},{"actor_id":"a"},{"actor_type":"admin","actor_id":"a"}, {"actor_type":"human","actor_id":"a","extra":1}):
            with self.subTest(value=repr(value)),self.assertRaises(ModelError):actor(value)

    def test_actor_failure_points_into_correct_audit_field(self):
        value=common_artifact(updated_by={"actor_type":"human","actor_id":""})
        with self.assertRaises(ModelError) as caught:artifact_audit(value)
        self.assertEqual(caught.exception.pointer,"/updated_by/actor_id")
