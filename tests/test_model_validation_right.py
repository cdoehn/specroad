"""Failure boundaries and full dependency coverage for the common pipeline."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError
from pathlib import Path
import copy
import json
import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

from specroad.model.errors import ModelError
from specroad.validation import (ModelDocument, ModelGate, GateContext, GateResult, GateDependencies, ValidationReport, validate_model)
from support.artifacts import artifact_bytes
from support.domain import approved_value
from support.records import record_value
from support.model_validation import artifact, doc, edge, profile, title_gate, no_dependencies
from support.io_guards import block_imports_and_open
from support.portable import build_distribution
from support.processes import run_python


class ModelValidationRightTests(unittest.TestCase):
    def check_model(self, *values, **kwargs):
        return validate_model(tuple(doc(v) for v in values), profile=profile(), **kwargs)

    def test_multiple_parse_failures_are_retained(self):
        result = validate_model((ModelDocument("a",b'no'),ModelDocument("b",b'{"bad":}')),profile=profile())
        self.assertEqual({d["path"] for d in result.diagnostics},{"a","b"})
        self.assertIs(result.data["model_valid"],False)

    def test_invalid_schema_in_unselected_source_still_blocks(self):
        good,bad=artifact(),artifact(number=1);del bad["statement"]
        result=self.check_model(good,bad,selected_ids=(good["id"],))
        self.assertFalse(result.passed)
        self.assertEqual(result.data["structural_scope"],"all_supplied_documents")

    def test_duplicate_relation_ids_across_sources_are_rejected(self):
        a,b,c=[artifact(number=i) for i in range(3)]
        a["relations"]=[edge(c)];b["relations"]=[edge(c)]
        self.assertEqual(self.check_model(a,b,c).diagnostics[0]["reason"],"duplicate_relation_id")

    def test_depends_on_cycles_are_not_hierarchy_cycles(self):
        a,b=artifact("component"),artifact("component",1)
        a["relations"]=[edge(b,"depends_on",1)];b["relations"]=[edge(a,"depends_on",2)]
        result=self.check_model(a,b)
        self.assertTrue(result.passed)

    def test_interface_field_references_expand_scope(self):
        a,b=artifact("component"),artifact("component",1)
        iface=artifact("interface",source_component=a["id"],target_component=b["id"])
        result=self.check_model(a,b,iface,selected_ids=(iface["id"],))
        self.assertTrue(result.passed)
        self.assertEqual(set(result.data["checked_ids"]),{a["id"],b["id"],iface["id"]})

    def test_interface_dangling_field_is_not_schema_success(self):
        result=self.check_model(artifact("interface"))
        self.assertEqual(result.diagnostics[0]["reason"],"validation_field_target_missing")
        self.assertEqual(result.diagnostics[0]["pointer"],"/source_component")

    def test_verification_subjects_are_required_dependencies(self):
        v=record_value("verification",subjects=[artifact()["id"]])
        result=self.check_model(v)
        self.assertFalse(result.passed)
        self.assertEqual(result.diagnostics[0]["pointer"],"/subjects/0")

    def test_evidence_slot_test_reference_is_required(self):
        a=artifact()
        v=record_value("verification",subjects=[a["id"]],evidence_slots=[{"check_id":"one","test_id":record_value("test")["id"],"dimension":"overall"}])
        result=self.check_model(a,v)
        self.assertEqual(result.diagnostics[0]["pointer"],"/evidence_slots/0/test_id")

    def test_evidence_subjects_are_not_silently_omitted(self):
        e=record_value("evidence")
        result=self.check_model(e)
        self.assertFalse(result.passed)
        self.assertEqual(result.diagnostics[0]["pointer"],"/subjects/0/artifact_id")

    def test_valid_evidence_fields_do_not_prove_freshness(self):
        a=artifact("requirement")
        e=record_value("evidence")
        result=self.check_model(a,e)
        statuses={s["stage"]:s["status"] for s in result.data["stages"]}
        self.assertEqual(statuses["evidence_currentness"],"unavailable")
        self.assertIsNone(result.data["model_valid"])

    def test_configuration_parent_missing_is_blocking(self):
        v=record_value("configuration",parent="SR-CFG-"+"1"*26)
        self.assertEqual(self.check_model(v).diagnostics[0]["pointer"],"/parent")

    def test_review_requires_existing_stored_relation(self):
        v=record_value("relation_review")
        result=self.check_model(v)
        self.assertEqual(result.diagnostics[0]["reason"],"validation_review_relation_missing")

    def test_review_connects_both_endpoints_to_scope(self):
        a,b=artifact(),artifact(number=1)
        a["relations"]=[edge(b)]
        review=record_value("relation_review")
        result=self.check_model(a,b,review,selected_ids=(review["id"],))
        self.assertEqual(set(result.data["checked_ids"]),{a["id"],b["id"],review["id"]})
        self.assertFalse(result.passed)

    def test_provenance_source_reference_is_checked(self):
        a=artifact(provenance=[{"source_id":record_value("source")["id"],"captured_at":"2026-01-01T00:00:00Z","excerpt":"text"}])
        result=self.check_model(a)
        self.assertEqual(result.diagnostics[0]["pointer"],"/provenance/0/source_id")

    def test_free_text_and_extensions_are_not_dependency_instructions(self):
        unknown=artifact(number=9)["id"]
        result=self.check_model(artifact(statement=unknown,extensions={"example.a":{"references":[unknown]}}))
        self.assertTrue(result.passed)

    def test_duplicate_id_labels_do_not_deduplicate_artifacts(self):
        a,b=artifact(display_id="same"),artifact(number=1,display_id="same")
        result=self.check_model(a,b)
        self.assertTrue(result.passed);self.assertEqual(len(result.data["checked_ids"]),2)

    def test_future_gate_missing_cannot_be_optional_for_subset(self):
        a=artifact();b=approved_value("goal",id=artifact(number=1)["id"])
        a["relations"]=[edge(b)]
        result=self.check_model(a,b,selected_ids=(a["id"],))
        self.assertFalse(result.complete)
        self.assertEqual(next(s for s in result.data["stages"] if s["stage"]=="lifecycle")["checked_ids"],[b["id"]])

    def test_unrelated_semantic_gate_not_required_for_narrow_subjects(self):
        a=artifact();b=approved_value("goal",id=artifact(number=1)["id"])
        result=self.check_model(a,b,selected_ids=(a["id"],))
        self.assertTrue(result.passed)
        self.assertEqual(result.data["checked_ids"],[a["id"]])

    def test_absent_language_service_not_passed(self):
        result=self.check_model(artifact("requirement"))
        self.assertIsNone(result.data["model_valid"])
        self.assertEqual(next(s for s in result.data["stages"] if s["stage"]=="language_policy")["status"],"unavailable")

    def test_sealed_state_maturity_mismatch_fails_schema(self):
        result=self.check_model(record_value("baseline",maturity="draft"))
        self.assertIs(result.data["model_valid"],False)

    def test_explicit_profile_lint_cannot_be_ignored(self):
        from support.profiles import profile_data
        from specroad.profiles.values import ProfileResource
        from specroad.profiles.composition import compose_profiles
        # Use the actual software profile with named SRX rules, not a invented declaration.
        from specroad.storage.profiles import load_bundled_profile
        p=compose_profiles([load_bundled_profile("core@0.2.0"),load_bundled_profile("software-en@0.2.0")],core_key="core@0.2.0",project_profiles=("software-en@0.2.0",))
        result=validate_model((doc(artifact()),),profile=p)
        has_rules=bool(p.data["merge"]["lint_rules"])
        self.assertTrue(has_rules)
        self.assertEqual(next(s for s in result.data["stages"] if s["stage"]=="profile_lint")["status"],"unavailable")

    def test_dependency_callback_missing_target_prevents_execution(self):
        calls=[]
        gate=ModelGate("extension:check","1",lambda c:c.dependency_result({i:[artifact(number=99)["id"]] for i in c.subjects}),lambda c:calls.append(c))
        result=self.check_model(artifact(),gates=(gate,))
        self.assertFalse(result.passed);self.assertEqual(calls,[])

    def test_dependency_callback_wrong_binding_is_rejected(self):
        gate=title_gate(dependencies=lambda c:GateDependencies("f"*64,{i:[] for i in c.subjects}))
        self.assertFalse(self.check_model(artifact(),gates=(gate,)).passed)

    def test_dependency_callback_exception_does_not_leak_details(self):
        def broken(c):raise RuntimeError("SECRET-CONTENT")
        result=self.check_model(artifact(),gates=(title_gate(dependencies=broken),))
        self.assertEqual(result.diagnostics[0]["reason"],"validation_gate_discovery_failed")
        self.assertNotIn("SECRET-CONTENT",json.dumps(result.data))

    def test_gate_exception_does_not_publish_stale_success(self):
        def broken(c):raise RuntimeError("SECRET-CONTENT")
        gate=ModelGate("extension:broken","1",no_dependencies,broken)
        result=self.check_model(artifact(),gates=(gate,))
        self.assertFalse(result.passed);self.assertNotIn("SECRET-CONTENT",json.dumps(result.data))

    def test_gate_cannot_reuse_discovery_binding_as_check_binding(self):
        saved=[]
        def deps(c):saved.append(c.input_sha256);return no_dependencies(c)
        gate=ModelGate("extension:phase","1",deps,lambda c:GateResult(saved[0],c.subjects))
        self.assertFalse(self.check_model(artifact(),gates=(gate,)).passed)

    def test_old_gate_result_rejected_after_model_change(self):
        cached=[]
        def check(c):
            if not cached:cached.append(c.result())
            return cached[0]
        gate=ModelGate("extension:cache","1",no_dependencies,check)
        self.assertTrue(self.check_model(artifact(),gates=(gate,)).passed)
        self.assertFalse(self.check_model(artifact(statement="changed"),gates=(gate,)).passed)

    def test_source_byte_reformatting_changes_observation_binding(self):
        value=artifact();p=profile()
        one=validate_model((doc(value,"a"),),profile=p)
        two=validate_model((ModelDocument("a",b" " + artifact_bytes(value)),),profile=p)
        self.assertTrue(one.passed and two.passed)
        self.assertNotEqual(one.data["input_sha256"],two.data["input_sha256"])

    def test_external_resource_binding_changes_gate_inputs(self):
        bindings=[]
        def check(c):bindings.append(c.input_sha256);return c.result()
        a=ModelGate("extension:bound","1",no_dependencies,check,"a"*64)
        b=ModelGate("extension:bound","1",no_dependencies,check,"b"*64)
        self.check_model(artifact(),gates=(a,));self.check_model(artifact(),gates=(b,))
        self.assertNotEqual(*bindings)
        with self.assertRaises(ModelError):ModelGate("extension:bad","1",no_dependencies,check,"bad")

    def test_gate_context_mutation_cannot_change_other_gates(self):
        def check(c):
            value=c.artifact(c.subjects[0]);value["title"]="forbidden"
            data=c.profile_data;data.clear()
            return c.result()
        gate=ModelGate("extension:a","1",no_dependencies,check)
        self.assertTrue(self.check_model(artifact(),gates=(gate,title_gate())).passed)

    def test_gate_diagnostic_must_refer_to_its_subjects(self):
        gate=ModelGate("extension:wrong","1",no_dependencies,lambda c:c.result([{"reason":"wrong","artifact_id":artifact(number=99)["id"]}]))
        result=self.check_model(artifact(),gates=(gate,))
        self.assertFalse(result.passed)
        self.assertEqual(result.diagnostics[0]["reason"],"validation_gate_diagnostic_outside_subjects")

    def test_malformed_gate_diagnostic_is_blocking(self):
        for value in ({"reason":"x","severity":"unknown"},{"reason":"x","pointer":4},{"reason":"x","artifact_id":False}):
            gate=ModelGate("extension:bad","1",no_dependencies,lambda c,v=value:c.result([v]))
            with self.subTest(value=value):self.assertFalse(self.check_model(artifact(),gates=(gate,)).passed)

    def test_warning_is_not_escalated_by_pipeline(self):
        gate=ModelGate("extension:warning","1",no_dependencies,lambda c:c.result([{"reason":"notice","severity":"warning"}]))
        result=self.check_model(artifact(),gates=(gate,))
        self.assertTrue(result.passed);self.assertEqual(result.diagnostics[0]["severity"],"warning")

    def test_unrelated_hook_does_not_execute(self):
        def broken(c):raise AssertionError("not applicable")
        gate=ModelGate("baseline_integrity","1",broken,broken)
        self.assertTrue(self.check_model(artifact(),gates=(gate,)).passed)

    def test_deep_dependency_chain_terminates(self):
        values=[artifact(number=i) for i in range(1100)]
        for i in range(len(values)-1):values[i]["relations"]=[edge(values[i+1],number=i)]
        result=self.check_model(*values,selected_ids=(values[0]["id"],))
        self.assertTrue(result.passed);self.assertEqual(len(result.data["checked_ids"]),1100)

    def test_dependency_cycles_terminate_without_dropping_ids(self):
        values=[artifact(number=i) for i in range(3)]
        def deps(c):return c.dependency_result({v["id"]:[values[(i+1)%3]["id"]] for i,v in enumerate(values)})
        result=self.check_model(*values,selected_ids=(values[0]["id"],),gates=(title_gate(dependencies=deps),))
        self.assertTrue(result.passed);self.assertEqual(len(result.data["checked_ids"]),3)

    def test_concurrent_calls_own_their_state(self):
        p=profile();gate=title_gate()
        def run(i):return validate_model((doc(artifact(number=i)),),profile=p,gates=(gate,)).data
        with ThreadPoolExecutor(max_workers=4) as executor:results=list(executor.map(run,range(20)))
        self.assertEqual(len({r["input_sha256"] for r in results}),20)
        self.assertTrue(all(r["model_valid"] is True for r in results))

    def test_validating_does_not_read_files_or_import_adapters(self):
        source=doc(artifact());p=profile()
        # Resolve everything before blocking imports (also compatible with 3.10).
        with block_imports_and_open(), patch.object(os,"open",side_effect=AssertionError("File I/O forbidden")):
            result=validate_model((source,),profile=p)
        self.assertTrue(result.passed)

    def test_report_cannot_accidentally_be_used_as_boolean_success(self):
        result=self.check_model(approved_value("goal"))
        with self.assertRaises(TypeError):bool(result)
        with self.assertRaises(TypeError):ValidationReport()
        with self.assertRaises(TypeError):GateContext()

    def test_portable_module_and_zipapp_expose_same_pipeline(self):
        value=artifact();p=profile()
        from support.profiles import profile_data
        pbytes=artifact_bytes(profile_data(profile_id="core"))
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);module,archive=build_distribution(root/"build")
            moved=root/"moved";shutil.move(str(module),moved)
            moved_archive=root/"app.pyz";shutil.move(str(archive),moved_archive)
            for entry in (moved,moved_archive):
                code=("import sys,json;sys.path.insert(0,"+repr(str(entry))+");"
                    "from specroad.validation import ModelDocument,validate_model;"
                    "from specroad.profiles.values import ProfileResource;"
                    "from specroad.profiles.composition import compose_profiles;"
                    "p=compose_profiles([ProfileResource("+repr(pbytes)+")],core_key='core@0.2.0');"
                    "r=validate_model((ModelDocument('one',"+repr(artifact_bytes(value))+"),),profile=p);"
                    "assert r.passed;assert r.data['approval_granted'] is False")
                child=run_python(["-I","-S","-B","-c",code],root,capture=True)
                self.assertEqual(child.returncode,0,child.stderr.decode())
