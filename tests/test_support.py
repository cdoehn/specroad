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


class FixtureRobustnessTests(unittest.TestCase):
    def test_failed_setup_and_bad_paths_leave_no_files(self):
        invalid = ({"../escape": b"x"}, {"/absolute": b"x"}, {"C:/drive": b"x"},
                   {"a\\b": b"x"}, {"a//b": b"x"}, {"./a": b"x"},
                   {"name": "not bytes"}, {"a": b"x", "a/child": b"y"},
                   {"A": b"x", "a": b"y"})
        with temporary_project({"keep": b"keep"}) as parent:
            before = tree_state(parent)
            for files in invalid:
                with self.subTest(files=files), self.assertRaises((ValueError, TypeError)):
                    with temporary_project(files, parent=parent):
                        self.fail("Invalid fixture accepted")
                self.assertEqual(tree_state(parent), before)

    def test_context_exception_cleans_up_but_propagates(self):
        class ExpectedFailure(Exception):
            pass
        with temporary_project() as parent:
            before = tree_state(parent)
            with self.assertRaises(ExpectedFailure):
                with temporary_project(parent=parent) as root:
                    (root / "created").write_bytes(b"work")
                    raise ExpectedFailure()
            self.assertFalse(root.exists())
            self.assertEqual(tree_state(parent), before)

    def test_parallel_fixtures_do_not_share_bytes_or_paths(self):
        with temporary_project() as first, temporary_project() as second:
            self.assertNotEqual(first, second)
            self.assertEqual(tree_state(first), tree_state(second))
            (first / "specroad.json").write_bytes(b"changed")
            self.assertEqual((second / "specroad.json").read_bytes(), b"{}\n")

    def test_original_fixture_mapping_is_not_mutated_or_kept_live(self):
        files = {"file": b"first"}
        with temporary_project(files) as root:
            files["file"] = b"second"
            files["extra"] = b"extra"
            self.assertEqual(tree_state(root), {"file": ("file", b"first")})

    def test_invalid_clock_movement_never_changes_time(self):
        clock = ManualClock()
        before = clock.utc_now(), clock.monotonic_ns()
        for value in (-1, True, 0.5, float("nan"), "1", 10**40):
            with self.subTest(value=value), self.assertRaises((ValueError, OverflowError)):
                clock.advance(value)
            self.assertEqual((clock.utc_now(), clock.monotonic_ns()), before)
        with self.assertRaises(ValueError):
            ManualClock(datetime(2020, 1, 1))

    def test_invalid_entropy_request_does_not_consume_fixture(self):
        chunks = [b"abcd"]
        entropy = ByteSequence(chunks)
        chunks[0] = b"other"
        for count in (True, 0, -1, 1.5, 3):
            with self.subTest(count=count), self.assertRaises(ValueError):
                entropy(count)
        self.assertEqual(entropy(4), b"abcd")
        with self.assertRaises(RuntimeError):
            entropy(4)

    def test_injected_services_do_not_mutate_global_time_or_random(self):
        import random
        import time
        state, real_time = random.getstate(), time.time
        ManualClock().advance(4)
        self.assertEqual(ByteSequence([b"abc"])(3), b"abc")
        self.assertEqual(random.getstate(), state)
        self.assertIs(time.time, real_time)

    def test_child_environment_does_not_leak_parent_secrets_or_pythonpath(self):
        import os
        from unittest.mock import patch
        original_cwd = Path.cwd()
        with temporary_project() as root, patch.dict(os.environ, {
            "SPECRD_TEST_SECRET": "private", "PYTHONPATH": str(root), "VIRTUAL_ENV": str(root),
        }):
            before = dict(os.environ)
            process = run_core("import os,json;print(json.dumps({'secret':os.getenv('SPECRD_TEST_SECRET'),"
                               "'path':os.getenv('PYTHONPATH'),'venv':os.getenv('VIRTUAL_ENV'),"
                               "'cwd':os.getcwd()}))", root, capture=True)
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertEqual(json.loads(process.stdout), {
                "secret": None, "path": None, "venv": None, "cwd": str(root.resolve()),
            })
            self.assertEqual(dict(os.environ), before)
        self.assertEqual(Path.cwd(), original_cwd)

    def test_child_failure_does_not_destroy_fixture(self):
        with temporary_project({"keep": b"keep"}) as root:
            before = tree_state(root)
            process = run_core("raise RuntimeError('intentional behavior failure')", root)
            self.assertNotEqual(process.returncode, 0)
            self.assertEqual(tree_state(root), before)

    def test_tree_observation_and_cleanup_never_follow_external_link(self):
        import os
        with temporary_project({"valuable": b"original"}) as outside:
            before = tree_state(outside)
            with temporary_project() as root:
                (root / "empty").mkdir()
                os.symlink(outside, root / "external", target_is_directory=True)
                state = tree_state(root)
                self.assertEqual(state["external"], ("symlink", str(outside)))
                self.assertEqual(state["empty"], ("directory", None))
                self.assertNotIn("external/valuable", state)
            self.assertEqual(tree_state(outside), before)
