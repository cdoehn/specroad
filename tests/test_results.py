"""Behavior and machine contracts only; never console wording or layout."""

from dataclasses import replace
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from specroad.cli import main
from specroad.cli.application import dispatch, dispatch_result
from specroad.cli.registry import CommandRegistry, CommandSpec, CommandClass, PreflightProfile, EffectScope, OptionSpec
from specroad.cli.results import (CommandResult, Diagnostic, FailureKind,
    ResultContractError, ResultStatus, serialize_result)


def command(handler, **kwargs):
    fields = dict(command_id="fixture.check", words=("fixture", "check"),
                  command_class=CommandClass.READ_ONLY, preflight_profile=PreflightProfile.BOOTSTRAP,
                  effect_scope=EffectScope.NONE, handler=handler,
                  options=(OptionSpec("--format", takes_value=True, choices=("pretty", "json", "sarif")),))
    fields.update(kwargs)
    return CommandSpec(**fields)


class ResultWorkTests(unittest.TestCase):
    def test_json_envelope_has_version_required_fields_and_real_result(self):
        original = CommandResult("fixture.check", result={"count": 2, "items": ["a", "b"]})
        data = json.loads(serialize_result(original))
        self.assertEqual(set(data), {"format_version", "command", "status", "project", "result", "result_ref", "diagnostics", "summary"})
        self.assertEqual(data["format_version"], "2.0.0")
        self.assertEqual(data["result"], {"count": 2, "items": ["a", "b"]})
        self.assertEqual((data["status"], data["summary"]["complete"], original.exit_code), ("success", True, 0))
        self.assertIsNone(data["project"])
        self.assertIsNone(data["result_ref"])

    def test_failure_classes_preserve_complete_report_and_exit_code(self):
        for kind in FailureKind:
            result = CommandResult.failed("fixture.check", kind, complete=True,
                diagnostics=(Diagnostic("TEST", "error", "test", "finding"),), result={"checked": 2})
            data = json.loads(serialize_result(result))
            self.assertEqual((result.exit_code, data["status"], data["summary"]["complete"]), (int(kind), "failed", True))
            self.assertEqual(data["result"], {"checked": 2})

    def test_incomplete_success_and_unknown_status_are_rejected(self):
        for changes in ({"complete": False}, {"complete": 1}, {"failure": FailureKind.MODEL},
                        {"status": "invented"}, {"status": ResultStatus.FAILED},
                        {"status": ResultStatus.FAILED, "failure": True}):
            with self.assertRaises(ResultContractError):
                CommandResult("fixture.check", **changes)

    def test_diagnostics_keep_all_fields_and_stable_machine_order(self):
        first = Diagnostic("RULE_B", "warning", "lint", "b", path="b.json", location={"line": 2}, related_ids=["b", "a"])
        second = Diagnostic("RULE_A", "error", "schema", "a", path="a.json")
        one = json.loads(serialize_result(CommandResult("fixture.check", diagnostics=(first, second))))
        two = json.loads(serialize_result(CommandResult("fixture.check", diagnostics=(second, first))))
        self.assertEqual(one, two)
        self.assertEqual({d["code"] for d in one["diagnostics"]}, {"RULE_A", "RULE_B"})
        self.assertEqual(set(one["diagnostics"][0]), {"code", "severity", "category", "message", "origin", "rule_id", "artifact_id", "path", "location", "rationale", "remediation", "related_ids"})

    def test_result_snapshot_cannot_be_mutated_by_callers_or_serializers(self):
        payload = {"items": [{"value": 1}]}
        result = CommandResult("fixture.check", result=payload)
        payload["items"][0]["value"] = 2
        document = result.as_dict()
        document["result"]["items"][0]["value"] = 3
        self.assertEqual(result.as_dict()["result"]["items"][0]["value"], 1)
        with self.assertRaises(TypeError):
            result.result["items"][0]["value"] = 4

    def test_non_json_values_are_not_silently_stringified(self):
        for value in (float("nan"), float("inf"), b"binary", object(), {1: "number key"}):
            with self.assertRaises(ResultContractError):
                CommandResult("fixture.check", result=value)

    def test_typed_dispatch_executes_handler_once_and_preserves_input(self):
        calls = []
        def handler(invocation):
            calls.append(invocation.command.command_id)
            return CommandResult(invocation.command.command_id, result={"count": 7})
        registry = CommandRegistry((command(handler),))
        args = ["fixture", "check", "--format", "json"]
        before = list(args)
        result = dispatch_result(args, registry=registry)
        self.assertEqual(result.as_dict()["result"], {"count": 7})
        self.assertEqual(calls, ["fixture.check"])
        self.assertEqual(args, before)

    def test_wrong_result_command_is_an_internal_failure(self):
        registry = CommandRegistry((command(lambda _: CommandResult("other")),))
        self.assertEqual(dispatch(["fixture", "check"], registry=registry), 4)

    def test_handler_io_failure_is_environment_not_success(self):
        def handler(_):
            raise PermissionError("controlled I/O failure")
        registry = CommandRegistry((command(handler),))
        result = dispatch_result(["fixture", "check"], registry=registry)
        self.assertEqual(result.exit_code, 5)
        self.assertFalse(result.complete)

    def test_main_returns_one_json_document_and_does_not_touch_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "unchanged"
            source.write_bytes(b"input")
            out = io.StringIO()
            with patch("pathlib.Path.cwd", side_effect=AssertionError("bootstrap must not select root")):
                code = main(["--help", "--format", "json"], stdout=out, stderr=io.StringIO())
            data = json.loads(out.getvalue())
            self.assertEqual((code, data["command"], data["status"]), (0, "help", "success"))
            self.assertTrue(data["summary"]["complete"])
            self.assertEqual(source.read_bytes(), b"input")
            self.assertEqual(len(list(Path(tmp).iterdir())), 1)

    def test_invalid_json_invocation_is_failed_not_a_fake_success(self):
        out = io.StringIO()
        code = main(["not-implemented", "--format", "json"], stdout=out, stderr=io.StringIO())
        data = json.loads(out.getvalue())
        self.assertEqual((code, data["status"], data["summary"]["complete"]), (2, "failed", False))
        self.assertIsNone(data["result"])

    def test_sarif_preserves_complete_diagnostics_and_policy_failure(self):
        outcome = CommandResult.failed("fixture.check", FailureKind.POLICY, complete=True,
            diagnostics=(Diagnostic("SRV001", "error", "schema", "finding", path="a b.json"),))
        data = json.loads(serialize_result(outcome, "sarif"))
        self.assertEqual(data["version"], "2.1.0")
        self.assertEqual(data["runs"][0]["results"][0]["ruleId"], "SRV001")
        self.assertEqual(data["runs"][0]["invocations"][0]["exitCode"], 1)
        self.assertEqual(data["runs"][0]["properties"]["specroad"]["diagnostics"], outcome.as_dict()["diagnostics"])

    def test_incomplete_report_cannot_masquerade_as_completed_sarif(self):
        outcome = CommandResult.failed("fixture.check", FailureKind.ENVIRONMENT)
        data = json.loads(serialize_result(outcome, "sarif"))
        self.assertEqual(data["status"], "failed")
        self.assertFalse(data["summary"]["complete"])

    def test_serialization_is_independent_of_a_renderer(self):
        with patch("specroad.cli.presentation.render", side_effect=AssertionError("renderer not allowed")):
            outcome = dispatch_result(["--help", "--format", "json"])
            self.assertEqual(json.loads(serialize_result(outcome))["command"], "help")

    def test_output_io_failure_is_not_success(self):
        class FailingStream(io.StringIO):
            def write(self, value):
                raise OSError("controlled failure")
        self.assertEqual(main(["--help", "--format", "json"], stdout=FailingStream(), stderr=io.StringIO()), 5)
