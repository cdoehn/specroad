"""Behavior of test isolation services; no text, layout or documentation oracles."""

from datetime import datetime, timezone
import io
import json
from pathlib import Path
import unittest

from specroad.cli import main
from specroad.cli.application import dispatch_result
from support import ByteSequence, ManualClock, run_cli, run_core, temporary_project, tree_state


class FixtureWorkTests(unittest.TestCase):
    def test_public_operation_and_cli_preserve_real_project_bytes(self):
        with temporary_project() as root:
            before = tree_state(root)
            self.assertEqual(dispatch_result(["--help"], cwd=root).exit_code, 0)
            self.assertEqual(main(["--help"], stdout=io.StringIO()), 0)
            process = run_cli(["--help"], root)
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertEqual(tree_state(root), before)

    def test_bad_cli_request_is_an_error_without_file_effects(self):
        with temporary_project() as root:
            before = tree_state(root)
            process = run_cli(["not-implemented"], root)
            self.assertEqual(process.returncode, 2, process.stderr)
            self.assertEqual(tree_state(root), before)

    def test_clock_advances_only_when_explicitly_requested(self):
        clock = ManualClock()
        initial = clock.utc_now()
        self.assertEqual(clock.monotonic_ns(), 0)
        clock.advance(1_500_000_000)
        self.assertEqual(clock.monotonic_ns(), 1_500_000_000)
        self.assertEqual((clock.utc_now() - initial).total_seconds(), 1.5)
        self.assertEqual(ManualClock().monotonic_ns(), 0)

    def test_entropy_has_reproducible_finite_values(self):
        expected = (bytes(range(16)), bytes(reversed(range(16))))
        first, second = ByteSequence(expected), ByteSequence(expected)
        self.assertEqual([first(16), first(16)], list(expected))
        self.assertEqual([second(16), second(16)], list(expected))
        with self.assertRaises(RuntimeError):
            first(16)

    def test_fixture_cleanup_removes_only_owned_directory(self):
        with temporary_project({"keep": b"untouched"}) as parent:
            before = tree_state(parent)
            with temporary_project({"nested/data": b"data"}, parent=parent) as root:
                self.assertEqual((root / "nested/data").read_bytes(), b"data")
            self.assertFalse(root.exists())
            self.assertEqual(tree_state(parent), before)

    def test_subprocess_closes_stdin_and_returns_machine_data(self):
        with temporary_project() as root:
            process = run_core("import json;print(json.dumps({'stdin':sys.stdin.read(), 'value':7}))",
                               root, capture=True)
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertEqual(json.loads(process.stdout), {"stdin": "", "value": 7})
