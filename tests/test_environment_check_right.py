"""Environment diagnosis on restricted roots and uncertain native observations."""
from contextlib import contextmanager
from dataclasses import replace
import json
import os
from pathlib import Path
import stat
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from specroad.cli.commands import builtin_registry
from specroad.cli.contracts import CommandProtocol, EffectScope, PreflightProfile
from specroad.cli.registry import CommandRegistry
from specroad.model.errors import ModelError
from specroad.model.schema_catalog import SchemaCatalog
from support import run_core
from support.model import configuration_file, put
from support.read_only import inventory, no_write_attempts
from test_environment_check import checks, report
from test_preflight_profiles import startup_access


@contextmanager
def readonly(root):
    paths = [root, *root.rglob('*')]
    modes = {p: stat.S_IMODE(p.stat().st_mode) for p in paths}
    try:
        for p in paths:
            p.chmod(0o555 if p.is_dir() else 0o444)
        yield
    finally:
        for p, mode in modes.items():
            p.chmod(mode)


@pytest.mark.parametrize('state', ['clean', 'unknown_lock', 'pending'])
@pytest.mark.parametrize('target', [None, 'version', 'fixture.writer'])
def test_readonly_root_reports_only_proven_prerequisites_without_effects(tmp_path, state, target):
    configuration_file(tmp_path, transaction_policy={'auto_recover': True})
    put(tmp_path, 'spec/invalid.json', b'Invalid model is outside this diagnosis')
    if state == 'pending':
        put(tmp_path, '.specroad/transactions/pending/journal.json', b'Never read or repair')
    elif state == 'unknown_lock':
        put(tmp_path, '.specroad/locks/project.json', b'Owner not inspected or adopted')
    calls = []
    writer = replace(builtin_registry().resolve('version'), command_id='fixture.writer',
        words=('fixture', 'writer'), preflight_profile=PreflightProfile.INPUT_READ,
        effect_scope=EffectScope.EXTERNAL_OUTPUT, requires_write_paths=('output',),
        handler=lambda invocation: calls.append(invocation) or 0,
        protocol=CommandProtocol('fixture-v1', {'command_id': 'fixture.writer'}))
    registry = CommandRegistry((*builtin_registry().commands, writer))
    options = {'--project': str(tmp_path)}
    if target is not None:
        options['--for-command'] = target
    with readonly(tmp_path):
        before = inventory(tmp_path)
        with startup_access(tmp_path):
            result = report(options, registry=registry)
        assert inventory(tmp_path) == before
        assert stat.S_IMODE(tmp_path.stat().st_mode) == 0o555
        assert stat.S_IMODE((tmp_path / 'specroad.json').stat().st_mode) == 0o444
    assert calls == [] and result.complete
    value = result.as_dict()['result']
    SchemaCatalog().validate('environment-v1', value)
    blocked = state != 'clean'
    assert result.exit_code == (5 if blocked else 0)
    assert value['compatible'] is (False if blocked else None if target == 'fixture.writer' else True)
    assert value['operation_readiness'] == ('not_requested' if target is None else
        'blocked' if blocked else 'unknown' if target == 'fixture.writer' else 'ready')
    assert value['recovery_required'] is (True if state == 'pending' else None if blocked else False)
    assert value['semantic_validation_performed'] is False
    assert checks(value)['project.metadata']['state'] == 'passed'
    if state == 'unknown_lock':
        assert checks(value)['project.operational']['reason'] == 'operational_state_unknown'
    if target == 'fixture.writer':
        assert checks(value)['command.write_paths']['state'] == 'unknown'


@pytest.mark.parametrize('state', ['unknown_file', 'unknown_directory', 'mixed'])
def test_unclassified_operational_entries_do_not_invent_recovery_certainty(tmp_path, state):
    configuration_file(tmp_path)
    if state == 'unknown_directory':
        put(tmp_path, '.specroad/unclassified/private', b'Do not descend')
    else:
        put(tmp_path, '.specroad/unclassified', b'Not a verified journal')
    if state == 'mixed':
        put(tmp_path, '.specroad/transactions/pending/journal.json', b'Known active entry')
    before = inventory(tmp_path)
    with startup_access(tmp_path):
        result = report({'--project': str(tmp_path), '--for-command': 'version'})
    assert result.exit_code == 5 and result.complete
    assert result.result['compatible'] is False and result.result['operation_readiness'] == 'blocked'
    assert result.result['recovery_required'] is (True if state == 'mixed' else None)
    assert checks(result.result)['project.operational']['reason'] == (
        'recovery_required' if state == 'mixed' else 'operational_state_unknown')
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('kind', ['missing_attribute', 'oserror', 'valueerror', 'overflow',
    'infinite', 'negative', 'text', 'boolean', 'reversed', 'malformed', 'float', 'bad_infinity', 'zero'])
def test_optional_limit_uncertainty_never_becomes_host_capacity_or_a_blocker(tmp_path, kind):
    values = {'infinite': (-1, -1), 'negative': (-2, -2), 'text': ('1', '2'),
              'boolean': (True, True), 'reversed': (200, 100), 'malformed': (1, 2, 3),
              'float': (1.0, 2.0), 'bad_infinity': (1, 2), 'zero': (0, 100)}
    failures = {'oserror': OSError, 'valueerror': ValueError, 'overflow': OverflowError}

    def getrlimit(resource):
        if resource == 2:
            return 9, 9  # CPU time allowance is not a CPU-capacity observation.
        if kind in failures:
            raise failures[kind]('Unavailable native observation')
        return values.get(kind, (1, 2))

    api = SimpleNamespace(RLIMIT_CPU=2, RLIM_INFINITY=True if kind == 'bad_infinity' else -1,
                          getrlimit=getrlimit)
    if kind != 'missing_attribute':
        api.RLIMIT_AS = 1
    with patch('specroad.runtime.limits._resource_api', return_value=api), startup_access(tmp_path), \
         patch.object(os, 'cpu_count', side_effect=AssertionError('Host total is not a quota')):
        result = report({'--for-command': 'version'}, cwd=tmp_path)
    assert result.exit_code == 0 and result.complete and result.result['compatible'] is True
    assert result.result['operation_readiness'] == 'ready'
    observations = result.result['observations']
    assert observations['memory_limit']['state'] == ('observed' if kind == 'zero' else 'unknown')
    assert observations['memory_limit']['value'] == (0 if kind == 'zero' else None)
    assert observations['memory_limit']['scope'] == 'process_address_space_ceiling'
    for name in ('cpu_capacity', 'storage_capacity'):
        assert observations[name]['state'] == 'unknown' and observations[name]['value'] is None
    SchemaCatalog().validate('environment-v1', result.as_dict()['result'])
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize('denied_name', ['specroad.json', '.specroad'])
def test_actual_metadata_open_failure_retains_environment_class_without_repair(tmp_path, denied_name):
    configuration_file(tmp_path)
    (tmp_path / '.specroad').mkdir()
    before = inventory(tmp_path)
    native = os.open
    denied = []

    def opening(path, *args, **kwargs):
        if Path(path).name == denied_name:
            denied.append(path)
            raise PermissionError(13, 'Denied owned metadata')
        return native(path, *args, **kwargs)

    with patch.object(os, 'open', opening), no_write_attempts():
        result = report({'--project': str(tmp_path), '--for-command': 'version'})
    assert denied and result.exit_code == 5 and inventory(tmp_path) == before
    if denied_name == '.specroad':
        assert result.complete and result.result['compatible'] is False
        assert result.result['recovery_required'] is None
        assert checks(result.result)['project.metadata']['reason'] == 'project_metadata_unavailable'
        SchemaCatalog().validate('environment-v1', result.as_dict()['result'])
    else:
        assert not result.details['preflight']['normal_operation_started']


@pytest.mark.parametrize('kind', ['config_symlink', 'operational_symlink'])
def test_unsafe_metadata_never_reads_foreign_content_or_changes_it(tmp_path, kind):
    root = tmp_path / 'project'; root.mkdir()
    foreign = tmp_path / 'foreign'; foreign.mkdir()
    configuration_file(root)
    put(foreign, 'private', b'Foreign private bytes must never be read by the report')
    if kind == 'operational_symlink':
        (root / '.specroad').symlink_to(foreign, target_is_directory=True)
    else:
        target = root / 'specroad.json'; target.unlink()
        target.symlink_to(foreign / 'private')
    before = inventory(tmp_path)
    with startup_access(root):
        result = report({'--project': str(root)})
    assert result.exit_code == 7 and inventory(tmp_path) == before
    assert 'Foreign private bytes' not in json.dumps(result.as_dict())
    if kind == 'operational_symlink':
        assert result.complete and result.result['recovery_required'] is None
        assert result.result['compatible'] is False


@pytest.mark.parametrize('valid', [False, True])
def test_regular_configuration_alias_is_read_only_and_keeps_format_checks(tmp_path, valid):
    # Unlike a symlink, this is a regular entry at the selected config path.
    # The read contract does not acquire the writer's single-link authority.
    root = tmp_path / 'project'; root.mkdir()
    configuration_file(root)
    selected = root / 'specroad.json'
    shared = tmp_path / 'shared-config'
    shared.write_bytes(selected.read_bytes() if valid else b'INVALID-CONFIGURATION-CONTENT')
    selected.unlink(); os.link(shared, selected)
    before = inventory(tmp_path)
    with startup_access(root):
        result = report({'--project': str(root)})
    assert result.exit_code == (0 if valid else 3)
    assert selected.stat().st_nlink == shared.stat().st_nlink == 2
    assert inventory(tmp_path) == before
    assert 'INVALID-CONFIGURATION-CONTENT' not in json.dumps(result.as_dict())
    if valid:
        assert result.complete and result.result['compatible'] is True
        assert result.result['semantic_validation_performed'] is False
    else:
        assert not result.details['preflight']['normal_operation_started']


@pytest.mark.parametrize('kind', ['configuration', 'operational'])
def test_metadata_change_during_diagnosis_keeps_conflict_and_current_bytes(tmp_path, kind, monkeypatch):
    configuration_file(tmp_path)
    (tmp_path / '.specroad').mkdir()
    changed = []
    if kind == 'configuration':
        native = os.scandir

        def scanning(path):
            if not changed:
                configuration_file(tmp_path, validation_policy={'fail_on': 'warning'})
                changed.append(kind)
            return native(path)

        monkeypatch.setattr(os, 'scandir', scanning)
    else:
        native = os.close

        def closing(fd):
            current = Path(os.readlink('/proc/self/fd/' + str(fd)))
            native(fd)
            if not changed and current == tmp_path / '.specroad':
                put(tmp_path, '.specroad/locks/project.json', b'New writer; never remove')
                changed.append(kind)

        monkeypatch.setattr(os, 'close', closing)
    result = report({'--project': str(tmp_path), '--for-command': 'version'})
    assert changed == [kind] and result.exit_code == 6 and result.complete
    assert result.result['compatible'] is False and result.result['operation_readiness'] == 'blocked'
    assert result.result['recovery_required'] is None
    assert checks(result.result)['project.metadata']['reason'] == (
        'project_configuration_changed' if kind == 'configuration' else 'project_metadata_changed')
    if kind == 'configuration':
        assert b'warning' in (tmp_path / 'specroad.json').read_bytes()
    else:
        assert (tmp_path / '.specroad/locks/project.json').read_bytes() == b'New writer; never remove'


def test_fresh_readonly_project_diagnosis_has_no_writes_processes_or_secret_disclosure(tmp_path):
    configuration_file(tmp_path)
    put(tmp_path, 'spec/private.json', b'PRIVATE-FILE-CONTENT')
    body = '''
import os, json
os.environ['SPECROAD_TEST_SECRET'] = 'PRIVATE-ENVIRONMENT-CONTENT'
root = os.getcwd(); attempts = []
def observe(event, args):
    forbidden = {'subprocess.Popen', 'os.system', 'os.posix_spawn', 'socket.connect',
        'socket.getaddrinfo', 'resource.setrlimit', 'os.mkdir', 'os.remove', 'os.rename',
        'os.chmod', 'os.truncate', 'os.utime', 'os.symlink', 'os.link'}
    denied = event in forbidden
    if event == 'open':
        name, mode, flags = args
        denied |= bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))
        if isinstance(name, (str, bytes)):
            path = os.path.abspath(os.fsdecode(name))
            if path == root or path.startswith(root + os.sep):
                denied |= path not in {root, os.path.join(root, 'specroad.json')}
    if event in {'os.scandir', 'os.listdir'}:
        name = args[0]
        path = (os.readlink('/proc/self/fd/' + str(name)) if isinstance(name, int)
                else os.path.abspath(os.fsdecode(name)))
        denied |= path == root or path.startswith(root + os.sep)
    if denied:
        attempts.append(event)
        raise AssertionError('Forbidden environment-check effect')
sys.addaudithook(observe)
from specroad.cli.application import dispatch_result
result = dispatch_result(['environment', 'check', '--project', root, '--for-command', 'version'])
assert result.exit_code == 0 and result.result['compatible'] is True, result.as_dict()
assert result.result['metadata']['metadata_bytes_read'] > 0
assert result.result['semantic_validation_performed'] is False and attempts == []
print(json.dumps(result.as_dict()))
'''
    with readonly(tmp_path):
        before = inventory(tmp_path)
        child = run_core(body, tmp_path, capture=True)
        assert child.returncode == 0, child.stderr
        assert inventory(tmp_path) == before
    assert b'PRIVATE-ENVIRONMENT-CONTENT' not in child.stdout
    assert b'PRIVATE-FILE-CONTENT' not in child.stdout
    assert json.loads(child.stdout)['result']['recovery_required'] is False


@pytest.mark.parametrize('mutation', ['python_empty', 'support_missing', 'distribution_empty',
    'build_hash', 'unknown_number', 'observed_null', 'extra_runtime_secret'])
def test_public_schema_rejects_missing_identity_and_false_resource_observations(tmp_path, mutation):
    with patch('specroad.runtime.limits._resource_api', return_value=None), startup_access(tmp_path):
        value = report(cwd=tmp_path).as_dict()['result']
    catalog = SchemaCatalog(); catalog.validate('environment-v1', value)
    if mutation == 'python_empty':
        value['python'] = {}
    elif mutation == 'support_missing':
        del value['python']['supported']
    elif mutation == 'distribution_empty':
        value['distribution'] = {}
    elif mutation == 'build_hash':
        value['distribution']['build_sha256'] = 'not-a-sha256'
    elif mutation == 'extra_runtime_secret':
        value['python']['environment'] = {'secret': 'not part of the runtime contract'}
    else:
        observation = value['observations']['memory_limit']
        if mutation == 'unknown_number':
            observation['value'] = 123
        else:
            observation['state'] = 'observed'
    with pytest.raises(ModelError):
        catalog.validate('environment-v1', value)


def test_repeated_diagnoses_recheck_current_operational_state_without_reusing_a_clear_report(tmp_path):
    configuration_file(tmp_path)
    with startup_access(tmp_path):
        first = report({'--project': str(tmp_path)})
    put(tmp_path, '.specroad/locks/project.json', b'Uninspected current owner')
    before = inventory(tmp_path)
    with startup_access(tmp_path):
        second = report({'--project': str(tmp_path)})
    assert first.exit_code == 0 and first.result['recovery_required'] is False
    assert second.exit_code == 5 and second.result['recovery_required'] is None
    assert first.result['compatible'] is True and second.result['compatible'] is False
    assert inventory(tmp_path) == before
