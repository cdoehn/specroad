"""Domain contract behavior; neither rendered text nor documentation is an oracle."""

from pathlib import Path
import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest

from specroad.model.domain_schemas import domain_schema, validate_domain_fields
from specroad.model.errors import ModelError
from specroad.model.paths import artifact_path
from specroad.storage.domain_artifact import DomainArtifact, read_domain_artifact
from specroad.storage import ProjectSource
from support.artifacts import artifact_bytes
from support.domain import PREFIXES, domain_value, relation, waiver
from support.model import configuration_file, put
from support.portable import build_distribution

ROOT = Path(__file__).resolve().parents[1]


class DomainWorkTests(unittest.TestCase):
    def load(self, value, **options):
        return DomainArtifact(artifact_bytes(value), **options)

    def test_minimal_drafts_load_for_all_thirteen_types(self):
        for kind in PREFIXES:
            with self.subTest(kind=kind):
                value = domain_value(kind)
                resource = self.load(value)
                self.assertEqual(resource.data, value)
                self.assertEqual(resource.artifact_type, kind)
                self.assertEqual(resource.validation_scope, "domain_fields_only")

    def test_type_minimum_fields_are_not_filled_from_defaults(self):
        minimum = {
            "goal": ("statement", "owner"), "need": ("stakeholder", "statement", "owner"),
            "capability": ("description", "owner", "implementation_status", "verification_plan_status"),
            "requirement": ("requirement_kind", "language", "normative_force", "statement", "priority", "criticality", "implementation_status", "verification_plan_status"),
            "scenario": ("actors", "trigger", "main_flow"), "decision": ("context", "decision", "rationale", "owner"),
            "risk": ("description", "probability", "impact", "risk_status", "owner"),
            "assumption": ("statement", "validation_status", "owner"),
            "component": ("description", "responsibility", "owner", "implementation_status"),
            "interface": ("description", "source_component", "target_component", "owner", "implementation_status"),
            "release": ("name", "objective", "readiness_policy"), "milestone": ("objective", "owner"),
            "task": ("description", "owner", "implementation_status", "verification_plan_status", "done_criteria"),
        }
        for kind, names in minimum.items():
            for field in names:
                with self.subTest(kind=kind, field=field):
                    value = domain_value(kind); value.pop(field); before = copy.deepcopy(value)
                    with self.assertRaises(ModelError): self.load(value)
                    self.assertEqual(value, before)

    def test_common_contract_remains_mandatory(self):
        for kind in PREFIXES:
            for field in ("id", "schema_version", "maturity", "revision", "created_by", "relations", "extensions"):
                with self.subTest(kind=kind, field=field):
                    value = domain_value(kind); value.pop(field)
                    with self.assertRaises(ModelError): self.load(value)

    def test_field_names_are_closed_per_type(self):
        for kind in PREFIXES:
            for field in ("status", "verification_result", "verification_status", "arbitrary"):
                with self.subTest(kind=kind, field=field), self.assertRaises(ModelError) as caught:
                    self.load(domain_value(kind, **{field: "passed"}))
                self.assertEqual(caught.exception.reason, "unknown_field")

    def test_status_axes_are_not_interchangeable(self):
        for kind in ("capability", "requirement", "task"):
            for field, value in (("implementation_status", "planned"), ("implementation_status", "passed"),
                                 ("verification_plan_status", "implemented"), ("verification_plan_status", "passed")):
                with self.subTest(kind=kind, field=field, value=value), self.assertRaises(ModelError):
                    self.load(domain_value(kind, **{field: value}))

    def test_all_implementation_values_preserved_independently(self):
        for kind in ("capability", "requirement", "component", "interface", "task"):
            for status in ("not_started", "in_progress", "implemented", "blocked", "not_applicable"):
                with self.subTest(kind=kind, status=status):
                    value = domain_value(kind, implementation_status=status)
                    result = self.load(value).data
                    self.assertEqual(result, value)
                    self.assertNotIn("verification_result", result)
                    self.assertEqual(result["maturity"], "draft")

    def test_all_verification_plan_values_require_no_inferred_result(self):
        for kind in ("capability", "requirement", "task"):
            for status in ("not_planned", "planned", "running", "waived", "not_applicable"):
                with self.subTest(kind=kind, status=status):
                    value = domain_value(kind, verification_plan_status=status)
                    if status == "waived": value["verification_waiver"] = waiver()
                    result = self.load(value).data
                    self.assertEqual(result, value)
                    self.assertEqual(result["implementation_status"], "not_started")
                    self.assertNotIn("verification_result", result)

    def test_status_axes_only_exist_on_specified_types(self):
        for kind in ("goal", "need", "scenario", "decision", "risk", "assumption", "release", "milestone"):
            with self.subTest(kind=kind), self.assertRaises(ModelError):
                self.load(domain_value(kind, implementation_status="implemented"))
        for kind in ("component", "interface"):
            with self.subTest(kind=kind), self.assertRaises(ModelError):
                self.load(domain_value(kind, verification_plan_status="planned"))

    def test_requirement_enumerations_are_exact(self):
        values = {"requirement_kind": ("functional", "quality", "interface", "data", "constraint", "security", "safety", "compliance"),
                  "priority": ("mandatory", "high", "medium", "low"),
                  "criticality": ("normal", "important", "critical", "safety_critical"),
                  "normative_force": ("must", "must_not", "should", "may")}
        for field, choices in values.items():
            for choice in choices:
                value = domain_value("requirement", **{field: choice})
                if choice == "should": value.update(deviation_conditions="During evaluation", deviation_authority="reviewer")
                with self.subTest(field=field, choice=choice): self.assertEqual(self.load(value).data, value)
            for bad in ("invalid", choices[0].upper(), True, None, [choices[0]]):
                with self.subTest(field=field, invalid=str(bad)), self.assertRaises(ModelError):
                    self.load(domain_value("requirement", **{field: bad}))

    def test_no_normative_force_inferred_from_text_or_priority(self):
        value = domain_value("requirement", statement="MUST should may", priority="mandatory")
        value.pop("normative_force")
        with self.assertRaises(ModelError): self.load(value)
        value["normative_force"] = "may"
        self.assertEqual(self.load(value).data, value)

    def test_should_metadata_required_from_draft(self):
        for extra in ({}, {"deviation_conditions": "exception"}, {"deviation_authority": "reviewer"},
                      {"deviation_conditions": "", "deviation_authority": "reviewer"}):
            with self.subTest(extra=str(extra)), self.assertRaises(ModelError):
                self.load(domain_value("requirement", normative_force="should", **extra))

    def test_waiver_requires_declared_binding_metadata(self):
        for kind in ("capability", "requirement", "task"):
            with self.subTest(kind=kind), self.assertRaises(ModelError):
                self.load(domain_value(kind, verification_plan_status="waived"))
            for field in ("reason", "scope_descriptor", "expiry_condition", "human_review_id", "artifact_sha256"):
                data = waiver(); data.pop(field)
                with self.subTest(kind=kind, field=field), self.assertRaises(ModelError):
                    self.load(domain_value(kind, verification_plan_status="waived", verification_waiver=data))

    def test_owner_accepts_explicit_role_or_actor(self):
        for actor in ("engineering", {"actor_type": "human", "actor_id": "alice"}):
            self.assertEqual(self.load(domain_value(owner=actor)).data["owner"], actor)
        for actor in ("", "  ", None, 1, [], {"actor_type": "human"}, {"actor_type": "robot", "actor_id": "alice"}):
            with self.subTest(actor=str(actor)), self.assertRaises(ModelError): self.load(domain_value(owner=actor))

    def test_empty_required_text_is_rejected(self):
        for kind, field in (("goal", "statement"), ("need", "stakeholder"), ("capability", "description"),
                            ("requirement", "statement"), ("scenario", "trigger"), ("decision", "rationale"),
                            ("risk", "description"), ("assumption", "statement"), ("component", "responsibility"),
                            ("interface", "description"), ("release", "objective"), ("milestone", "objective"), ("task", "description")):
            for bad in ("", " \t\n", "nul\x00value", None, 8, []):
                with self.subTest(kind=kind, field=field, bad=str(bad)), self.assertRaises(ModelError):
                    self.load(domain_value(kind, **{field: bad}))

    def test_scenario_and_done_criteria_require_real_sequences(self):
        for kind, field in (("scenario", "actors"), ("scenario", "main_flow"), ("task", "done_criteria")):
            for bad in ([], "step", [""], [False], {}):
                with self.subTest(kind=kind, field=field, bad=str(bad)), self.assertRaises(ModelError):
                    self.load(domain_value(kind, **{field: bad}))

    def test_risk_assessments_are_values_not_boolean_success(self):
        for probability in (0, 1, 0.25, "unlikely"):
            value = domain_value("risk", probability=probability)
            self.assertEqual(self.load(value).data, value)
        for bad in (True, None, {}, [], -0.1, 1.1):
            with self.subTest(bad=str(bad)), self.assertRaises(ModelError):
                self.load(domain_value("risk", probability=bad))

    def test_unenumerated_risk_and_assumption_labels_not_interpreted(self):
        for kind, field in (("risk", "risk_status"), ("assumption", "validation_status")):
            value = domain_value(kind, **{field: "organization-specific-label"})
            self.assertEqual(self.load(value).data, value)
            for bad in ("", None, True, {}):
                with self.subTest(kind=kind, bad=str(bad)), self.assertRaises(ModelError):
                    self.load(domain_value(kind, **{field: bad}))

    def test_component_references_use_component_identity_grammar(self):
        for field in ("source_component", "target_component"):
            for bad in ("SR-REQ-0001", "../component", "", True, {"id": "SR-COMP-0001"}):
                with self.subTest(field=field, bad=str(bad)), self.assertRaises(ModelError):
                    self.load(domain_value("interface", **{field: bad}))
        self.assertEqual(self.load(domain_value("interface", source_component="SR-COMP-0001")).data["source_component"], "SR-COMP-0001")

    def test_milestone_has_exactly_one_release_relation(self):
        for relations in ([], [relation(), relation()], [relation(target="SR-MS-0001")],
                          [{"type": "part_of"}], [relation(kind="depends_on")]):
            with self.subTest(relations=str(relations)), self.assertRaises(ModelError):
                self.load(domain_value("milestone", relations=relations))
        value = domain_value("milestone", relations=[relation(), relation("depends_on", "SR-TASK-0001")])
        self.assertEqual(self.load(value).data, value)

    def test_readiness_policy_is_data_not_evaluated(self):
        value = domain_value("release", readiness_policy={"require_current_evidence": True})
        resource = self.load(value)
        self.assertEqual(resource.data, value)
        self.assertNotIn("ready", resource.data)
        for bad in ("ready", True, None, []):
            with self.subTest(bad=str(bad)), self.assertRaises(ModelError):
                self.load(domain_value("release", readiness_policy=bad))

    def test_record_owns_bytes_and_returns_detached_data(self):
        value = domain_value("requirement", extensions={"example.org": {"nested": [1, 2]}})
        raw = artifact_bytes(value); resource = DomainArtifact(raw)
        exposed = resource.data; exposed["extensions"]["example.org"]["nested"].clear()
        value["statement"] = "Changed outside"
        self.assertEqual(resource.source_bytes, raw)
        self.assertEqual(resource.data["extensions"]["example.org"]["nested"], [1, 2])
        with self.assertRaises(AttributeError): resource.id = "altered"
        for bad in (bytearray(raw), raw.decode(), {}):
            with self.subTest(type=type(bad).__name__), self.assertRaises(ModelError): DomainArtifact(bad)

    def test_schema_resources_are_independent_and_versioned(self):
        identities = set()
        for kind in PREFIXES:
            schema = domain_schema(kind); identities.add(schema["$id"])
            self.assertEqual(json.loads(json.dumps(schema)), schema)
            schema["properties"].clear(); schema["required"].clear()
            self.assertTrue(domain_schema(kind)["properties"])
            self.assertTrue(domain_schema(kind)["required"])
        self.assertEqual(len(identities), 14)

    def test_other_registered_types_remain_explicitly_unsupported(self):
        for kind in ("evidence", "document", "source", "configuration", "proposal"):
            with self.subTest(kind=kind), self.assertRaises(ModelError) as caught: domain_schema(kind)
            self.assertEqual(caught.exception.reason, "domain_type_not_supported")

    def test_version_and_expected_type_cannot_be_overridden(self):
        for version in ("0.1.0", "0.2.1", "99.0.0"):
            with self.subTest(version=version), self.assertRaises(ModelError):
                self.load(domain_value(schema_version=version))
        with self.assertRaises(ModelError): self.load(domain_value(), expected_type="need")

    def test_strict_reader_rejects_duplicate_keys_and_trailing_data(self):
        raw = artifact_bytes(domain_value())
        for bad in (raw + b' {}', b'\xef\xbb\xbf' + raw, b'{"x":1,"x":2}', b'[]'):
            with self.subTest(raw=repr(bad)[:40]), self.assertRaises(ModelError): DomainArtifact(bad)

    def test_opaque_semantics_and_unicode_are_preserved(self):
        value = domain_value("requirement", statement="e\u0301 / é / العربية / 日本語", normative_force="must_not",
                             scope={"boundary": "device"}, actor="operator", response={"behavior": "no network"},
                             timing={"value": 10, "unit": "ms"}, thresholds=[{"minimum": 1}], exceptions=[])
        before = copy.deepcopy(value); validate_domain_fields(value)
        self.assertEqual(value, before)
        self.assertEqual(self.load(value).data, before)

    def test_bound_read_preserves_original_and_creates_no_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); configuration_file(root)
            value = domain_value(); path = artifact_path("goal", value["id"], "SR")
            raw = artifact_bytes(value) + b'\n'; original = put(root, path, raw)
            before = sorted(str(p.relative_to(root)) for p in root.rglob("*"))
            resource = read_domain_artifact(ProjectSource(root), path)
            self.assertEqual(resource.source_bytes, raw)
            self.assertEqual(original.read_bytes(), raw)
            self.assertEqual(before, sorted(str(p.relative_to(root)) for p in root.rglob("*")))

    def test_invalid_bound_read_retains_file_and_structured_error_path(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); configuration_file(root)
            value = domain_value(statement=""); path = artifact_path("goal", value["id"], "SR")
            raw = artifact_bytes(value); original = put(root, path, raw)
            with self.assertRaises(ModelError) as caught: read_domain_artifact(ProjectSource(root), path)
            self.assertEqual(caught.exception.path, path)
            self.assertEqual(original.read_bytes(), raw)
            self.assertFalse((root / ".specroad").exists())

    def test_wrong_path_or_stale_project_is_still_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); configuration_file(root); source = ProjectSource(root)
            value = domain_value(); wrong = "spec/goals/SR-GOAL-0001.json"
            put(root, wrong, artifact_bytes(value))
            with self.assertRaises(ModelError): read_domain_artifact(source, wrong)
            right = artifact_path("goal", value["id"], "SR"); put(root, right, artifact_bytes(value))
            configuration_file(root, project_name="Changed")
            with self.assertRaises(ModelError): read_domain_artifact(source, right)

    def test_domain_contract_loads_from_relocated_module_and_zipapp(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            build_distribution(root / "build", ROOT / "src")
            (root / "build").rename(root / "moved")
            raw = artifact_bytes(domain_value("requirement"))
            program = (
                "import sys; sys.path.insert(0,sys.argv[1]); "
                "from specroad.storage.domain_artifact import DomainArtifact; "
                "r=DomainArtifact(sys.stdin.buffer.read()); "
                "assert r.artifact_type=='requirement'; assert r.validation_scope=='domain_fields_only'; "
                "assert r.data['verification_plan_status']=='not_planned'"
            )
            for distribution in (root / "moved/module", root / "moved/specroad.pyz"):
                result = subprocess.run([sys.executable, "-I", "-S", "-B", "-c", program, str(distribution)],
                                        input=raw, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
                self.assertEqual(result.returncode, 0)


class DomainRightTests(unittest.TestCase):
    def load(self, value, **options):
        return DomainArtifact(artifact_bytes(value), **options)

    def test_stored_maturities_are_read_not_transitioned(self):
        from support.domain import approved_value
        for kind in PREFIXES:
            for maturity in ("draft", "proposed", "in_review", "approved", "rejected", "superseded", "retired"):
                with self.subTest(kind=kind, maturity=maturity):
                    value = approved_value(kind) if maturity == "approved" else domain_value(kind, maturity=maturity)
                    resource = self.load(value)
                    self.assertEqual(resource.data, value)
                    self.assertEqual(resource.validation_scope, "domain_fields_only")
                    self.assertNotIn("verification_result", resource.data)

    def test_approved_metadata_required_by_type(self):
        from support.domain import approved_value
        fields = {"goal": ("success_criterion",), "need": ("rationale", "priority"),
                  "capability": ("outcome", "priority"), "requirement": ("rationale",),
                  "scenario": ("preconditions", "postconditions", "exceptions"),
                  "decision": ("alternatives", "consequences"),
                  "assumption": ("validation_method", "reevaluation_condition"),
                  "release": ("scope_descriptor",), "milestone": ("done_criteria",)}
        for kind, names in fields.items():
            for field in names:
                with self.subTest(kind=kind, field=field):
                    value = approved_value(kind); value.pop(field)
                    with self.assertRaises(ModelError): self.load(value)
                    value["maturity"] = "draft"
                    self.assertEqual(self.load(value).data, value)

    def test_goal_criterion_is_not_synthesized(self):
        for criterion in ("Setup takes at most ten steps.", ["Runs offline", "Completes without writes"]):
            value = domain_value("goal", maturity="approved", success_criterion=criterion)
            self.assertEqual(self.load(value).data["success_criterion"], criterion)
        for bad in ("", [], [""], True, {}):
            with self.subTest(bad=str(bad)), self.assertRaises(ModelError):
                self.load(domain_value("goal", maturity="approved", success_criterion=bad))

    def test_interface_contract_or_reason_required(self):
        value = domain_value("interface", maturity="approved")
        with self.assertRaises(ModelError): self.load(value)
        for extra in ({"contract": "Input/output contract"}, {"contract": {"input": "JSON"}},
                      {"contract_not_applicable": "Only an internal type boundary"}):
            changed = dict(value, **extra)
            self.assertEqual(self.load(changed).data, changed)
        for extra in ({"contract": ""}, {"contract": {}}, {"contract_not_applicable": True},
                      {"contract_not_applicable": ""}):
            with self.subTest(extra=str(extra)), self.assertRaises(ModelError): self.load(dict(value, **extra))

    def test_task_does_not_invent_reverse_implementation_links(self):
        # Relations are stored at their source. The task cannot decide whether
        # another requirement/decision points to it until graph resolution.
        value = domain_value("task", maturity="approved", implementation_status="implemented", relations=[])
        result = self.load(value)
        self.assertEqual(result.data, value)
        self.assertEqual(result.validation_scope, "domain_fields_only")
        self.assertNotIn("verification_result", result.data)

    def test_incoming_risk_mitigation_not_replaced_by_fake_acceptance(self):
        value = domain_value("risk", maturity="approved", relations=[])
        self.assertEqual(self.load(value).data, value)
        self.assertNotIn("acceptance_rationale", self.load(value).data)

    def test_release_date_accepts_real_iso_dates_without_interpreting_schedule(self):
        for date in ("2024-02-29", "2026-09-15", "2000-02-29", "9999-12-31"):
            with self.subTest(date=date):
                self.assertEqual(self.load(domain_value("release", target_date=date)).data["target_date"], date)
        for bad in ("2026-02-29", "1900-02-29", "2026-13-01", "2026-09-31", "20260915", "2026-9-15",
                    "0000-01-01", "2026-09-15T00:00:00Z", "2026-09-15\n", True, None):
            with self.subTest(bad=str(bad)), self.assertRaises(ModelError):
                self.load(domain_value("release", target_date=bad))

    def test_builtin_date_format_does_not_accept_unsupported_formats(self):
        from specroad.model._schema import validate_builtin
        validate_builtin("2024-02-29", {"type": "string", "format": "date"})
        with self.assertRaises(ModelError): validate_builtin("2023-02-29", {"type": "string", "format": "date"})
        with self.assertRaises(ValueError): validate_builtin("anything", {"format": "custom"})

    def test_invalid_status_datatypes_rejected_on_every_applicable_type(self):
        for kind in ("capability", "requirement", "component", "interface", "task"):
            for value in (None, False, 1, [], {}, "Implemented", " in_progress", "not_started\n"):
                with self.subTest(kind=kind, value=str(value)), self.assertRaises(ModelError):
                    self.load(domain_value(kind, implementation_status=value))
        for kind in ("capability", "requirement", "task"):
            for value in (None, False, 1, [], {}, "passed", "failed", "stale", "waived "):
                with self.subTest(kind=kind, value=str(value)), self.assertRaises(ModelError):
                    self.load(domain_value(kind, verification_plan_status=value))

    def test_failed_validation_does_not_mutate_input_or_audit_metadata(self):
        for kind in PREFIXES:
            value = domain_value(kind, maturity="not_a_status"); before = copy.deepcopy(value)
            with self.subTest(kind=kind), self.assertRaises(ModelError): validate_domain_fields(value)
            self.assertEqual(value, before)

    def test_whole_waiver_is_preserved_without_claiming_authorization(self):
        data = waiver(); data["human_review_id"] = "human-review:external-17"
        value = domain_value("requirement", verification_plan_status="waived", verification_waiver=data)
        resource = self.load(value)
        self.assertEqual(resource.data, value)
        self.assertEqual(resource.validation_scope, "domain_fields_only")
        self.assertEqual(resource.data["maturity"], "draft")

    def test_waiver_hashes_and_actor_metadata_cannot_be_fabricated_from_bools(self):
        for field, bad in (("artifact_sha256", "a" * 63), ("artifact_sha256", "A" * 64),
                           ("configuration_sha256", True), ("scope_descriptor", "all"),
                           ("human_review_id", True), ("expiry_condition", ""), ("reason", None)):
            data = waiver(); data[field] = bad
            with self.subTest(field=field, bad=str(bad)), self.assertRaises(ModelError):
                self.load(domain_value("task", verification_plan_status="waived", verification_waiver=data))

    def test_foreign_scope_and_policy_objects_are_not_executed(self):
        with tempfile.TemporaryDirectory() as temporary:
            sentinel = Path(temporary) / "executed"
            value = domain_value("release", readiness_policy={"command": "touch " + str(sentinel), "module": "malicious"})
            self.assertEqual(self.load(value).data, value)
            self.assertFalse(sentinel.exists())

    def test_instance_identity_remains_bound_for_all_types(self):
        for kind in PREFIXES:
            with self.subTest(kind=kind), self.assertRaises(ModelError):
                self.load(domain_value(kind, id="SR-UNKNOWN-0001"))

    def test_local_milestone_cardinality_has_precise_error_location(self):
        for relations, reason, pointer in (([], "milestone_release_cardinality", "/relations"),
                                          ([relation(target="bad")], "milestone_release_reference", "/relations/0/target")):
            with self.subTest(reason=reason), self.assertRaises(ModelError) as caught:
                self.load(domain_value("milestone", relations=relations), path="milestone.json")
            self.assertEqual((caught.exception.reason, caught.exception.pointer, caught.exception.path), (reason, pointer, "milestone.json"))

    def test_schema_mutation_cannot_weaken_other_reads(self):
        schema = domain_schema("requirement")
        schema["allOf"].clear(); schema["properties"]["normative_force"]["enum"].append("optional")
        with self.assertRaises(ModelError): self.load(domain_value("requirement", normative_force="optional"))
        with self.assertRaises(ModelError): self.load(domain_value("requirement", normative_force="should"))

    def test_references_are_only_checked_lexically_not_auto_created(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); configuration_file(root)
            value = domain_value("interface"); name = artifact_path("interface", value["id"], "SR")
            put(root, name, artifact_bytes(value))
            resource = read_domain_artifact(ProjectSource(root), name)
            self.assertEqual(resource.data, value)
            self.assertFalse((root / "spec/components").exists())

    def test_bound_reader_rejects_symlinks_without_followup_mutation(self):
        from specroad.security import SafetyViolation
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); configuration_file(root)
            value = domain_value(); target = put(root, "original.json", artifact_bytes(value))
            name = artifact_path("goal", value["id"], "SR")
            link = root / name; link.parent.mkdir(parents=True); link.symlink_to(target)
            with self.assertRaises(SafetyViolation): read_domain_artifact(ProjectSource(root), name)
            self.assertEqual(target.read_bytes(), artifact_bytes(value))

    def test_declared_language_is_never_inferred_or_rewritten(self):
        value = domain_value("requirement", language="DE-de", statement="An English statement.")
        self.assertEqual(self.load(value).data, value)
        value.pop("language")
        with self.assertRaises(ModelError): self.load(value)

    def test_schema_validation_does_not_rewrite_stored_statuses(self):
        from support.domain import approved_value
        for kind in ("capability", "requirement", "task"):
            value = approved_value(kind, implementation_status="blocked", verification_plan_status="running")
            self.assertEqual(self.load(value).data, value)

    def test_non_json_values_do_not_enter_the_model(self):
        for bad in (float("nan"), float("inf"), set(), object()):
            value = domain_value("risk"); value["probability"] = bad
            with self.subTest(type=type(bad).__name__), self.assertRaises(ModelError): validate_domain_fields(value)

    def test_retired_record_loading_does_not_revive_or_approve_it(self):
        value = domain_value("task", maturity="retired", implementation_status="blocked")
        resource = self.load(value)
        self.assertEqual(resource.data["maturity"], "retired")
        self.assertEqual(resource.data["implementation_status"], "blocked")
        self.assertEqual(resource.data["revision"], 1)
