"""Actual command gates and native access boundaries, without UI or timing oracles."""
from contextlib import contextmanager, ExitStack
from dataclasses import replace
import builtins
import io
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from specroad.cli.application import dispatch_result, execute_request
from specroad.cli.contracts import (CommandClass, CommandSpec, CommandUsageError,
    EffectScope, OptionSpec, PreflightProfile)
from specroad.cli.invocation_context import prepare_invocation
from specroad.cli.options import global_options
from specroad.cli.registry import CommandRegistry
from support.model import configuration_file, put
from support.read_only import inventory, no_write_attempts


def registry(calls, kind='read', *, metadata=False):
    classes = {'read': (CommandClass.READ_ONLY, EffectScope.NONE),
               'plan': (CommandClass.PLAN_OUTPUT, EffectScope.EXTERNAL_OUTPUT),
               'generated': (CommandClass.GENERATED_OUTPUT, EffectScope.EXTERNAL_OUTPUT),
               'dryrun': (CommandClass.NORMATIVE_WRITE, EffectScope.NORMATIVE_TRANSACTION)}
    cls, effect = classes[kind]
    profile = (PreflightProfile.PROJECT_METADATA if metadata else
               PreflightProfile.PROJECT_WRITE if kind == 'dryrun' else PreflightProfile.PROJECT_READ)
    return CommandRegistry((CommandSpec('fixture.read', ('fixture', 'read'), cls,
        profile, effect, lambda i: calls.append(i.resolved) or 0,
        options=(*global_options('--project'), *((OptionSpec('--dry-run'),) if kind == 'dryrun' else ())),
        aliases=(('fixture-read',),), requires_project=True),))


def request(root, kind='read'):
    options = {'--project': str(root)}
    if kind == 'dryrun':
        options['--dry-run'] = True
    return {'command_id': 'fixture.read', 'options': options}


@contextmanager
def startup_access(root):
    """Record actual opens/enumeration, including descriptor-relative paths.

    Opening code/distribution files outside this owned project remains possible.
    No model, historical or active journal body may be opened during this gate.
    """
    events, forbidden = [], []
    directories = {'.', '.specroad', '.specroad/locks', '.specroad/transactions', '.specroad/recovery'}

    def observe(event, name, directory=None):
        if isinstance(name, int):
            path = Path(os.readlink('/proc/self/fd/' + str(name)))
        else:
            parent = Path.cwd() if directory is None else Path(os.readlink('/proc/self/fd/' + str(directory)))
            path = parent / os.fsdecode(name)
        if not path.is_relative_to(root):
            return
        logical = path.relative_to(root).as_posix()
        events.append((event, logical))
        allowed = directories | {'specroad.json'} if event == 'open' else directories - {'.'}
        if logical not in allowed:
            forbidden.append((event, logical))
            raise AssertionError('Preflight accessed data outside its current metadata scope')

    native_open, native_builtin, native_io = os.open, builtins.open, io.open

    def opening(name, flags, *args, **kwargs):
        observe('open', name, kwargs.get('dir_fd'))
        return native_open(name, flags, *args, **kwargs)

    def stream_open(native):
        def call(name, *args, **kwargs):
            observe('open', name)
            return native(name, *args, **kwargs)
        return call

    with ExitStack() as stack:
        stack.enter_context(patch.object(os, 'open', opening))
        stack.enter_context(patch.object(builtins, 'open', stream_open(native_builtin)))
        stack.enter_context(patch.object(io, 'open', stream_open(native_io)))
        for name in ('scandir', 'listdir'):
            native = getattr(os, name)

            def enumerate_entries(path='.', *, _name=name, _native=native):
                observe(_name, path)
                return _native(path)

            stack.enter_context(patch.object(os, name, enumerate_entries))
        with no_write_attempts():
            yield events
    assert forbidden == []


@pytest.mark.parametrize('kind', ['read', 'plan', 'generated'])
def test_project_read_opens_only_current_metadata_before_handler(tmp_path, kind):
    configuration_file(tmp_path)
    for name in ('spec/invalid.json', 'profiles/invalid.json', 'attachments/private.bin',
                 'archive/objects/invalid.json', '.git/HEAD', '.specroad/cache/invalid',
                 '.specroad/requests/invalid.json', '.specroad/transactions/receipts/invalid.json',
                 '.specroad/recovery/transaction-audit/invalid.json'):
        put(tmp_path, name, b'Uninterpreted data outside the startup scope')
    before = inventory(tmp_path)
    calls = []
    with startup_access(tmp_path) as accesses:
        result = execute_request(request(tmp_path, kind), registry=registry(calls, kind)).result
    assert result.exit_code == 0 and len(calls) == 1
    assert calls[0].project_root == tmp_path
    assert ('scandir', '.specroad/transactions') in accesses
    assert {p for event, p in accesses if event == 'open'} <= {
        '.', 'specroad.json', '.specroad', '.specroad/transactions', '.specroad/recovery'}
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('kind', ['read', 'plan', 'generated', 'dryrun'])
@pytest.mark.parametrize('state', ['journal', 'lock', 'recovery'])
def test_project_read_blocks_all_entry_routes_without_loading_or_mutating_pending_data(tmp_path, kind, state):
    configuration_file(tmp_path, transaction_policy={'auto_recover': True})
    paths = {'journal': '.specroad/transactions/pending/journal.json',
             'lock': '.specroad/locks/project.json',
             'recovery': '.specroad/recovery/pending/journal.json'}
    put(tmp_path, paths[state], b'Presence blocks; this body must not be read or repaired')
    before = inventory(tmp_path)
    calls = []
    commands = registry(calls, kind)
    flags = ['--dry-run'] if kind == 'dryrun' else []
    with startup_access(tmp_path):
        results = [execute_request(request(tmp_path, kind), registry=commands).result,
                   dispatch_result(['fixture-read', '--project', str(tmp_path), *flags], registry=commands),
                   commands.execute_result(commands.parse(['fixture', 'read', *flags]), cwd=tmp_path)]
    for result in results:
        assert result.exit_code == 5
        data = result.details['preflight']
        assert data['profile'] == 'project_read' and data['reason'] == 'recovery_required'
        assert not data['normal_operation_started'] and not data['model_loaded']
        assert not data['write_authorized'] and not data['recovery_performed']
    assert calls == [] and inventory(tmp_path) == before


@pytest.mark.parametrize('arguments', [('--help',), ('version',), ('capabilities',),
    ('command', 'describe', 'version'), ('schema', 'list'), ('schema', 'show', 'json-envelope-v2')])
def test_bootstrap_ignores_broken_project_and_pending_transaction(tmp_path, arguments):
    put(tmp_path, 'specroad.json', b'invalid JSON')
    put(tmp_path, '.specroad/transactions/pending/journal.json', b'pending')
    before = inventory(tmp_path)
    with startup_access(tmp_path) as accesses:
        result = dispatch_result(arguments, cwd=tmp_path)
    assert result.exit_code == 0 and result.project is None
    assert accesses == [] and inventory(tmp_path) == before


def test_metadata_diagnosis_stays_available_without_loading_pending_data(tmp_path):
    configuration_file(tmp_path)
    put(tmp_path, '.specroad/transactions/pending/journal.json', b'pending')
    calls = []
    with startup_access(tmp_path) as accesses:
        result = execute_request(request(tmp_path), registry=registry(calls, metadata=True)).result
    assert result.exit_code == 0 and len(calls) == 1
    assert all(event == 'open' and path in ('.', 'specroad.json') for event, path in accesses)


@pytest.mark.parametrize('change', ['version', 'unknown_field', 'invalid_json'])
def test_project_read_rejects_invalid_configuration_before_handler(tmp_path, change):
    configuration_file(tmp_path, **({'schema_version': '99.0.0'} if change == 'version' else
                                  {'foreign_field': True} if change == 'unknown_field' else {}))
    if change == 'invalid_json':
        (tmp_path / 'specroad.json').write_bytes(b'broken')
    calls = []
    before = inventory(tmp_path)
    with no_write_attempts():
        result = execute_request(request(tmp_path), registry=registry(calls)).result
    assert result.exit_code == 3 and calls == []
    assert result.details['preflight']['normal_operation_started'] is False
    if change == 'version':
        assert result.details['preflight']['model_error']['highest_supported'] == '0.2.0'
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('profile', [PreflightProfile.PROJECT_READ, PreflightProfile.PROJECT_WRITE])
def test_project_profile_cannot_declare_projectless_execution(profile):
    with pytest.raises(CommandUsageError):
        replace(registry([]).commands[0], preflight_profile=profile, requires_project=False)


def test_changed_configuration_cannot_mix_old_options_with_current_preflight(tmp_path, monkeypatch):
    configuration_file(tmp_path)
    (tmp_path / '.specroad').mkdir()
    native = os.scandir
    changed = False

    def replacing(path):
        nonlocal changed
        if not changed:
            changed = True
            configuration_file(tmp_path, validation_policy={'fail_on': 'warning'})
        return native(path)

    monkeypatch.setattr(os, 'scandir', replacing)
    calls = []
    result = execute_request(request(tmp_path), registry=registry(calls)).result
    assert result.exit_code == 6 and calls == []
    assert result.details['preflight']['reason'] == 'preflight_configuration_changed'
    assert b'warning' in (tmp_path / 'specroad.json').read_bytes()


def test_operational_change_during_startup_blocks_the_handler(tmp_path, monkeypatch):
    configuration_file(tmp_path)
    (tmp_path / '.specroad').mkdir()
    native = os.close
    changed = False

    def replacing(descriptor):
        nonlocal changed
        path = Path(os.readlink('/proc/self/fd/' + str(descriptor)))
        native(descriptor)
        if not changed and path == tmp_path / '.specroad':
            changed = True
            put(tmp_path, '.specroad/locks/project.json', b'new writer')

    monkeypatch.setattr(os, 'close', replacing)
    calls = []
    result = execute_request(request(tmp_path), registry=registry(calls)).result
    assert result.exit_code == 6 and calls == []
    assert result.details['preflight']['reason'] == 'preflight_operational_metadata_changed'
    assert (tmp_path / '.specroad/locks/project.json').read_bytes() == b'new writer'


def test_prepared_invocation_does_not_reuse_a_previous_clear_gate(tmp_path):
    configuration_file(tmp_path)
    calls = []
    commands = registry(calls)
    prepared = prepare_invocation(commands.parse(['fixture-read']), cwd=tmp_path)
    put(tmp_path, '.specroad/transactions/later/journal.json', b'later transaction')
    before = inventory(tmp_path)
    with no_write_attempts():
        result = commands.execute_result(prepared, cwd=tmp_path)
    assert result.exit_code == 5 and calls == []
    assert inventory(tmp_path) == before


def test_relocated_project_uses_only_its_current_root(tmp_path):
    root = tmp_path / 'before'
    root.mkdir()
    configuration_file(root)
    calls = []
    commands = registry(calls)
    assert execute_request(request(root), registry=commands).result.exit_code == 0
    moved = tmp_path / 'after'
    root.rename(moved)
    assert execute_request(request(moved), registry=commands).result.exit_code == 0
    assert [call.project_root for call in calls] == [root, moved]


def test_linked_operational_namespace_is_rejected_without_following_it(tmp_path):
    root = tmp_path / 'project'
    foreign = tmp_path / 'foreign'
    root.mkdir()
    foreign.mkdir()
    configuration_file(root)
    (root / '.specroad').symlink_to(foreign, target_is_directory=True)
    calls = []
    with no_write_attempts():
        result = execute_request(request(root), registry=registry(calls)).result
    assert result.exit_code == 7 and calls == []
    assert result.details['preflight']['reason'] == 'unsafe_preflight_resource'
    assert list(foreign.iterdir()) == []
