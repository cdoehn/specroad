"""Actual adapter boundaries, resource freshness, selection and simultaneous findings."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from specroad.changes import assess_change_target, dry_run_change, TargetError
from specroad.model.canonical import canonical_json_bytes
from specroad.model.errors import ModelError
from specroad.profiles import compose_profiles
from specroad.storage.read_only import validate_project_read_only
from specroad.validation import validate_model, assess_validation, ValidationResources, ModelGate, ModelDocument
from specroad.validation import production
from tests.support.core_lint import requirement_graph
from tests.support.languages import load_registry, registry_bytes
from tests.support.model_validation import artifact, edge
from tests.support.profile_composition import lint
from tests.support.production_validation import inputs, write_project, target_model
from tests.support.read_only import inventory, no_write_attempts
from tests.support.targets import plan, POLICY


def data_for(values=None, **kwargs):
    registry = load_registry(registry_bytes(("language", "en"), ("language", "de"),
        ("language", "und"), ("language", "enm"), ("region", "US"), ("region", "IN")))
    return inputs([artifact("requirement", language="en")] if values is None else values,
                  supplied_registry=registry, **kwargs)


def report(data, **kwargs):
    return validate_model(data.documents, profile=data.profile, resources=data.resources, **kwargs)


def stage(result, name):
    return next(s for s in result.data["stages"] if s["stage"] == name)


def profile_paths(data):
    return {p.key: "profiles/" + p.profile_id + ".json" for p in data.profiles}


class ProductionValidationRightTests(unittest.TestCase):
    def test_nonmatching_profile_types_are_not_claimed_checked(self):
        result = report(data_for([artifact("goal")]))
        self.assertTrue(result.passed)
        self.assertEqual(stage(result, "profile_lint")["status"], "not_applicable")

    def test_rule_maturity_filter_uses_the_actual_stored_state(self):
        rule = lint("local:approved", value=False, severity="error")
        rule["maturities"] = ["approved"]
        self.assertTrue(report(data_for(rules=[rule])).passed)
        approved = report(data_for(requirement_graph(), rules=[rule]))
        self.assertTrue(any(d.get("rule_id") == "local:approved" for d in approved.diagnostics))

    def test_selection_keeps_outside_language_and_profile_dependencies(self):
        a, b = artifact("requirement", language="en"), artifact("requirement", 1, language="de")
        result = report(data_for([a, b]), selected_ids=[a["id"]])
        self.assertEqual(result.data["checked_ids"], sorted([a["id"], b["id"]]))
        self.assertTrue(any(d.get("artifact_id") == b["id"] and d.get("code") == "SRV179"
                            for d in result.diagnostics))

    def test_profile_srx_observes_actual_incoming_relations(self):
        requirement, goal = artifact("requirement", language="en"), artifact("goal")
        requirement["relations"] = [edge(goal, "addresses")]
        rule = lint("local:incoming", severity="error")
        rule["artifact_types"] = ["goal"]
        rule["program"]["expression"] = {"op": "eq", "args": [
            {"op": "field", "context": "relations", "pointer": "/0/target"},
            {"op": "literal", "value": requirement["id"]}]}
        self.assertTrue(report(data_for([requirement, goal], rules=[rule]), selected_ids=[goal["id"]]).passed)

    def test_independent_language_and_profile_findings_are_all_preserved(self):
        values = [artifact("requirement", i, language="de") for i in range(7)]
        data = data_for(values, rules=[lint("local:a", value=False), lint("local:b", value=False)])
        result = report(data)
        self.assertEqual(len(result.diagnostics), 21)
        self.assertEqual(assess_validation(result).summary["diagnostic_count"], 21)
        for value in values:
            self.assertEqual(len([d for d in result.diagnostics if d.get("artifact_id") == value["id"]]), 3)

    def test_source_and_selection_order_do_not_change_findings(self):
        values = [artifact("requirement", i, language="de") for i in range(3)]
        data = data_for(values, rules=[lint(value=False)])
        one = report(data, selected_ids=[v["id"] for v in values])
        two = validate_model(tuple(reversed(data.documents)), profile=data.profile,
            resources=data.resources, selected_ids=[v["id"] for v in reversed(values)])
        self.assertEqual(one.data, two.data)

    def test_warning_and_strict_change_threshold_only(self):
        data = data_for([artifact("requirement", language="de")],
            language_policy={"allowed_ranges": ["en"], "disallowed_language": "warning"})
        result = report(data)
        normal, strict = assess_validation(result), assess_validation(result, strict=True)
        self.assertEqual((normal.exit_code, strict.exit_code), (0, 1))
        self.assertEqual(normal.diagnostics, strict.diagnostics)
        self.assertEqual(normal.diagnostics[0].severity, "warning")

    def test_profile_severity_override_is_used_by_actual_predicate(self):
        data = data_for(rules=[lint("local:rule", value=False, severity="error")],
            local_profile={"severity_overrides": {"local:rule": "warning"}})
        result = report(data)
        self.assertEqual((assess_validation(result).exit_code,
                          assess_validation(result, fail_on="warning").exit_code), (0, 1))
        finding = next(d for d in result.diagnostics if d.get("rule_id") == "local:rule")
        self.assertEqual(finding["severity"], "warning")
        self.assertEqual(len(finding["rule_sha256"]), 64)

    def test_project_mixing_retains_full_active_requirement_membership(self):
        values = [artifact("requirement", language="en"), artifact("requirement", 1, language="de")]
        data = data_for(values, language_policy={"allowed_ranges": ["*"],
            "mixed_languages": {"project": "error"}})
        result = report(data, selected_ids=[values[0]["id"]])
        findings = [d for d in result.diagnostics if d.get("code") == "SRV180"]
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["related_ids"], sorted(v["id"] for v in values))
        self.assertEqual(findings[0]["tags"], ["de", "en"])

    def test_registry_and_unspecified_findings_are_independent(self):
        values = [artifact("requirement", language="zz"), artifact("requirement", 1, language="und")]
        result = report(data_for(values, language_policy={"allowed_ranges": ["*"]}))
        self.assertTrue({"SRV178", "SRV181"} <= {d.get("code") for d in result.diagnostics})

    def test_nonboolean_and_runtime_type_errors_are_input_failures(self):
        bad_type = lint("local:type", severity="info")
        bad_type["program"]["expression"] = {"op": "not", "arg": {"op": "literal", "value": 1}}
        for rule in (lint(value=1, severity="info"), bad_type):
            with self.subTest(rule=rule["rule_id"]):
                result = report(data_for(rules=[rule]))
                self.assertEqual(assess_validation(result).exit_code, 3)
                self.assertTrue(any(d.get("code") == "SRV110" and d["severity"] == "error"
                                    for d in result.diagnostics))

    def test_stricter_profile_srx_structure_limit_is_enforced(self):
        data = data_for(local_profile={"hard_limits": {"srx_nodes": 1}})
        result = report(data)
        self.assertEqual(assess_validation(result).exit_code, 3)
        self.assertTrue(any(d.get("code") == "SRV111" and d["limit"] == 1 for d in result.diagnostics))

    def test_soft_srx_work_target_does_not_become_a_failure(self):
        data = data_for(resource_limits={"srx_operations": 1, "srx_iterations": 1, "srx_graph_steps": 1})
        self.assertTrue(report(data).passed)

    def test_formal_errors_and_language_errors_do_not_hide_missing_reviews(self):
        requirement, goal, verification = requirement_graph()
        requirement.update(statement="TODO define behavior.", language="de")
        verification["subjects"] = [goal["id"]]
        result = report(data_for([requirement, goal, verification]))
        self.assertTrue({"SRV033", "SRV032", "SRV179"} <= {d.get("code") for d in result.diagnostics})
        self.assertEqual(stage(result, "review_currentness")["status"], "unavailable")
        self.assertEqual(assess_validation(result).exit_code, 5)
        self.assertFalse(result.data["approval_granted"])

    def test_foreign_effective_profile_is_rejected_against_actual_bytes(self):
        data = data_for()
        foreign = data_for(rules=[lint(value=False)]).profile
        with self.assertRaisesRegex(ModelError, "validation_profile_context_mismatch"):
            validate_model(data.documents, profile=foreign, resources=data.resources)

    def test_configured_profile_selection_cannot_reuse_previous_composition(self):
        data = data_for()
        config = dict(data.configuration, profiles=["absent@0.2.0"])
        resources = ValidationResources(canonical_json_bytes(config), registry=data.registry,
            profile_resources=data.profiles, core_key=data.profiles[0].key)
        with self.assertRaisesRegex(ModelError, "profile_not_available"):
            validate_model(data.documents, profile=data.profile, resources=resources)

    def test_explicit_cli_profile_selection_is_bound_and_replaces_project_selection(self):
        data = data_for()
        config = dict(data.configuration, profiles=["absent@0.2.0"])
        selected = [data.profiles[1].key]
        resources = ValidationResources(canonical_json_bytes(config), registry=data.registry,
            profile_resources=data.profiles, core_key=data.profiles[0].key, cli_profiles=selected)
        effective = compose_profiles(data.profiles, core_key=data.profiles[0].key,
            project_profiles=config["profiles"], cli_profiles=selected, language_registry=data.registry)
        self.assertTrue(validate_model(data.documents, profile=effective, resources=resources).passed)

    def test_changed_owned_configuration_cannot_reuse_resource_binding(self):
        data = data_for()
        object.__setattr__(data.resources, "configuration_bytes",
                           canonical_json_bytes(dict(data.configuration, project_name="Other")))
        with self.assertRaisesRegex(ModelError, "validation_resource_inputs_changed"):
            report(data)

    def test_missing_profile_bytes_cannot_be_replaced_by_a_hash_label(self):
        data = data_for()
        resources = ValidationResources(data.configuration_bytes, registry=data.registry)
        with self.assertRaisesRegex(ModelError, "validation_profile_resource_bytes_required"):
            validate_model(data.documents, profile=data.profile, resources=resources)

    def test_registry_cached_metadata_is_rebuilt_from_actual_bound_bytes(self):
        data = data_for()
        object.__setattr__(data.resources.registry, "_records", {})
        self.assertTrue(report(data).passed)

    def test_foreign_registry_bytes_cannot_match_the_project_binding(self):
        data = data_for()
        with self.assertRaisesRegex(ModelError, "registry_hash_mismatch"):
            ValidationResources(data.configuration_bytes, registry=load_registry())

    def test_gate_observation_cannot_be_replayed_after_configuration_change(self):
        data, changed = data_for(), data_for(project_name="Changed project")
        saved = []
        def observe(context):
            if not saved:
                saved.append(context.result())
            return saved[0]
        gate = ModelGate("extension:bound-review-observation", "1",
            lambda c: c.dependency_result({i: [] for i in c.subjects}), observe)
        self.assertTrue(report(data, gates=[gate]).passed)
        result = report(changed, gates=[gate])
        self.assertTrue(any(d["reason"] == "validation_gate_result_unbound_or_incomplete"
                            for d in result.diagnostics))
        self.assertFalse(result.passed)


class ProjectProductionValidationRightTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.data = data_for()
        write_project(self.root, self.data)

    def read(self, **kwargs):
        args = dict(profile_resources=self.data.profiles, core_key=self.data.profiles[0].key,
                    profile_paths=profile_paths(self.data))
        args.update(kwargs)
        return validate_project_read_only(self.root, **args)

    def during_check(self, mutation):
        called = []
        original = production.evaluate
        def evaluate(*args, **kwargs):
            result = original(*args, **kwargs)
            if not called:
                called.append(True)
                mutation()
            return result
        with patch.object(production, "evaluate", evaluate):
            result = self.read()
        self.assertTrue(called)
        self.assertFalse(result.data["freshness_verified"])
        self.assertFalse(result.data["resource_files_verified"])
        self.assertIsNone(result.data["validation"])
        return result

    def test_explicit_project_profiles_and_registry_are_rechecked_without_writes(self):
        before = inventory(self.root)
        with no_write_attempts():
            result = self.read()
        self.assertEqual(result.exit_code, 0)
        self.assertTrue(result.data["resource_files_verified"])
        self.assertEqual(len(result.data["resource_bindings"]), 3)
        self.assertEqual(inventory(self.root), before)

    def test_supplied_profile_values_do_not_claim_disk_freshness(self):
        result = self.read(profile_paths=None)
        self.assertEqual(result.exit_code, 0)
        self.assertFalse(result.data["resource_files_verified"])
        self.assertEqual([r["kind"] for r in result.data["resource_bindings"]], ["language_registry"])

    def test_stale_profile_bytes_are_rejected_even_when_canonical_hash_matches(self):
        path = self.root / "profiles/core.json"
        path.write_bytes(b" " + path.read_bytes())
        with no_write_attempts():
            result = self.read()
        self.assertEqual(result.exit_code, 5)
        self.assertEqual(result.data["diagnostics"][0]["reason"], "read_only_profile_observation_changed")
        self.assertFalse(result.data["model_loaded"])

    def test_all_selected_profile_paths_are_required_and_unambiguous(self):
        paths = profile_paths(self.data)
        for bad in ({}, {self.data.profiles[0].key: paths[self.data.profiles[0].key]},
                    dict.fromkeys(paths, "profiles/core.json")):
            with self.subTest(paths=bad):
                result = self.read(profile_paths=bad)
                self.assertEqual(result.exit_code, 2)
                self.assertFalse(result.data["model_loaded"])

    def test_profile_change_during_real_srx_check_invalidates_the_read(self):
        path = self.root / "profiles/software-en.json"
        result = self.during_check(lambda: path.write_bytes(b" " + path.read_bytes()))
        self.assertEqual(result.exit_code, 5)
        self.assertEqual(result.data["diagnostics"][0]["reason"], "read_only_resource_changed")
        self.assertTrue(path.read_bytes().startswith(b" "))

    def test_registry_change_during_real_srx_check_invalidates_the_read(self):
        path = self.root / self.data.configuration["language_registry"]["path"]
        result = self.during_check(lambda: path.write_bytes(path.read_bytes() + b"\n"))
        self.assertEqual(result.exit_code, 3)
        self.assertEqual(result.data["diagnostics"][0]["reason"], "registry_hash_mismatch")

    def test_configuration_change_during_real_check_discards_observations(self):
        path = self.root / "specroad.json"
        result = self.during_check(lambda: path.write_bytes(b" " + path.read_bytes()))
        self.assertEqual(result.exit_code, 5)

    def test_artifact_change_during_real_check_discards_observations(self):
        path = self.root / self.data.documents[0].path
        result = self.during_check(lambda: path.write_bytes(b" " + path.read_bytes()))
        self.assertEqual(result.exit_code, 5)
        self.assertEqual(result.data["diagnostics"][0]["reason"], "read_only_source_changed")

    def test_missing_or_damaged_configured_registry_is_input_error_without_fallback(self):
        path = self.root / self.data.configuration["language_registry"]["path"]
        for raw in (None, b"damaged"):
            with self.subTest(raw=raw):
                if raw is None:
                    path.unlink()
                else:
                    path.write_bytes(raw)
                with no_write_attempts():
                    result = self.read()
                self.assertEqual(result.exit_code, 3)
                self.assertFalse(result.data["checks_complete"])
                self.assertIsNone(result.data["validation"])

    def test_missing_profile_file_is_not_recreated(self):
        path = self.root / "profiles/software-en.json"
        path.unlink()
        with no_write_attempts():
            result = self.read()
        self.assertEqual(result.exit_code, 5)
        self.assertFalse(path.exists())

    def test_linked_profile_resource_is_refused_without_following_or_repair(self):
        path = self.root / "profiles/software-en.json"
        original = path.read_bytes()
        other = self.root / "external-profile.json"
        other.write_bytes(original)
        path.unlink()
        path.symlink_to(other)
        before = inventory(self.root)
        with no_write_attempts():
            result = self.read()
        self.assertEqual(result.exit_code, 7)
        self.assertEqual(inventory(self.root), before)

    def test_linked_registry_resource_is_a_security_refusal(self):
        path = self.root / self.data.configuration["language_registry"]["path"]
        other = self.root / "external-registry.txt"
        other.write_bytes(path.read_bytes())
        path.unlink()
        path.symlink_to(other)
        before = inventory(self.root)
        with no_write_attempts():
            result = self.read()
        self.assertEqual(result.exit_code, 7)
        self.assertEqual(result.data["diagnostics"][0]["reason"], "unsafe_registry_resource")
        self.assertEqual(inventory(self.root), before)


class TargetProductionValidationRightTests(unittest.TestCase):
    def test_warning_strict_parity_across_project_target_and_dry_run(self):
        data = data_for([artifact("requirement", language="de")],
            language_policy={"allowed_ranges": ["en"], "disallowed_language": "warning"})
        model = target_model(data)
        change = plan(model, [])
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_project(root, data)
            for strict in (False, True):
                with self.subTest(strict=strict), no_write_attempts():
                    target = assess_change_target(change, model, policy=POLICY, strict=strict)
                    dry = dry_run_change(change, model, policy=POLICY, strict=strict)
                    project = validate_project_read_only(root, profile_resources=data.profiles,
                        core_key=data.profiles[0].key, profile_paths=profile_paths(data), strict=strict)
                self.assertEqual(target.data, dry.data["assessment"])
                self.assertEqual(target.data["validation"]["diagnostics"], project.data["validation"]["diagnostics"])
                self.assertEqual(project.exit_code, 1 if strict else 0)
                self.assertEqual(target.target_validated, not strict)

    def test_target_keeps_simultaneous_actual_profile_and_language_findings(self):
        data = data_for([artifact("requirement", language="de")], rules=[lint(value=False, severity="error")])
        model = target_model(data)
        change = plan(model, [])
        target = assess_change_target(change, model, policy=POLICY)
        dry = dry_run_change(change, model, policy=POLICY)
        self.assertEqual(target.data, dry.data["assessment"])
        self.assertEqual({d["code"] for d in target.data["validation"]["diagnostics"]}, {"PROFILE_LINT", "SRV179"})
        self.assertFalse(target.target_validated)

    def test_changed_target_profile_source_cannot_reuse_manifest(self):
        model = target_model(data_for())
        change = plan(model, [])
        documents = list(model.resource_files)
        index = next(i for i, d in enumerate(documents) if d.path == "profiles/core.json")
        documents[index] = ModelDocument(documents[index].path, b" " + documents[index].content)
        object.__setattr__(model, "resource_files", tuple(documents))
        with self.assertRaisesRegex(TargetError, "target_sources_changed"):
            assess_change_target(change, model, policy=POLICY)

    def test_target_rebuilds_registry_instead_of_using_derived_metadata(self):
        model = target_model(data_for())
        change = plan(model, [])
        object.__setattr__(model.language_registry, "_records", {})
        result = assess_change_target(change, model, policy=POLICY)
        self.assertTrue(result.target_validated)
        self.assertFalse(result.data["approval_granted"])
        self.assertFalse(result.data["write_authorized"])
