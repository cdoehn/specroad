"""Behavior of the shared, non-writing requirement constructor."""
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
from specroad.model.configuration import ProjectConfiguration
from specroad.model.domain_schemas import validate_domain_fields
from specroad.model.errors import ModelError
from specroad.model.identity_values import ArtifactIdentity
from specroad.model.requirement import NormativeForce, RequirementDraft, prepare_requirement, requirement_meaning
from support.domain import domain_value
from support.model import configuration_value
from support.portable import build_distribution, files_under

IDENTITY = ArtifactIdentity("SR-REQ-" + "0" * 26, "random128-v1", "requirement", "SR")
ACTOR = Actor("human", "author")
TIME = UtcTimestamp("2026-09-16T00:00:00.123456789Z")


def fields(**changes):
    data = {"title": "Offline operation", "requirement_kind": "functional", "language": "de-DE",
            "normative_force": "must", "statement": "Das System funktioniert ohne Netzwerkverbindung.",
            "priority": "low", "criticality": "normal"}
    data.update(changes)
    return data


def prepare(value=None, **options):
    return prepare_requirement(fields() if value is None else value, identity=IDENTITY,
                               actor=ACTOR, planned_at=TIME, **options)


class RequirementWorkTests(unittest.TestCase):
    def test_indicative_statement_without_modal_word(self):
        draft = prepare()
        self.assertEqual(draft.meaning.statement, fields()["statement"])
        self.assertEqual(draft.meaning.normative_force, NormativeForce.MUST)
        self.assertEqual(draft.data["maturity"], "draft")
        self.assertEqual(draft.validation_scope, "requirement_fields_only")
        validate_domain_fields(draft.data, expected_type="requirement")

    def test_four_forces_are_exact_independent_values(self):
        for force in ("must", "must_not", "should", "may"):
            with self.subTest(force=force):
                extra = {"deviation_conditions": "During evaluation", "deviation_authority": "reviewer"} if force == "should" else {}
                self.assertEqual(prepare(fields(normative_force=force, **extra)).meaning.normative_force.value, force)

    def test_should_requires_both_deviation_fields(self):
        for extra in ({}, {"deviation_conditions": "Exception"}, {"deviation_authority": "reviewer"}):
            with self.subTest(extra=extra), self.assertRaises(ModelError):
                prepare(fields(normative_force="should", **extra))

    def test_should_accepts_structured_authority(self):
        authority = {"actor_type": "human", "actor_id": "reviewer"}
        draft = prepare(fields(normative_force="should", deviation_conditions="During review", deviation_authority=authority))
        self.assertEqual(draft.data["deviation_authority"], authority)

    def test_no_force_default(self):
        value = fields(); value.pop("normative_force")
        with self.assertRaises(ModelError) as caught: prepare(value)
        self.assertEqual(caught.exception.pointer, "/normative_force")

    def test_no_language_default(self):
        value = fields(); value.pop("language")
        with self.assertRaises(ModelError) as caught: prepare(value)
        self.assertEqual(caught.exception.pointer, "/language")

    def test_explicit_project_default_is_materialized(self):
        value = fields(); value.pop("language")
        config = ProjectConfiguration(configuration_value(language_policy={"default_language": "en-IN"}))
        draft = prepare(value, configuration=config)
        self.assertEqual(draft.data["language"], "en-IN")
        self.assertEqual(draft.language_source, "project_default")
        self.assertNotIn("language", value)

    def test_input_language_wins_over_project_default(self):
        config = ProjectConfiguration(configuration_value(language_policy={"default_language": "en-IN"}))
        draft = prepare(configuration=config)
        self.assertEqual(draft.data["language"], "de-DE")
        self.assertEqual(draft.language_source, "input")

    def test_argument_language_materialized(self):
        value = fields(); value.pop("language")
        draft = prepare(value, language="ja")
        self.assertEqual(draft.data["language"], "ja")
        self.assertEqual(draft.language_source, "argument")

    def test_argument_force_materialized(self):
        value = fields(); value.pop("normative_force")
        draft = prepare(value, normative_force="must_not")
        self.assertEqual(draft.meaning.normative_force, NormativeForce.MUST_NOT)
        self.assertEqual(draft.force_source, "argument")

    def test_matching_argument_is_not_a_conflict(self):
        self.assertEqual(prepare(language="de-DE", normative_force="must").data, prepare().data)

    def test_conflicting_force_is_rejected_without_changing_input(self):
        value = fields(); before = copy.deepcopy(value)
        with self.assertRaises(ModelError) as caught: prepare(value, normative_force="may")
        self.assertEqual(caught.exception.reason, "requirement_input_conflict")
        self.assertEqual(caught.exception.pointer, "/normative_force")
        self.assertEqual(value, before)

    def test_conflicting_language_is_rejected(self):
        with self.assertRaises(ModelError) as caught: prepare(language="en")
        self.assertEqual(caught.exception.reason, "requirement_input_conflict")
        self.assertEqual(caught.exception.pointer, "/language")

    def test_defaults_do_not_use_default_locale(self):
        value = fields(); value.pop("language")
        with self.assertRaises(ModelError): prepare(value, configuration=ProjectConfiguration(configuration_value(default_locale="fr-FR")))

    def test_explicit_empty_language_does_not_trigger_default(self):
        config = ProjectConfiguration(configuration_value(language_policy={"default_language": "en"}))
        for invalid in (None, "", " ", [], 1):
            with self.subTest(invalid=invalid), self.assertRaises(ModelError):
                prepare(fields(language=invalid), configuration=config)

    def test_new_draft_has_explicit_audit(self):
        value = prepare().data
        self.assertEqual(value["revision"], 1)
        self.assertEqual(value["created_at"], TIME.value)
        self.assertEqual(value["updated_at"], TIME.value)
        self.assertEqual(value["created_by"], ACTOR.as_fields())
        self.assertEqual(value["updated_by"], ACTOR.as_fields())
        self.assertEqual(value["implementation_status"], "not_started")
        self.assertEqual(value["verification_plan_status"], "not_planned")

    def test_reserved_identity_or_approval_cannot_be_overridden(self):
        for key, val in (("id", IDENTITY.id), ("revision", 99), ("maturity", "approved"), ("created_by", ACTOR.as_fields())):
            with self.subTest(field=key), self.assertRaises(ModelError) as caught: prepare(fields(**{key: val}))
            self.assertEqual(caught.exception.reason, "reserved_requirement_field")

    def test_legacy_identity_not_generated_as_new(self):
        legacy = ArtifactIdentity("SR-REQ-0001", "legacy-sequential-v1", "requirement", "SR")
        with self.assertRaises(ModelError): prepare_requirement(fields(), identity=legacy, actor=ACTOR, planned_at=TIME)

    def test_wrong_identity_type_rejected(self):
        wrong = ArtifactIdentity("SR-GOAL-" + "0" * 26, "random128-v1", "goal", "SR")
        with self.assertRaises(ModelError): prepare_requirement(fields(), identity=wrong, actor=ACTOR, planned_at=TIME)

    def test_wrong_project_prefix_rejected(self):
        config = ProjectConfiguration(configuration_value(id_prefix="OTHER"))
        with self.assertRaises(ModelError): prepare(configuration=config)

    def test_structured_semantics_preserved(self):
        semantics = {"scope": {"boundary": "device"}, "actor": "operator", "trigger": "start",
                     "preconditions": ["configured"], "response": {"result": "ready"}, "object": "cache",
                     "timing": {"value": 10, "unit": "ms"}, "thresholds": [{"minimum": 1}], "exceptions": []}
        value = fields(**semantics); before = copy.deepcopy(value); draft = prepare(value)
        self.assertEqual({key: draft.data[key] for key in semantics}, semantics)
        self.assertEqual(value, before)

    def test_returned_data_is_owned(self):
        value = fields(preconditions=["A"]); draft = prepare(value)
        value["preconditions"].append("B")
        returned = draft.data; returned["preconditions"].append("C")
        self.assertEqual(draft.data["preconditions"], ["A"])
        with self.assertRaises(FrozenInstanceError): draft.force_source = "invented"

    def test_positive_proposition_with_must_not_is_not_negated(self):
        statement = "The system transmits telemetry to an external service."
        draft = prepare(fields(language="en-IN", normative_force="must_not", statement=statement))
        self.assertEqual(draft.meaning.statement, statement)

    def test_missing_mandatory_fields_rejected(self):
        for field in ("title", "requirement_kind", "statement", "priority", "criticality"):
            with self.subTest(field=field):
                value = fields(); value.pop(field)
                with self.assertRaises(ModelError): prepare(value)

    def test_unknown_fields_do_not_become_instructions(self):
        with self.assertRaises(ModelError): prepare(fields(detector_label="must"))

    def test_reading_legacy_requirement_does_not_restamp_it(self):
        value = domain_value("requirement", id="SR-REQ-0042", id_scheme="legacy-sequential-v1", revision=42)
        before = copy.deepcopy(value); meaning = requirement_meaning(value)
        self.assertEqual(meaning.normative_force, NormativeForce.MUST)
        self.assertEqual(value, before)

    def test_no_file_side_effect(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root / "sentinel").write_bytes(b"keep")
            before = files_under(root)
            with patch("pathlib.Path.write_bytes", side_effect=AssertionError("write attempted")):
                prepare()
            self.assertEqual(files_under(root), before)

    def test_same_explicit_inputs_are_deterministic(self):
        self.assertEqual(prepare().data, prepare().data)
