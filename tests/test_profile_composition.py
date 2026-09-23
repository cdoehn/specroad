"""Executable merge contracts; no console strings or documentation assertions."""
import copy
import json
from dataclasses import FrozenInstanceError
from itertools import permutations
import unittest
from unittest.mock import patch

from specroad.profiles import (EffectiveProfile, ProfileCompositionError,
    compose_profiles, check_composed_fields)
from specroad.model.canonical import canonical_json_bytes, canonical_json_sha256
from specroad.storage.profiles import load_bundled_profile
from specroad.graph.relation_obligations import RelationObligations
from specroad.graph.relations import SourceRelations
from support.profiles import encoded, requirement, selector
from support.profile_composition import profile, composed, lint, relation
from support.relations import artifact, edge, aid


class ProfileCompositionWorkTests(unittest.TestCase):
    def test_core_first_in_exact_order(self):
        a, b = profile("a"), profile("b")
        result = composed(a, b)
        self.assertEqual(result.profile_chain, ("core@0.2.0", "a@0.2.0", "b@0.2.0"))

    def test_core_version_is_exact_not_latest(self):
        core = profile("core", version="1.2.3")
        other = profile("core", version="9.0.0")
        result = compose_profiles([other, core], core_key=core.key)
        self.assertEqual(result.profile_chain, ("core@1.2.3",))

    def test_cli_replaces_project_instead_of_appending(self):
        a = profile("a", required_fields=[selector(fields=["/only_a"])])
        b = profile("b", required_fields=[selector(fields=["/only_b"])])
        result = composed(a, b, project_profiles=[a.key], cli_profiles=[b.key])
        self.assertEqual(result.profile_chain, ("core@0.2.0", b.key))
        self.assertTrue(check_composed_fields(result, requirement(only_b=1))["field_checks_passed"])
        self.assertEqual(result.selection_source, "cli")

    def test_empty_cli_uses_project(self):
        p = profile(); result = composed(p, cli_profiles=[])
        self.assertIn(p.key, result.profile_chain); self.assertEqual(result.selection_source, "project")

    def test_inactive_project_resource_is_not_resolved(self):
        p = profile(); result = composed(p, project_profiles=["absent@1.0.0"], cli_profiles=[p.key])
        self.assertEqual(result.profile_chain[-1], p.key)

    def test_missing_core_does_not_fall_back(self):
        with self.assertRaises(ProfileCompositionError):
            compose_profiles([profile("core")], core_key="core@0.3.0")

    def test_noncore_cannot_be_selected_as_core(self):
        p = profile()
        with self.assertRaises(ProfileCompositionError): compose_profiles([p], core_key=p.key)

    def test_duplicate_active_profile_identity_is_invalid(self):
        p = profile()
        with self.assertRaises(ProfileCompositionError): composed(p, project_profiles=[p.key, p.key])

    def test_two_versions_of_one_active_profile_conflict(self):
        a, b = profile("a"), profile("a", version="1.0.0")
        with self.assertRaises(ProfileCompositionError): composed(a, b)

    def test_explicit_core_in_additional_list_is_duplicate(self):
        with self.assertRaises(ProfileCompositionError): composed(project_profiles=["core@0.2.0"])

    def test_available_inventory_order_does_not_change_result(self):
        core, a, b = profile("core"), profile("a"), profile("b")
        outputs = [compose_profiles(list(p), core_key=core.key, project_profiles=[a.key, b.key]).canonical_bytes
                   for p in permutations([core, a, b])]
        self.assertEqual(len(set(outputs)), 1)

    def test_bundled_software_profiles_remain_compatible(self):
        values = [load_bundled_profile(k + "@0.2.0") for k in ("core", "software-de", "software-en")]
        result = compose_profiles(values, core_key=values[0].key, project_profiles=[p.key for p in values[1:]])
        for language in ("de-DE", "en-IN", "ar", "zh-Hans", "x-team"):
            self.assertTrue(check_composed_fields(result, requirement(language=language))["field_checks_passed"])
        self.assertEqual(len(result.data["merge"]["lint_rules"]), 1)
        self.assertEqual(len(result.minimum_relation_rules()), 1)

    def test_required_field_union_and_no_duplicates(self):
        a = profile("a", required_fields=[selector(fields=["/x", "/y"])])
        b = profile("b", required_fields=[selector(fields=["/y", "/z"])])
        observed = check_composed_fields(composed(a, b), requirement())
        self.assertEqual({x["pointer"] for x in observed["diagnostics"]}, {"/x", "/y", "/z"})
        self.assertEqual(observed["checked_fields"], 3)

    def test_forbidden_field_union(self):
        a = profile("a", forbidden_fields=[selector(fields=["/x"])])
        b = profile("b", forbidden_fields=[selector(fields=["/y"])])
        observed = check_composed_fields(composed(a, b), requirement(x=None, y=False))
        self.assertEqual(len(observed["diagnostics"]), 2)

    def test_presence_is_distinct_from_null(self):
        p = profile(required_fields=[selector(fields=["/x"])])
        result = composed(p)
        self.assertTrue(check_composed_fields(result, requirement(x=None))["field_checks_passed"])
        self.assertFalse(check_composed_fields(result, requirement())["field_checks_passed"])

    def test_allowed_values_intersection_affects_check(self):
        a = profile("a", allowed_values=[selector(field="/x", values=[1, 2, 3])])
        b = profile("b", allowed_values=[selector(field="/x", values=[2, 3, 4])])
        result = composed(a, b)
        for x, accepted in ((1, False), (2, True), (3.0, True), (True, False), (4, False)):
            self.assertIs(check_composed_fields(result, requirement(x=x))["field_checks_passed"], accepted)

    def test_optional_allowed_field_remains_optional(self):
        p = profile(allowed_values=[selector(field="/x", values=[1])])
        self.assertTrue(check_composed_fields(composed(p), requirement())["field_checks_passed"])

    def test_empty_intersection_blocks_composition(self):
        a = profile("a", allowed_values=[selector(field="/x", values=[1])])
        b = profile("b", allowed_values=[selector(field="/x", values=[True])])
        with self.assertRaises(ProfileCompositionError) as caught: composed(a, b)
        self.assertEqual(caught.exception.reason, "profile_empty_intersection")

    def test_required_forbidden_blocks_composition(self):
        a = profile("a", required_fields=[selector(fields=["/x"])])
        b = profile("b", forbidden_fields=[selector(fields=["/x"])])
        with self.assertRaises(ProfileCompositionError): composed(a, b)

    def test_disjoint_maturities_do_not_conflict(self):
        a = profile("a", required_fields=[selector(fields=["/x"], maturities=["approved"])])
        b = profile("b", forbidden_fields=[selector(fields=["/x"], maturities=["draft"])])
        result = composed(a, b)
        self.assertTrue(check_composed_fields(result, requirement())["field_checks_passed"])
        self.assertFalse(check_composed_fields(result, requirement(maturity="approved"))["field_checks_passed"])

    def test_disjoint_artifact_types_do_not_intersect(self):
        a = profile("a", allowed_values=[selector(field="/x", values=[1])])
        b = profile("b", allowed_values=[selector(field="/x", values=[2], artifact_types=["task"])])
        self.assertTrue(check_composed_fields(composed(a, b), requirement(x=1))["field_checks_passed"])

    def test_identical_relation_rules_are_kept_once(self):
        a = profile("a", relation_rules=[relation()]); b = profile("b", relation_rules=[relation()])
        self.assertEqual(len(composed(a, b).minimum_relation_rules()), 1)

    def test_lint_rules_keep_first_occurrence_order(self):
        a = profile("a", lint_rules=[lint("a"), lint("b")]); b = profile("b", lint_rules=[lint("b"), lint("c")])
        self.assertEqual([r["rule_id"] for r in composed(a, b).data["merge"]["lint_rules"]], ["a", "b", "c"])

    def test_rule_version_conflict_is_not_later_wins(self):
        with self.assertRaises(ProfileCompositionError):
            composed(profile("a", lint_rules=[lint()]), profile("b", lint_rules=[lint(version="2.0.0")]))

    def test_rule_hash_conflict_is_not_later_wins(self):
        with self.assertRaises(ProfileCompositionError):
            composed(profile("a", relation_rules=[relation()]), profile("b", relation_rules=[relation(minimum=2)]))

    def test_severity_overrides_are_later_wins(self):
        a = profile("a", lint_rules=[lint()], severity_overrides={"sample:lint": "error"})
        b = profile("b", severity_overrides={"sample:lint": "info"})
        result = composed(a, b)
        self.assertEqual(result.data["merge"]["lint_rules"][0]["severity"], "info")
        self.assertEqual(result.severity_for("sample:lint", "warning"), "info")

    def test_core_security_minimum_cannot_be_lowered(self):
        with self.assertRaises(ProfileCompositionError): composed(profile(severity_overrides={"SRV080": "warning"}))

    def test_core_declared_rule_minimum_is_preserved(self):
        core = profile("core", lint_rules=[lint(severity="error")])
        with self.assertRaises(ProfileCompositionError):
            composed(profile(severity_overrides={"sample:lint": "info"}), core=core)

    def test_severity_lookup_never_lowers_security_default(self):
        self.assertEqual(composed().severity_for("SRV080", "info"), "error")
        self.assertEqual(composed().severity_for("user:note", "info"), "info")

    def test_hash_matches_full_canonical_projection(self):
        result = composed(profile("a", lint_rules=[lint()]))
        self.assertEqual(result.canonical_bytes, canonical_json_bytes(result.data))
        self.assertEqual(result.sha256, canonical_json_sha256(result.data))
        self.assertEqual(result.data["profiles"][0]["profile_id"], "core")
        self.assertIn("required_fields", result.data["merge"])

    def test_profile_chain_order_is_hash_bound(self):
        a, b = profile("a"), profile("b")
        self.assertNotEqual(composed(a, b).sha256, composed(b, a).sha256)

    def test_canonical_resource_hash_ignores_source_indentation(self):
        from specroad.profiles import ProfileResource
        a = profile(); b = ProfileResource(json.dumps(a.data).encode())
        self.assertEqual(composed(a).sha256, composed(b).sha256)
        self.assertNotEqual(a.source_sha256, b.source_sha256)

    def test_source_selection_label_is_not_a_second_hash_semantics(self):
        p = profile(); a = composed(p); b = composed(p, cli_profiles=[p.key])
        self.assertEqual(a.sha256, b.sha256); self.assertNotEqual(a.selection_source, b.selection_source)

    def test_detached_output_cannot_mutate_composition(self):
        result = composed(profile(required_fields=[selector(fields=["/x"])])); old = result.sha256
        data = result.data; data["merge"]["required_fields"].clear(); data["profiles"].clear()
        result.binding()["sha256"] = "0" * 64
        self.assertEqual(result.sha256, old)
        self.assertFalse(check_composed_fields(result, requirement())["field_checks_passed"])
        with self.assertRaises(FrozenInstanceError): result.selection_source = "other"

    def test_inputs_are_not_mutated(self):
        a = profile("a", lint_rules=[lint()]); b = profile("b", severity_overrides={"sample:lint": "info"})
        original = (a.source_bytes, b.source_bytes); keys = [a.key, b.key]; composed(a, b, project_profiles=keys)
        self.assertEqual((a.source_bytes, b.source_bytes), original); self.assertEqual(keys, [a.key, b.key])

    def test_composed_relation_rule_is_usable_by_existing_checker(self):
        p = composed(profile(relation_rules=[relation(minimum=2)]))
        target = SourceRelations(encoded(artifact("test", 2)))
        source = SourceRelations(encoded(artifact(relations=[edge("verified_by", aid("test", 2))])))
        result = RelationObligations([source, target], profile_rules=p.minimum_relation_rules())
        found = [r for r in result.checks if r.rule_id == "sample:relations"]
        self.assertEqual(len(found), 1); self.assertFalse(found[0].satisfied)

    def test_local_checks_are_not_approval_or_complete_model_validation(self):
        observed = check_composed_fields(composed(), requirement())
        self.assertTrue(observed["profile_composition_checked"])
        for key in ("approval_granted", "relation_rules_checked", "lint_rules_checked"):
            self.assertFalse(observed[key])

    def test_conflict_diagnostic_does_not_return_an_effective_hash(self):
        a = profile("a", required_fields=[selector(fields=["/x"])])
        b = profile("b", forbidden_fields=[selector(fields=["/x"])])
        with self.assertRaises(ProfileCompositionError) as caught: composed(a, b)
        diagnostic = caught.exception.diagnostic()
        self.assertEqual(diagnostic["code"], "SRV142"); self.assertEqual(diagnostic["exit_code"], 3)
        self.assertFalse(diagnostic["effective_profile_available"]); self.assertNotIn("sha256", diagnostic)
