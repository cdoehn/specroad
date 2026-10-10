"""Native hard exits, closed replay evidence and preservation of foreign state."""
from contextlib import contextmanager
from hashlib import sha256
import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from specroad.authoring import _bootstrap_io as bootstrap
from specroad.authoring import initialization
from specroad.cli.application import dispatch_result, execute_request
from specroad.model.canonical import canonical_json_bytes
from support.command_parity import process_environment, run_python
from support.read_only import inventory, no_write_attempts
from test_project_initialization import check_project, EXPECTED_DIRECTORIES


CRASH_BODY = '''
import os, sys
sys.path.insert(0, sys.argv[1])
from specroad.authoring import _bootstrap_io as io
from specroad.authoring.initialization import initialize_project
target, cut = sys.argv[2:]
prepare, move, native, finish = io.BootstrapTree.prepare, io.rename_new, io._rename_native, io.BootstrapTree.retain_completed
def prepared(self, *args):
    prepare(self, *args)
    if cut == 'prepared': os._exit(73)
def moved(function, source_fd, source, target_fd, destination):
    move(function, source_fd, source, target_fd, destination)
    if cut == destination: os._exit(73)
def native_moved(function, source_fd, source, target_fd, destination):
    native(function, source_fd, source, target_fd, destination)
    if cut == 'receipt-move' and source == io.STAGING: os._exit(73)
def finished(self):
    finish(self)
    if cut == 'complete': os._exit(73)
io.BootstrapTree.prepare, io.rename_new = prepared, moved
io._rename_native, io.BootstrapTree.retain_completed = native_moved, finished
initialize_project(target)
raise AssertionError('fault boundary was not reached')
'''


def interrupt(root, cut='prepared'):
    repository = Path(__file__).resolve().parents[1]
    result = run_python(CRASH_BODY, [str(repository / 'src'), str(root), cut],
                        cwd=root.parent, environment=process_environment())
    assert result.returncode == 73, (result.stdout, result.stderr)
    stage = root / bootstrap.STAGING
    receipt = root.joinpath(*bootstrap.COMPLETED)
    record = stage / 'journal.json' if stage.exists() else receipt / 'journal.json'
    return record, json.loads(record.read_bytes())


def preserved(root):
    return (inventory(root), tuple((str(p.relative_to(root)), p.lstat().st_dev,
            p.lstat().st_ino, p.lstat().st_nlink) for p in [root, *sorted(root.rglob('*'))]))


@contextmanager
def no_bootstrap_writes():
    with no_write_attempts(), patch.object(bootstrap, '_rename_native',
            side_effect=AssertionError('unexpected native mutation')) as native:
        yield
    native.assert_not_called()


@pytest.mark.parametrize('cut', ['prepared', '.specroad', 'archive', 'attachments',
    'generated', 'mappings', 'profiles', 'rules', 'spec', 'specroad.json', 'receipt-move', 'complete'])
@pytest.mark.parametrize('kind', ['missing', 'repository'])
def test_fresh_process_replays_each_real_publication_boundary(tmp_path, monkeypatch, cut, kind):
    root = tmp_path / 'project'
    if kind == 'repository':
        root.mkdir(); (root / '.git').mkdir(); (root / '.git/config').write_bytes(b'foreign git bytes')
        (root / 'README').write_bytes(b'foreign repository bytes')
    foreign = {p: (p.read_bytes(), p.stat().st_ino, p.stat().st_mode)
               for p in root.rglob('*') if p.is_file()} if root.exists() else {}
    record, journal = interrupt(root, cut)
    original = record.read_bytes()
    # A replay must use the stored identities, not fresh entropy or timestamps.
    monkeypatch.setattr(initialization, 'initial_content', lambda *a: pytest.fail('reallocated bootstrap'))
    result = execute_request({'command_id': 'init', 'arguments': {'path': str(root)}}, cwd=tmp_path).result
    payload = check_project(root, result)
    for item in payload['files']:
        expected = journal['entries'][item['path']]
        assert item['sha256'] == expected['sha256'] and item['size'] == expected['size']
        assert (root / item['path']).stat().st_ino == expected['identity'][1]
    receipt = root.joinpath(*bootstrap.COMPLETED)
    assert (receipt / 'journal.json').read_bytes() == original
    assert receipt.stat().st_ino == journal['stage_identity'][1]
    assert all((p.read_bytes(), p.stat().st_ino, p.stat().st_mode) == state for p, state in foreign.items())
    before = preserved(root)
    with no_bootstrap_writes(): repeated = dispatch_result(['init', str(root)])
    assert repeated.exit_code == 0 and repeated.as_dict()['result'] == payload
    assert preserved(root) == before


@pytest.mark.parametrize('cut', ['prepared', 'cache', 'transactions', 'objects', 'core.json',
                                 'language-data', 'documents', 'specroad.json', 'receipt-move'])
def test_replay_retains_all_reused_empty_directory_inodes(tmp_path, cut):
    root = tmp_path / 'project'; root.mkdir()
    names = {p for p in EXPECTED_DIRECTORIES if '/' not in p}
    for name in names: (root / name).mkdir(mode=0o750)
    original = {name: ((root / name).stat().st_ino, (root / name).stat().st_mode) for name in names}
    interrupt(root, cut)
    check_project(root, dispatch_result(['init', str(root)]))
    assert {name: ((root / name).stat().st_ino, (root / name).stat().st_mode) for name in names} == original


@pytest.mark.parametrize('damage', ['unknown-field', 'version', 'state', 'root-inode',
    'stage-inode', 'boolean-inode', 'duplicate-inode', 'unknown-path', 'missing-path',
    'traversal', 'wrong-units', 'duplicate-unit', 'unknown-reused', 'executable',
    'oversized-payload', 'noncanonical', 'duplicate-key', 'oversized-journal', 'invalid-json'])
def test_invalid_journal_never_authorizes_writes(tmp_path, damage):
    root = tmp_path / 'project'; record, value = interrupt(root)
    entries = value['entries']; config = entries['specroad.json']
    if damage == 'unknown-field': value['execute'] = 'must never execute'
    elif damage == 'version': value['format'] = 'specroad-bootstrap-v2'
    elif damage == 'state': value['state'] = 'complete'
    elif damage == 'root-inode': value['root_identity'][1] += 1
    elif damage == 'stage-inode': value['stage_identity'][1] += 1
    elif damage == 'boolean-inode': config['identity'][0] = True
    elif damage == 'duplicate-inode': config['identity'] = entries['profiles/core.json']['identity']
    elif damage == 'unknown-path': entries['foreign'] = dict(config)
    elif damage == 'missing-path': entries.pop('rules')
    elif damage == 'traversal': entries['../foreign'] = dict(config)
    elif damage == 'wrong-units': value['units'].reverse()
    elif damage == 'duplicate-unit': value['units'].append('specroad.json')
    elif damage == 'unknown-reused': value['reused_directories']['foreign'] = dict(entries['rules'])
    elif damage == 'executable': config['mode'] = 0o755
    elif damage == 'oversized-payload': config['size'] = 1000000000
    raw = canonical_json_bytes(value)
    if damage == 'noncanonical': raw += b'\n'
    elif damage == 'duplicate-key': raw = b'{"state":"prepared",' + raw[1:]
    elif damage == 'oversized-journal': raw = b' ' * 262145
    elif damage == 'invalid-json': raw = b'{broken'
    record.write_bytes(raw)
    before = preserved(tmp_path)
    with no_bootstrap_writes(): result = dispatch_result(['init', str(root)])
    assert result.exit_code == 6
    assert preserved(tmp_path) == before


@pytest.mark.parametrize('damage', ['bytes', 'inode', 'mode', 'hardlink', 'symlink',
    'extra-stage', 'extra-published', 'missing', 'both-locations', 'order', 'alias',
    'journal-symlink', 'journal-hardlink', 'receipt-conflict'])
def test_actual_ambiguous_or_foreign_state_is_preserved(tmp_path, damage):
    root = tmp_path / 'project'; record, value = interrupt(root, '.specroad')
    staged = root / bootstrap.STAGING
    target = staged / 'profiles/core.json'
    if damage == 'bytes': target.write_bytes(target.read_bytes() + b'\n')
    elif damage == 'inode':
        replacement = target.with_name('replacement'); replacement.write_bytes(target.read_bytes()); replacement.replace(target)
    elif damage == 'mode': target.chmod(0o600)
    elif damage == 'hardlink': os.link(target, tmp_path / 'foreign-link')
    elif damage == 'symlink':
        raw = target.read_bytes(); target.unlink(); (tmp_path / 'foreign').write_bytes(raw); target.symlink_to(tmp_path / 'foreign')
    elif damage == 'extra-stage': (staged / 'unlisted').write_bytes(b'foreign staged data')
    elif damage == 'extra-published': (root / '.specroad/foreign').write_bytes(b'foreign published data')
    elif damage == 'missing': target.unlink()
    elif damage == 'both-locations': (root / 'profiles').mkdir()
    elif damage == 'order': (staged / 'spec').rename(root / 'spec')
    elif damage == 'alias': (root / 'SPEC').mkdir()
    elif damage == 'journal-symlink':
        other = tmp_path / 'foreign-journal'; record.rename(other); record.symlink_to(other)
    elif damage == 'journal-hardlink': os.link(record, tmp_path / 'foreign-journal')
    elif damage == 'receipt-conflict': root.joinpath(*bootstrap.COMPLETED).mkdir()
    before = preserved(tmp_path)
    with no_bootstrap_writes(): result = dispatch_result(['init', str(root)])
    assert result.exit_code == (7 if damage in ('symlink', 'journal-symlink') else 6)
    assert preserved(tmp_path) == before


@pytest.mark.parametrize('kind', ['configuration', 'document', 'resource'])
def test_rehashed_payload_still_must_match_native_bootstrap_contract(tmp_path, kind):
    root = tmp_path / 'project'; record, journal = interrupt(root)
    if kind == 'configuration': path = 'specroad.json'
    elif kind == 'document': path = next(p for p in journal['entries'] if p.startswith('spec/documents/') and p.endswith('.json'))
    else: path = 'profiles/core.json'
    payload = root / bootstrap.STAGING / path
    value = json.loads(payload.read_bytes())
    if kind == 'configuration': value['project_name'] = 'different project'
    elif kind == 'document': value['document_role'] = 'supporting'
    else: value['title'] = 'unbound resource'
    raw = canonical_json_bytes(value); payload.write_bytes(raw)
    journal['entries'][path].update(size=len(raw), sha256=sha256(raw).hexdigest())
    record.write_bytes(canonical_json_bytes(journal))
    before = preserved(tmp_path)
    with no_bootstrap_writes(): result = dispatch_result(['init', str(root)])
    assert result.exit_code == 6 and preserved(tmp_path) == before


@pytest.mark.parametrize('after', [False, True])
def test_interrupted_replay_retains_actual_prefix_for_next_attempt(tmp_path, monkeypatch, after):
    root = tmp_path / 'project'; record, journal = interrupt(root, '.specroad')
    original = bootstrap.rename_new; failed = False
    def fail_once(function, source_fd, source, target_fd, destination):
        nonlocal failed
        if destination == 'profiles' and not failed:
            failed = True
            if after: original(function, source_fd, source, target_fd, destination)
            raise OSError('owned replay failure')
        return original(function, source_fd, source, target_fd, destination)
    with monkeypatch.context() as scoped:
        scoped.setattr(bootstrap, 'rename_new', fail_once)
        result = dispatch_result(['init', str(root)])
    assert failed and result.exit_code == 5
    assert result.as_dict()['summary']['bootstrap']['mutation_possible'] is True
    assert record.exists() and not (root / 'specroad.json').exists()
    payload = check_project(root, dispatch_result(['init', str(root)]))
    assert all(item['sha256'] == journal['entries'][item['path']]['sha256'] for item in payload['files'])


@pytest.mark.parametrize('after', [False, True])
def test_late_receipt_failure_retains_complete_project(tmp_path, monkeypatch, after):
    root = tmp_path / 'project'; original = bootstrap._rename_native; failed = False
    def fail_once(function, source_fd, source, target_fd, destination):
        nonlocal failed
        if source == bootstrap.STAGING and not failed:
            failed = True
            if after: original(function, source_fd, source, target_fd, destination)
            raise OSError('owned receipt failure')
        return original(function, source_fd, source, target_fd, destination)
    with monkeypatch.context() as scoped:
        scoped.setattr(bootstrap, '_rename_native', fail_once)
        result = dispatch_result(['init', str(root)])
    assert failed and result.exit_code in (5, 6)
    before = {p: p.read_bytes() for p in root.rglob('*.json') if p.name != 'journal.json'}
    check_project(root, dispatch_result(['init', str(root)]))
    assert all(p.read_bytes() == raw for p, raw in before.items())


@pytest.mark.parametrize('where', ['staged', 'published', 'reused'])
def test_rollback_does_not_remove_foreign_bytes_added_during_failure(tmp_path, monkeypatch, where):
    root = tmp_path / 'project'; root.mkdir(); (root / 'README').write_bytes(b'original foreign')
    if where == 'reused': (root / 'rules').mkdir()
    original = bootstrap.rename_new; foreign = None
    def fail(function, source_fd, source, target_fd, destination):
        nonlocal foreign
        if destination == 'profiles' and foreign is None:
            if where == 'staged': foreign = root / bootstrap.STAGING / 'foreign'
            elif where == 'published': foreign = root / '.specroad/foreign'
            else: foreign = root / 'rules/foreign'
            foreign.write_bytes(b'not bootstrap-owned')
            raise OSError('owned failure with foreign mutation')
        return original(function, source_fd, source, target_fd, destination)
    monkeypatch.setattr(bootstrap, 'rename_new', fail)
    result = dispatch_result(['init', str(root)])
    assert result.exit_code == 6 and foreign.read_bytes() == b'not bootstrap-owned'
    assert (root / 'README').read_bytes() == b'original foreign'
    assert (root / bootstrap.STAGING / 'journal.json').exists()
    assert not (root / 'specroad.json').exists()


@pytest.mark.parametrize('damage', ['project-edit', 'receipt-extra', 'receipt-link', 'missing-journal'])
def test_completed_receipt_does_not_authorize_reinitializing_changed_project(tmp_path, damage):
    root = tmp_path / 'project'; check_project(root, dispatch_result(['init', str(root)]))
    receipt = root.joinpath(*bootstrap.COMPLETED)
    if damage == 'project-edit': (root / 'rules/new-user-rule').write_bytes(b'keep user data')
    elif damage == 'receipt-extra': (receipt / 'unlisted').write_bytes(b'keep foreign evidence')
    elif damage == 'receipt-link':
        outside = tmp_path / 'receipt'; receipt.rename(outside); receipt.symlink_to(outside, target_is_directory=True)
    else: (receipt / 'journal.json').unlink()
    before = preserved(tmp_path)
    with no_bootstrap_writes(): result = dispatch_result(['init', str(root)])
    assert result.exit_code == (7 if damage == 'receipt-link' else 6)
    assert preserved(tmp_path) == before


def test_incomplete_preparation_without_record_remains_untouched(tmp_path):
    root = tmp_path / 'project'; stage = root / bootstrap.STAGING; stage.mkdir(parents=True)
    (stage / 'fragment').write_bytes(b'unknown ownership without a closed record')
    before = preserved(tmp_path)
    with no_bootstrap_writes(): result = dispatch_result(['init', str(root)])
    assert result.exit_code == 6 and preserved(tmp_path) == before
