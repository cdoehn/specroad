"""Native external Restore transport; no CLI, Work or release-success claim."""
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from specroad.changes._lock_files import LockFiles
from specroad.changes.recovery_values import RecoveryAuthority
from specroad.model.canonical import canonical_json_bytes, canonical_json_sha256
from specroad.recovery import (RestoreError, execute_restore, publish_restore_plan,
                               read_restore_inputs, verify_restore_plan)
from specroad.recovery import files as transport
from support.model import put
from support.read_only import inventory, no_write_attempts
from support.restore import restore_case, plan_for


def case(tmp_path, kind='project_bundle', *, journal=False):
    options, originals, _ = restore_case(tmp_path, kind)
    damaged = next(p for p in originals if p.startswith('spec/goals/'))
    put(options['project_root'], damaged, b'\x00broken\xff')
    if journal:
        put(options['project_root'], '.specroad/transactions/broken/journal.json', b'{broken')
    plan = plan_for(options)
    out = tmp_path / 'external'; out.mkdir()
    return options, originals, plan, out


def selection(plan):
    path = '.specroad/transactions/broken'
    rows = [r for r in plan.data['inventory']['entries']
            if r['path'] == path or r['path'].startswith(path + '/')]
    return canonical_json_bytes({'format_version': 'restore-journal-selection-v1',
        'restore_plan_sha256': plan.data['restore_plan_sha256'],
        'entries': [{'path': path, 'sha256': canonical_json_sha256(rows)}]})


@pytest.mark.parametrize('kind', ['project_bundle', 'baseline'])
def test_publish_complete_original_plan_then_read_and_execute_selected_journals(tmp_path, kind):
    options, _, plan, out = case(tmp_path, kind, journal=True)
    before = {k: inventory(options[k]) for k in ('project_root', 'source_root')}
    result = publish_restore_plan(plan.source_bytes, output_root=out, output='plans/restore.json')
    assert result.source_bytes == (out / 'plans/restore.json').read_bytes() == plan.source_bytes
    assert result.sha256 == sha256(plan.source_bytes).hexdigest()
    assert (out / 'plans/restore.json').stat().st_mode & 0o777 == 0o600
    assert (out / 'plans').stat().st_mode & 0o777 == 0o700
    assert sorted(str(p.relative_to(out)) for p in out.rglob('*')) == ['plans', 'plans/restore.json']
    assert all(inventory(options[k]) == v for k, v in before.items())
    raw = selection(plan); put(out, 'selection.json', raw)
    with no_write_attempts():
        loaded, chosen = read_restore_inputs(out, 'plans/restore.json',
            selection_root=out, selection_path='selection.json')
    assert loaded.source_bytes == plan.source_bytes and chosen == raw
    calls = []
    def authorize(request):
        calls.append(request)
        return True
    # This synthetic test host makes a fresh decision. Neither file grants it.
    done = execute_restore(loaded.source_bytes, affected_journals=chosen,
        expected_target_root=plan.data['expected_target_root'],
        authority=RecoveryAuthority('synthetic-file-host', '1', authorize),
        actor={'actor_type': 'tool', 'actor_id': 'synthetic-file-reader'}, request_id='file-test').data
    assert calls and all(c['affected_journals'] == json.loads(raw) for c in calls)
    assert done['result'] == 'restored' and not done['recovery_required']
    assert not (options['project_root'] / '.specroad/transactions/broken').exists()
    # Static file reading retains original bindings after execution changed the
    # inventory. Live preflight would incorrectly prevent this valid replay.
    with no_write_attempts():
        replay, again = read_restore_inputs(out, 'plans/restore.json',
            selection_root=out, selection_path='selection.json')
    assert replay.source_bytes == loaded.source_bytes and again == chosen


@pytest.mark.parametrize('existing', ['same', 'different', 'directory'])
def test_existing_output_is_never_overwritten(tmp_path, existing):
    _, _, plan, out = case(tmp_path)
    if existing == 'directory': (out / 'plan.json').mkdir()
    else: put(out, 'plan.json', plan.source_bytes if existing == 'same' else b'foreign')
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(RestoreError) as error:
        publish_restore_plan(plan.source_bytes, output_root=out, output='plan.json')
    assert error.value.exit_code == 6 and inventory(tmp_path) == before


@pytest.mark.parametrize('location', ['project', 'descendant', 'ancestor', 'source_project',
                                    'other_project', 'symlink', 'relative', 'missing', 'none'])
def test_output_root_restrictions_are_checked_without_writes(tmp_path, location):
    options, _, plan, out = case(tmp_path)
    roots = {'project': options['project_root'], 'ancestor': tmp_path,
             'source_project': options['source_root'], 'none': None,
             'relative': 'relative', 'missing': tmp_path / 'missing'}
    if location == 'descendant':
        roots[location] = options['project_root'] / 'generated'; roots[location].mkdir()
    elif location == 'other_project':
        put(out, 'specroad.json', b'broken project boundary'); roots[location] = out
    elif location == 'symlink':
        roots[location] = tmp_path / 'link'; roots[location].symlink_to(out, target_is_directory=True)
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(RestoreError) as error:
        publish_restore_plan(plan.source_bytes, output_root=roots[location], output='plan.json')
    assert error.value.exit_code == {'relative': 2, 'none': 2, 'missing': 5}.get(location, 7)
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('path', ['../escape', '/absolute', 'bad\\path', '.specroad/plan.json',
                               'specroad.json', 'Plan.json', 'link/plan.json', 'nested/plan.json'])
def test_unsafe_output_paths_aliases_and_nested_projects_are_rejected(tmp_path, path):
    _, _, plan, out = case(tmp_path)
    put(out, 'plan.json', b'foreign')
    (out / 'link').symlink_to(out, target_is_directory=True)
    put(out, 'nested/specroad.json', b'other project')
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(RestoreError) as error:
        publish_restore_plan(plan.source_bytes, output_root=out, output=path)
    assert error.value.exit_code == 7 and inventory(tmp_path) == before


@pytest.mark.parametrize('changed', ['source', 'inventory', 'missing_source', 'missing_root'])
def test_stale_plan_cannot_publish_even_a_private_output(tmp_path, changed):
    options, _, plan, out = case(tmp_path)
    if changed == 'source': put(options['source_root'], options['source_path'], b'changed')
    elif changed == 'inventory': put(options['project_root'], 'spec/new', b'changed')
    elif changed == 'missing_source': (options['source_root'] / options['source_path']).unlink()
    else: options['source_root'].rename(tmp_path / 'moved-origin')
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(RestoreError) as error:
        publish_restore_plan(plan.source_bytes, output_root=out, output='plan.json')
    assert error.value.exit_code == 6 and inventory(tmp_path) == before


@pytest.mark.parametrize('changed', ['source', 'inventory', 'project_inode', 'parent_inode', 'image', 'target'])
def test_recheck_between_staging_and_atomic_publication_preserves_real_state(tmp_path, monkeypatch, changed):
    options, _, plan, out = case(tmp_path)
    native = transport._write_new
    def stage(parent, name, raw):
        identity = native(parent, name, raw)
        if changed == 'source': put(options['source_root'], options['source_path'], b'changed')
        elif changed == 'inventory': put(options['project_root'], 'spec/new', b'changed')
        elif changed == 'project_inode':
            options['project_root'].rename(tmp_path / 'original-current')
            options['project_root'].mkdir()
        elif changed == 'parent_inode':
            (out / 'plans').rename(out / 'old-plans'); (out / 'plans').mkdir()
        elif changed == 'image': put(out, 'plans/' + name, b'changed')
        else: put(out, 'plans/plan.json', b'foreign arrival')
        return identity
    monkeypatch.setattr(transport, '_write_new', stage)
    with pytest.raises(RestoreError) as error:
        publish_restore_plan(plan.source_bytes, output_root=out, output='plans/plan.json')
    assert error.value.exit_code in (6, 7)
    target = out / 'plans/plan.json'
    if changed == 'target': assert target.read_bytes() == b'foreign arrival'
    else: assert not target.exists()
    assert list(out.rglob('.specroad-restore-plan-*.tmp'))


@pytest.mark.parametrize('when', ['staging', 'before_move', 'after_move'])
def test_io_failure_preserves_external_images_and_never_mutates_project(tmp_path, monkeypatch, when):
    options, _, plan, out = case(tmp_path)
    before = inventory(options['project_root'])
    native = transport.replace_bound_image
    def fail(*args, **kwargs):
        if when == 'after_move': native(*args, **kwargs)
        raise OSError('synthetic disk failure')
    monkeypatch.setattr(transport, '_write_new' if when == 'staging' else 'replace_bound_image', fail)
    with pytest.raises(RestoreError) as error:
        publish_restore_plan(plan.source_bytes, output_root=out, output='plan.json')
    assert error.value.exit_code == 5 and inventory(options['project_root']) == before
    if when == 'after_move': assert (out / 'plan.json').read_bytes() == plan.source_bytes
    else: assert not (out / 'plan.json').exists()


def test_external_mutex_conflict_does_not_acquire_a_project_writer(tmp_path):
    options, _, plan, out = case(tmp_path)
    before = inventory(tmp_path)
    with LockFiles(out) as held:
        held.acquire()
        with no_write_attempts(), pytest.raises(RestoreError) as error:
            publish_restore_plan(plan.source_bytes, output_root=out, output='plan.json')
    assert error.value.exit_code == 5 and inventory(tmp_path) == before


@pytest.mark.parametrize('point', ['staged', 'published'])
def test_real_process_exit_leaves_only_private_or_complete_external_plan(tmp_path, point):
    options, _, plan, out = case(tmp_path)
    before = inventory(options['project_root'])
    script = '''import sys, os
sys.path.insert(0, sys.argv[1])
from specroad.recovery import files
point, root = sys.argv[2:]
name = '_write_new' if point == 'staged' else 'replace_bound_image'
native = getattr(files, name)
def stop(*args, **kwargs):
    result = native(*args, **kwargs)
    os._exit(71)
setattr(files, name, stop)
files.publish_restore_plan(sys.stdin.buffer.read(), output_root=root, output='plan.json')
'''
    process = subprocess.run([sys.executable, '-I', '-B', '-c', script,
        str(Path(__file__).resolve().parents[1] / 'src'), point, str(out)],
        input=plan.source_bytes, capture_output=True, timeout=120)
    assert process.returncode == 71, process.stderr
    assert inventory(options['project_root']) == before
    if point == 'staged':
        assert not (out / 'plan.json').exists()
        assert len(list(out.glob('.specroad-restore-plan-*.tmp'))) == 1
    else:
        assert (out / 'plan.json').read_bytes() == plan.source_bytes
        assert not list(out.glob('.specroad-restore-plan-*.tmp'))


@pytest.mark.parametrize('bad', ['malformed', 'noncanonical', 'hash', 'symlink', 'hardlink', 'fifo'])
def test_untrusted_plan_files_are_rejected_without_writes(tmp_path, bad):
    _, _, plan, out = case(tmp_path)
    target = out / 'plan.json'
    if bad == 'symlink': target.symlink_to(out / 'original'); put(out, 'original', plan.source_bytes)
    elif bad == 'hardlink': put(out, 'original', plan.source_bytes); os.link(out / 'original', target)
    elif bad == 'fifo': os.mkfifo(target)
    elif bad == 'malformed': target.write_bytes(b'{broken')
    elif bad == 'noncanonical': target.write_bytes(plan.source_bytes + b'\n')
    else:
        data = plan.data; data['restore_plan_sha256'] = 'f' * 64
        target.write_bytes(canonical_json_bytes(data))
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(RestoreError) as error:
        read_restore_inputs(out, 'plan.json')
    assert error.value.exit_code == (7 if bad in ('symlink', 'hardlink', 'fifo') else 3)
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('bad', ['omitted', 'empty', 'wrong_plan', 'wrong_tree', 'unpaired', 'malformed'])
def test_selection_file_is_explicit_and_bound_to_original_plan(tmp_path, bad):
    _, _, plan, out = case(tmp_path, journal=True)
    put(out, 'plan.json', plan.source_bytes)
    raw = json.loads(selection(plan))
    if bad == 'empty': raw['entries'] = []
    elif bad == 'wrong_plan': raw['restore_plan_sha256'] = 'f' * 64
    elif bad == 'wrong_tree': raw['entries'][0]['sha256'] = 'f' * 64
    put(out, 'selected.json', b'broken' if bad == 'malformed' else canonical_json_bytes(raw))
    kwargs = {} if bad == 'omitted' else {'selection_root': out, 'selection_path': 'selected.json'}
    if bad == 'unpaired': del kwargs['selection_path']
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(RestoreError) as error:
        read_restore_inputs(out, 'plan.json', **kwargs)
    assert error.value.exit_code == {'omitted': 5, 'empty': 5, 'wrong_plan': 6,
        'wrong_tree': 6, 'unpaired': 2, 'malformed': 3}[bad]
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('changed', ['plan', 'selection', 'missing_plan'])
def test_input_files_are_reread_after_qualification(tmp_path, monkeypatch, changed):
    _, _, plan, out = case(tmp_path, journal=True)
    put(out, 'plan.json', plan.source_bytes); put(out, 'selection.json', selection(plan))
    native = transport.journal_selection
    def checked(*args):
        result = native(*args)
        if changed == 'missing_plan': (out / 'plan.json').unlink()
        else: put(out, changed + '.json', b'changed')
        return result
    monkeypatch.setattr(transport, 'journal_selection', checked)
    with pytest.raises(RestoreError) as error:
        read_restore_inputs(out, 'plan.json', selection_root=out, selection_path='selection.json')
    assert error.value.exit_code == 6


def test_reading_original_plan_does_not_forge_live_freshness_or_authority(tmp_path):
    options, _, plan, out = case(tmp_path)
    put(out, 'plan.json', plan.source_bytes)
    (options['source_root'] / options['source_path']).unlink()
    before = inventory(tmp_path)
    with no_write_attempts():
        loaded, selected = read_restore_inputs(out, 'plan.json')
        assert loaded.source_bytes == plan.source_bytes and selected is None
        with pytest.raises(RestoreError) as error:
            verify_restore_plan(loaded.source_bytes)
        assert error.value.exit_code == 6
        with pytest.raises(RestoreError) as error:
            execute_restore(loaded.source_bytes, expected_target_root=plan.data['expected_target_root'],
                actor={'actor_type': 'tool', 'actor_id': 'synthetic-file-reader'}, authority=None)
        assert error.value.exit_code == 2
    assert inventory(tmp_path) == before
