"""Bound diagnostics, explicit minima and unavailable/fresh input behavior."""
from hashlib import sha256
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from specroad.graph.relations import SourceRelations
from specroad.lint import lint_core
from specroad.model.errors import ModelError
from specroad.model.paths import artifact_path
from specroad.profiles.composition import compose_profiles
from specroad.storage import read_only as reader
from specroad.storage.profiles import load_bundled_profile
from specroad.storage.project import ProjectSource
from tests.support.artifacts import artifact_bytes
from tests.support.core_lint import requirement_graph, sources
from tests.support.domain import domain_value
from tests.support.model import put
from tests.support.model_validation import artifact, edge
from tests.support.profile_composition import profile as resource, relation
from tests.support.read_only import inventory, literal_policy, make_project, no_write_attempts
from tests.support.records import record_value


def configured(*rules, **changes):
    values = (load_bundled_profile("core@0.2.0"),
              resource("lint-test", relation_rules=list(rules), **changes))
    return values, compose_profiles(values, core_key="core@0.2.0",
                                   project_profiles=("lint-test@0.2.0",))


def dependency_rule(**changes):
    return relation(rule_id="lint-test:dependency", relation_types=["depends_on"],
                    endpoint_types=["component"], **changes)


class CoreLintRightTests(unittest.TestCase):
    def test_all_independent_missing_obligations_are_retained(self):
        values = [artifact("requirement", number=n, maturity="approved") for n in range(51)]
        report = lint_core(sources(values))
        self.assertEqual(len(report["diagnostics"]), 153)
        for value in values:
            findings = [d for d in report["diagnostics"] if d["artifact_id"] == value["id"]]
            self.assertEqual({(d["code"], d["pointer"]) for d in findings},
                             {("SRV002", "/rationale"), ("SRV031", "/relations"),
                              ("SRV032", "/relations")})
            self.assertEqual({d["path"] for d in findings},
                             {artifact_path("requirement", value["id"], "SR")})

    def test_source_and_selection_order_do_not_change_the_report(self):
        values = [artifact("requirement", number=n, maturity="approved") for n in range(3)]
        selected = [v["id"] for v in values]
        self.assertEqual(lint_core(sources(values), selected_ids=selected),
                         lint_core(sources(values[::-1]), selected_ids=selected[::-1]))

    def test_selection_keeps_targets_but_omits_unselected_field_findings(self):
        values = requirement_graph()
        bad = artifact("requirement", number=2, maturity="approved")
        report = lint_core(sources((*values, bad)), selected_ids=[values[0]["id"]])
        self.assertEqual(report["diagnostics"], [])
        self.assertEqual(report["checked_ids"], [values[0]["id"]])
        self.assertEqual(len(report["source_bindings"]), 4)

    def test_incoming_minimum_observes_the_opposite_endpoint(self):
        requirement = artifact("requirement")
        task = domain_value("task")
        requirement["relations"] = [edge(task, "implemented_by", 1)]
        _, profile = configured(relation(artifact_types=["task"], direction="incoming",
            relation_types=["implemented_by"], endpoint_types=["requirement"], minimum=2))
        report = lint_core(sources((requirement, task)), selected_ids=[task["id"]], profile=profile)
        finding = report["diagnostics"][0]
        self.assertEqual((finding["actual"], finding["minimum"], finding["direction"]), (1, 2, "incoming"))
        self.assertEqual(finding["endpoint_ids"], [requirement["id"]])
        self.assertEqual(finding["relation_ids"], [requirement["relations"][0]["relation_id"]])

    def test_both_direction_counts_one_stored_symmetric_edge_once(self):
        left, right = artifact("requirement"), artifact("requirement", number=1)
        left["relations"] = [edge(right, "duplicates", 1)]
        _, profile = configured(relation(relation_types=["duplicates"], endpoint_types=["requirement"],
                                          direction="both", minimum=2))
        report = lint_core(sources((left, right)), profile=profile)
        self.assertEqual([d["actual"] for d in report["diagnostics"]], [1, 1])
        self.assertEqual({d["artifact_id"] for d in report["diagnostics"]}, {left["id"], right["id"]})

    def test_outgoing_minimum_counts_distinct_relations_to_one_endpoint(self):
        requirement, component = artifact("requirement"), domain_value("component")
        requirement["relations"] = [edge(component, "depends_on", n) for n in (1, 2)]
        _, profile = configured(dependency_rule(minimum=2))
        self.assertEqual(lint_core(sources((requirement, component)), profile=profile)["diagnostics"], [])
        requirement["relations"].pop()
        finding = lint_core(sources((requirement, component)), profile=profile)["diagnostics"][0]
        self.assertEqual((finding["actual"], finding["minimum"]), (1, 2))
        self.assertEqual(finding["endpoint_ids"], [component["id"]])

    def test_maturity_filters_do_not_promote_nonapproved_requirements(self):
        for maturity in ("draft", "proposed", "in_review", "approved", "rejected", "superseded", "retired"):
            with self.subTest(maturity=maturity):
                value = artifact("requirement", maturity=maturity)
                _, profile = configured(dependency_rule(maturities=["proposed"]))
                report = lint_core(sources((value,)), profile=profile)
                expected = {"SRV002", "SRV031", "SRV032"} if maturity == "approved" else {"SRV023"} if maturity == "proposed" else set()
                self.assertEqual({d["code"] for d in report["diagnostics"]}, expected)

    def test_present_optional_rationale_still_obeys_its_field_contract(self):
        for kind in ("requirement", "need"):
            with self.subTest(kind=kind):
                value = domain_value(kind)
                self.assertEqual(lint_core(sources((value,)))["diagnostics"], [])
                value["rationale"] = []
                finding = lint_core(sources((value,)))["diagnostics"][0]
                self.assertEqual((finding["reason"], finding["pointer"]), ("invalid_rationale", "/rationale"))

    def test_unconditional_rationale_contracts_apply_before_approval(self):
        for value in (domain_value("decision"), record_value("proposal")):
            with self.subTest(kind=value["artifact_type"]):
                self.assertEqual(lint_core(sources((value,)))["diagnostics"], [])
                del value["rationale"]
                finding = lint_core(sources((value,)))["diagnostics"][0]
                self.assertEqual((finding["code"], finding["reason"], finding["pointer"]),
                                 ("SRV002", "missing_rationale", "/rationale"))

    def test_warning_fail_policy_changes_pass_status_not_severity(self):
        values = requirement_graph()
        _, profile = configured(dependency_rule(severity="warning"))
        for arguments, passed in (({}, True), ({"strict": True}, False), ({"fail_on": "warning"}, False)):
            with self.subTest(arguments=arguments):
                report = lint_core(sources(values), profile=profile, **arguments)
                self.assertIs(report["core_checks_passed"], passed)
                self.assertEqual([d["severity"] for d in report["diagnostics"]], ["warning"])

    def test_profile_overrides_cannot_lower_intrinsic_core_errors(self):
        value = artifact("requirement", maturity="approved")
        with self.assertRaisesRegex(ModelError, "profile_core_severity_lowered"):
            configured(dependency_rule(), severity_overrides={"core:requirement-origin": "info"})
        _, profile = configured(dependency_rule(), severity_overrides={"lint-test:dependency": "info"})
        report = lint_core(sources((value,)), profile=profile)
        by_rule = {d["rule_id"]: d for d in report["diagnostics"]}
        self.assertEqual(by_rule["lint-test:dependency"]["severity"], "info")
        self.assertEqual(by_rule["core:requirement-origin"]["severity"], "error")
        self.assertFalse(report["core_checks_passed"])

    def test_invalid_inputs_have_controlled_errors(self):
        good = sources(requirement_graph())
        for bad in (None, {}, "bad", [object()]):
            with self.subTest(source=type(bad).__name__), self.assertRaises(ModelError):
                lint_core(bad)
        for arguments in ({"selected_ids": []}, {"selected_ids": False}, {"selected_ids": [1]},
                          {"selected_ids": [good[0].identity.id] * 2}, {"selected_ids": ["missing"]},
                          {"profile": {}}, {"strict": 1}, {"fail_on": "info"}):
            with self.subTest(arguments=arguments), self.assertRaises(ModelError):
                lint_core(good, **arguments)

    def test_diagnostic_source_labels_are_unambiguous(self):
        values = requirement_graph()
        for path in (1, [], ""):
            with self.subTest(path=path), self.assertRaises(ModelError):
                lint_core((SourceRelations(artifact_bytes(values[0]), path=path),))
        with self.assertRaisesRegex(ModelError, "core_lint_duplicate_source_path"):
            lint_core(tuple(SourceRelations(artifact_bytes(v), path="same.json") for v in values))
        with self.assertRaisesRegex(ModelError, "duplicate_artifact_id"):
            lint_core((sources(values)[0], SourceRelations(artifact_bytes(values[0]), path="other.json")))

    def test_invalid_references_never_count_as_satisfied_minima(self):
        values = requirement_graph()
        with self.assertRaisesRegex(ModelError, "missing_relation_target"):
            lint_core(sources(values[:2]))
        values[0]["relations"][1] = edge(values[1], "verified_by", 2)
        with self.assertRaisesRegex(ModelError, "relation_type_pair_forbidden"):
            lint_core(sources(values))

    def test_source_bytes_and_relation_policy_have_independent_bindings(self):
        records = sources(requirement_graph())
        _, one = configured(dependency_rule(minimum=1))
        _, two = configured(dependency_rule(minimum=2))
        first = lint_core(records, profile=one)
        other_policy = lint_core(records, profile=two)
        self.assertEqual(first["minimum_relations_input_sha256"], other_policy["minimum_relations_input_sha256"])
        self.assertNotEqual(first["minimum_relations_policy_sha256"], other_policy["minimum_relations_policy_sha256"])
        changed = (SourceRelations(records[0].source_bytes + b"\n", path=records[0].path), *records[1:])
        other_bytes = lint_core(changed, profile=one)
        self.assertNotEqual(first["source_bindings"], other_bytes["source_bindings"])
        self.assertEqual(first["minimum_relations_policy_sha256"], other_bytes["minimum_relations_policy_sha256"])


class ProjectCoreLintRightTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "project"
        self.root.mkdir()
        self.values = requirement_graph()
        self.requirement = self.values[0]

    def read(self, **arguments):
        options = {"policy": literal_policy(), "selected_ids": [self.requirement["id"]]}
        options.update(arguments)
        return reader.lint_project_read_only(self.root, **options)

    def changing_core(self, action):
        original = reader.lint_core
        def changed(*args, **kwargs):
            value = original(*args, **kwargs)
            action()
            return value
        return patch.object(reader, "lint_core", changed)

    def assert_invalidated(self, result, code=5):
        self.assertEqual(result.exit_code, code)
        self.assertFalse(result.passed)
        self.assertFalse(result.data["freshness_verified"])
        self.assertFalse(result.data["checks_complete"])
        self.assertIsNone(result.data["lint"])
        self.assertIsNone(result.data["source_observation_sha256"])

    def test_independent_core_and_literal_occurrences_are_not_collapsed(self):
        values = [artifact("requirement", number=n, maturity="approved", language="en",
                           statement="TODO and TODO") for n in (1, 2)]
        make_project(self.root, *values)
        before = inventory(self.root)
        with no_write_attempts():
            result = self.read(selected_ids=[v["id"] for v in values])
        self.assertEqual(result.exit_code, 1)
        self.assertEqual(len(result.data["lint"]["diagnostics"]), 10)
        for value in values:
            findings = [d for d in result.data["lint"]["diagnostics"] if d["artifact_id"] == value["id"]]
            self.assertEqual(len(findings), 5)
            self.assertEqual([d["start"] for d in findings if d["code"] == "SRV033"], [0, 9])
        self.assertEqual(inventory(self.root), before)

    def test_partial_selection_uses_full_references_without_claiming_full_model(self):
        bad = artifact("requirement", number=2, maturity="approved")
        make_project(self.root, *self.values, bad)
        with no_write_attempts():
            result = self.read()
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(len(result.data["source_bindings"]), 4)
        self.assertEqual(result.data["lint"]["checked_ids"], [self.requirement["id"]])
        self.assertFalse(result.data["project_complete"])

    def test_incoming_profile_checks_work_for_selected_task(self):
        task = domain_value("task", maturity="approved", language="en")
        self.requirement["relations"].append(edge(task, "implemented_by", 3))
        resources, _ = configured(relation(artifact_types=["task"], direction="incoming",
            relation_types=["implemented_by"], endpoint_types=["requirement"], minimum=2))
        make_project(self.root, *self.values, task, profiles=["lint-test@0.2.0"])
        with no_write_attempts():
            result = self.read(selected_ids=[task["id"]], policy=literal_policy(fields=["/description"]),
                               profile_resources=resources, core_key="core@0.2.0", strict=True)
        self.assertEqual(result.exit_code, 1)
        finding = result.data["lint"]["diagnostics"][0]
        self.assertEqual((finding["code"], finding["artifact_id"], finding["actual"]),
                         ("SRV023", task["id"], 1))

    def test_missing_declared_language_retains_core_findings_and_incompleteness(self):
        need = domain_value("need", maturity="approved")
        make_project(self.root, need)
        before = inventory(self.root)
        with no_write_attempts():
            result = self.read(selected_ids=[need["id"]])
        self.assertEqual(result.exit_code, 5)
        self.assertIs(result.passed, False)
        self.assertFalse(result.data["checks_complete"])
        self.assertEqual(result.data["lint"]["diagnostics"][0]["reason"], "missing_rationale")
        self.assertEqual(result.data["lint"]["unavailable"], [{"artifact_id": need["id"],
            "path": artifact_path("need", need["id"], "SR"), "pointer": "/language",
            "reason": "literal_declared_language_required", "scope": "literal_checks"}])
        self.assertEqual(inventory(self.root), before)

    def test_missing_selected_glossary_resource_does_not_hide_core_errors(self):
        del self.requirement["rationale"]
        make_project(self.root, *self.values)
        with no_write_attempts():
            result = self.read(policy=literal_policy(term_ids=["SR-TERM-" + "0" * 26]))
        self.assertEqual(result.exit_code, 5)
        self.assertFalse(result.passed)
        self.assertEqual([d["code"] for d in result.data["lint"]["diagnostics"]], ["SRV002"])
        self.assertEqual(result.data["lint"]["unavailable"][0]["reason"], "literal_selected_term_missing")

    def test_no_applicable_literals_does_not_erase_known_profile_failure(self):
        self.requirement["maturity"] = "draft"
        resources, _ = configured(dependency_rule(severity="error"))
        make_project(self.root, *self.values, profiles=["lint-test@0.2.0"])
        result = self.read(profile_resources=resources, core_key="core@0.2.0")
        self.assertEqual(result.exit_code, 5)
        self.assertFalse(result.passed)
        self.assertFalse(result.data["lint"]["findings_passed"])
        self.assertEqual(result.data["lint"]["unavailable"][0]["reason"], "no_applicable_literal_checks")
        self.assertEqual([d["code"] for d in result.data["lint"]["diagnostics"]], ["SRV023"])

    def test_warning_threshold_is_consistent_in_core_and_reader(self):
        resources, _ = configured(dependency_rule(severity="warning"))
        make_project(self.root, *self.values, profiles=["lint-test@0.2.0"])
        for arguments, code in (({}, 0), ({"strict": True}, 1), ({"fail_on": "warning"}, 1)):
            with self.subTest(arguments=arguments), no_write_attempts():
                result = self.read(profile_resources=resources, core_key="core@0.2.0", **arguments)
                self.assertEqual(result.exit_code, code)
                self.assertIs(result.data["lint"]["core"]["core_checks_passed"], code == 0)
                self.assertIs(result.data["lint"]["findings_passed"], code == 0)
                self.assertEqual([d["severity"] for d in result.data["lint"]["diagnostics"]], ["warning"])

    def test_invalid_falsy_profile_selection_does_not_start_reading(self):
        for invalid in (False, None, "", {}, [1]):
            with self.subTest(value=invalid), patch.object(reader, "_source", side_effect=AssertionError("read")):
                result = self.read(cli_profiles=invalid)
                self.assertEqual(result.exit_code, 2)
                self.assertFalse(result.data["model_loaded"])

    def test_explicit_profile_resources_and_cli_selection_have_no_fallback(self):
        make_project(self.root, *self.values, profiles=["missing@0.2.0"])
        for resources in ([], (load_bundled_profile("core@0.2.0"),)):
            with self.subTest(resources=len(resources)), no_write_attempts():
                result = self.read(profile_resources=resources, core_key="core@0.2.0")
                self.assertEqual(result.exit_code, 2)
                self.assertFalse(result.data["model_loaded"])
        resources = (load_bundled_profile("core@0.2.0"), load_bundled_profile("software-en@0.2.0"))
        result = self.read(profile_resources=resources, core_key="core@0.2.0", cli_profiles=["software-en@0.2.0"])
        self.assertEqual(result.exit_code, 0)

    def test_invalid_unselected_bytes_are_not_hidden_by_selection(self):
        make_project(self.root, *self.values)
        bad = artifact("requirement", number=2)
        put(self.root, artifact_path("requirement", bad["id"], "SR"), b"not json")
        with no_write_attempts():
            self.assert_invalidated(self.read(), 3)

    def test_missing_or_wrong_relation_targets_leave_no_false_completed_report(self):
        for missing in (True, False):
            with self.subTest(missing=missing):
                if not missing:
                    self.requirement["relations"][1] = edge(self.values[1], "verified_by", 2)
                make_project(self.root, *self.values[:2])
                before = inventory(self.root)
                with no_write_attempts():
                    self.assert_invalidated(self.read(), 3)
                self.assertEqual(inventory(self.root), before)

    def test_same_size_source_change_with_restored_mtime_invalidates_read(self):
        make_project(self.root, *self.values)
        path = self.root / artifact_path("requirement", self.requirement["id"], "SR")
        original, info = path.read_bytes(), path.stat()
        changed = original.replace(b'"Sample"', b'"Change"')
        self.assertEqual(len(changed), len(original))
        self.assertNotEqual(changed, original)
        def action():
            path.write_bytes(changed)
            os.utime(path, ns=(info.st_atime_ns, info.st_mtime_ns))
        with self.changing_core(action):
            self.assert_invalidated(self.read())
        self.assertEqual(path.read_bytes(), changed)

    def test_created_or_deleted_sources_during_core_check_invalidate_read(self):
        for create in (True, False):
            with self.subTest(create=create):
                make_project(self.root, *self.values)
                extra = artifact("requirement", number=9)
                extra_path = artifact_path("requirement", extra["id"], "SR")
                target = self.root / extra_path
                if not create:
                    target.unlink()
                def action():
                    if create:
                        put(self.root, extra_path, artifact_bytes(extra))
                    else:
                        (self.root / artifact_path("goal", self.values[1]["id"], "SR")).unlink()
                with self.changing_core(action):
                    self.assert_invalidated(self.read())

    def test_configuration_change_after_core_check_invalidates_findings(self):
        make_project(self.root, *self.values)
        path = self.root / "specroad.json"
        with self.changing_core(lambda: path.write_bytes(path.read_bytes() + b"\n")):
            self.assert_invalidated(self.read())

    def test_operational_change_after_core_check_invalidates_findings(self):
        make_project(self.root, *self.values)
        with self.changing_core(lambda: put(self.root, ".specroad/recovery/pending", b"retain")):
            self.assert_invalidated(self.read())
        self.assertEqual((self.root / ".specroad/recovery/pending").read_bytes(), b"retain")

    def test_recovery_during_profile_composition_blocks_before_model_load(self):
        resources, _ = configured(dependency_rule())
        make_project(self.root, *self.values, profiles=["lint-test@0.2.0"])
        original = reader.compose_profiles
        def changed(*args, **kwargs):
            result = original(*args, **kwargs)
            put(self.root, ".specroad/recovery/pending", b"retain")
            return result
        with patch.object(reader, "compose_profiles", changed), patch.object(reader, "_capture_documents", side_effect=AssertionError("model read")):
            result = self.read(profile_resources=resources, core_key="core@0.2.0")
        self.assertEqual(result.exit_code, 5)
        self.assertFalse(result.data["model_loaded"])
        self.assertIsNone(result.data["lint"])

    def test_unavailable_or_unsafe_source_is_never_repaired(self):
        make_project(self.root, *self.values)
        with patch.object(ProjectSource, "read_normative", side_effect=PermissionError(13, "denied")), no_write_attempts():
            self.assert_invalidated(self.read())
        path = self.root / artifact_path("requirement", self.requirement["id"], "SR")
        outside = self.root.parent / "outside.json"
        outside.write_bytes(path.read_bytes())
        path.unlink()
        path.symlink_to(outside)
        before = inventory(self.root)
        with no_write_attempts():
            self.assert_invalidated(self.read(), 7)
        self.assertEqual(inventory(self.root), before)
        self.assertEqual(sha256(outside.read_bytes()).hexdigest(), sha256(artifact_bytes(self.requirement)).hexdigest())
