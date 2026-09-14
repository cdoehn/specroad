"""No presentation assertions: only semantic data, side effects and exit codes."""

import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from specroad.cli import main
from specroad.cli.application import CommandResponse, dispatch_result
from specroad.cli.results import CommandResult, Diagnostic, FailureKind


class MemoryTerminal(io.StringIO):
    def isatty(self):
        return True


class PresentationIndependenceTests(unittest.TestCase):
    def test_machine_payload_is_identical_for_tty_quiet_and_color_choices(self):
        documents = []
        for flags, no_color in (([], False), (["--quiet"], False), (["--no-color"], False),
                                (["--quiet", "--no-color"], True)):
            with patch.dict(os.environ, {"NO_COLOR": ""} if no_color else {}, clear=True):
                out = MemoryTerminal()
                code = main(["--help", "--format", "json", *flags], stdout=out, stderr=MemoryTerminal())
                documents.append(json.loads(out.getvalue()))
                self.assertEqual(code, 0)
        self.assertTrue(all(data == documents[0] for data in documents))

    def test_quiet_machine_report_keeps_payload_warnings_and_errors(self):
        outcome = CommandResult.failed("fixture.check", FailureKind.POLICY, complete=True,
            result={"items": [1, 2], "total": 2}, diagnostics=(
                Diagnostic("W1", "warning", "test", "warning"),
                Diagnostic("E1", "error", "test", "error")))
        out = MemoryTerminal()
        response = CommandResponse(outcome, {"--format": "json", "--quiet": True})
        with patch("specroad.cli.execute", return_value=response):
            code = main(["fixture", "check", "--format", "json", "--quiet"], stdout=out, stderr=MemoryTerminal())
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(out.getvalue()), outcome.as_dict())

    def test_format_and_color_options_do_not_change_project_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            marker = Path(tmp) / "specroad.json"
            marker.write_bytes(b'{"untouched":true}')
            for flags in ([], ["--quiet"], ["--no-color"], ["--format", "json", "--quiet"]):
                self.assertEqual(main(["--help", *flags], stdout=MemoryTerminal(), stderr=MemoryTerminal()), 0)
                self.assertEqual(marker.read_bytes(), b'{"untouched":true}')
                self.assertEqual(len(list(Path(tmp).iterdir())), 1)

    def test_command_logic_does_not_construct_a_presenter(self):
        with patch("specroad.cli.PrettyRenderer", side_effect=AssertionError("Renderer must be optional")):
            for flags in ([], ["--no-color"], ["--quiet"], ["--format", "json"]):
                self.assertEqual(dispatch_result(["--help", *flags]).exit_code, 0)

    def test_invalid_quiet_call_remains_an_error_with_complete_diagnostic_data(self):
        out = MemoryTerminal()
        code = main(["missing", "--format", "json", "--quiet", "--no-color"], stdout=out, stderr=MemoryTerminal())
        data = json.loads(out.getvalue())
        self.assertEqual((code, data["status"], data["summary"]["complete"]), (2, "failed", False))
        self.assertEqual(len(data["diagnostics"]), 1)
        self.assertEqual(data["diagnostics"][0]["severity"], "error")

    def test_closed_output_is_an_io_failure_not_a_success(self):
        stream = io.StringIO()
        stream.close()
        self.assertEqual(main(["--help", "--format", "json"], stdout=stream, stderr=io.StringIO()), 5)
