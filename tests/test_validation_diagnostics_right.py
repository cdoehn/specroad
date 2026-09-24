"""Full emitted finding preservation and isolation of policy from checks."""
import json
import unittest
from specroad.validation import (validate_model,assess_validation,validation_command_result,ModelDocument,ModelGate,ValidationAssessment)
from specroad.diagnostics import assess_diagnostics,ResultContractError
from specroad.cli.results import serialize_result
from support.model_validation import artifact,doc,profile,no_dependencies,edge
from test_validation_diagnostics import check


class ValidationDiagnosticRightTests(unittest.TestCase):
    def test_all_unknown_selected_ids_are_reported_without_counting_them(self):
        known=artifact();missing=["unknown:B","unknown:A"]
        a=assess_validation(check(known,selected_ids=(known["id"],*missing)))
        self.assertEqual({d.artifact_id for d in a.diagnostics},set(missing))
        self.assertEqual(a.summary["checked_artifacts"],1);self.assertEqual(a.exit_code,3)

    def test_unknown_selected_ids_are_not_fabricated_source_locations(self):
        a=assess_validation(check(artifact(),selected_ids=("MISSING",)))
        self.assertIsNone(a.diagnostics[0].path);self.assertIsNone(a.diagnostics[0].location["pointer"])

    def test_independent_gate_errors_are_all_retained(self):
        gates=tuple(ModelGate("extension:"+str(i),"1",no_dependencies,
                    lambda c:c.result([{"reason":"failure","code":c.gate_id,"severity":"error"}])) for i in range(12))
        a=assess_validation(check(artifact(),gates=gates));self.assertEqual(len(a.diagnostics),12)
        self.assertEqual({d.code for d in a.diagnostics},{g.gate_id for g in gates})

    def test_identical_gate_findings_remain_multiple_occurrences(self):
        g=ModelGate("extension:many","1",no_dependencies,
            lambda c:c.result([{"reason":"repeat","severity":"warning"}]*155))
        a=assess_validation(check(artifact(),gates=(g,)))
        self.assertEqual(a.summary["diagnostic_count"],155)

    def test_assessment_never_reexecutes_gate_when_threshold_changes(self):
        calls=[]
        def compute(c):calls.append(c.gate_id);return c.result([{"reason":"lint","severity":"warning"}])
        r=check(artifact(),gates=(ModelGate("extension:test","1",no_dependencies,compute),))
        a,b=assess_validation(r),assess_validation(r,strict=True)
        self.assertEqual(calls,["extension:test"]);self.assertEqual(a.diagnostics,b.diagnostics)

    def test_graph_error_has_known_source_identity_from_bound_report(self):
        a=artifact();a["relations"]=[edge(artifact(number=3))]
        r=assess_validation(check(a))
        self.assertEqual(r.diagnostics[0].artifact_id,a["id"])
        self.assertEqual(r.diagnostics[0].code,"SRV020")

    def test_missing_sources_do_not_pass_enrichment(self):
        r=check(artifact())
        with self.assertRaises(ResultContractError):assess_validation(r,documents=())

    def test_changed_source_path_is_not_accepted_for_enrichment(self):
        d=doc(artifact());r=validate_model((d,),profile=profile())
        with self.assertRaises(ResultContractError):assess_validation(r,documents=(ModelDocument("other",d.content),))

    def test_duplicate_source_label_is_rejected(self):
        d=doc(artifact());r=validate_model((d,),profile=profile())
        with self.assertRaises(ResultContractError):assess_validation(r,documents=(d,d))

    def test_source_order_is_not_significant(self):
        docs=(doc(artifact(number=1)),doc(artifact(number=2)));r=validate_model(docs,profile=profile())
        self.assertEqual(assess_validation(r,documents=docs).as_dict(),assess_validation(r,documents=docs[::-1]).as_dict())

    def test_parse_and_schema_failures_coexist(self):
        v=artifact();del v["title"]
        docs=(ModelDocument("bad.json",b'{]'),doc(v));a=assess_validation(validate_model(docs,profile=profile()))
        self.assertEqual({d.code for d in a.diagnostics},{"SRV001","SRV002"})
        self.assertFalse(a.assessment.complete)

    def test_unexpected_gate_exception_remains_internal_not_policy(self):
        def boom(c):raise RuntimeError("private exception details")
        a=assess_validation(check(artifact(),gates=(ModelGate("extension:boom","1",no_dependencies,boom),)))
        self.assertEqual(a.exit_code,4);self.assertEqual(a.diagnostics[0].rationale,"validation_gate_check_failed")

    def test_cannot_construct_successful_assessment_for_failed_report(self):
        r=validate_model((ModelDocument("bad",b'{]'),),profile=profile())
        with self.assertRaises(TypeError):ValidationAssessment(r,assess_diagnostics([]))

    def test_schema_summary_counts_identified_invalid_artifact(self):
        value=artifact();del value["title"]
        self.assertEqual(assess_validation(check(value)).summary["checked_artifacts"],1)

    def test_profile_rule_origin_and_pointer_are_preserved(self):
        p=profile(forbidden_fields=[{"artifact_types":["goal"],"maturities":[],"fields":["/statement"]}])
        a=assess_validation(validate_model((doc(artifact()),),profile=p))
        self.assertEqual(a.diagnostics[0].origin,"profile_rule");self.assertEqual(a.diagnostics[0].location["pointer"],"/statement")

    def test_cli_bridge_does_not_declare_unavailable_work_finished(self):
        a=assess_validation(validate_model((doc(artifact()),)))
        o=validation_command_result("fixture.validate",a);d=json.loads(serialize_result(o))
        self.assertEqual(o.exit_code,5);self.assertFalse(d["summary"]["complete"])
        self.assertNotIn("checkpoint",d["summary"])

    def test_producer_cannot_downgrade_protected_code(self):
        g=ModelGate("extension:bad","1",no_dependencies,lambda c:c.result([
            {"code":"SRV080","reason":"bad_path","severity":"info"}]))
        r=check(artifact(),gates=(g,))
        with self.assertRaises(ResultContractError):assess_validation(r)

    def test_unexpected_discovery_exception_is_internal_even_when_scope_fails(self):
        def boom(c): raise RuntimeError("private")
        gate=ModelGate("extension:boom","1",boom,lambda c:c.result([]))
        a=assess_validation(check(artifact(),gates=(gate,)))
        self.assertEqual(a.exit_code,4)
        self.assertEqual(a.diagnostics[0].rationale,"validation_gate_discovery_failed")

    def test_cycle_keeps_cycle_code_and_all_related_ids(self):
        a,b=artifact(number=1),artifact(number=2)
        a["relations"]=[edge(b,number=1)];b["relations"]=[edge(a,number=2)]
        observed=assess_validation(check(a,b))
        finding=observed.diagnostics[0]
        self.assertEqual(finding.code,"SRV022")
        self.assertEqual(set(finding.related_ids),{a["id"],b["id"],a["relations"][0]["relation_id"],b["relations"][0]["relation_id"]})
        self.assertEqual(observed.exit_code,3)

    def test_portable_distributions_share_diagnostic_contract_without_test_dependencies(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from support.portable import build_distribution
        from support.processes import run_python
        with TemporaryDirectory() as directory:
            root=Path(directory);out=root/"built"
            module,archive=build_distribution(out)
            module.rename(root/"moved-module");archive.rename(root/"moved.pyz")
            body = """
import sys,json
sys.path.insert(0, LOCATION)
from specroad.diagnostics import Diagnostic, assess_diagnostics, diagnostic_schema
from specroad.cli.results import Diagnostic as CliDiagnostic
from specroad.validation import validate_model, assess_validation, ModelDocument
assert CliDiagnostic is Diagnostic
warning=Diagnostic('CUSTOM','warning','model','fixture',origin='profile_rule',rule_id='custom:missing')
result=assess_diagnostics([warning],checked_ids=['unknown-id'],strict=True)
assert result.exit_code==1 and result.diagnostics[0].severity=='warning'
assert set(warning.as_dict())==set(diagnostic_schema()['required'])
report=assess_validation(validate_model([ModelDocument('broken.json',b'{]')]))
assert report.exit_code==3 and report.diagnostics[0].code=='SRV001'
json.dumps(report.as_dict(),allow_nan=False)
"""
            for name in ('moved-module','moved.pyz'):
                with self.subTest(distribution=name):
                    result=run_python(['-I','-S','-B','-c',body.replace('LOCATION',repr(str(root/name)))],root,capture=True)
                    self.assertEqual(result.returncode,0,result.stderr.decode('utf-8',errors='replace'))
