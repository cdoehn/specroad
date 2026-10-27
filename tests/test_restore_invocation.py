"""Real native Restore invocation; synthetic host decisions, no public CLI claim."""
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys

import pytest

from specroad.authoring._inspection_snapshot import InspectionSnapshot
from specroad.changes._lock_files import LockFiles
from specroad.changes.recovery_values import RecoveryAuthority
from specroad.cli import _restore_adapter as adapter
from specroad.cli._restore_adapter import run_restore
from specroad.recovery import RestoreError
from specroad.security import ProjectBoundary
from specroad.storage.operational_preflight import observe_operational_preflight
from support.model import put
from support.read_only import inventory, no_write_attempts
from support.restore import restore_case, plan_for
from support.scopes import descriptor
from test_restore_execution import ACTOR, files
from test_restore_execution_right import fixture, interrupted
from test_restore_files import case, selection
from test_restore_invocation_options import invocation
from test_restore_plan_right import retained_case


def planning(options, out):
    result = {'--project': str(options['project_root']), '--from': options['source_path'],
        '--source-root': str(options['source_root']), '--source-kind': options['source_kind'],
        '--dry-run': True, '--output-root': str(out), '--output': 'plans/original.json'}
    for key in ('default_locale', 'generated_path'):
        if key in options:
            result['--' + key.replace('_', '-')] = options[key]
    return result


def execution(options, plan, out, *, chosen=None):
    put(out, 'original.json', plan.source_bytes)
    value = {'--project': str(options['project_root']), '--plan-root': str(out),
        '--plan': 'original.json', '--expected-target-root': plan.data['expected_target_root'],
        '--actor-type': 'tool', '--actor-id': 'synthetic-invocation-host', '--request-id': 'invocation-test'}
    if chosen is not None:
        put(out, 'selected.json', chosen)
        value.update({'--selection-root': str(out), '--affected-journals': 'selected.json'})
    return value


def authority(check=lambda request: True):
    return RecoveryAuthority('synthetic-invocation-authorizer', '1', check)


def rejects(value, code, *, host=None):
    with no_write_attempts(), pytest.raises(RestoreError) as error:
        run_restore(value, authority=host)
    assert error.value.exit_code == code and not error.value.mutation_possible


@pytest.mark.parametrize('kind', ['project_bundle', 'baseline'])
@pytest.mark.parametrize('representation', ['argv', 'mapping'])
def test_explicit_plan_matches_native_bytes_without_project_or_source_writes(tmp_path, kind, representation):
    options, _, plan, out = case(tmp_path, kind, journal=True)
    before = {key: inventory(options[key]) for key in ('project_root', 'source_root')}
    def not_authorized(request):
        raise AssertionError('Planning must not obtain writer authority')
    result = run_restore(invocation(planning(options, out), representation), authority=authority(not_authorized))
    assert result.source_bytes == plan.source_bytes == (out / 'plans/original.json').read_bytes()
    assert result.sha256 == sha256(plan.source_bytes).hexdigest()
    assert result.data['project_root'] == str(options['project_root'])
    assert all(inventory(options[key]) == snapshot for key, snapshot in before.items())
    assert not (options['project_root'] / '.specroad/locks/project.json').exists()


@pytest.mark.parametrize('kind', ['project_bundle', 'baseline'])
@pytest.mark.parametrize('damage', ['missing', 'invalid'])
def test_damaged_configuration_uses_independent_coverage_not_ordinary_project_loading(tmp_path, kind, damage):
    options, _, evidence = retained_case(tmp_path, kind)
    path = options['project_root'] / 'specroad.json'
    if damage == 'missing': path.unlink()
    else: path.write_bytes(b'\xffbroken')
    expected = plan_for(options)
    before = inventory(options['project_root'])
    out = tmp_path / 'output'; out.mkdir()
    result = run_restore(invocation(planning(options, out), 'argv'))
    assert result.source_bytes == expected.source_bytes
    assert all(files(result, 'target')[p] == raw for p, raw in evidence.items())
    assert inventory(options['project_root']) == before


@pytest.mark.parametrize('kind', ['project_bundle', 'baseline'])
def test_new_process_and_changed_working_directory_use_only_explicit_roots(tmp_path, kind):
    options, _, _ = restore_case(tmp_path, kind)
    expected = plan_for(options)
    out = tmp_path / 'output'; out.mkdir()
    elsewhere = tmp_path / 'other'; elsewhere.mkdir()
    put(elsewhere, 'specroad.json', b'{not the selected project}')
    script = '''import json, sys
sys.path.insert(0, sys.argv[1])
from specroad.cli._restore_adapter import run_restore
result = run_restore(json.load(sys.stdin))
sys.stdout.buffer.write(result.source_bytes)
'''
    run = subprocess.run([sys.executable, '-I', '-B', '-c', script,
        str(Path(__file__).resolve().parents[1] / 'src')], cwd=elsewhere,
        input=json.dumps(invocation(planning(options, out), 'argv')).encode(),
        capture_output=True, timeout=180)
    assert run.returncode == 0, run.stderr
    assert run.stdout == expected.source_bytes == (out / 'plans/original.json').read_bytes()


@pytest.mark.parametrize('kind', ['project_bundle', 'baseline'])
@pytest.mark.parametrize('representation', ['argv', 'mapping'])
def test_execute_exact_original_files_checks_current_authority_and_native_target(tmp_path, kind, representation):
    options, _, plan, out = case(tmp_path, kind, journal=True)
    chosen = selection(plan)
    value = invocation(execution(options, plan, out, chosen=chosen), representation)
    calls = []
    host = authority(lambda request: calls.append(request) is None)
    done = run_restore(value, authority=host).data
    assert done['result'] == 'restored' and not done['recovery_required']
    assert calls and all(c['affected_journals'] == json.loads(chosen) for c in calls)
    actual = InspectionSnapshot(options['project_root'], None, include_archive_objects=True)
    assert actual.raw == files(plan, 'target')
    assert actual.model.manifest(actual.model.artifacts, descriptor('project')).sha256 == plan.data['expected_target_root']
    audit = json.loads((options['project_root'] / done['audit_path']).read_bytes())
    assert audit['authority_id'] == host.authority_id
    assert audit['request']['actor'] == {'actor_type': 'tool', 'actor_id': 'synthetic-invocation-host'}
    assert audit['request']['plan_bytes_sha256'] == plan.sha256
    assert audit['request']['request_id'] == 'invocation-test'
    assert not (options['project_root'] / '.specroad/transactions/broken').exists()
    before = inventory(tmp_path)
    calls.clear()
    # Native replay may acquire/release its exact temporary owner under the
    # shared mutex. It must not duplicate any durable publication or audit.
    replay = run_restore(value, authority=host).data
    assert replay['replayed'] and replay['result'] == 'restored' and calls
    assert inventory(tmp_path) == before
    # A stored successful decision does not authorize a fresh invocation.
    rejects(value, 7, host=authority(lambda request: False))
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('fault,code', [('missing_authority', 2), ('denied', 7), ('raising', 7),
    ('truthy', 7), ('target', 6), ('other_project', 6), ('selection_omitted', 5),
    ('bad_plan', 3), ('source_changed', 6), ('inventory_changed', 6)])
def test_initial_failures_preserve_all_real_files(tmp_path, fault, code):
    options, _, plan, out = case(tmp_path, journal=True)
    value = execution(options, plan, out, chosen=None if fault == 'selection_omitted' else selection(plan))
    host = authority()
    if fault == 'missing_authority': host = None
    elif fault == 'denied': host = authority(lambda request: False)
    elif fault == 'truthy': host = authority(lambda request: 1)
    elif fault == 'raising':
        def fail(request): raise RuntimeError('synthetic host failure')
        host = authority(fail)
    elif fault == 'target': value['--expected-target-root'] = '0' * 64
    elif fault == 'other_project': value['--project'] = str(options['source_root'])
    elif fault == 'bad_plan': put(out, 'original.json', b'{broken')
    elif fault == 'source_changed': put(options['source_root'], options['source_path'], b'changed')
    elif fault == 'inventory_changed': put(options['project_root'], 'spec/foreign', b'foreign')
    before = inventory(tmp_path)
    rejects(invocation(value, 'mapping'), code, host=host)
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('fault,code', [('wrong_kind', 3), ('bundle_override', 2),
    ('existing', 6), ('inside_project', 7), ('source_link', 7), ('project_link', 7)])
def test_plan_mode_rejects_fallbacks_overwrites_and_unsafe_roots(tmp_path, fault, code):
    options, _, _, out = case(tmp_path)
    value = planning(options, out)
    if fault == 'wrong_kind':
        value.update({'--source-kind': 'baseline', '--default-locale': 'en-GB', '--generated-path': 'output'})
    elif fault == 'bundle_override': value['--default-locale'] = 'en-GB'
    elif fault == 'existing': put(out, 'plans/original.json', b'foreign')
    elif fault == 'inside_project': value['--output-root'] = str(options['project_root'])
    else:
        link = tmp_path / 'link'
        link.symlink_to(options['source_root' if fault == 'source_link' else 'project_root'], target_is_directory=True)
        value['--source-root' if fault == 'source_link' else '--project'] = str(link)
    before = inventory(tmp_path)
    rejects(invocation(value, 'argv'), code)
    assert inventory(tmp_path) == before


def test_replaced_explicit_project_inode_is_rejected_after_passive_plan_read(tmp_path, monkeypatch):
    options, _, plan, out = case(tmp_path)
    value = execution(options, plan, out)
    original = adapter.read_restore_inputs
    def read_then_exchange(*args, **kwargs):
        read = original(*args, **kwargs)
        options['project_root'].rename(tmp_path / 'detached')
        options['project_root'].mkdir()
        put(options['project_root'], 'foreign', b'preserve')
        return read
    monkeypatch.setattr(adapter, 'read_restore_inputs', read_then_exchange)
    with pytest.raises(RestoreError) as error:
        run_restore(invocation(value, 'mapping'), authority=authority())
    assert error.value.exit_code == 7 and not error.value.mutation_possible
    assert sorted(p.name for p in options['project_root'].iterdir()) == ['foreign']
    assert (options['project_root'] / 'foreign').read_bytes() == b'preserve'
    assert not (tmp_path / 'detached/.specroad/locks/project.json').exists()


@pytest.mark.parametrize('representation', ['argv', 'mapping'])
@pytest.mark.parametrize('extent', ['partial', 'full'])
def test_original_file_invocation_resumes_real_abrupt_process_without_source(tmp_path, representation, extent):
    options, plan, chosen, changed, old = fixture(tmp_path)
    root = options['project_root']
    before = {p: (root / p).read_bytes() for p in changed}
    out = tmp_path / 'input'; out.mkdir()
    value = execution(options, plan, out, chosen=chosen)
    value['--request-id'] = 'restore-test'
    interrupted(plan, chosen, 'publish', count=1 if extent == 'partial' else len(changed))
    (options['source_root'] / options['source_path']).unlink()
    snapshot = inventory(root)
    rejects(invocation(value, representation), 5, host=authority())
    assert inventory(root) == snapshot
    with LockFiles(root) as access:
        owner = access.read_record()[0]
    value.update({'--force': True, '--expected-lock-sha256': owner.sha256,
                  '--reason': 'Synthetic explicit recovery after process exit'})
    calls = []
    done = run_restore(invocation(value, representation),
        authority=authority(lambda request: calls.append(request) is None)).data
    assert done['request']['actor'] == ACTOR
    assert done['source_observation']['status'] == 'unavailable_or_changed'
    takeovers = [c for c in calls if c['action'] == 'takeover']
    assert takeovers and all(c['actor']['actor_id'] == 'synthetic-invocation-host' for c in takeovers)
    if extent == 'full':
        assert done['result'] == 'restored' and not done['recovery_required']
        assert all((root / p).read_bytes() == raw for p, raw in files(plan, 'target').items())
        assert not (root / old).exists()
    else:
        assert done['result'] == 'rolled_back' and done['recovery_required']
        assert {p: (root / p).read_bytes() for p in changed} == before
        assert (root / old / 'journal.json').read_bytes() == b'{damaged'
        assert observe_operational_preflight(ProjectBoundary(root))['recovery_required']
    assert (out / 'original.json').read_bytes() == plan.source_bytes
    assert (out / 'selected.json').read_bytes() == chosen
