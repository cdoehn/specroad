"""Profile data and its actual scoped effects, never display/document snapshots."""
import copy
from dataclasses import FrozenInstanceError
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from specroad.profiles import ProfileResource, ProfileError, resolve_profile, check_profile_fields
from specroad.storage.profiles import bundled_profile_index, load_bundled_profile
from specroad.model.errors import ModelError
from specroad.model.canonical import canonical_json_sha256
from specroad.srx import SrxProgram, EvaluationContext, evaluate
from specroad.graph.relations import SourceRelations
from specroad.graph.relation_obligations import RelationObligations
from support.profiles import encoded, profile_data, selector, requirement
from support.artifacts import common_artifact
from support.relations import artifact, edge, aid
from support.portable import build_distribution, files_under
from support.srx import roots
from support.io_guards import block_imports_and_open

KEYS = ("core@0.2.0", "software-de@0.2.0", "software-en@0.2.0")

class ProfileWorkTests(unittest.TestCase):
    def test_three_exact_bundled_profiles(self):
        entries = bundled_profile_index()
        self.assertEqual([p["profile_id"]+"@"+p["version"] for p in entries], list(KEYS))

    def test_profiles_match_canonical_and_original_hashes(self):
        for key in KEYS:
            with self.subTest(key=key):
                p = load_bundled_profile(key)
                self.assertEqual(p.sha256, canonical_json_sha256(p.data))
                self.assertEqual(p.source_sha256, sha256(p.source_bytes).hexdigest())

    def test_detached_values_and_bindings(self):
        p = load_bundled_profile(KEYS[1]); data = p.data; data["required_fields"].clear()
        binding = p.binding(); binding["sha256"] = "0"*64
        self.assertTrue(p.data["required_fields"])
        self.assertNotEqual(p.binding()["sha256"], "0"*64)

    def test_profile_is_immutable(self):
        with self.assertRaises(FrozenInstanceError):
            load_bundled_profile(KEYS[0]).version = "1.0.0"

    def test_original_formatting_is_kept_separate(self):
        v = profile_data(); a = ProfileResource(encoded(v)); b = ProfileResource(json.dumps(v).encode())
        self.assertEqual(a.sha256, b.sha256); self.assertNotEqual(a.source_sha256, b.source_sha256)
        self.assertEqual(a.source_bytes, encoded(v))

    def test_profile_content_change_changes_hash(self):
        a = ProfileResource(encoded(profile_data()))
        b = ProfileResource(encoded(profile_data(required_fields=[selector(fields=["/statement"])])))
        self.assertNotEqual(a.sha256, b.sha256)

    def test_core_checks_common_fields(self):
        p = load_bundled_profile(KEYS[0]); v = common_artifact()
        self.assertTrue(check_profile_fields(p, v)["field_checks_passed"])
        del v["title"]
        self.assertEqual(check_profile_fields(p, v)["diagnostics"][0]["pointer"], "/title")

    def test_software_rules_do_not_apply_to_goal(self):
        r = check_profile_fields(load_bundled_profile(KEYS[1]), common_artifact())
        self.assertEqual(r["checked_fields"], 0); self.assertTrue(r["field_checks_passed"])

    def test_choice_changes_actual_field_checks(self):
        v = requirement(); del v["statement"]
        self.assertTrue(check_profile_fields(load_bundled_profile(KEYS[0]), v)["field_checks_passed"])
        self.assertFalse(check_profile_fields(load_bundled_profile(KEYS[1]), v)["field_checks_passed"])

    def test_both_software_profiles_accept_mixed_declared_languages(self):
        for key in KEYS[1:]:
            for language in ("de-DE", "en-IN", "ja-JP", "zh-Hans", "ar", "hi-IN", "x-team"):
                with self.subTest(key=key, language=language):
                    v = requirement(language=language); before = copy.deepcopy(v)
                    self.assertTrue(check_profile_fields(load_bundled_profile(key), v)["field_checks_passed"])
                    self.assertEqual(v, before)

    def test_software_profiles_have_compatible_rule_definitions(self):
        a,b = [load_bundled_profile(k) for k in KEYS[1:]]
        for family in ("required_fields", "forbidden_fields", "allowed_values", "relation_rules", "lint_rules", "severity_overrides"):
            self.assertEqual(a.data[family], b.data[family])

    def test_approved_requirement_requires_rationale(self):
        p = load_bundled_profile(KEYS[1]); v = requirement(maturity="approved")
        self.assertEqual(check_profile_fields(p,v)["diagnostics"][0]["pointer"], "/rationale")
        v["rationale"] = "Explicit reason"
        self.assertTrue(check_profile_fields(p,v)["field_checks_passed"])

    def test_draft_does_not_gain_approval_only_fields(self):
        self.assertTrue(check_profile_fields(load_bundled_profile(KEYS[1]), requirement())["field_checks_passed"])

    def test_no_full_model_or_approval_claim(self):
        result = check_profile_fields(load_bundled_profile(KEYS[1]), requirement())
        self.assertEqual(result["validation_scope"], "profile_fields_only")
        for k in ("approval_granted", "profile_composition_checked", "relation_rules_checked", "lint_rules_checked"):
            self.assertIs(result[k], False)

    def test_required_null_is_present(self):
        p = ProfileResource(encoded(profile_data(required_fields=[selector(fields=["/optional"])])))
        self.assertTrue(check_profile_fields(p, requirement(optional=None))["field_checks_passed"])
        self.assertFalse(check_profile_fields(p, requirement())["field_checks_passed"])

    def test_forbidden_present_null_is_rejected(self):
        p = ProfileResource(encoded(profile_data(forbidden_fields=[selector(fields=["/optional"])])))
        self.assertFalse(check_profile_fields(p, requirement(optional=None))["field_checks_passed"])
        self.assertTrue(check_profile_fields(p, requirement())["field_checks_passed"])

    def test_allowed_values_does_not_create_presence_requirement(self):
        p = ProfileResource(encoded(profile_data(allowed_values=[selector(field="/optional", values=[1])])) )
        self.assertTrue(check_profile_fields(p, requirement())["field_checks_passed"])
        self.assertFalse(check_profile_fields(p, requirement(optional=None))["field_checks_passed"])

    def test_allowed_values_are_strictly_typed(self):
        p = ProfileResource(encoded(profile_data(allowed_values=[selector(field="/optional", values=[1])])) )
        for value, expected in ((1,True),(1.0,True),(True,False),("1",False),(None,False)):
            with self.subTest(value=value):
                self.assertIs(check_profile_fields(p, requirement(optional=value))["field_checks_passed"], expected)

    def test_allowed_structures_preserve_array_order(self):
        p = ProfileResource(encoded(profile_data(allowed_values=[selector(field="/optional", values=[{"a":[1,2]}])])) )
        self.assertTrue(check_profile_fields(p, requirement(optional={"a":[1,2]}))["field_checks_passed"])
        self.assertFalse(check_profile_fields(p, requirement(optional={"a":[2,1]}))["field_checks_passed"])

    def test_pointer_escapes_address_literal_field_names(self):
        p = ProfileResource(encoded(profile_data(required_fields=[selector(fields=["/a~1b/~0x"])])))
        self.assertTrue(check_profile_fields(p, requirement(**{"a/b":{"~x":False}}))["field_checks_passed"])

    def test_lint_program_is_real_but_not_run_on_load(self):
        rule = load_bundled_profile(KEYS[1]).rules("lint_rules")[0]
        p = SrxProgram(rule["definition"]["program"], rule_id=rule["rule_id"])
        self.assertTrue(evaluate(p, EvaluationContext(roots(requirement()), rule_id=rule["rule_id"])))
        self.assertFalse(evaluate(p, EvaluationContext(roots({}), rule_id=rule["rule_id"])))
        self.assertEqual(rule["sha256"], canonical_json_sha256(rule["definition"]))

    def test_profile_relation_rules_feed_existing_engine(self):
        p = load_bundled_profile(KEYS[1]); source = SourceRelations(encoded(artifact(maturity="approved")))
        checked = RelationObligations([source], profile_rules=p.minimum_relation_rules())
        found = [c for c in checked.checks if c.rule_id=="software:requirement-verification"]
        self.assertEqual(len(found),1); self.assertFalse(found[0].satisfied)
        target = SourceRelations(encoded(artifact("test",2)))
        source = SourceRelations(encoded(artifact(maturity="approved",relations=[edge("verified_by",aid("test",2))])))
        found = [c for c in RelationObligations([source,target],profile_rules=p.minimum_relation_rules()).checks
                 if c.rule_id=="software:requirement-verification"]
        self.assertTrue(found[0].satisfied)

    def test_severity_overrides_are_passive_declarations(self):
        p = ProfileResource(encoded(profile_data(severity_overrides={"lint:optional":"info"})))
        self.assertEqual(p.data["severity_overrides"], {"lint:optional":"info"})
        self.assertFalse(check_profile_fields(p,requirement())["profile_composition_checked"])

    def test_explicit_resolver_has_no_default_or_fallback(self):
        p = load_bundled_profile(KEYS[0])
        self.assertIs(resolve_profile(KEYS[0], [p]), p)
        with self.assertRaises(ProfileError): resolve_profile("core@0.2.1",[p])
        with self.assertRaises(ProfileError): resolve_profile("core",[p])

    def test_duplicates_are_not_silently_selected(self):
        p = load_bundled_profile(KEYS[0])
        with self.assertRaises(ProfileError): resolve_profile(KEYS[0],[p,p])

    def test_resolver_and_fields_do_not_read_io(self):
        p = load_bundled_profile(KEYS[0]); v = requirement()
        with block_imports_and_open():
            self.assertIs(resolve_profile(KEYS[0],[p]), p)
            self.assertTrue(check_profile_fields(p,v)["field_checks_passed"])

    def test_unknown_fields_and_executable_callbacks_rejected(self):
        for key in ("command", "callback", "imports", "default_language", "default_locale", "$ref"):
            with self.subTest(key=key), self.assertRaises(ProfileError):
                ProfileResource(encoded(profile_data(**{key:"do-not-execute"})))

    def test_unknown_srx_never_runs_on_load(self):
        v = load_bundled_profile(KEYS[1]).data
        v["lint_rules"][0]["program"]["expression"] = {"op":"shell", "command":"sentinel"}
        with self.assertRaises(ProfileError) as caught: ProfileResource(encoded(v))
        self.assertEqual(caught.exception.reason,"profile_invalid_srx")

    def test_unsupported_profile_schema_and_format(self):
        for key in ("schema_version", "profile_format_version"):
            with self.subTest(key=key), self.assertRaises(ProfileError):
                ProfileResource(encoded(profile_data(**{key:"999.0.0"})))

    def test_nonexact_versions_rejected(self):
        for version in ("latest", "^0.2.0", "0.2", "01.2.0", "0.2.0-01", "0.2.0\n", None, 2):
            with self.subTest(version=version), self.assertRaises(ProfileError):
                ProfileResource(encoded(profile_data(version=version)))

    def test_declaration_bytes_must_be_strict_json(self):
        for raw in (b'{"version":"0.2.0","version":"0.2.0"}', b'[]', b'{}x', b'\xff', encoded(profile_data())+b'{}'):
            with self.subTest(raw=raw[:30]), self.assertRaises(ModelError): ProfileResource(raw)

    def test_empty_values_and_duplicate_rule_ids_rejected(self):
        with self.assertRaises(ProfileError):
            ProfileResource(encoded(profile_data(allowed_values=[selector(field="/priority",values=[])])))
        v=load_bundled_profile(KEYS[1]).data;v["relation_rules"]*=2
        with self.assertRaises(ProfileError): ProfileResource(encoded(v))

    def test_portable_module_and_zipapp_ship_exact_resources(self):
        with tempfile.TemporaryDirectory() as t:
            module, archive = build_distribution(Path(t)/"out")
            moved=Path(t)/"moved";archive.rename(moved.with_suffix(".pyz"));module.rename(moved)
            code = "import sys,json;sys.path.insert(0,sys.argv[1]);from specroad.storage.profiles import load_bundled_profile;print(json.dumps([load_bundled_profile(k).binding() for k in "+repr(KEYS)+"]))"
            expected=[load_bundled_profile(k).binding() for k in KEYS]
            for source in (moved,moved.with_suffix(".pyz")):
                proc=subprocess.run([sys.executable,"-I","-B","-c",code,str(source)],cwd=t,capture_output=True)
                self.assertEqual(proc.returncode,0,proc.stderr.decode());self.assertEqual(json.loads(proc.stdout),expected)

    def test_build_identity_includes_profile_bytes(self):
        from support.portable import copy_source_fixture
        with tempfile.TemporaryDirectory() as t:
            t=Path(t); source=copy_source_fixture(t/"source")
            first,_=build_distribution(t/"one",source=source)
            old=(first/"specroad/_build.py").read_bytes()
            path=source/"specroad/profile_data/core.json";path.write_bytes(path.read_bytes()+b" ")
            second,_=build_distribution(t/"two",source=source)
            self.assertNotEqual(old,(second/"specroad/_build.py").read_bytes())
