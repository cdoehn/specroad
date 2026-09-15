"""Bootstrap effects and fresh context; no help, formatting or timing oracles."""

from pathlib import Path
import os
import tempfile
import unittest
from unittest.mock import patch

from specroad.cli.application import dispatch, dispatch_result
from specroad.cli.registry import (CommandClass, CommandRegistry, CommandSpec,
                                   EffectScope, PreflightProfile)
from specroad.cli.options import global_options
from specroad.cli.results import CommandResult
from support import run_core


def metadata_registry(calls):
    def handle(invocation):
        calls.append(invocation.resolved)
        return CommandResult(invocation.command.command_id, result={
            "profiles": list(invocation.resolved.values["profiles"])})
    return CommandRegistry((CommandSpec(
        command_id="fixture.metadata", words=("fixture", "metadata"),
        command_class=CommandClass.READ_ONLY,
        preflight_profile=PreflightProfile.PROJECT_METADATA,
        effect_scope=EffectScope.NONE, requires_project=True,
        options=global_options("--project"), handler=handle),))


def write_project(root, profile="one@1.0.0"):
    import json
    root.mkdir(parents=True, exist_ok=True)
    (root / "specroad.json").write_text(json.dumps({"profiles": [profile]}), encoding="utf-8")


def no_imports(prefixes):
    # Import denial is an executable resource-boundary observation, not a
    # source-code or internal function-name assertion.
    return '''
class ImportBoundary:
    def find_spec(self, fullname, path=None, target=None):
        if any(fullname == p or fullname.startswith(p + '.') for p in PREFIXES):
            raise AssertionError('Unneeded subsystem requested: ' + fullname)
sys.meta_path.insert(0, ImportBoundary())
'''.replace('PREFIXES', repr(prefixes))


class BootstrapWorkTests(unittest.TestCase):
    def test_cli_import_does_not_request_execution_or_project_subsystems(self):
        body = no_imports(('specroad.cli.application', 'specroad.cli.presentation',
                           'specroad.cli.project_selection', 'specroad.security'))
        with tempfile.TemporaryDirectory() as tmp:
            r = run_core(body + '\nimport specroad.cli\n', tmp)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_help_runs_without_project_or_distribution_identity_services(self):
        body = no_imports(('specroad.cli.project_selection', 'specroad.security',
                           'specroad.runtime.identity', 'specroad.cli.presentation'))
        body += "\nfrom specroad.cli.application import dispatch\nassert dispatch(['--help']) == 0\n"
        with tempfile.TemporaryDirectory() as tmp:
            r = run_core(body, tmp)
            self.assertEqual(r.returncode, 0, r.stderr)

    def test_machine_version_does_not_load_presenter_or_project(self):
        body = no_imports(('specroad.cli.project_selection', 'specroad.security',
                           'specroad.cli.presentation', 'py3langid', 'numpy'))
        body += "\nimport io\nfrom specroad.cli import main\nassert main(['version', '--format', 'json'], stdout=io.StringIO()) == 0\n"
        with tempfile.TemporaryDirectory() as tmp:
            r = run_core(body, tmp)
            self.assertEqual(r.returncode, 0, r.stderr)

    def test_each_call_reads_current_configuration(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); calls = []; registry = metadata_registry(calls)
            write_project(root, 'one@1.0.0')
            self.assertEqual(dispatch(['fixture', 'metadata'], registry=registry, cwd=root), 0)
            write_project(root, 'two@1.0.0')
            self.assertEqual(dispatch(['fixture', 'metadata'], registry=registry, cwd=root), 0)
            self.assertEqual(calls[0].values['profiles'][-1], 'one@1.0.0')
            self.assertEqual(calls[1].values['profiles'][-1], 'two@1.0.0')
            self.assertIsNot(calls[0], calls[1])

    def test_explicit_selection_does_not_leak_to_next_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp); root = parent / 'project'; empty = parent / 'empty'; empty.mkdir()
            write_project(root); calls = []; registry = metadata_registry(calls)
            self.assertEqual(dispatch(['fixture', 'metadata', '--project', str(root)], registry=registry, cwd=empty), 0)
            self.assertEqual(dispatch(['fixture', 'metadata'], registry=registry, cwd=empty), 2)
            self.assertEqual(len(calls), 1)
            self.assertEqual(list(empty.iterdir()), [])

    def test_current_working_directory_is_recomputed(self):
        previous = Path.cwd()
        with tempfile.TemporaryDirectory() as tmp:
            first = Path(tmp) / 'a'; second = Path(tmp) / 'b'
            write_project(first); write_project(second)
            calls = []; registry = metadata_registry(calls)
            try:
                os.chdir(first)
                self.assertEqual(dispatch(['fixture', 'metadata'], registry=registry), 0)
                os.chdir(second)
                self.assertEqual(dispatch(['fixture', 'metadata'], registry=registry), 0)
            finally:
                os.chdir(previous)
            self.assertEqual([c.project_root for c in calls], [first.resolve(), second.resolve()])

    def test_bootstrap_does_not_require_current_directory(self):
        with patch('pathlib.Path.cwd', side_effect=FileNotFoundError):
            for args in (['--help'], ['version']):
                self.assertEqual(dispatch_result(args).exit_code, 0)
                self.assertEqual(dispatch_result(args, cwd='/missing/unneeded').project, None)

    def test_new_process_needs_no_prior_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ('first', 'fresh'):
                cwd = root / name; cwd.mkdir()
                r = run_core("from specroad.cli.application import dispatch;sys.exit(dispatch(['version']))", cwd)
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertEqual(list(cwd.iterdir()), [])
