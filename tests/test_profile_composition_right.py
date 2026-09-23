"""Conflict, policy, binding, isolation and portable-composition regressions."""
import copy
from concurrent.futures import ThreadPoolExecutor
from itertools import combinations, permutations
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from specroad.profiles import (ProfileResource, ProfileError, ProfileCompositionError,
    compose_profiles, check_composed_fields)
from specroad.model.errors import ModelError
from specroad.model.canonical import canonical_json_sha256
from specroad.model.language_package_values import LanguagePackage
from specroad.model.language_registry import LanguageRegistry
from specroad.storage.language_packages import load_bundled_package
from specroad.storage.profiles import load_bundled_profile
from specroad.srx.resource_policy import ResourcePolicy
from support.profiles import encoded, requirement, selector
from support.profile_composition import composed, profile, lint, relation
from support.languages import load_registry, registry_bytes
from support.portable import build_distribution
from support.io_guards import block_imports_and_open


class ProfileCompositionRightTests(unittest.TestCase):
    def test_all_nonempty_subsets_intersect_against_independent_oracle(self):
        universe = ("a", "b", "c")
        subsets = [s for n in (1, 2, 3) for s in combinations(universe, n)]
        for left in subsets:
            for right in subsets:
                expected = set(left).intersection(right)
                a = profile("a", allowed_values=[selector(field="/x", values=list(left))])
                b = profile("b", allowed_values=[selector(field="/x", values=list(right))])
                with self.subTest(left=left, right=right):
                    if not expected:
                        with self.assertRaises(ProfileCompositionError): composed(a, b)
                    else:
                        result = composed(a, b)
                        for x in universe:
                            self.assertEqual(check_composed_fields(result, requirement(x=x))["field_checks_passed"], x in expected)

    def test_multi_profile_intersection_not_pairwise_reset(self):
        ps = [profile(str_name, allowed_values=[selector(field="/x", values=values)])
              for str_name, values in (("a", [1, 2]), ("b", [2, 3]), ("c", [1, 3]))]
        with self.assertRaises(ProfileCompositionError): composed(*ps)

    def test_nested_objects_and_array_order_in_allowed_intersection(self):
        a = profile("a", allowed_values=[selector(field="/x", values=[{"a": [1, True]}, {"b": None}])])
        b = profile("b", allowed_values=[selector(field="/x", values=[{"b": None}, {"a": [True, 1]}])])
        rows = composed(a, b).data["merge"]["allowed_values"]
        self.assertTrue(all(r["values"] == [{"b": None}] for r in rows))

    def test_unicode_not_normalized_in_value_sets(self):
        a = profile("a", allowed_values=[selector(field="/x", values=["é"])])
        b = profile("b", allowed_values=[selector(field="/x", values=["e\u0301"])])
        with self.assertRaises(ProfileCompositionError): composed(a, b)

    def test_scope_grouping_does_not_change_materialized_fields(self):
        a = profile("a", required_fields=[selector(fields=["/y", "/x"])])
        b = profile("a", required_fields=[selector(fields=["/x"]), selector(fields=["/y"])])
        self.assertEqual(composed(a).data["merge"], composed(b).data["merge"])
        self.assertNotEqual(composed(a).sha256, composed(b).sha256)  # source resource is still bound

    def test_overlapping_selector_conflict_is_not_hidden_by_grouping(self):
        a = profile("a", required_fields=[selector(fields=["/x"], artifact_types=["requirement", "task"])])
        b = profile("b", forbidden_fields=[selector(fields=["/x"], artifact_types=["task"], maturities=["approved"])])
        with self.assertRaises(ProfileCompositionError): composed(a, b)

    def test_conflicting_entries_in_a_single_resource_are_rejected(self):
        p = profile(required_fields=[selector(fields=["/x"])], forbidden_fields=[selector(fields=["/x"])])
        with self.assertRaises(ProfileCompositionError): composed(p)

    def test_forbidden_parent_cannot_hold_a_required_child(self):
        a = profile("a", required_fields=[selector(fields=["/x/y"])])
        b = profile("b", forbidden_fields=[selector(fields=["/x"])])
        with self.assertRaises(ProfileCompositionError): composed(a, b)

    def test_required_parent_with_forbidden_child_is_consistent(self):
        p = profile(required_fields=[selector(fields=["/x"])], forbidden_fields=[selector(fields=["/x/y"])])
        self.assertTrue(check_composed_fields(composed(p), requirement(x={}))["field_checks_passed"])

    def test_escaped_slash_field_is_not_a_parent_segment(self):
        p = profile(required_fields=[selector(fields=["/x~1y"])], forbidden_fields=[selector(fields=["/x"])])
        self.assertTrue(check_composed_fields(composed(p), requirement(**{"x/y": 1}))["field_checks_passed"])

    def test_cross_family_rule_collision_is_not_hidden(self):
        a = profile("a", relation_rules=[relation("same")]); b = profile("b", lint_rules=[lint("same")])
        with self.assertRaises(ProfileCompositionError): composed(a, b)

    def test_rule_reordering_preserves_first_occurrence(self):
        a = profile("a", lint_rules=[lint("b"), lint("a")]); b = profile("b", lint_rules=[lint("a"), lint("b")])
        self.assertEqual([r["rule_id"] for r in composed(a, b).data["merge"]["lint_rules"]], ["b", "a"])

    def test_conflicting_definition_cannot_be_hidden_by_override(self):
        a = profile("a", lint_rules=[lint(severity="warning")])
        b = profile("b", lint_rules=[lint(severity="error")], severity_overrides={"sample:lint": "info"})
        with self.assertRaises(ProfileCompositionError): composed(a, b)

    def test_rule_binding_is_original_not_modified_effective_definition(self):
        rule = lint(); p = profile(lint_rules=[rule], severity_overrides={rule["rule_id"]: "info"})
        merged = composed(p).data["merge"]
        self.assertEqual(merged["rule_bindings"][0]["sha256"], canonical_json_sha256(rule))
        self.assertEqual(merged["lint_rules"][0]["severity"], "info")

    def test_security_downgrade_cannot_be_fixed_by_a_later_override(self):
        a = profile("a", severity_overrides={"SRV042": "info"})
        b = profile("b", severity_overrides={"SRV042": "error"})
        with self.assertRaises(ProfileCompositionError): composed(a, b)

    def test_protected_error_categories_never_weaken(self):
        for code in ("SRV001", "SRV010", "SRV027", "SRV042", "SRV060", "SRV072", "SRV080", "SRV081", "SRV082", "SRV083", "SRV111", "SRV149", "SRV150", "SRV157", "SRV158", "SRV170", "SRV193", "SRV195"):
            with self.subTest(code=code), self.assertRaises(ProfileCompositionError):
                composed(profile(severity_overrides={code: "warning"}))

    def test_nonsecurity_diagnostic_can_be_lowered(self):
        p = composed(profile(severity_overrides={"SRV050": "info", "SRV033": "warning"}))
        self.assertEqual(p.severity_for("SRV050", "warning"), "info")
        self.assertEqual(p.severity_for("SRV033", "error"), "warning")

    def test_core_rule_minimum_does_not_turn_warning_into_error(self):
        p = composed(core=profile("core", lint_rules=[lint(severity="warning")]))
        self.assertEqual(p.severity_for("sample:lint", "info"), "warning")

    def test_hard_limits_use_smallest_from_every_profile(self):
        ps = [profile("a", hard_limits={"srx_depth": 80, "srx_nodes": 600}),
              profile("b", hard_limits={"srx_depth": 100, "srx_nodes": 300}),
              profile("c", hard_limits={"srx_depth": 25})]
        for ordered in permutations(ps):
            merged = composed(*ordered).data["merge"]["hard_limits"]
            self.assertEqual(merged, {"srx_depth": 25, "srx_nodes": 300})
            policy = ResourcePolicy.from_project({"resource_limits": merged}, rule_id="check")
            self.assertEqual(policy.structure.ast_depth, 25); self.assertEqual(policy.structure.ast_nodes, 300)

    def test_no_undeclared_hard_limits_are_invented(self):
        self.assertEqual(composed().data["merge"]["hard_limits"], {})

    def test_invalid_hard_limit_values_are_not_coerced(self):
        for value in (True, False, 0, -1, 1.5, "10", None, []):
            with self.subTest(value=value), self.assertRaises(ProfileError): profile(hard_limits={"srx_nodes": value})

    def test_soft_limits_do_not_become_hard_cutoffs(self):
        for name in ("srx_operations", "srx_iterations", "srx_graph_steps", "diagnostic_count", "model_bytes", "query_default_limit", "trace_depth", "unknown"):
            with self.subTest(name=name), self.assertRaises(ProfileError): profile(hard_limits={name: 3})

    def test_scalar_normative_policy_requires_equality(self):
        a = profile("a", normative_policy={"review_mode": "strict", "nullable": None})
        b = profile("b", normative_policy={"review_mode": "strict", "extra": True})
        self.assertEqual(composed(a, b).data["merge"]["normative_policy"], {"review_mode": "strict", "nullable": None, "extra": True})

    def test_disagreeing_scalar_policy_is_conflict_not_later_wins(self):
        for left, right in (("strict", "optional"), (True, 1), (None, "none")):
            a = profile("a", normative_policy={"review_mode": left}); b = profile("b", normative_policy={"review_mode": right})
            with self.subTest(left=left, right=right), self.assertRaises(ProfileCompositionError): composed(a, b)

    def test_scalar_numeric_json_equality_is_preserved(self):
        a = profile("a", normative_policy={"threshold": 1}); b = profile("b", normative_policy={"threshold": 1.0})
        self.assertEqual(composed(a, b).data["merge"]["normative_policy"], {"threshold": 1})

    def test_nonscalar_policy_is_not_recursively_or_last_merged(self):
        for value in ({"x": 1}, [1]):
            with self.assertRaises(ProfileError): profile(normative_policy={"value": value})

    def test_language_locale_srx_and_soft_policies_stay_in_project_layer(self):
        for name in ("default_language", "default_locale", "language", "language_policy", "analyzer_policy", "srx_policy", "srx_operations", "resource_limits", "generated_path"):
            with self.subTest(name=name), self.assertRaises(ProfileError): profile(normative_policy={name: "x"})

    def test_language_registry_identity_and_actual_hash_are_bound(self):
        registry = load_registry(); result = composed(language_registry=registry)
        row = result.data["language_registry"]
        self.assertEqual(row["registry_id"], "iana-language-subtags")
        self.assertEqual(row["registry_version"], registry.version); self.assertEqual(row["sha256"], registry.sha256)
        self.assertNotEqual(result.sha256, composed().sha256)

    def test_registry_content_change_changes_effective_hash(self):
        a = load_registry(); b = load_registry(registry_bytes(("language", "de")))
        self.assertEqual(a.version, b.version)
        self.assertNotEqual(composed(language_registry=a).sha256, composed(language_registry=b).sha256)

    def test_registry_version_change_is_bound(self):
        a = load_registry(); b = load_registry(registry_bytes(version="2021-01-01"), version="2021-01-01")
        self.assertNotEqual(composed(language_registry=a).sha256, composed(language_registry=b).sha256)

    def test_language_packages_are_explicit_and_ordered(self):
        a = load_bundled_package("de@1.0.0"); b = load_bundled_package("en@1.0.0")
        p = composed(language_packages=[a, b]); q = composed(language_packages=[b, a])
        self.assertEqual(p.data["language_packages"], [a.binding(), b.binding()]); self.assertNotEqual(p.sha256, q.sha256)
        for language in ("ar", "hi", "zh-Hans", "x-test"):
            self.assertTrue(check_composed_fields(p, requirement(language=language))["field_checks_passed"])

    def test_identical_package_duplicates_coalesce(self):
        p = load_bundled_package("de@1.0.0")
        self.assertEqual(composed(language_packages=[p, p]).sha256, composed(language_packages=[p]).sha256)

    def test_conflicting_package_bytes_are_not_silently_replaced(self):
        p = load_bundled_package("de@1.0.0"); q = LanguagePackage(p.source_bytes+b"\n")
        with self.assertRaises(ProfileCompositionError): composed(language_packages=[p, q])

    def test_registry_and_package_dictionaries_are_not_trusted_objects(self):
        with self.assertRaises(ProfileCompositionError): composed(language_registry=load_registry().__dict__)
        p = load_bundled_package("de@1.0.0")
        with self.assertRaises(ProfileCompositionError): composed(language_packages=[p.binding()])

    def test_tampered_typed_package_metadata_is_detected(self):
        p = load_bundled_package("de@1.0.0"); object.__setattr__(p, "sha256", "0"*64)
        with self.assertRaises(ProfileCompositionError): composed(language_packages=[p])

    def test_tampered_profile_metadata_is_detected(self):
        p = profile(); object.__setattr__(p, "version", "9.0.0")
        with self.assertRaises(ProfileCompositionError): composed(p)

    def test_unselected_profiles_are_not_hash_inputs(self):
        core, p, unused = profile("core"), profile("a"), profile("unused")
        a = compose_profiles([core, p], core_key=core.key, project_profiles=[p.key])
        b = compose_profiles([core, p, unused], core_key=core.key, project_profiles=[p.key])
        self.assertEqual(a.sha256, b.sha256)

    def test_unselected_conflicting_chain_member_does_not_leak_into_cli_selection(self):
        bad = profile("bad", required_fields=[selector(fields=["/x"])], forbidden_fields=[selector(fields=["/x"])])
        good = profile("good")
        result = composed(bad, good, project_profiles=[bad.key], cli_profiles=[good.key])
        self.assertNotIn(bad.key, result.profile_chain)

    def test_foreign_selection_values_do_not_execute_conversion_hooks(self):
        class Strange(list):
            def __iter__(self): raise AssertionError("unexpected iteration")
            def __bool__(self): raise AssertionError("unexpected conversion")
        for key in ("project_profiles", "cli_profiles", "language_packages"):
            with self.subTest(key=key), self.assertRaises(ProfileCompositionError): composed(**{key: Strange()})

    def test_lint_runtime_error_is_not_evaluated_by_composition(self):
        r = lint(); r["program"]["expression"] = {"op": "divide", "args": [{"op": "literal", "value": 1}, {"op": "literal", "value": 0}]}
        p = composed(profile(lint_rules=[r]))
        self.assertTrue(check_composed_fields(p, requirement())["field_checks_passed"])

    def test_composition_performs_no_implicit_io_or_environment_lookup(self):
        core = profile("core"); p = profile(required_fields=[selector(fields=["/x"])])
        with block_imports_and_open():
            result = compose_profiles([core, p], core_key=core.key, project_profiles=[p.key])
            self.assertFalse(check_composed_fields(result, requirement())["field_checks_passed"])

    def test_many_required_fields_are_not_truncated(self):
        p = composed(profile(required_fields=[selector(fields=["/f"+str(i) for i in range(230)])]))
        result = check_composed_fields(p, requirement())
        self.assertEqual(result["checked_fields"], 230); self.assertEqual(len(result["diagnostics"]), 230)

    def test_parallel_composition_does_not_mix_requests(self):
        ps = [profile("p"+str(i), required_fields=[selector(fields=["/x"+str(i)])]) for i in range(24)]
        serial_expected = [composed(p).sha256 for p in ps]
        with ThreadPoolExecutor(max_workers=4) as pool:
            self.assertEqual(list(pool.map(lambda p: composed(p).sha256, ps)), serial_expected)

    def test_failed_composition_preserves_inputs_and_later_success(self):
        a = profile("a", required_fields=[selector(fields=["/x"])]); b = profile("b", forbidden_fields=[selector(fields=["/x"])])
        old = [a.source_bytes, b.source_bytes]; expected = composed(a).sha256
        with self.assertRaises(ProfileCompositionError): composed(a, b)
        self.assertEqual([a.source_bytes, b.source_bytes], old); self.assertEqual(composed(a).sha256, expected)

    def test_conflicts_do_not_leak_normative_values_into_diagnostics(self):
        a = profile("a", normative_policy={"mode": "PRIVATE-ALPHA"}); b = profile("b", normative_policy={"mode": "PRIVATE-BETA"})
        with self.assertRaises(ProfileCompositionError) as caught: composed(a, b)
        result = json.dumps(caught.exception.diagnostic())
        self.assertNotIn("PRIVATE", result); self.assertNotIn("sha256", result)

    def test_merge_hard_and_scalar_policies_change_hash(self):
        for changes in ({"hard_limits": {"srx_nodes": 10}}, {"normative_policy": {"review_mode": "strict"}}):
            self.assertNotEqual(composed(profile()).sha256, composed(profile(**changes)).sha256)

    def test_malformed_program_in_unused_branch_is_rejected_before_composition(self):
        r = lint(); r["program"]["expression"] = {"op": "and", "args": [{"op": "literal", "value": False}, {"op": "shell"}]}
        with self.assertRaises(ProfileError): profile(lint_rules=[r])

    def test_single_field_observer_compatibility_is_preserved(self):
        from specroad.profiles import check_profile_fields
        p = profile(required_fields=[selector(fields=["/x"])], allowed_values=[selector(field="/y", values=[1])])
        for value in (requirement(), requirement(x=None), requirement(x=2, y=1), requirement(x=1, y=True)):
            old = check_profile_fields(p, value); new = check_composed_fields(composed(p), value)
            self.assertEqual(old["field_checks_passed"], new["field_checks_passed"])
            self.assertEqual(old["checked_fields"], new["checked_fields"])
            self.assertEqual([(x["reason"], x["pointer"]) for x in old["diagnostics"]], [(x["reason"], x["pointer"]) for x in new["diagnostics"]])

    def test_portable_module_and_zipapp_have_same_composition(self):
        keys = ("core@0.2.0", "software-de@0.2.0", "software-en@0.2.0")
        resources = [load_bundled_profile(k) for k in keys]
        expected = compose_profiles(resources, core_key=keys[0], project_profiles=keys[1:]).data
        with tempfile.TemporaryDirectory() as t:
            module, archive = build_distribution(Path(t)/"out")
            moved = Path(t)/"moved"; module.rename(moved); zipped = Path(t)/"moved.pyz"; archive.rename(zipped)
            code = "import sys,json;sys.path.insert(0,sys.argv[1]);from specroad.storage.profiles import load_bundled_profile;from specroad.profiles import compose_profiles;k="+repr(keys)+";p=compose_profiles([load_bundled_profile(x) for x in k],core_key=k[0],project_profiles=k[1:]);print(json.dumps(p.data))"
            for source in (moved, zipped):
                proc = subprocess.run([sys.executable, "-I", "-B", "-c", code, str(source)], cwd=t, capture_output=True)
                self.assertEqual(proc.returncode, 0, proc.stderr.decode()); self.assertEqual(json.loads(proc.stdout), expected)
