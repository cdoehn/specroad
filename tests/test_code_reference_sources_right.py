"""Adversarial code sources remain passive, bounded reads with no fallback."""
from hashlib import sha256
import errno
import json
import os
import stat
from types import SimpleNamespace
import zlib

import pytest

from specroad.model.errors import ModelError
from specroad.query.git_source import GitObjectSource
from specroad.security import ProjectBoundary, SafetyViolation
from specroad.security import paths as path_guards
from specroad.storage.attachments import fingerprint_file
from specroad.verification import read_code_reference
from support.git_objects import GitFixture
from support.model import put
from support.portable import build_distribution
from support.processes import run_core, run_python
from support.read_only import inventory, no_write_attempts
from test_code_reference_sources import RAW, PATH, KINDS, reference, repository


def after_read(monkeypatch, change):
    """Inject an actual owned-file change after a real descriptor read."""
    original = os.fdopen
    class ChangedStream:
        def __init__(self, *args, **kwargs):
            self.stream = original(*args, **kwargs)
        def __enter__(self):
            return self
        def __exit__(self, *args):
            self.stream.close()
        def fileno(self):
            return self.stream.fileno()
        def read(self):
            raw = self.stream.read()
            change()
            return raw
    monkeypatch.setattr(os, 'fdopen', ChangedStream)


@pytest.mark.parametrize('parent', ['src', 'src/nested'])
def test_new_nested_root_during_read_invalidates_code_and_attachment_binding(tmp_path, monkeypatch, parent):
    target = put(tmp_path, 'src/nested/owned.data', RAW)
    boundary = ProjectBoundary(tmp_path)
    marker = tmp_path / parent / 'specroad.json'
    after_read(monkeypatch, lambda: marker.write_bytes(b'{}'))
    with pytest.raises(SafetyViolation):
        read_code_reference(boundary, reference(path='src/nested/owned.data'))
    assert marker.read_bytes() == b'{}' and target.read_bytes() == RAW
    with pytest.raises(SafetyViolation):
        fingerprint_file(boundary, 'src/nested/owned.data')


@pytest.mark.parametrize('change', ['grow', 'replace_leaf', 'link_leaf', 'link_parent', 'replace_root'])
def test_source_changes_during_read_yield_no_hash_and_preserve_actual_state(tmp_path, monkeypatch, change):
    root = tmp_path / 'project'; root.mkdir()
    target = put(root, PATH, RAW)
    outside = tmp_path / 'outside'; outside.mkdir()
    put(outside, 'owned.data', b'FOREIGN')
    boundary = ProjectBoundary(root)
    changed = []
    def alter():
        changed.append(change)
        if change == 'grow':
            target.write_bytes(RAW + b'changed')
        elif change in ('replace_leaf', 'link_leaf'):
            target.rename(target.with_name('saved'))
            if change == 'replace_leaf':
                target.write_bytes(b'replacement')
            else:
                target.symlink_to(outside / 'owned.data')
        elif change == 'link_parent':
            (root / 'src').rename(root / 'saved')
            (root / 'src').symlink_to(outside, target_is_directory=True)
        else:
            root.rename(tmp_path / 'saved-root')
            root.mkdir()
        changed.append(inventory(tmp_path))
    after_read(monkeypatch, alter)
    with pytest.raises(SafetyViolation):
        read_code_reference(boundary, reference())
    assert changed[0] == change and inventory(tmp_path) == changed[1]
    assert (outside / 'owned.data').read_bytes() == b'FOREIGN'


@pytest.mark.parametrize('component', ['src', 'owned.data'])
def test_link_swap_between_check_and_open_never_reads_the_foreign_target(tmp_path, monkeypatch, component):
    root = tmp_path / 'project'; root.mkdir()
    target = put(root, PATH, RAW)
    outside = tmp_path / 'outside'; outside.mkdir()
    put(outside, 'owned.data', b'FOREIGN')
    source = ProjectBoundary(root)
    original = os.open; changed = []
    def opening(path, *args, **kwargs):
        if path == component and not changed:
            if component == 'src':
                (root / 'src').rename(root / 'saved')
                (root / 'src').symlink_to(outside, target_is_directory=True)
            else:
                target.rename(target.with_name('saved'))
                target.symlink_to(outside / 'owned.data')
            changed.append(True)
        return original(path, *args, **kwargs)
    monkeypatch.setattr(os, 'open', opening)
    with pytest.raises(SafetyViolation):
        read_code_reference(source, reference())
    assert changed and (outside / 'owned.data').read_bytes() == b'FOREIGN'
    saved = root / 'saved/owned.data' if component == 'src' else root / 'src/saved'
    assert saved.read_bytes() == RAW


@pytest.mark.parametrize('link_kind', ['internal', 'dangling', 'loop'])
def test_all_link_kinds_are_rejected_consistently_with_attachments(tmp_path, link_kind):
    target = put(tmp_path, PATH, RAW)
    link = tmp_path / 'link'
    link.symlink_to(target if link_kind == 'internal' else tmp_path / ('absent' if link_kind == 'dangling' else 'link'))
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(SafetyViolation):
        read_code_reference(ProjectBoundary(tmp_path), reference(path='link'))
    with no_write_attempts(), pytest.raises(SafetyViolation):
        fingerprint_file(ProjectBoundary(tmp_path), 'link')
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('special', ['directory', 'fifo', 'socket'])
def test_special_files_are_rejected_before_reading_or_blocking(tmp_path, monkeypatch, special):
    target = tmp_path / 'special'
    if special == 'directory':
        target.mkdir()
    elif special == 'fifo':
        os.mkfifo(target)
    else:
        # Labelled OS-metadata injection: binding a real socket is unavailable
        # in restricted runners. This case proves rejection before leaf open,
        # not successful creation or access to a real socket.
        target.write_bytes(RAW)
        native_stat, native_open = os.stat, os.open
        def socket_metadata(path, *args, **kwargs):
            if path == 'special' and kwargs.get('dir_fd') is not None:
                return SimpleNamespace(st_mode=stat.S_IFSOCK | 0o600)
            return native_stat(path, *args, **kwargs)
        def forbid_leaf(path, *args, **kwargs):
            if path == 'special':
                raise AssertionError('special entry opened before rejection')
            return native_open(path, *args, **kwargs)
        monkeypatch.setattr(os, 'stat', socket_metadata)
        monkeypatch.setattr(os, 'open', forbid_leaf)
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(SafetyViolation):
        read_code_reference(ProjectBoundary(tmp_path), reference(path='special'))
    assert inventory(tmp_path) == before


def test_missing_descriptor_safety_does_not_use_a_path_only_fallback(tmp_path, monkeypatch):
    put(tmp_path, PATH, RAW); source = ProjectBoundary(tmp_path)
    before = inventory(tmp_path)
    monkeypatch.setattr(path_guards, '_HAS_SAFE_OPEN', False)
    def forbidden(*args, **kwargs):
        raise AssertionError('unsafe fallback open')
    monkeypatch.setattr(os, 'open', forbidden)
    with pytest.raises(OSError) as caught:
        read_code_reference(source, reference())
    assert caught.value.errno == errno.ENOTSUP and inventory(tmp_path) == before


@pytest.mark.parametrize('failure', ['io', 'memory', 'interrupt'])
def test_failure_after_real_read_closes_descriptors_without_retry_or_partial_success(tmp_path, monkeypatch, failure):
    put(tmp_path, PATH, RAW); before = inventory(tmp_path)
    opened = []; reads = []
    original = os.open
    def opening(*args, **kwargs):
        descriptor = original(*args, **kwargs); opened.append(descriptor); return descriptor
    monkeypatch.setattr(os, 'open', opening)
    error = {'io': OSError(errno.EIO, 'owned injected failure'),
             'memory': MemoryError(), 'interrupt': KeyboardInterrupt()}[failure]
    def fail():
        reads.append(True)
        raise error
    after_read(monkeypatch, fail)
    with pytest.raises(type(error)) as caught:
        read_code_reference(ProjectBoundary(tmp_path), reference())
    assert caught.value is error and reads == [True]
    assert inventory(tmp_path) == before and opened
    for descriptor in opened:
        with pytest.raises(OSError) as closed:
            os.fstat(descriptor)
        assert closed.value.errno == errno.EBADF


@pytest.mark.parametrize('bad_path', ['../secret', '/secret', 'C:/secret', '\\\\server\\share',
    'src/../../secret', 'src\\secret', 'src/.git/config', 'src/.PATCHHARBOR/config.json',
    'src/CON', 'src/file:stream', 'src/x\x00y', 'src/x\ud800y'])
def test_revalidated_record_rejects_unsafe_paths_before_any_open(tmp_path, monkeypatch, bad_path):
    record = reference(); value = record.data; value['path'] = bad_path
    # Even a trusted caller forcibly replacing the otherwise frozen raw input
    # cannot bypass the ordinary stored-record validator.
    object.__setattr__(record, 'source_bytes', json.dumps(value, ensure_ascii=True).encode())
    source = ProjectBoundary(tmp_path)
    def forbidden(*args, **kwargs):
        raise AssertionError('invalid record accessed a source')
    monkeypatch.setattr(os, 'open', forbidden)
    with pytest.raises(ModelError):
        read_code_reference(source, record)


def test_native_looking_callback_subclass_does_not_gain_read_authority(tmp_path):
    class ForeignBoundary(ProjectBoundary):
        def read_bytes(self, path):
            raise AssertionError('foreign reader invoked')
    source = ForeignBoundary(tmp_path)
    with pytest.raises(ModelError) as caught:
        read_code_reference(source, reference())
    assert caught.value.reason == 'code_reference_source_required'


@pytest.mark.parametrize('kind', ['symbol_hint', 'text_anchor', 'line_range'])
@pytest.mark.parametrize('matching', [False, True])
def test_hints_and_selectors_never_become_currency_even_with_matching_file_bytes(tmp_path, kind, matching):
    put(tmp_path, PATH, RAW)
    fields = {'file_sha256': sha256(RAW).hexdigest() if matching else '0' * 64}
    if kind == 'symbol_hint': fields['symbol_hint'] = '__import__("os").system("compiler")'
    if kind == 'text_anchor': fields['anchor'] = {'text': '$(language-server)', 'line': 999999}
    if kind == 'line_range': fields['encoding'] = 'unavailable-language-codec'
    record = reference(kind, **fields); before = inventory(tmp_path)
    with no_write_attempts():
        result = read_code_reference(ProjectBoundary(tmp_path), record)
    assert result.source_bytes == RAW and result.data['reference'] == record.data
    assert result.data['file_hash_matches'] is matching
    assert result.data['symbol_resolved'] is result.data['selection_evaluated'] is False
    assert result.data['reference_state_evaluated'] is False
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('mode', ['120000', '160000'])
def test_git_symlink_and_submodule_entries_cannot_supply_source_bytes(tmp_path, mode):
    repo = GitFixture(tmp_path / 'repo')
    commit = repo.commit({PATH: (mode, b'../outside' if mode == '120000' else 'a' * 40)})
    source = GitObjectSource(repo.root, commit); before = repo.capture()
    with pytest.raises(SafetyViolation):
        read_code_reference(source, reference())
    assert repo.capture() == before


def test_git_nested_project_is_not_read_as_parent_project_code(tmp_path):
    repo = GitFixture(tmp_path / 'repo')
    commit = repo.commit({PATH: RAW, 'src/specroad.json': b'{}'})
    source = GitObjectSource(repo.root, commit); before = repo.capture()
    with pytest.raises(SafetyViolation):
        read_code_reference(source, reference())
    assert repo.capture() == before


def test_git_bytes_never_follow_a_working_tree_symlink(repository, tmp_path):
    repo, commit = repository
    outside = tmp_path / 'outside'; outside.write_bytes(b'FOREIGN')
    (repo.root / PATH).unlink(); (repo.root / PATH).symlink_to(outside)
    before = inventory(tmp_path)
    result = read_code_reference(GitObjectSource(repo.root, commit), reference(git_commit=commit))
    assert result.source_bytes == RAW and inventory(tmp_path) == before


@pytest.mark.parametrize('corruption', ['missing', 'different_bytes'])
def test_missing_or_corrupt_git_blob_never_returns_disk_bytes_or_fetches(repository, tmp_path, corruption):
    repo, commit = repository
    marker = tmp_path / 'executed'
    helper = tmp_path / 'helper'; helper.write_text('#!/bin/sh\ntouch "' + str(marker) + '"\n'); helper.chmod(0o700)
    with (repo.git / 'config').open('a') as stream:
        stream.write('\n[remote "origin"]\nurl = ext::' + str(helper) + '\npromisor = true\n'
                     '[protocol "ext"]\nallow = always\n[core]\nfsmonitor = ' + str(helper) + '\n')
    source = GitObjectSource(repo.root, commit)
    blob = repo.object('blob', RAW); path = repo.git / 'objects' / blob[:2] / blob[2:]
    if corruption == 'missing': path.unlink()
    else: path.write_bytes(zlib.compress(b'blob 6\0forged'))
    before = inventory(tmp_path)
    with pytest.raises(ModelError) as caught:
        read_code_reference(source, reference())
    assert caught.value.reason == ('git_object_read_failed' if corruption == 'missing' else 'git_object_identity_mismatch')
    assert not marker.exists() and inventory(tmp_path) == before


@pytest.mark.parametrize('change', ['replace_storage', 'alternates', 'linked_storage'])
def test_git_storage_change_after_binding_is_rejected_before_blob_read(repository, tmp_path, change):
    repo, commit = repository; source = GitObjectSource(repo.root, commit)
    foreign = tmp_path / 'foreign'; foreign.write_bytes(b'unchanged')
    if change == 'replace_storage':
        repo.git.rename(repo.root / 'saved-git'); repo.git.mkdir()
    elif change == 'alternates':
        put(repo.git, 'objects/info/alternates', str(foreign).encode())
    else:
        (repo.git / 'objects/link').symlink_to(foreign)
    before = inventory(tmp_path)
    with pytest.raises(SafetyViolation):
        read_code_reference(source, reference())
    assert inventory(tmp_path) == before


class Sha256GitFixture(GitFixture):
    """Same data-only local store with real SHA-256 Git object headers."""
    def __init__(self, root):
        super().__init__(root)
        (self.git / 'config').write_bytes(b'[core]\nrepositoryformatversion = 1\nbare = false\n'
                                        b'[extensions]\nobjectformat = sha256\n')
    def object(self, kind, data):
        raw = kind.encode() + b' ' + str(len(data)).encode() + b'\0' + data
        oid = sha256(raw).hexdigest()
        target = self.git / 'objects' / oid[:2] / oid[2:]
        target.parent.mkdir(exist_ok=True); target.write_bytes(zlib.compress(raw))
        return oid


@pytest.mark.parametrize('bindings', ['commit', 'blob', 'both'])
def test_sha256_git_commit_and_blob_ids_are_exact_and_distinct_from_raw_file_hash(tmp_path, bindings):
    repo = Sha256GitFixture(tmp_path / 'repo'); commit = repo.commit({PATH: RAW})
    blob = sha256(b'blob ' + str(len(RAW)).encode() + b'\0' + RAW).hexdigest()
    fields = {}
    if bindings in ('commit', 'both'): fields['git_commit'] = commit
    if bindings in ('blob', 'both'): fields['git_blob'] = blob
    before = repo.capture()
    result = read_code_reference(GitObjectSource(repo.root, commit), reference(**fields))
    assert len(commit) == len(blob) == 64 and blob != sha256(RAW).hexdigest()
    assert result.source_bytes == RAW and result.data['file_sha256'] == sha256(RAW).hexdigest()
    assert result.data['git_commit'] == commit and result.data['git_blob'] == blob
    assert repo.capture() == before


@pytest.mark.parametrize('field', ['git_commit', 'git_blob'])
def test_sha256_git_does_not_accept_sha1_identifiers(repository, tmp_path, field):
    sha1_repo, sha1_commit = repository
    repo = Sha256GitFixture(tmp_path / 'sha256'); commit = repo.commit({PATH: RAW})
    expected = sha1_commit if field == 'git_commit' else sha1_repo.object('blob', RAW)
    before = inventory(tmp_path)
    with pytest.raises(ModelError) as caught:
        read_code_reference(GitObjectSource(repo.root, commit), reference(**{field: expected}))
    assert caught.value.reason == 'code_reference_' + field + '_mismatch'
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('mode', ['core', 'pyz'])
@pytest.mark.parametrize('kind', KINDS)
def test_fresh_runtime_audit_rejects_execution_network_and_writes_for_every_kind(tmp_path, mode, kind):
    project = tmp_path / 'project'; project.mkdir()
    put(project, PATH, RAW)
    # A shell-like literal filename and executable mode must remain data too.
    name = 'src/$(compiler);language-server.py'
    put(project, name, RAW).chmod(0o755)
    record = reference(kind, path=name)
    body = '''import json,os,sys
from specroad.verification import read_code_reference
from specroad.security import ProjectBoundary
from specroad.storage.record_artifact import RecordArtifact
from specroad.query.git_source import GitObjectSource
'''
    body += 'reference=RecordArtifact(' + repr(record.source_bytes) + ')\n'
    body += 'source=ProjectBoundary(' + repr(str(project)) + ')\n'
    body += '''forbidden={'subprocess.Popen','os.system','os.posix_spawn','os.exec','os.fork',
 'socket.__new__','socket.connect','socket.getaddrinfo','socket.bind',
 'os.mkdir','os.remove','os.rename','os.rmdir','os.symlink','os.link','os.chmod','os.truncate','os.utime'}
def guard(event,args):
    if event in forbidden:
        raise AssertionError('prohibited effect: '+event)
    if event == 'open':
        path,mode,flags=args
        if (isinstance(mode,str) and any(c in mode for c in 'wax+')) or (
            isinstance(flags,int) and flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND)):
            raise AssertionError('write attempted')
sys.addaudithook(guard)
result=read_code_reference(source,reference)
print(json.dumps(result.data))
'''
    before = inventory(project)
    if mode == 'core': completed = run_core(body, tmp_path, capture=True)
    else:
        _, package = build_distribution(tmp_path / 'distribution')
        completed = run_python(['-I', '-S', '-B', '-c',
            'import sys;sys.path.insert(0,' + repr(str(package)) + ')\n' + body], tmp_path, capture=True)
    assert completed.returncode == 0, completed.stderr
    data = json.loads(completed.stdout)
    assert data['reference'] == record.data and data['file_sha256'] == sha256(RAW).hexdigest()
    assert data['source_code_executed'] is data['symbol_resolved'] is data['reference_state_evaluated'] is False
    assert inventory(project) == before
