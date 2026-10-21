"""H.3 state behavior on owned native files and immutable Git trees."""
from dataclasses import FrozenInstanceError
from hashlib import sha256
import errno
import json
import os

import pytest

from specroad.model.canonical import canonical_json_bytes
from specroad.model.errors import ModelError
from specroad.query.git_source import GitObjectSource
from specroad.security import ProjectBoundary, SafetyViolation
from specroad.security.resource_access import opened_resource
from specroad.verification import CodeReferenceState, assess_code_reference, read_code_reference
from support.git_objects import GitFixture
from support.model import put
from support.portable import build_distribution
from support.processes import run_core, run_python
from support.read_only import inventory, no_write_attempts
from test_code_line_selection import line_reference
from test_code_reference_sources import PATH, reference
from test_code_reference_sources_right import after_read
from test_code_relocation import anchored_reference


def assessed_file(root, raw, record):
    put(root, PATH, raw)
    before, original = inventory(root), record.source_bytes
    with no_write_attempts():
        result = assess_code_reference(ProjectBoundary(root), record)
    assert inventory(root) == before and record.source_bytes == original
    assert result.data['reference'] == record.data
    assert result.data['reference_sha256'] == sha256(original).hexdigest()
    return result


@pytest.mark.parametrize('raw', [b'', b'a\r\nb\r', b'\xff\x00'])
@pytest.mark.parametrize('matches', [True, False])
def test_file_currency_uses_only_original_byte_hash(tmp_path, raw, matches):
    record = reference(file_sha256=sha256(raw).hexdigest() if matches else '0' * 64)
    data = assessed_file(tmp_path, raw, record).data
    assert (data['state'], data['reason']) == (('current', None) if matches else ('stale', 'file_changed'))
    assert data['source']['file_sha256'] == sha256(raw).hexdigest()
    assert data['target_present'] and data['source']['size'] == len(raw)
    assert data['selection_location'] is None and data['selection_location_sha256'] is None
    assert data['selection_evaluated'] is False
    assert data['diagnostics'] == [] and data['new_position'] is None


@pytest.mark.parametrize('mode', ['line_range', 'text', 'bytes'])
@pytest.mark.parametrize('raw,position,state,reason,new', [
    (b'KEEP\n', 1, 'current', None, None),
    (b'KEEP\nKEEP\nKEEP\n', 2, 'current', None, None),
    (b'new\nKEEP\n', 1, 'relocated', None, 2),
    (b'KEEP\n', 9, 'relocated', None, 1),
    (b'other\n', 1, 'stale', 'selection_missing', None),
    (b'new\nKEEP\nKEEP\n', 1, 'stale', 'selection_ambiguous', None),
], ids=['stored', 'stored-beats-duplicates', 'relocated', 'old-position-gone', 'no-hit', 'multiple-hits'])
def test_first_matching_selection_rule_decides_one_state(tmp_path, mode, raw, position, state, reason, new):
    selected = b'KEEP\n'
    # Every case has a changed whole-file hash: it must never override the
    # independently stored selector or turn a stored hit into relocation.
    if mode == 'line_range':
        record = line_reference(b'old source', selected, start=position, end=position)
    else:
        start = (len(selected) if position == 2 else position - 1) if mode == 'bytes' else position
        record = anchored_reference(b'old source', selected, mode=mode, start=start,
                                    count=len(selected) if mode == 'bytes' else 1)
    data = assessed_file(tmp_path, raw, record).data
    assert (data['state'], data['reason']) == (state, reason)
    assert data['source']['file_hash_matches'] is False
    assert data['selection_evaluated'] and data['reference_state_evaluated']
    expected = None if new is None else ({'start_byte': raw.index(selected), 'byte_count': len(selected)}
        if mode == 'bytes' else {'start_line': new, 'end_line': new})
    assert data['new_position'] == expected
    assert data['diagnostics'] == (['file_changed_outside_selection'] if state == 'current' else [])
    located = data['selection_location']
    assert data['selection_location_sha256'] == sha256(canonical_json_bytes(located)).hexdigest()
    assert located['source'] == data['source']
    if state == 'current':
        assert located['stored_position_matches'] and located['search_performed'] is False
        assert located['match_count'] is None
    elif reason == 'selection_missing':
        assert located['match_count'] == 0
    elif reason == 'selection_ambiguous':
        assert located['match_count'] == 2 and located['matched_position'] is None


@pytest.mark.parametrize('mode', ['line_range', 'text'])
def test_changed_newlines_outside_selection_remain_current(tmp_path, mode):
    old, raw, selected = b'head\nKEEP\ntail', b'changed\r\nKEEP\r\nnew tail', b'KEEP\n'
    record = (line_reference(old, selected, start=2, end=2) if mode == 'line_range'
              else anchored_reference(old, selected, start=2))
    data = assessed_file(tmp_path, raw, record).data
    assert data['state'] == 'current' and data['reason'] is None
    assert data['source']['file_hash_matches'] is False
    assert data['selection_location']['stored_position_matches']
    assert data['new_position'] is None


def test_matching_file_hash_cannot_replace_a_wrong_selection_hash(tmp_path):
    raw = b'actual\n'
    data = assessed_file(tmp_path, raw, line_reference(raw, b'expected\n')).data
    assert data['source']['file_hash_matches']
    assert (data['state'], data['reason']) == ('stale', 'selection_missing')


@pytest.mark.parametrize('kind', ['file', 'line_range', 'text_anchor', 'symbol_hint', 'generated_artifact'])
@pytest.mark.parametrize('parent_present', [False, True])
def test_absent_file_path_wins_before_selector_or_hint_evaluation(tmp_path, kind, parent_present):
    if parent_present:
        (tmp_path / 'src').mkdir()
    record = reference(kind)
    before = inventory(tmp_path)
    with no_write_attempts():
        data = assess_code_reference(ProjectBoundary(tmp_path), record).data
    assert (data['state'], data['reason']) == ('missing', 'target_missing')
    assert data['target_present'] is False and data['source'] is data['source_sha256'] is None
    assert data['selection_location'] is None and data['selection_evaluated'] is False
    assert data['new_position'] is None and data['reference'] == record.data
    assert inventory(tmp_path) == before
    # The original byte-reader API keeps its established error contract.
    with pytest.raises(FileNotFoundError):
        read_code_reference(ProjectBoundary(tmp_path), record)


@pytest.mark.parametrize('raw,expected', [(b'KEEP\n', 'current'), (b'new\nKEEP\n', 'relocated'), (b'other\n', 'stale')])
def test_historical_git_selection_decides_without_head_or_worktree_fallback(tmp_path, raw, expected):
    repo = GitFixture(tmp_path / 'repo')
    commit = repo.commit({PATH: raw})
    record = line_reference(b'old', b'KEEP\n', git_commit=commit)
    source = GitObjectSource(repo.root, commit)
    repo.commit({PATH: b'HEAD changed'}, parent=commit)
    put(repo.root, PATH, b'working source changed')
    before = repo.capture()
    data = assess_code_reference(source, record).data
    assert data['state'] == expected and data['git_commit'] == commit
    assert data['source']['file_sha256'] == sha256(raw).hexdigest()
    assert repo.capture() == before


def test_missing_git_path_does_not_read_a_new_head_or_existing_working_file(tmp_path):
    repo = GitFixture(tmp_path / 'repo')
    commit = repo.commit({'other': b'owned'})
    source = GitObjectSource(repo.root, commit)
    repo.commit({PATH: b'KEEP\n'}, parent=commit)
    put(repo.root, PATH, b'KEEP\n')
    record = line_reference(b'KEEP\n', b'KEEP\n', git_commit=commit)
    before = repo.capture()
    data = assess_code_reference(source, record).data
    assert (data['state'], data['reason']) == ('missing', 'target_missing')
    assert data['git_commit'] == commit and data['source_kind'] == 'git'
    assert data['source'] is None and data['target_present'] is False
    assert repo.capture() == before


@pytest.mark.parametrize('change', ['store', 'root'])
def test_cached_git_absence_does_not_admit_replacement_source_identity(tmp_path, change):
    repo = GitFixture(tmp_path / 'repo')
    commit = repo.commit({})
    source = GitObjectSource(repo.root, commit)
    target = repo.git if change == 'store' else repo.root
    saved = tmp_path / ('saved-' + change)
    target.rename(saved)
    target.mkdir()
    before = inventory(tmp_path)
    with pytest.raises(SafetyViolation):
        assess_code_reference(source, reference())
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('error_case', ['encoding', 'decode', 'legacy_anchor', 'symbol_hint', 'generated_artifact'])
def test_unassessable_present_reference_is_an_error_not_a_currency_guess(tmp_path, error_case):
    raw = b'A\n'
    if error_case == 'encoding':
        record = line_reference(raw, raw, encoding='unavailable-codec')
        reason = 'code_reference_encoding_unavailable'
    elif error_case == 'decode':
        raw = b'\xff'
        record = line_reference(raw, raw)
        reason = 'code_reference_decode_failed'
    elif error_case == 'legacy_anchor':
        record = reference('text_anchor', file_sha256=sha256(raw).hexdigest())
        reason = 'code_reference_anchor_unsupported'
    else:
        record = reference(error_case, file_sha256=sha256(raw).hexdigest())
        reason = 'code_reference_state_kind_unsupported'
    with pytest.raises(ModelError) as caught:
        assessed_file(tmp_path, raw, record)
    assert caught.value.reason == reason


@pytest.mark.parametrize('value', [None, {}, b'{}'])
def test_state_requires_a_validated_record_before_source_access(tmp_path, value):
    with pytest.raises(ModelError) as caught:
        assess_code_reference(ProjectBoundary(tmp_path), value)
    assert caught.value.reason == 'code_reference_record_required'


def test_state_rejects_untrusted_reader_and_mismatched_git_authority(tmp_path):
    class Reader:
        def read_bytes(self, path):
            raise AssertionError('untrusted callback')
    with pytest.raises(ModelError) as caught:
        assess_code_reference(Reader(), reference())
    assert caught.value.reason == 'code_reference_source_required'
    with pytest.raises(ModelError) as caught:
        assess_code_reference(ProjectBoundary(tmp_path), reference(git_commit='a' * 40))
    assert caught.value.reason == 'code_reference_git_source_required'


@pytest.mark.parametrize('kind', ['link', 'nested', 'directory'])
def test_unsafe_paths_do_not_turn_into_missing_or_stale(tmp_path, kind):
    put(tmp_path, PATH, b'A')
    if kind == 'link':
        (tmp_path / PATH).unlink()
        (tmp_path / PATH).symlink_to(tmp_path / 'absent')
    elif kind == 'nested':
        put(tmp_path, 'src/specroad.json', b'{}')
    else:
        (tmp_path / PATH).unlink(); (tmp_path / PATH).mkdir()
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(SafetyViolation):
        assess_code_reference(ProjectBoundary(tmp_path), reference())
    assert inventory(tmp_path) == before


def test_disappearance_after_real_read_is_not_reclassified_as_absence(tmp_path, monkeypatch):
    target = put(tmp_path, PATH, b'A')
    after_read(monkeypatch, target.unlink)
    with pytest.raises((FileNotFoundError, SafetyViolation)):
        assess_code_reference(ProjectBoundary(tmp_path), reference())
    assert not target.exists()


@pytest.mark.parametrize('change', ['appear', 'parent_link', 'nested_root', 'replace_root'])
def test_missing_observation_revalidates_absence_and_all_existing_boundaries(tmp_path, change):
    root = tmp_path / 'project'; root.mkdir(); (root / 'src').mkdir()
    outside = tmp_path / 'outside'; outside.mkdir()
    boundary = ProjectBoundary(root)
    with pytest.raises(SafetyViolation):
        with opened_resource(boundary, PATH, missing_ok=True) as observed:
            assert observed == (None, None)
            if change == 'appear':
                put(root, PATH, b'new')
            elif change == 'parent_link':
                (root / 'src').rename(root / 'saved')
                (root / 'src').symlink_to(outside, target_is_directory=True)
            elif change == 'nested_root':
                put(root, 'src/specroad.json', b'{}')
            else:
                root.rename(tmp_path / 'saved-root'); root.mkdir()
            changed = inventory(tmp_path)
    assert inventory(tmp_path) == changed


def test_missing_probe_preserves_io_errors_and_closes_owned_descriptors(tmp_path, monkeypatch):
    (tmp_path / 'src').mkdir()
    original_open, original_stat = os.open, os.stat
    opened = []
    def opening(*args, **kwargs):
        descriptor = original_open(*args, **kwargs); opened.append(descriptor); return descriptor
    def failing(path, *args, **kwargs):
        if path == 'owned.data' and kwargs.get('dir_fd') is not None:
            raise PermissionError(errno.EACCES, 'owned denied read')
        return original_stat(path, *args, **kwargs)
    boundary = ProjectBoundary(tmp_path)
    monkeypatch.setattr(os, 'open', opening); monkeypatch.setattr(os, 'stat', failing)
    with pytest.raises(PermissionError):
        assess_code_reference(boundary, reference())
    assert opened
    for descriptor in opened:
        with pytest.raises(OSError) as caught:
            os.fstat(descriptor)
        assert caught.value.errno == errno.EBADF


def test_state_projection_is_detached_and_never_boolean_authority(tmp_path):
    result = assessed_file(tmp_path, b'wrong\nKEEP\n', line_reference(b'old', b'KEEP\n'))
    data, digest = result.data, result.sha256
    assert digest == sha256(canonical_json_bytes(data)).hexdigest()
    assert data['format_version'] == 'code-reference-state-v1'
    assert data['validation_scope'] == 'code_reference_state_only'
    assert data['reference_state_evaluated']
    for key in ('symbol_resolved', 'source_code_executed', 'write_authorized'):
        assert data[key] is False
    data['reference'].clear(); data['source'].clear(); data['new_position']['start_line'] = 99
    assert result.sha256 == digest and result.data['new_position']['start_line'] == 2
    with pytest.raises(FrozenInstanceError): result._encoded = b'{}'
    with pytest.raises(TypeError): CodeReferenceState()
    with pytest.raises(TypeError): bool(result)


@pytest.mark.parametrize('mode', ['core', 'pyz'])
def test_state_runs_in_fresh_standard_library_only_runtime(tmp_path, mode):
    project = tmp_path / 'project'; project.mkdir()
    raw = b'__import__("os").system("compiler")\r\nchanged outside'
    selected = b'__import__("os").system("compiler")\n'
    put(project, PATH, raw)
    record = line_reference(b'old', selected)
    body = '''import json,os,sys
class OnlyCoreAndStdlib:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] not in sys.stdlib_module_names | {'specroad'}:
            raise AssertionError('third-party import attempted: '+fullname)
sys.meta_path.insert(0, OnlyCoreAndStdlib())
from specroad.verification import assess_code_reference
from specroad.security import ProjectBoundary
from specroad.storage.record_artifact import RecordArtifact
'''
    body += 'source=ProjectBoundary(' + repr(str(project)) + ')\n'
    body += 'record=RecordArtifact(' + repr(record.source_bytes) + ')\n'
    body += '''def guard(event,args):
    if event in {'subprocess.Popen','os.system','socket.__new__','os.mkdir','os.remove','os.rename'}:
        raise AssertionError('prohibited effect: '+event)
    if event == 'open':
        path,mode,flags=args
        if (isinstance(mode,str) and any(c in mode for c in 'wax+')) or (
            isinstance(flags,int) and flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND)):
            raise AssertionError('write attempted')
sys.addaudithook(guard)
print(json.dumps(assess_code_reference(source,record).data))
'''
    before = inventory(project)
    if mode == 'core':
        completed = run_core(body, tmp_path, capture=True)
    else:
        _, package = build_distribution(tmp_path / 'distribution')
        completed = run_python(['-I', '-S', '-B', '-c', 'import sys;sys.path.insert(0,' + repr(str(package)) + ')\n' + body], tmp_path, capture=True)
    assert completed.returncode == 0, completed.stderr
    data = json.loads(completed.stdout)
    assert data == assess_code_reference(ProjectBoundary(project), record).data
    assert data['state'] == 'current' and data['source']['file_hash_matches'] is False
    assert inventory(project) == before
