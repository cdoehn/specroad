"""Behavior and machine contracts only; never console wording or layout."""

from dataclasses import replace
import hashlib
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
    ResultContractError, ResultStatus, serialize_result, ResultReference,
    OperationFailure, ContinuationClaim, CheckpointValidation, VerifiedContinuation, confirm_continuation)


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


class ResultRobustnessTests(unittest.TestCase):
    def test_partial_requires_explicit_completed_subcontract(self):
        result = CommandResult("fixture.check", ResultStatus.PARTIAL,
            partial_scope="Only the explicitly selected release", result={"checked": 2})
        data = json.loads(serialize_result(result))
        self.assertEqual((result.exit_code, data["status"]), (0, "partial"))
        self.assertTrue(data["summary"]["complete"])
        for kwargs in ({}, {"partial_scope": ""}, {"partial_scope": "selected", "complete": False}):
            with self.assertRaises(ResultContractError):
                CommandResult("fixture.check", ResultStatus.PARTIAL, **kwargs)

    def test_continuation_cannot_be_forged_with_bare_data_or_a_boolean(self):
        for value in (None, True, {}, {"checkpoint": "exists"}):
            with self.assertRaises(ResultContractError):
                CommandResult("fixture.check", ResultStatus.CONTINUATION_REQUIRED, complete=False, continuation=value)
        with self.assertRaises(ResultContractError):
            VerifiedContinuation()
        self.assertEqual(dispatch(["fixture", "check"], registry=CommandRegistry((command(lambda _: 8),))), 4)

    def test_all_known_failures_keep_their_own_exit_class(self):
        for kind in FailureKind:
            def handler(invocation, selected=kind):
                raise OperationFailure(selected, "Controlled failure", details={"blocker": "controlled"})
            result = dispatch_result(["fixture", "check"], registry=CommandRegistry((command(handler),)))
            self.assertEqual((result.exit_code, result.as_dict()["summary"]["failure_kind"]), (int(kind), kind.name.lower()))
            self.assertFalse(result.complete)

    def test_successful_recording_of_negative_review_is_not_a_policy_gate(self):
        result = CommandResult("fixture.check", result={"review_outcome": "rejected"},
            diagnostics=(Diagnostic("SRV027", "error", "review_outcome", "Negative review recorded"),))
        self.assertEqual((result.exit_code, result.status), (0, ResultStatus.SUCCESS))
        self.assertEqual(result.as_dict()["diagnostics"][0]["severity"], "error")

    def test_summary_cannot_forge_control_state(self):
        for field in ("complete", "work_id", "next_action", "delivery", "failure_kind", "partial_scope"):
            with self.assertRaises(ResultContractError):
                CommandResult("fixture.check", details={field: "forged"})

    def test_recursive_and_invalid_unicode_data_are_rejected(self):
        recursive = []
        recursive.append(recursive)
        for value in (recursive, "\ud800", {"\ud800": 1}):
            with self.assertRaises(ResultContractError):
                CommandResult("fixture.check", result=value)

    def test_invalid_diagnostic_values_are_rejected(self):
        for changes in ({"severity": "fatal"}, {"location": "line"}, {"related_ids": "one"}, {"code": ""}):
            fields = dict(code="D1", severity="error", category="test", message="finding")
            fields.update(changes)
            with self.assertRaises(ResultContractError):
                Diagnostic(**fields)

    def test_external_reference_delivers_full_result_without_inline_duplication(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "result.json"
            payload = {"items": list(range(100)), "total": 100}
            raw = json.dumps(payload).encode()
            path.write_bytes(raw)
            reference = ResultReference(str(path), "application/json", len(raw), hashlib.sha256(raw).hexdigest(), "fixture-result-v1")
            outcome = CommandResult("fixture.check", result_ref=reference)
            data = json.loads(serialize_result(outcome))
            self.assertIsNone(data["result"])
            self.assertEqual(data["result_ref"]["size"], len(raw))
            self.assertEqual(json.loads(path.read_bytes()), payload)
            self.assertEqual(outcome.exit_code, 0)
            with self.assertRaises(ResultContractError):
                replace(outcome, result={"truncated": True})

    def test_missing_corrupt_or_linked_delivery_cannot_claim_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "result.json"
            raw = b'{}'
            reference = ResultReference(str(path), "application/json", len(raw), hashlib.sha256(raw).hexdigest(), "fixture-result-v1")
            outcome = CommandResult("fixture.check", result_ref=reference)
            registry = CommandRegistry((command(lambda _: outcome),))
            self.assertEqual(dispatch(["fixture", "check"], registry=registry), 5)
            path.write_bytes(b'[]')
            self.assertEqual(dispatch(["fixture", "check"], registry=registry), 6)
            target = Path(tmp) / "target.json"
            target.write_bytes(raw)
            path.unlink()
            path.symlink_to(target)
            self.assertEqual(dispatch(["fixture", "check"], registry=registry), 7)
            self.assertEqual(target.read_bytes(), raw)

    def test_result_reference_metadata_rejects_incomplete_or_boolean_values(self):
        fields = dict(path="result.json", media_type="application/json", size=2,
                      sha256="a" * 64, result_schema="fixture-v1")
        for change in ({"sha256": "abcdef"}, {"size": True}, {"size": -1}, {"media_type": "json"}, {"result_schema": ""}):
            with self.assertRaises(ResultContractError):
                ResultReference(**(fields | change))

    def test_sarif_retains_all_severities_and_diagnostic_metadata(self):
        outcome = CommandResult("fixture.check", diagnostics=tuple(Diagnostic(
            "D" + str(index), severity, "test", "finding", rule_id="R" + str(index),
            artifact_id="A", rationale="because", remediation="fix", location={"line": 2})
            for index, severity in enumerate(("info", "warning", "error"))))
        data = json.loads(serialize_result(outcome, "sarif"))
        results = data["runs"][0]["results"]
        self.assertEqual({item["level"] for item in results}, {"note", "warning", "error"})
        self.assertEqual({item["properties"]["specroad"]["rule_id"] for item in results}, {"R0", "R1", "R2"})
        self.assertEqual(len(results), 3)

    def test_selected_project_failure_preserves_known_root_without_invented_hashes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            from support.model import configuration_file
            configuration_file(root)
            cmd = command(lambda _: (_ for _ in ()).throw(OperationFailure(FailureKind.CONFLICT, "stale")),
                preflight_profile=PreflightProfile.PROJECT_READ, requires_project=True)
            result = dispatch_result(["fixture", "check"], registry=CommandRegistry((cmd,)), cwd=root)
            self.assertEqual(result.exit_code, 6)
            self.assertEqual(result.as_dict()["project"]["project_root"], str(root))
            self.assertIsNone(result.as_dict()["project"]["model_root_sha256"])


class ContinuationBoundaryTests(unittest.TestCase):
    """Test the injection boundary, not a fictitious production work engine.

    This verifier understands only this test fixture. No built-in command uses
    it; actual work manifests and resume execution are a later plan step.
    """
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "checkpoint.json"
        self.raw = b'{"fixture_state":"verified","remaining":["next"]}'
        self.path.write_bytes(self.raw)
        self.claim = ContinuationClaim("WORK-" + "0" * 25 + "1", 3, None, "a" * 64, str(self.path), self.temp.name)

    def verifier(self, claim):
        data = json.loads(Path(claim.checkpoint).read_bytes())
        if data != {"fixture_state": "verified", "remaining": ["next"]}:
            raise OperationFailure(FailureKind.CONFLICT, "Fixture no longer matches")
        return CheckpointValidation(claim, len(self.raw), hashlib.sha256(self.raw).hexdigest())

    def outcome(self):
        return CommandResult("fixture.check", ResultStatus.CONTINUATION_REQUIRED, complete=False,
                             continuation=confirm_continuation(self.claim, self.verifier))

    def test_confirmed_checkpoint_has_code_eight_and_all_control_fields(self):
        outcome = self.outcome()
        data = json.loads(serialize_result(outcome))
        self.assertEqual((outcome.exit_code, data["status"]), (8, "continuation_required"))
        self.assertIsNone(data["result"])
        self.assertIsNone(data["result_ref"])
        self.assertFalse(data["summary"]["complete"])
        for name in ("work_id", "completed_units", "total_units", "remaining_manifest_sha256", "checkpoint", "next_action"):
            self.assertIn(name, data["summary"])
        self.assertEqual(data["summary"]["next_action"]["command_id"], "work.resume")
        self.assertEqual(data["summary"]["completed_units"], 3)
        self.assertEqual(self.path.read_bytes(), self.raw)

    def test_no_verifier_or_boolean_approval_cannot_create_continuation(self):
        for verifier in (None, lambda _: True, lambda _: {}, lambda _: self.claim):
            with self.assertRaises(ResultContractError):
                confirm_continuation(self.claim, verifier)

    def test_another_claim_or_incorrect_file_hash_is_not_confirmation(self):
        other = replace(self.claim, work_id="WORK-" + "1" * 26)
        with self.assertRaises(ResultContractError):
            confirm_continuation(self.claim, lambda _: CheckpointValidation(other, len(self.raw), hashlib.sha256(self.raw).hexdigest()))
        with self.assertRaises(OperationFailure):
            confirm_continuation(self.claim, lambda c: CheckpointValidation(c, len(self.raw), "b" * 64))

    def test_checkpoint_disappearance_is_not_continuation(self):
        outcome = self.outcome()
        self.path.unlink()
        registry = CommandRegistry((command(lambda _: outcome),))
        self.assertEqual(dispatch(["fixture", "check"], registry=registry), 5)

    def test_changed_checkpoint_is_not_reused_from_an_old_approval(self):
        outcome = self.outcome()
        self.path.write_bytes(b'{"fixture_state":"invalid","remaining":[]}')
        registry = CommandRegistry((command(lambda _: outcome),))
        self.assertEqual(dispatch(["fixture", "check"], registry=registry), 6)

    def test_sarif_request_for_continuation_returns_json_control_envelope(self):
        outcome = self.outcome()
        data = json.loads(serialize_result(outcome, "sarif"))
        self.assertEqual((data["format_version"], data["status"]), ("2.0.0", "continuation_required"))
        self.assertFalse(data["summary"]["complete"])
        self.assertEqual(outcome.exit_code, 8)

    def test_continuation_cannot_claim_final_delivery_or_completion(self):
        outcome = self.outcome()
        for change in ({"complete": True}, {"result": {"done": True}}, {"status": ResultStatus.SUCCESS}):
            with self.assertRaises(ResultContractError):
                replace(outcome, **change)

    def test_malformed_work_identifiers_hashes_or_unit_counts_are_rejected(self):
        for change in ({"work_id": "WORK-short"}, {"completed_units": True}, {"completed_units": -1},
                       {"total_units": 2}, {"remaining_manifest_sha256": "short"}):
            with self.assertRaises(ResultContractError):
                replace(self.claim, **change)

    def test_linked_checkpoint_is_refused_before_calling_verifier(self):
        target = Path(self.temp.name) / "outside.json"
        target.write_bytes(self.raw)
        self.path.unlink()
        self.path.symlink_to(target)
        calls = []
        with self.assertRaises(OperationFailure) as caught:
            confirm_continuation(self.claim, lambda claim: calls.append(claim) or self.verifier(claim))
        self.assertEqual(caught.exception.kind, FailureKind.SECURITY)
        self.assertEqual(calls, [])
        self.assertEqual(target.read_bytes(), self.raw)

    def test_no_external_or_canonical_files_are_created_by_confirmation(self):
        before = {p.name: p.read_bytes() for p in Path(self.temp.name).iterdir()}
        proof = confirm_continuation(self.claim, self.verifier)
        proof.verify()
        after = {p.name: p.read_bytes() for p in Path(self.temp.name).iterdir()}
        self.assertEqual(before, after)
