"""Complete admitted H.3 matrix and fail-closed source/absence boundaries."""
from hashlib import sha256
import errno
import json
import os
from types import SimpleNamespace
import zlib

import pytest

from specroad.model.errors import ModelError
from specroad.query.git_source import GitObjectSource
from specroad.query import _git_reader
from specroad.security import ProjectBoundary, SafetyViolation
from specroad.security.resource_access import opened_resource
from specroad.verification import assess_code_reference, read_code_reference
from support.git_objects import GitFixture
from support.model import put
from support.portable import build_distribution
from support.processes import run_core, run_python
from support.read_only import inventory, no_write_attempts
from test_code_reference_sources import PATH, reference
from test_code_reference_sources_right import Sha256GitFixture
from test_code_line_selection import line_reference
from test_code_relocation import anchored_reference


def selection_record(mode, raw, selected, *, matching=True, start=1, count=1, **fields):
    fields['file_sha256'] = sha256(raw).hexdigest() if matching else '0' * 64
    if mode == 'line_range':
        return line_reference(raw, selected, start=start, end=start + count - 1, **fields)
    return anchored_reference(raw, selected, mode=mode,
        start=start - 1 if mode == 'bytes' else start,
        count=len(selected) if mode == 'bytes' else count, **fields)


def native_source(root, kind, raw):
    if kind == 'file':
        put(root, PATH, raw)
        return ProjectBoundary(root), None
    fixture = (GitFixture if kind == 'sha1' else Sha256GitFixture)(root / 'repo')
    commit = fixture.commit({PATH: raw})
    put(fixture.root, PATH, b'not the selected Git source')
    return GitObjectSource(fixture.root, commit), fixture


@pytest.mark.parametrize('source_kind', ['file', 'sha1', 'sha256'])
@pytest.mark.parametrize('matching', [True, False])
@pytest.mark.parametrize('mode', ['line_range', 'text', 'bytes'])
@pytest.mark.parametrize('raw,selected,state,reason', [
    (b'A\nA\n', b'A\n', 'current', None),
    (b'x\nA\n', b'A\n', 'relocated', None),
    (b'x\n', b'A\n', 'stale', 'selection_missing'),
    (b'x\nA\nA\n', b'A\n', 'stale', 'selection_ambiguous'),
], ids=['stored-wins', 'unique-other', 'no-other', 'multiple-others'])
def test_selection_matrix_keeps_state_independent_of_whole_file_hash(
        tmp_path, source_kind, matching, mode, raw, selected, state, reason):
    source, repo = native_source(tmp_path, source_kind, raw)
    fields = {} if repo is None else {'git_commit': source.commit_id}
    record = selection_record(mode, raw, selected, matching=matching, **fields)
    original, before = record.source_bytes, inventory(tmp_path)
    data = assess_code_reference(source, record).data
    assert (data['state'], data['reason']) == (state, reason)
    assert data['target_present'] and data['source']['file_hash_matches'] is matching
    assert data['selection_location']['source'] == data['source']
    assert data['diagnostics'] == (['file_changed_outside_selection'] if state == 'current' and not matching else [])
    if state == 'relocated':
        assert data['new_position'] == ({'start_byte': 2, 'byte_count': len(selected)} if mode == 'bytes'
                                        else {'start_line': 2, 'end_line': 2})
    else:
        assert data['new_position'] is None
    if state == 'stale':
        located = data['selection_location']
        assert located['match_count'] == (0 if reason == 'selection_missing' else 2)
        assert located['selection_sha256'] is located['matched_position'] is None
    assert data['write_authorized'] is False and record.source_bytes == original
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('source_kind', ['file', 'sha1', 'sha256'])
@pytest.mark.parametrize('matching', [True, False])
def test_file_matrix_hashes_binary_data_without_selection_or_decoding(tmp_path, source_kind, matching):
    raw = b'\xff\x00\r\n'
    source, repo = native_source(tmp_path, source_kind, raw)
    fields = {} if repo is None else {'git_commit': source.commit_id}
    record = reference(file_sha256=sha256(raw).hexdigest() if matching else '0' * 64, **fields)
    before = inventory(tmp_path)
    data = assess_code_reference(source, record).data
    assert (data['state'], data['reason']) == (('current', None) if matching else ('stale', 'file_changed'))
    assert data['source']['file_sha256'] == sha256(raw).hexdigest()
    assert data['selection_evaluated'] is False and data['selection_location'] is None
    assert inventory(tmp_path) == before


def object_path(repo, oid):
    return repo.git / 'objects' / oid[:2] / oid[2:]


def path_objects(repo, source):
    # Decode the owned fixture's immutable commit, not a source under test.
    raw = zlib.decompress(object_path(repo, source.commit_id).read_bytes()).split(b'\0', 1)[1]
    return {'commit': source.commit_id, 'root_tree': raw.split(b'\n', 1)[0][5:].decode(),
            'parent_tree': source._entries['src'][2], 'blob': source._entries[PATH][2]}


@pytest.mark.parametrize('source_kind', ['sha1', 'sha256'])
@pytest.mark.parametrize('missing', ['commit', 'root_tree', 'parent_tree', 'blob'])
@pytest.mark.parametrize('kind', ['file', 'line_range', 'text_anchor', 'symbol_hint', 'generated_artifact'])
def test_missing_bound_objects_take_first_h3_row_without_source_hash_or_fallback(tmp_path, source_kind, missing, kind):
    source, repo = native_source(tmp_path, source_kind, b'A\n')
    objects = path_objects(repo, source)
    object_path(repo, objects[missing]).unlink()
    # Selector/hint evaluation must not run when the object is absent.
    record = reference(kind, git_commit=source.commit_id, git_blob=objects['blob'])
    before = inventory(tmp_path)
    data = assess_code_reference(source, record).data
    assert (data['state'], data['reason']) == ('missing', 'target_missing')
    assert data['source_kind'] == 'git' and data['git_commit'] == source.commit_id
    assert data['target_present'] is False and data['source'] is data['source_sha256'] is None
    assert data['selection_location'] is data['selection_location_sha256'] is None
    assert data['selection_evaluated'] is False and data['new_position'] is None
    assert data['reference'] == record.data and inventory(tmp_path) == before


@pytest.mark.parametrize('target', ['commit', 'root_tree', 'parent_tree', 'blob'])
@pytest.mark.parametrize('corruption', ['malformed', 'wrong_content', 'wrong_type'])
def test_corruption_cannot_masquerade_as_missing_git_objects(tmp_path, target, corruption):
    source, repo = native_source(tmp_path, 'sha1', b'A\n')
    path = object_path(repo, path_objects(repo, source)[target])
    if corruption == 'malformed':
        path.write_bytes(b'not a zlib object')
    else:
        kind = ('blob' if target != 'blob' else 'tree') if corruption == 'wrong_type' else (
            'commit' if target == 'commit' else 'blob' if target == 'blob' else 'tree')
        path.write_bytes(zlib.compress(kind.encode() + b' 6\0forged'))
    before = inventory(tmp_path)
    with pytest.raises(ModelError) as caught:
        assess_code_reference(source, reference())
    assert caught.value.reason in {'git_object_read_failed', 'git_object_response_invalid', 'git_object_identity_mismatch'}
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('parent_kind', ['symlink', 'gitlink', 'file', 'nested'])
def test_missing_git_children_cannot_hide_unsafe_parents(tmp_path, parent_kind):
    repo = GitFixture(tmp_path / 'repo')
    content = {'symlink': {'src': ('120000', b'../outside')},
               'gitlink': {'src': ('160000', 'a' * 40)},
               'file': {'src': b'ordinary file'},
               'nested': {'src/specroad.json': b'{}'}}[parent_kind]
    source = GitObjectSource(repo.root, repo.commit(content))
    before = inventory(tmp_path)
    with pytest.raises(SafetyViolation):
        assess_code_reference(source, reference())
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('field', ['git_commit', 'git_blob'])
def test_present_git_binding_mismatch_is_not_a_state(tmp_path, field):
    source, repo = native_source(tmp_path, 'sha1', b'A\n')
    before = inventory(tmp_path)
    with pytest.raises(ModelError) as caught:
        assess_code_reference(source, reference(**{field: 'a' * 40}))
    assert caught.value.reason == 'code_reference_' + field + '_mismatch'
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('reply', ['empty', 'truncated', 'extra_reply', 'wrong_id', 'wrong_size', 'wrong_type', 'ambiguous'])
def test_batch_machine_protocol_requires_one_exact_well_formed_reply(tmp_path, monkeypatch, reply):
    source, repo = native_source(tmp_path, 'sha1', b'A\n')
    oid = source.commit_id.encode()
    outputs = {'empty': b'', 'truncated': oid + b' missing',
        'extra_reply': oid + b' missing\n' + oid + b' missing\n',
        'wrong_id': b'0' * 40 + b' missing\n', 'wrong_size': oid + b' commit 999\nx\n',
        'wrong_type': oid + b' blob 1\nx\n', 'ambiguous': oid + b' ambiguous\n'}
    monkeypatch.setattr(_git_reader.subprocess, 'run', lambda *a, **kw:
        SimpleNamespace(stdout=outputs[reply], stderr=b'', returncode=0))
    with pytest.raises(ModelError) as caught:
        assess_code_reference(source, reference())
    assert caught.value.reason == 'git_object_response_invalid'


@pytest.mark.parametrize('failure', ['nonzero', 'stderr', 'io', 'interrupt'])
def test_process_or_resource_failure_is_never_a_missing_observation(tmp_path, monkeypatch, failure):
    source, repo = native_source(tmp_path, 'sha1', b'A\n')
    before = inventory(tmp_path)
    def fail(*args, **kwargs):
        if failure == 'io': raise PermissionError(errno.EACCES, 'owned denied execution')
        if failure == 'interrupt': raise KeyboardInterrupt()
        return SimpleNamespace(stdout=source.commit_id.encode() + b' missing\n',
            stderr=b'owned failure' if failure == 'stderr' else b'',
            returncode=3 if failure == 'nonzero' else 0)
    monkeypatch.setattr(_git_reader.subprocess, 'run', fail)
    expected = OSError if failure == 'io' else KeyboardInterrupt if failure == 'interrupt' else ModelError
    with pytest.raises(expected): assess_code_reference(source, reference())
    assert inventory(tmp_path) == before


def test_original_reader_still_errors_on_missing_blob_and_no_fetch_is_attempted(tmp_path):
    source, repo = native_source(tmp_path, 'sha1', b'A\n')
    marker = tmp_path / 'external-execution'
    helper = tmp_path / 'helper'
    helper.write_text('#!/bin/sh\ntouch "' + str(marker) + '"\n'); helper.chmod(0o700)
    with (repo.git / 'config').open('a') as stream:
        stream.write('\n[remote "origin"]\nurl = ext::' + str(helper) + '\npromisor = true\n'
                     '[protocol "ext"]\nallow = always\n[core]\nfsmonitor = ' + str(helper) + '\n')
    object_path(repo, path_objects(repo, source)['blob']).unlink()
    before = inventory(tmp_path)
    with pytest.raises(ModelError) as caught:
        read_code_reference(source, reference())
    assert caught.value.reason == 'git_object_read_failed'
    assert assess_code_reference(source, reference()).data['state'] == 'missing'
    assert not marker.exists() and inventory(tmp_path) == before


@pytest.mark.parametrize('shape', ['empty', 'truncated', 'overlap', 'unicode', 'no_final_lf'])
@pytest.mark.parametrize('mode', ['line_range', 'text'])
def test_text_extent_and_normalization_preserve_distinct_stale_reasons(tmp_path, shape, mode):
    raw, selected, start, count, reason = {
        'empty': (b'', b'', 1, 1, 'selection_missing'),
        'truncated': (b'A\n', b'A\n', 1, 2, 'selection_missing'),
        'overlap': (b'x\nA\nA\nA\n', b'A\nA\n', 1, 2, 'selection_ambiguous'),
        'unicode': ('x\ne\u0301\n'.encode(), 'é\n'.encode(), 1, 1, 'selection_missing'),
        'no_final_lf': (b'x\nA', b'A\n', 1, 1, 'selection_missing')}[shape]
    source, _ = native_source(tmp_path, 'file', raw)
    record = selection_record(mode, raw, selected, start=start, count=count)
    before = inventory(tmp_path)
    with no_write_attempts(): data = assess_code_reference(source, record).data
    assert (data['state'], data['reason']) == ('stale', reason)
    assert data['new_position'] is None and inventory(tmp_path) == before


def test_overlapping_byte_hits_are_ambiguous_without_normalization(tmp_path):
    source, _ = native_source(tmp_path, 'file', b'xAAAA')
    record = anchored_reference(b'xAAAA', b'AA', mode='bytes', start=0, count=2)
    data = assess_code_reference(source, record).data
    assert (data['state'], data['reason']) == ('stale', 'selection_ambiguous')
    assert data['selection_location']['match_count'] == 3 and data['new_position'] is None


def test_file_disappearing_between_stat_and_open_is_not_missing(tmp_path, monkeypatch):
    target = put(tmp_path, PATH, b'A\n')
    source = ProjectBoundary(tmp_path); original = os.open
    def opening(path, *args, **kwargs):
        if path == 'owned.data' and kwargs.get('dir_fd') is not None:
            target.unlink()
        return original(path, *args, **kwargs)
    monkeypatch.setattr(os, 'open', opening)
    with pytest.raises(FileNotFoundError): assess_code_reference(source, reference())
    assert not target.exists()


def test_missing_project_root_does_not_mean_missing_code_target(tmp_path):
    root = tmp_path / 'root'; root.mkdir()
    source = ProjectBoundary(root); root.rename(tmp_path / 'saved')
    before = inventory(tmp_path)
    with pytest.raises(FileNotFoundError): assess_code_reference(source, reference())
    assert inventory(tmp_path) == before


def test_user_body_file_not_found_remains_an_error_in_optional_guard(tmp_path):
    boundary = ProjectBoundary(tmp_path)
    error = FileNotFoundError('owned body failure')
    with pytest.raises(FileNotFoundError) as caught:
        with opened_resource(boundary, PATH, missing_ok=True): raise error
    assert caught.value is error


@pytest.mark.parametrize('mode', ['core', 'pyz'])
@pytest.mark.parametrize('absent', [False, True])
def test_native_git_status_runs_in_fresh_core_without_execution_or_fetch(tmp_path, mode, absent):
    source, repo = native_source(tmp_path, 'sha1', b'x\nA\n')
    record = line_reference(b'old', b'A\n', git_commit=source.commit_id)
    if absent: object_path(repo, path_objects(repo, source)['blob']).unlink()
    body = '''import json,os,stat,sys
class OnlyCoreAndStdlib:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] not in sys.stdlib_module_names | {'specroad'}:
            raise AssertionError('third-party import: '+fullname)
sys.meta_path.insert(0, OnlyCoreAndStdlib())
from specroad.verification import assess_code_reference
from specroad.query.git_source import GitObjectSource
from specroad.storage.record_artifact import RecordArtifact
'''
    body += 'source=GitObjectSource(' + repr(str(repo.root)) + ',' + repr(source.commit_id) + ')\n'
    body += 'record=RecordArtifact(' + repr(record.source_bytes) + ')\n'
    body += '''def guard(event,args):
    if event == 'subprocess.Popen':
        executable,argv,cwd,env=args
        assert executable == source._executable
        assert '--no-lazy-fetch' in argv and '--no-optional-locks' in argv
        assert '--git-dir='+str(source.root / '.git') in argv
        assert 'cat-file' in argv and env['GIT_NO_LAZY_FETCH']=='1'
        assert env['GIT_ALLOW_PROTOCOL']=='' and 'protocol.allow=never' in argv
    elif event in {'os.system','socket.__new__','socket.connect','os.mkdir','os.remove','os.rename'}:
        raise AssertionError('prohibited effect: '+event)
    if event == 'open':
        path,mode,flags=args
        if (isinstance(mode,str) and any(c in mode for c in 'wax+')) or (
            isinstance(flags,int) and flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND)):
            # subprocess wraps its anonymous stdin pipe in a writable stream
            # to send the exact object ID, and opens the null device O_RDWR
            # for DEVNULL on ordinary reads. Neither changes stored files.
            if isinstance(path,int) and stat.S_ISFIFO(os.fstat(path).st_mode):
                return
            if (path == os.devnull and stat.S_ISCHR(os.stat(path).st_mode)
                    and isinstance(flags,int) and not flags & (os.O_CREAT|os.O_TRUNC|os.O_APPEND)):
                return
            raise AssertionError('write attempted')
sys.addaudithook(guard)
try:
    open(source.root / 'forbidden-write', 'wb')
except AssertionError:
    pass
else:
    raise AssertionError('filesystem write guard is inactive')
print(json.dumps(assess_code_reference(source,record).data))
'''
    before = repo.capture()
    if mode == 'core': completed = run_core(body, tmp_path, capture=True)
    else:
        _, package = build_distribution(tmp_path / 'distribution')
        completed = run_python(['-I', '-S', '-B', '-c', 'import sys;sys.path.insert(0,' + repr(str(package)) + ')\n' + body], tmp_path, capture=True)
    assert completed.returncode == 0, completed.stderr
    data = json.loads(completed.stdout)
    assert data == assess_code_reference(source, record).data
    assert data['state'] == ('missing' if absent else 'relocated')
    assert repo.capture() == before
