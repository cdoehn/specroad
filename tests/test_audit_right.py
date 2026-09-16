"""Audit field boundary regressions, including strict persisted UTC-Z spelling."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from specroad.model.audit import Actor, ArtifactAudit, Revision, UtcTimestamp, actor, artifact_audit
from specroad.model.artifact_schemas import validate_common_fields
from specroad.model.artifact_types import artifact_types
from specroad.model.errors import ModelError
from specroad.storage.artifact_common import CommonArtifact, read_common_artifact
from specroad.storage.project import ProjectSource
from support.artifacts import common_artifact, artifact_bytes
from support.model import configuration_file, put
from support.portable import build_distribution, files_under


class AuditRightTests(unittest.TestCase):
    def test_all_common_artifact_types_require_z_not_plus_zero_offset(self):
        for item in artifact_types():
            for field in ("created_at", "updated_at"):
                for value in ("2026-01-01T00:00:00+00:00", "2026-01-01T00:00:00z"):
                    data = common_artifact(item.artifact_type, item.prefix, **{field:value})
                    with self.subTest(kind=item.artifact_type, field=field, value=value), self.assertRaises(ModelError):
                        validate_common_fields(data)

    def test_typed_and_schema_utc_boundaries_agree(self):
        values=("2024-02-29T12:34:56Z", "2024-01-01t00:00:00.0000000000001Z",
                "2024-01-01T00:00:00+00:00", "2024-01-01T00:00:00z", "2024-01-01T00:00:00-00:00",
                "2023-02-29T00:00:00Z", "2024-01-01T23:59:60Z", "2016-12-31T23:59:60Z",
                "2024-01-01T00:00:00Z\n", "2024-01-01T00:00:00,2Z")
        for value in values:
            results=[]
            for check in (lambda: UtcTimestamp(value), lambda: validate_common_fields(common_artifact(created_at=value))):
                try: check(); results.append(True)
                except ModelError: results.append(False)
            with self.subTest(value=value): self.assertEqual(results[0],results[1])

    def test_fractional_seconds_remain_exact_through_common_reader(self):
        text="2026-01-01T00:00:00.1234567890123456789Z"
        raw=artifact_bytes(common_artifact(created_at=text,updated_at=text))
        resource=CommonArtifact(raw)
        self.assertEqual(resource.audit.created_at.value,text)
        self.assertEqual(resource.source_bytes,raw)

    def test_historical_revision_is_read_without_recreation_or_increment(self):
        raw=artifact_bytes(common_artifact(revision=7,updated_at="2026-02-01T00:00:00Z"))
        resource=CommonArtifact(raw)
        for _ in range(3):self.assertEqual(resource.audit.revision.value,7)
        self.assertEqual(resource.source_bytes,raw)

    def test_integral_number_projection_does_not_rewrite_source_bytes(self):
        raw=artifact_bytes(common_artifact(revision=7.0));resource=CommonArtifact(raw)
        self.assertEqual(resource.audit.revision.value,7)
        self.assertEqual(resource.source_bytes,raw)
        self.assertEqual(resource.common_fields["revision"],7.0)

    def test_missing_actor_identity_never_resolves_from_environment(self):
        for name in ("created_by","updated_by"):
            value=common_artifact(**{name:{"actor_type":"human"}})
            with self.assertRaises(ModelError):artifact_audit(value)
            with self.assertRaises(ModelError):validate_common_fields(value)

    def test_actors_are_not_coerced_from_strings_or_nonobjects(self):
        for value in ("human:a", None, [], 1, True):
            with self.subTest(value=repr(value)),self.assertRaises(ModelError):actor(value)

    def test_blank_nul_and_non_unicode_actor_ids_are_rejected(self):
        for value in ("", " \n\t", "a\0b", "\ud800", None, True, 1):
            with self.subTest(value=repr(value)),self.assertRaises(ModelError):Actor("human",value)

    def test_actor_type_is_closed_and_case_sensitive(self):
        for value in ("Human", "AI", "administrator", "", True, [], {}):
            with self.subTest(value=repr(value)),self.assertRaises(ModelError):Actor(value,"a")

    def test_invalid_audit_resource_leaves_file_and_directory_unchanged(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);configuration_file(root)
            raw=artifact_bytes(common_artifact(updated_at="2026-01-01T00:00:00+00:00"))
            name="spec/goals/"+common_artifact()["id"]+".json"
            put(root,name,raw); before=files_under(root); source=ProjectSource(root)
            with self.assertRaises(ModelError):read_common_artifact(source,name)
            self.assertEqual(files_under(root),before)

    def test_valid_reader_exposes_owned_audit_fields_without_writes(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);configuration_file(root)
            raw=artifact_bytes(common_artifact()); name="spec/goals/"+common_artifact()["id"]+".json"
            put(root,name,raw); before=files_under(root)
            resource=read_common_artifact(ProjectSource(root),name)
            fields=resource.audit.as_fields(); fields["created_by"]["actor_id"]="other"
            self.assertEqual(resource.audit.created_by.actor_id,"test-author")
            self.assertEqual(files_under(root),before)

    def test_bad_revision_inputs_do_not_change_original_metadata(self):
        for revision in (True, 0, -1, "1", 1.5):
            value=common_artifact(revision=revision); before=artifact_bytes(value)
            with self.assertRaises(ModelError):artifact_audit(value)
            self.assertEqual(artifact_bytes(value),before)

    def test_audit_record_requires_typed_nested_values(self):
        valid=artifact_audit(common_artifact())
        for name in ("revision","created_at","created_by","updated_at","updated_by"):
            fields={key:getattr(valid,key) for key in ("revision","created_at","created_by","updated_at","updated_by")}
            fields[name]=None
            with self.assertRaises(ModelError) as caught:ArtifactAudit(**fields)
            self.assertEqual(caught.exception.pointer,"/"+name)

    def test_large_exact_integer_is_not_rounded_by_revision_value(self):
        number=10**50 + 1
        self.assertEqual(Revision(number).value,number)
        # This pure value does not relax the independent JSON numeric boundary.

    def test_invalid_timestamp_diagnostics_do_not_include_source_text(self):
        secret="private-value-not-a-date"
        with self.assertRaises(ModelError) as caught:artifact_audit(common_artifact(updated_at=secret))
        self.assertEqual(caught.exception.pointer,"/updated_at")
        self.assertNotIn(secret,json.dumps(caught.exception.diagnostic()))

    def test_utc_extreme_calendar_dates_and_leap_candidates_preserve_values(self):
        for value in ("0001-01-01T00:00:00Z", "9999-12-31T23:59:59.999999999Z",
                      "2016-12-31T23:59:60.5Z", "2024-06-30T23:59:60Z"):
            self.assertEqual(UtcTimestamp(value).value,value)
        for value in ("2024-06-29T23:59:60Z", "2024-12-31T22:59:60Z", "2024-06-30T23:58:60Z"):
            with self.assertRaises(ModelError):UtcTimestamp(value)

    def test_metadata_fields_cannot_be_used_as_a_policy_override(self):
        value=common_artifact(revision=7,metadata_policy_version="make-me-new")
        self.assertEqual(artifact_audit(value).revision.value,7)
        self.assertNotIn("metadata_policy_version",artifact_audit(value).as_fields())

    def test_relocated_distributions_provide_relation_history_and_audit_values(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);build_distribution(root/"build")
            moved=root/"moved";(root/"build").rename(moved)
            raw=artifact_bytes(common_artifact()).decode("utf-8")
            for location in (moved/"module",moved/"specroad.pyz"):
                code=("import sys;sys.path.insert(0,sys.argv[1]);"
                      "from specroad.model.audit import Actor,UtcTimestamp,new_artifact_audit;"
                      "from specroad.storage.artifact_common import CommonArtifact;"
                      "from specroad.model.identity_history import HistoryOrigin,compare_histories,HistoryComparison;"
                      "from specroad.storage.history_observation import observe_artifact_history;"
                      "from specroad.model.relation_identity import RelationInventory,allocate_relation_identity;"
                      "r=CommonArtifact(sys.argv[2].encode());assert r.audit.revision.value==1;"
                      "a=new_artifact_audit(actor=Actor('human','a'),planned_at=UtcTimestamp('2026-01-01T00:00:00Z'));"
                      "assert a.revision.value==1;"
                      "o=observe_artifact_history(r.source_bytes,origin=HistoryOrigin(r.id,'h','e'));"
                      "assert compare_histories(o,o)==HistoryComparison.IDENTICAL_COPY;"
                      "i=allocate_relation_identity(RelationInventory([],[],[]));assert i.identity.id_scheme=='random128-v1'")
                result=subprocess.run([sys.executable,"-I","-S","-B","-c",code,str(location),raw],cwd=root,
                    stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
                self.assertEqual(result.returncode,0,result.stderr.decode())
