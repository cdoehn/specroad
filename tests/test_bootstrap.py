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


class BootstrapRobustnessTests(unittest.TestCase):
    def test_changed_config_is_not_hidden_by_a_previous_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); write_project(root); calls = []; registry = metadata_registry(calls)
            self.assertEqual(dispatch(['fixture', 'metadata'], registry=registry, cwd=root), 0)
            (root / 'specroad.json').write_bytes(b'not json')
            self.assertEqual(dispatch(['fixture', 'metadata'], registry=registry, cwd=root), 2)
            self.assertEqual(len(calls), 1)
            self.assertEqual((root / 'specroad.json').read_bytes(), b'not json')

    def test_removed_config_is_not_recreated(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); write_project(root); calls = []; registry = metadata_registry(calls)
            self.assertEqual(dispatch(['fixture', 'metadata', '--project', str(root)], registry=registry), 0)
            (root / 'specroad.json').unlink()
            self.assertEqual(dispatch(['fixture', 'metadata', '--project', str(root)], registry=registry), 2)
            self.assertEqual(len(calls), 1)
            self.assertEqual(list(root.iterdir()), [])

    def test_invalid_explicit_root_cannot_fall_back_to_valid_current_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); write_project(root); calls = []
            result = dispatch_result(['fixture', 'metadata', '--project', str(root / 'missing')],
                                     registry=metadata_registry(calls), cwd=root)
            self.assertEqual(result.exit_code, 2)
            self.assertEqual(calls, [])
            self.assertFalse((root / 'missing').exists())

    def test_bootstrap_remains_available_beside_corrupt_project_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root / 'specroad.json').write_bytes(b'invalid json')
            for args in (['--help'], ['version']):
                self.assertEqual(dispatch(args, cwd=root), 0)
            self.assertEqual((root / 'specroad.json').read_bytes(), b'invalid json')
            self.assertEqual(len(list(root.iterdir())), 1)

    def test_current_runtime_is_rechecked_in_reused_embedding_process(self):
        from specroad.runtime import UnsupportedRuntimeError
        with patch('specroad.runtime.check_runtime', side_effect=[None, UnsupportedRuntimeError('private runtime detail')]):
            self.assertEqual(dispatch(['version']), 0)
            outcome = dispatch_result(['version'])
            self.assertEqual(outcome.exit_code, 5)
            self.assertEqual(outcome.result, None)
        self.assertEqual(dispatch(['version']), 0)

    def test_stored_invocation_context_is_not_an_authority(self):
        from specroad.cli.invocation_context import prepare_invocation
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); write_project(root); registry = metadata_registry([])
            parsed = registry.parse(['fixture', 'metadata'])
            first = prepare_invocation(parsed, cwd=root)
            write_project(root, 'fresh@1.0.0')
            second = prepare_invocation(first, cwd=root)
            self.assertEqual(second.resolved.values['profiles'][-1], 'fresh@1.0.0')
            self.assertEqual(first.resolved.values['profiles'][-1], 'one@1.0.0')

    def test_context_preparation_rejects_non_invocation(self):
        from specroad.cli.invocation_context import prepare_invocation
        from specroad.cli.registry import CommandUsageError
        for value in (None, {}, [], 'version'):
            with self.assertRaises(CommandUsageError):
                prepare_invocation(value)

    def test_instrumented_bootstrap_performs_no_project_reads_scans_or_processes(self):
        body = '''
import os
root = os.getcwd()
effects = []
def observe(event, args):
    if event in {'subprocess.Popen', 'os.system', 'os.posix_spawn', 'socket.connect', 'socket.getaddrinfo'}:
        effects.append(event)
        raise AssertionError('external effect during bootstrap')
    if event in {'open', 'os.scandir', 'os.listdir'} and args and isinstance(args[0], (str, bytes)):
        path = os.path.abspath(os.fsdecode(args[0]))
        if path == root or path.startswith(root + os.sep):
            effects.append(event)
            raise AssertionError('project access during bootstrap')
sys.addaudithook(observe)
from specroad.cli.application import dispatch
assert dispatch(['--help']) == 0
assert dispatch(['version']) == 0
assert effects == []
'''
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root / 'specroad.json').write_bytes(b'broken')
            (root / 'archive').mkdir(); (root / 'archive/item').write_bytes(b'untouched')
            r = run_core(body, root)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual((root / 'archive/item').read_bytes(), b'untouched')

    def test_metadata_only_call_does_not_read_model_or_git(self):
        body = '''
import os
from specroad.cli.application import dispatch
from specroad.cli.registry import CommandSpec, CommandRegistry, CommandClass, PreflightProfile, EffectScope
root = os.getcwd()
reads = []
violations = []
def observe(event, args):
    if event in {'subprocess.Popen', 'os.system', 'os.posix_spawn', 'socket.connect'}:
        violations.append(event)
        raise AssertionError('external process during metadata-only call')
    if event in {'open', 'os.scandir', 'os.listdir'} and args and isinstance(args[0], (str, bytes)):
        path = os.path.abspath(os.fsdecode(args[0]))
        if path == root or path.startswith(root + os.sep):
            # Opening the root directory for descriptor-relative safe reads is
            # not directory enumeration and must remain possible.
            if event == 'open' and isinstance(args[2], int):
                assert not args[2] & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC)
                if path == root and args[2] & os.O_DIRECTORY:
                    return
            if event != 'open' or path != os.path.join(root, 'specroad.json'):
                violations.append(event)
                raise AssertionError('unexpected model/archive scan')
            reads.append(path)
sys.addaudithook(observe)
calls = []
command = CommandSpec('fixture.metadata', ('fixture', 'metadata'), CommandClass.READ_ONLY,
                      PreflightProfile.PROJECT_METADATA, EffectScope.NONE,
                      handler=lambda i: calls.append(i.resolved.project_root) or 0, requires_project=True)
assert dispatch(['fixture', 'metadata'], registry=CommandRegistry((command,))) == 0
assert len(calls) == 1 and len(reads) == 1
assert violations == []
'''
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); write_project(root)
            (root / 'model').mkdir(); (root / 'model/broken').write_bytes(b'not a model')
            (root / '.git').mkdir()
            r = run_core(body, root)
            self.assertEqual(r.returncode, 0, r.stderr)

    def test_unused_handlers_are_not_activated_during_preparation(self):
        from dataclasses import replace
        calls = []
        with tempfile.TemporaryDirectory() as tmp:
            registry = metadata_registry(calls)
            selected = replace(registry.commands[0], command_id='fixture.other', words=('other',),
                               handler=lambda i: self.fail('unselected handler executed'))
            from specroad.cli.commands import builtin_registry
            registry = CommandRegistry((*builtin_registry().commands, *registry.commands, selected))
            self.assertEqual(dispatch(['--help'], registry=registry, cwd=tmp), 0)
            self.assertEqual(calls, [])

    def test_moved_project_uses_current_root_not_previous_location(self):
        with tempfile.TemporaryDirectory() as tmp:
            old = Path(tmp) / 'old'; new = Path(tmp) / 'new'; write_project(old)
            calls = []; registry = metadata_registry(calls)
            self.assertEqual(dispatch(['fixture', 'metadata', '--project', str(old)], registry=registry), 0)
            old.rename(new)
            self.assertEqual(dispatch(['fixture', 'metadata', '--project', str(new)], registry=registry), 0)
            self.assertEqual(calls[-1].project_root, new.resolve())
            self.assertEqual(dispatch(['fixture', 'metadata', '--project', str(old)], registry=registry), 2)
            self.assertFalse(old.exists())

    def test_explicit_root_works_when_current_directory_lookup_is_unavailable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); write_project(root); calls = []
            with patch('pathlib.Path.cwd', side_effect=FileNotFoundError):
                code = dispatch(['fixture', 'metadata', '--project', str(root)], registry=metadata_registry(calls))
            self.assertEqual(code, 0)
            self.assertEqual(len(calls), 1)
