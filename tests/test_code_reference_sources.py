"""Owned original source bytes, safe Git reads and passive code selectors."""
from dataclasses import FrozenInstanceError
from hashlib import sha1, sha256
import json
import subprocess

import pytest

from specroad.graph.references import validate_relation_references
from specroad.graph.relations import SourceRelations
from specroad.model.errors import ModelError
from specroad.query.git_source import GitObjectSource
from specroad.security import ProjectBoundary, SafetyViolation
from specroad.storage.record_artifact import RecordArtifact
from specroad.verification import CodeReferenceSource, read_code_reference
from support.import_guards import CORE_STDLIB_IMPORT_GUARD
from support.artifacts import artifact_bytes
from support.git_objects import GitFixture
from support.model import put
from support.records import record_value
from support.relations import artifact, edge


RAW = b'not a programming language\r\n\xff\x00original bytes\r'
PATH = 'src/owned.data'
KINDS = ('file', 'line_range', 'text_anchor', 'symbol_hint', 'generated_artifact')


def reference(kind='file', **overrides):
    fields = {'path': PATH, 'reference_kind': kind, 'file_sha256': sha256(RAW).hexdigest()}
    if kind == 'line_range':
        fields.update(start_line=1, end_line=2, encoding='utf-8', selection_sha256='a' * 64)
    if kind == 'text_anchor':
        fields.update(anchor={'text': 'owned', 'line': 1}, selection_sha256='b' * 64)
    if kind == 'symbol_hint':
        fields['symbol_hint'] = 'opaque::symbol<T>()'
    fields.update(overrides)
    return RecordArtifact(artifact_bytes(record_value('code_ref', **fields)), expected_type='code_ref')


@pytest.fixture
def repository(tmp_path):
    fixture = GitFixture(tmp_path / 'project')
    commit = fixture.commit({PATH: RAW})
    put(fixture.root, PATH, b'different working bytes')
    return fixture, commit


@pytest.mark.parametrize('kind', KINDS)
@pytest.mark.parametrize('provider', ['file', 'git'])
def test_all_five_kinds_bind_original_bytes_without_evaluating_selectors(tmp_path, kind, provider):
    record = reference(kind)
    if provider == 'file':
        put(tmp_path, PATH, RAW)
        source = ProjectBoundary(tmp_path)
    else:
        repo = GitFixture(tmp_path / 'repo')
        commit = repo.commit({PATH: RAW})
        source = GitObjectSource(repo.root, commit)
    result = read_code_reference(source, record)
    data = result.data
    assert isinstance(result, CodeReferenceSource)
    assert result.source_bytes == RAW
    assert data['reference'] == record.data
    assert data['reference_sha256'] == sha256(record.source_bytes).hexdigest()
    assert data['path'] == PATH and data['source_kind'] == provider
    assert data['size'] == len(RAW) and data['file_sha256'] == sha256(RAW).hexdigest()
    assert data['file_hash_matches'] is True
    assert data['selection_evaluated'] is data['reference_state_evaluated'] is False
    assert data['symbol_resolved'] is data['source_code_executed'] is data['write_authorized'] is False
    assert 'state' not in data and 'current' not in data


@pytest.mark.parametrize('raw', [b'', b'\n', b'a\r\nb\r', b'\xff\x00', 'e\u0301東京'.encode()])
def test_raw_file_hash_does_not_decode_normalize_or_drop_final_newline(tmp_path, raw):
    put(tmp_path, PATH, raw)
    result = read_code_reference(ProjectBoundary(tmp_path), reference(file_sha256=sha256(raw).hexdigest()))
    assert result.source_bytes == raw
    assert result.data['file_sha256'] == sha256(raw).hexdigest()
    assert result.data['size'] == len(raw) and result.data['file_hash_matches']


def test_changed_file_is_observed_without_rewriting_record_or_deciding_currency(tmp_path):
    put(tmp_path, PATH, b'changed')
    record = reference('line_range')
    before = record.source_bytes
    result = read_code_reference(ProjectBoundary(tmp_path), record)
    assert result.data['file_hash_matches'] is False
    assert result.source_bytes == b'changed'
    assert result.data['reference']['file_sha256'] == sha256(RAW).hexdigest()
    assert result.data['reference_state_evaluated'] is False
    assert record.source_bytes == before and (tmp_path / PATH).read_bytes() == b'changed'


@pytest.mark.parametrize('bindings', ['commit', 'blob', 'both', 'none'])
def test_optional_git_identifiers_bind_the_path_blob_not_the_working_file(repository, bindings):
    repo, commit = repository
    blob = sha1(b'blob ' + str(len(RAW)).encode() + b'\0' + RAW, usedforsecurity=False).hexdigest()
    fields = {}
    if bindings in ('commit', 'both'):
        fields['git_commit'] = commit
    if bindings in ('blob', 'both'):
        fields['git_blob'] = blob
    before = repo.capture()
    result = read_code_reference(GitObjectSource(repo.root, commit), reference(**fields))
    assert result.source_bytes == RAW
    assert result.data['git_commit'] == commit and result.data['git_blob'] == blob
    assert result.data['reference'] == reference(**fields).data
    assert repo.capture() == before


def test_historical_commit_stays_bound_after_branch_moves(repository):
    repo, commit = repository
    source = GitObjectSource(repo.root, 'main')
    repo.commit({PATH: b'later'}, parent=commit)
    before = repo.capture()
    result = read_code_reference(source, reference(git_commit=commit))
    assert result.source_bytes == RAW and result.data['git_commit'] == commit
    assert repo.capture() == before


@pytest.mark.parametrize('field', ['git_commit', 'git_blob'])
def test_mismatched_git_binding_never_falls_back_to_disk(repository, field):
    repo, commit = repository
    put(repo.root, PATH, RAW)
    before = repo.capture()
    with pytest.raises(ModelError) as caught:
        read_code_reference(GitObjectSource(repo.root, commit), reference(**{field: 'a' * 40}))
    assert caught.value.reason == 'code_reference_' + field + '_mismatch'
    assert caught.value.pointer == '/' + field
    assert repo.capture() == before


@pytest.mark.parametrize('field', ['git_commit', 'git_blob'])
def test_stored_git_binding_requires_explicit_git_source_before_file_read(tmp_path, monkeypatch, field):
    source = ProjectBoundary(tmp_path)
    def forbidden(*args):
        raise AssertionError('file fallback attempted')
    monkeypatch.setattr(ProjectBoundary, 'read_bytes', forbidden)
    with pytest.raises(ModelError) as caught:
        read_code_reference(source, reference(**{field: 'a' * 40}))
    assert caught.value.reason == 'code_reference_git_source_required'


def test_symbol_hint_and_executable_file_are_never_run_or_resolved(tmp_path, monkeypatch):
    marker = tmp_path / 'executed'
    code = ('from pathlib import Path\nPath(' + repr(str(marker)) + ').touch()\n').encode()
    put(tmp_path, PATH, code).chmod(0o755)
    record = reference('symbol_hint', symbol_hint='__import__("os").system("false")',
                       file_sha256=sha256(code).hexdigest())
    def forbidden(*args, **kwargs):
        raise AssertionError('process launch attempted')
    monkeypatch.setattr(subprocess, 'Popen', forbidden)
    result = read_code_reference(ProjectBoundary(tmp_path), record)
    assert result.source_bytes == code and result.data['file_hash_matches']
    assert result.data['symbol_resolved'] is result.data['reference_state_evaluated'] is False
    assert not marker.exists()


def test_git_executable_remains_raw_data_and_only_git_reads_are_started(tmp_path, monkeypatch):
    repo = GitFixture(tmp_path / 'repo')
    marker = repo.root / 'executed'
    code = ('from pathlib import Path\nPath(' + repr(str(marker)) + ').touch()\n').encode()
    commit = repo.commit({PATH: ('100755', code)})
    before = repo.capture()
    original = subprocess.run
    calls = []
    def allowed(argv, **kwargs):
        # No compiler, interpreter, checkout, fetch, shell or language server.
        from pathlib import Path
        assert Path(argv[0]).name == 'git' and kwargs['shell'] is False
        arguments = iter(argv[1:])
        for argument in arguments:
            if argument == '-c':
                next(arguments)
            elif not argument.startswith('-'):
                command = argument
                break
        else:
            raise AssertionError('missing Git command')
        # "commit" after cat-file is an object type, not a Git write command.
        assert command in ('rev-parse', 'ls-tree', 'cat-file')
        calls.append(tuple(argv))
        return original(argv, **kwargs)
    monkeypatch.setattr(subprocess, 'run', allowed)
    result = read_code_reference(GitObjectSource(repo.root, commit), reference('generated_artifact'))
    assert calls and result.source_bytes == code
    assert repo.capture() == before and not marker.exists()


def test_unavailable_file_yields_no_hash(tmp_path):
    with pytest.raises(FileNotFoundError):
        read_code_reference(ProjectBoundary(tmp_path), reference())


def test_unavailable_git_path_does_not_use_existing_working_file(repository):
    repo, commit = repository
    put(repo.root, 'disk-only', RAW)
    before = repo.capture()
    with pytest.raises(ModelError) as caught:
        read_code_reference(GitObjectSource(repo.root, commit), reference(path='disk-only'))
    assert caught.value.reason == 'git_path_missing' and repo.capture() == before


@pytest.mark.parametrize('path', ['../outside', '/outside', 'C:\\outside', '.git/config', 'a//b'])
def test_unsafe_stored_paths_are_rejected_before_source_access(tmp_path, monkeypatch, path):
    source = ProjectBoundary(tmp_path)
    def forbidden(*args):
        raise AssertionError('unsafe source accessed')
    monkeypatch.setattr(ProjectBoundary, 'read_bytes', forbidden)
    with pytest.raises(ModelError):
        read_code_reference(source, reference(path=path))


@pytest.mark.parametrize('kind', ['file', 'parent'])
def test_external_symlinks_cannot_supply_code_bytes(tmp_path, kind):
    project = tmp_path / 'project'; project.mkdir()
    outside = tmp_path / 'outside'; outside.mkdir()
    put(outside, 'owned.data', RAW)
    if kind == 'file':
        (project / 'link').symlink_to(outside / 'owned.data')
        path = 'link'
    else:
        (project / 'link').symlink_to(outside, target_is_directory=True)
        path = 'link/owned.data'
    with pytest.raises(SafetyViolation):
        read_code_reference(ProjectBoundary(project), reference(path=path))
    assert (outside / 'owned.data').read_bytes() == RAW


def test_nested_project_cannot_supply_code_bytes(tmp_path):
    put(tmp_path, 'nested/specroad.json', b'{}')
    put(tmp_path, 'nested/owned.data', RAW)
    with pytest.raises(SafetyViolation):
        read_code_reference(ProjectBoundary(tmp_path), reference(path='nested/owned.data'))


@pytest.mark.parametrize('value', [None, {}, b'{}'])
def test_untyped_records_are_rejected_before_read(tmp_path, value):
    with pytest.raises(ModelError) as caught:
        read_code_reference(ProjectBoundary(tmp_path), value)
    assert caught.value.reason == 'code_reference_record_required'


def test_other_record_types_are_rejected_before_read(tmp_path):
    with pytest.raises(ModelError):
        read_code_reference(ProjectBoundary(tmp_path), RecordArtifact(artifact_bytes(record_value('test'))))


def test_arbitrary_source_callbacks_are_not_a_read_capability():
    class FakeSource:
        def read_bytes(self, path):
            raise AssertionError('untrusted reader called')
    with pytest.raises(ModelError) as caught:
        read_code_reference(FakeSource(), reference())
    assert caught.value.reason == 'code_reference_source_required'


def test_owned_bytes_and_detached_reference_survive_later_source_changes(tmp_path):
    path = put(tmp_path, PATH, RAW)
    result = read_code_reference(ProjectBoundary(tmp_path), reference('text_anchor'))
    digest = result.sha256
    data = result.data; data['reference']['anchor'].clear(); data['file_sha256'] = '0' * 64
    path.write_bytes(b'new')
    assert result.source_bytes == RAW and result.sha256 == digest
    assert result.data['reference']['anchor'] == {'text': 'owned', 'line': 1}
    with pytest.raises(FrozenInstanceError):
        result.source_bytes = b'forged'
    with pytest.raises(TypeError):
        bool(result)
    with pytest.raises(TypeError):
        CodeReferenceSource()


@pytest.mark.parametrize('source_type', ['capability', 'requirement', 'decision'])
def test_native_implemented_by_relation_resolves_to_bound_code_reference(tmp_path, source_type):
    put(tmp_path, PATH, RAW)
    code = reference()
    origin = artifact(source_type, relations=[edge('implemented_by', code.id)])
    resolved = validate_relation_references([
        SourceRelations(artifact_bytes(origin)), SourceRelations(code.source_bytes)])
    observed = read_code_reference(ProjectBoundary(tmp_path), code)
    assert len(resolved.relations) == 1
    assert resolved.relations[0].target.id == observed.data['reference']['id']
    assert resolved.relations[0].target.artifact_type == 'code_ref'
    assert resolved.relations[0].relation.type == 'implemented_by'


@pytest.mark.parametrize('mode', ['core', 'pyz'])
def test_public_reader_in_fresh_standard_library_only_runtime(tmp_path, mode):
    from support.portable import build_distribution
    from support.processes import run_core, run_python
    project = tmp_path / 'project'; project.mkdir()
    put(project, PATH, RAW)
    record = reference('symbol_hint')
    body = CORE_STDLIB_IMPORT_GUARD + '''import sys,json
from specroad.verification import read_code_reference
from specroad.security import ProjectBoundary
from specroad.storage.record_artifact import RecordArtifact
'''
    body += 'record=RecordArtifact(' + repr(record.source_bytes) + ')\n'
    body += 'result=read_code_reference(ProjectBoundary(' + repr(str(project)) + '),record)\n'
    body += 'print(json.dumps(result.data))\n'
    if mode == 'core':
        completed = run_core(body, tmp_path, capture=True)
    else:
        _, package = build_distribution(tmp_path / 'distribution')
        completed = run_python(['-I', '-S', '-B', '-c',
            'import sys;sys.path.insert(0,' + repr(str(package)) + ')\n' + body], tmp_path, capture=True)
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout) == read_code_reference(ProjectBoundary(project), record).data
    assert (project / PATH).read_bytes() == RAW
