"""Boundary cases for explicit requirement metadata, not prose semantics."""
import copy
from dataclasses import FrozenInstanceError
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from specroad.model.audit import Actor, UtcTimestamp
from specroad.model.canonical import canonical_json_sha256
from specroad.model.configuration import ProjectConfiguration
from specroad.model.domain_fields import REQUIREMENT_KINDS, PRIORITIES, CRITICALITIES
from specroad.model.domain_schemas import domain_schema, validate_domain_fields
from specroad.model.errors import ModelError
from specroad.model.requirement import NormativeForce, RequirementDraft, prepare_requirement, requirement_meaning
from specroad.model.requirement_duration import RequirementDuration
from specroad.storage.requirement import RequirementArtifact, read_requirement
from specroad.storage.project import ProjectSource
from support.domain import domain_value
from support.model import configuration_value, configuration_file, put
from support.portable import build_distribution, files_under
from test_requirement import fields, prepare, IDENTITY, ACTOR, TIME


class RequirementRightTests(unittest.TestCase):
    def test_all_forces_independent_of_all_priorities(self):
        for force in ("must", "must_not", "should", "may"):
            for priority in PRIORITIES:
                with self.subTest(force=force, priority=priority):
                    extra = dict(deviation_conditions="During review", deviation_authority="reviewer") if force == "should" else {}
                    draft = prepare(fields(normative_force=force, priority=priority, **extra))
                    self.assertEqual(draft.data["normative_force"], force)
                    self.assertEqual(draft.data["priority"], priority)

    def test_kind_does_not_determine_force(self):
        for kind in REQUIREMENT_KINDS:
            with self.subTest(kind=kind):
                self.assertEqual(prepare(fields(requirement_kind=kind, normative_force="may")).meaning.normative_force, NormativeForce.MAY)

    def test_criticality_does_not_determine_force(self):
        for criticality in CRITICALITIES:
            with self.subTest(criticality=criticality):
                self.assertEqual(prepare(fields(criticality=criticality, normative_force="may")).data["normative_force"], "may")

    def test_keywords_never_repair_missing_force(self):
        for statement in ("MUSS", "must", "SHOULD", "must not", "Das System SOLLTE laufen."):
            with self.subTest(statement=statement):
                value = fields(statement=statement, priority="mandatory"); value.pop("normative_force")
                with self.assertRaises(ModelError): prepare(value)

    def test_prose_is_not_semantically_rewritten(self):
        for statement in ("Das System sollte keinen Alarm auslösen.", "The system must not stop.", "No telemetry is transmitted."):
            with self.subTest(statement=statement):
                self.assertEqual(prepare(fields(normative_force="must_not", statement=statement)).meaning.statement, statement)

    def test_analyzer_extension_is_passive(self):
        extension = {"org.example": {"detected_language": "fr", "normative_force": "may", "script": "do not execute"}}
        self.assertEqual(prepare(fields(extensions=extension)).meaning.normative_force, NormativeForce.MUST)
        self.assertEqual(prepare(fields(extensions=extension)).meaning.language, "de-DE")

    def test_no_host_metadata_sources(self):
        with patch.dict(os.environ, {"LANG": "ar", "LANGUAGE": "ar", "LC_ALL": "ar", "USER": "detected-author"}), \
             patch("time.time", side_effect=AssertionError("clock consulted")), \
             patch("locale.getlocale", side_effect=AssertionError("locale consulted")), \
             patch("secrets.token_bytes", side_effect=AssertionError("identity allocated")):
            value = prepare().data
        self.assertEqual(value["created_by"], ACTOR.as_fields())
        self.assertEqual(value["created_at"], TIME.value)
        self.assertEqual(value["language"], "de-DE")

    def test_no_host_default_when_language_missing(self):
        value=fields();value.pop("language")
        with patch.dict(os.environ, {"LANG": "en_US.UTF-8", "LC_ALL": "en_US.UTF-8"}), self.assertRaises(ModelError): prepare(value)

    def test_force_aliases_and_wrong_types_rejected(self):
        for force in (None, "", "MUST", "shall", "optional", "must ", ["must"], True, 1):
            with self.subTest(force=force), self.assertRaises(ModelError): prepare(fields(normative_force=force))

    def test_empty_deviation_values_rejected(self):
        for key in ("deviation_conditions", "deviation_authority"):
            for invalid in (None, "", " \n\t", "\0", {}, [], True):
                with self.subTest(key=key, invalid=invalid):
                    value=fields(normative_force="should",deviation_conditions="Review",deviation_authority="reviewer");value[key]=invalid
                    with self.assertRaises(ModelError):prepare(value)

    def test_invalid_authority_actor_rejected(self):
        for authority in ({"actor_id": "reviewer"}, {"actor_type": "human", "actor_id": " "}, {"actor_type": "unknown", "actor_id": "reviewer"}):
            with self.subTest(authority=authority), self.assertRaises(ModelError):
                prepare(fields(normative_force="should",deviation_conditions="Review",deviation_authority=authority))

    def test_unicode_statement_bytes_remain_distinct(self):
        decomposed=prepare(fields(statement="e\u0301"));composed=prepare(fields(statement="é"))
        self.assertEqual(decomposed.meaning.statement.encode(),b'e\xcc\x81')
        self.assertNotEqual(canonical_json_sha256(decomposed.data), canonical_json_sha256(composed.data))

    def test_multilingual_statements_preserved_without_detection(self):
        for language,statement in (("ar","النظام يعمل دون اتصال"),("ja","システムはオフラインで動作する。"),("hi","सिस्टम ऑफ़लाइन काम करता है।"),("x-project","opaque project text")):
            with self.subTest(language=language):
                draft=prepare(fields(language=language,statement=statement))
                self.assertEqual((draft.meaning.language,draft.meaning.statement),(language,statement))

    def test_surrogates_rejected_without_writing(self):
        with self.assertRaises(ModelError):prepare(fields(statement="\ud800"))

    def test_unknown_objects_are_not_converted(self):
        class Trap:
            def __str__(self):raise AssertionError("converted foreign object")
            def __reduce__(self):raise AssertionError("copied foreign object")
        with self.assertRaises(ModelError):prepare(fields(scope={"value":Trap()}))

    def test_cycles_are_rejected(self):
        value=fields();value["scope"]={};value["scope"]["self"]=value
        with self.assertRaises(ModelError):prepare(value)

    def test_raw_configuration_cannot_be_smuggled_as_default(self):
        with self.assertRaises(ModelError):prepare(configuration={"default_language":"en"})

    def test_invalid_project_default_is_not_repaired(self):
        for default in (None, "", " ", [], 2):
            with self.subTest(default=default):
                # The new closed policy rejects bad defaults at configuration
                # load, before they could reach the requirement constructor.
                with self.assertRaises(ModelError):
                    config=ProjectConfiguration(configuration_value(language_policy={"default_language":default}))
                    value=fields();value.pop("language")
                    prepare(value,configuration=config)

    def test_mutating_caller_config_does_not_change_draft(self):
        config_value=configuration_value(language_policy={"default_language":"ja"})
        config=ProjectConfiguration(config_value);config_value["language_policy"]["default_language"]="de"
        value=fields();value.pop("language");draft=prepare(value,configuration=config)
        detached=config.data;detached["language_policy"]["default_language"]="en"
        self.assertEqual(draft.meaning.language,"ja")

    def test_prepared_fields_roundtrip_through_reader(self):
        draft=prepare();raw=json.dumps(draft.data,ensure_ascii=False,indent=3).encode()
        record=RequirementArtifact(raw)
        self.assertEqual(record.source_bytes,raw)
        self.assertEqual(record.meaning,draft.meaning)
        self.assertEqual(record.data,draft.data)

    def test_loaded_record_missing_language_is_not_defaulted(self):
        value=domain_value("requirement");value.pop("language")
        with self.assertRaises(ModelError):RequirementArtifact(json.dumps(value).encode())

    def test_loaded_record_missing_force_is_not_defaulted(self):
        value=domain_value("requirement");value.pop("normative_force")
        with self.assertRaises(ModelError):RequirementArtifact(json.dumps(value).encode())

    def test_legacy_record_keeps_revision_and_actor(self):
        value=domain_value("requirement",id="SR-REQ-0033",id_scheme="legacy-sequential-v1",revision=55)
        raw=json.dumps(value,indent=4).encode();record=RequirementArtifact(raw)
        self.assertEqual(record.source_bytes,raw);self.assertEqual(record.data,value)

    def test_reader_returns_independent_data(self):
        record=RequirementArtifact(json.dumps(domain_value("requirement",preconditions=["A"])).encode())
        record.data["preconditions"].append("B")
        self.assertEqual(record.data["preconditions"],["A"])

    def test_reader_rejects_other_artifact_types(self):
        with self.assertRaises(ModelError):RequirementArtifact(json.dumps(domain_value("goal")).encode())

    def test_reader_rejects_duplicate_keys(self):
        raw=json.dumps(domain_value("requirement")).encode();raw=raw[:-1]+b',"normative_force":"may"}'
        with self.assertRaises(ModelError):RequirementArtifact(raw)

    def test_bound_reader_does_not_change_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);configuration_file(root);raw=json.dumps(domain_value("requirement")).encode()
            name=IDENTITY.path;put(root,name,raw);before=files_under(root)
            result=read_requirement(ProjectSource(root),name)
            self.assertEqual(result.source_bytes,raw);self.assertEqual(files_under(root),before)

    def test_bound_reader_rejects_path_identity_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);configuration_file(root);put(root,IDENTITY.path,json.dumps(domain_value("requirement",id="SR-REQ-"+"1"*26)).encode())
            with self.assertRaises(ModelError):read_requirement(ProjectSource(root),IDENTITY.path)

    def test_bound_reader_rejects_stale_configuration(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);configuration_file(root);put(root,IDENTITY.path,json.dumps(domain_value("requirement")).encode())
            source=ProjectSource(root);configuration_file(root,project_id="other")
            with self.assertRaises(ModelError):read_requirement(source,IDENTITY.path)

    def test_no_approval_or_verification_is_inferred(self):
        result=prepare(fields(normative_force="may",implementation_status="implemented"))
        self.assertEqual(result.data["maturity"],"draft")
        self.assertEqual(result.data["verification_plan_status"],"not_planned")
        self.assertNotIn("verification_result",result.data)

    def test_meaning_requires_requirement_record(self):
        with self.assertRaises(ModelError):requirement_meaning(domain_value("need"))

    def test_draft_cannot_wrap_approved_or_historical_content(self):
        for key,val in (("maturity","approved"),("revision",2),("updated_at","2026-09-17T00:00:00Z")):
            with self.subTest(field=key):
                data=prepare().data;data[key]=val
                with self.assertRaises(ModelError):RequirementDraft(data,language_source="input",force_source="input")

    def test_moved_distributions_keep_requirement_constructor(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);output=root/"build";build_distribution(output);moved=root/"moved";output.rename(moved)
            script=("import json;from specroad.model.requirement import prepare_requirement;"
                    "from specroad.model.audit import Actor,UtcTimestamp;from specroad.model.identity_values import ArtifactIdentity;"
                    "from specroad.storage.requirement import RequirementArtifact;"
                    "v=json.loads("+repr(json.dumps(fields()))+");"
                    "d=prepare_requirement(v,identity=ArtifactIdentity("+repr(IDENTITY.id)+",'random128-v1','requirement','SR'),"
                    "actor=Actor('human','test'),planned_at=UtcTimestamp('2026-09-16T00:00:00Z'));"
                    "r=RequirementArtifact(json.dumps(d.data).encode());assert r.meaning.normative_force.value=='must';assert r.data==d.data")
            # The payload API is imported from relocated module and archive paths;
            # no assertions depend on CLI presentation or installation location.
            for path in (moved/"module",moved/"specroad.pyz"):
                result=subprocess.run([sys.executable,"-I","-S","-B","-c","import sys;sys.path.insert(0,"+repr(str(path))+");"+script],stdin=subprocess.DEVNULL,cwd=root)
                self.assertEqual(result.returncode,0)


class RequirementDurationTests(unittest.TestCase):
    def test_iso_durations_preserved_without_unit_conversion(self):
        for value in ("PT0S","PT0.001S","P1Y2M3DT4H5M6S","P2W","P1M","PT1M","PT1,5H"):
            with self.subTest(value=value):self.assertEqual(RequirementDuration(value).data,value)

    def test_quantity_requires_explicit_supported_time_unit(self):
        for unit in ("s","ms","us","ns","min","h","d","wk"):
            with self.subTest(unit=unit):
                value={"value":1.25,"unit":unit};self.assertEqual(RequirementDuration(value).data,value)

    def test_unitless_and_invalid_values_rejected(self):
        for value in (3,True,None,{"value":3},{"unit":"s"},{"value":True,"unit":"s"},{"value":-1,"unit":"s"},{"value":"1","unit":"s"}):
            with self.subTest(value=value),self.assertRaises(ModelError):RequirementDuration(value)

    def test_invalid_iso_designators_rejected(self):
        for value in ("P","PT","P1DT","P1W2D","P1.5DT1H","PT1.5H2M","PT1S1H","3 seconds","PT1S\n"):
            with self.subTest(value=value),self.assertRaises(ModelError):RequirementDuration(value)

    def test_unknown_units_report_unsupported_not_validated(self):
        for unit in ("seconds","MS","m","kg","s/m.m"):
            with self.subTest(unit=unit),self.assertRaises(ModelError) as caught:RequirementDuration({"value":1,"unit":unit})
            self.assertEqual(caught.exception.reason,"unsupported_duration_unit")

    def test_nonfinite_duration_rejected(self):
        for value in (float("inf"),float("nan")):
            with self.assertRaises(ModelError):RequirementDuration({"value":value,"unit":"s"})

    def test_duration_is_owned(self):
        source={"value":10,"unit":"ms"};value=RequirementDuration(source);source["value"]=20
        value.data["unit"]="s";self.assertEqual(value.data,{"value":10,"unit":"ms"})

    def test_explicit_duration_can_be_used_in_requirement_semantics(self):
        duration=RequirementDuration({"value":10,"unit":"ms"})
        result=prepare(fields(timing=duration.data))
        self.assertEqual(result.data["timing"],duration.data)
