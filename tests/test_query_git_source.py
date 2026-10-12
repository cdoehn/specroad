"""Raw Git-source behavior with real objects and independently owned bytes."""
from dataclasses import FrozenInstanceError
import json
from pathlib import Path
import zlib

import pytest

from specroad.model.errors import ModelError
from specroad.query import GitObjectSource
from specroad.security import SafetyViolation
from support.git_objects import GitFixture
from support.model import configuration_value


CONFIG = json.dumps(configuration_value(), ensure_ascii=False).encode()
ARTIFACT = 'spec/requirements/SR-REQ-0001.json'


@pytest.fixture
def repository(tmp_path):
    value = GitFixture(tmp_path / 'project')
    value.commit({'specroad.json': CONFIG, ARTIFACT: b'{"version":"old"}\n'})
    return value


def test_git_ref_returns_bound_project_bytes_without_working_tree_change(repository):
    (repository.root / 'specroad.json').write_bytes(b'working tree differs')
    (repository.root / 'untracked.txt').write_bytes(b'never imported')
    before = repository.capture()
    source = GitObjectSource(repository.root, 'main')
    assert source.commit_id == (repository.git / 'refs/heads/main').read_text().strip()
    assert source.paths == (ARTIFACT, 'specroad.json')
    assert source.read_bytes('specroad.json') == CONFIG
    assert source.read_bytes(ARTIFACT) == b'{"version":"old"}\n'
    assert repository.capture() == before


@pytest.mark.parametrize('reference', ['HEAD', 'main', 'refs/heads/main', 'release', 'refs/tags/release', 'oid'])
def test_explicit_branch_tag_head_and_full_commit_bind_same_contents(repository, reference):
    oid = (repository.git / 'refs/heads/main').read_text().strip()
    repository.ref('refs/tags/release', oid)
    source = GitObjectSource(repository.root, oid if reference == 'oid' else reference)
    assert source.commit_id == oid and source.read_bytes('specroad.json') == CONFIG


def test_source_stays_bound_when_branch_moves_after_construction(repository):
    source = GitObjectSource(repository.root, 'main')
    second = repository.commit({'specroad.json': CONFIG, ARTIFACT: b'new'}, parent=source.commit_id)
    before = repository.capture()
    assert source.read_bytes(ARTIFACT) == b'{"version":"old"}\n'
    newer = GitObjectSource(repository.root, 'main')
    assert newer.commit_id == second and newer.read_bytes(ARTIFACT) == b'new'
    assert repository.capture() == before


def test_raw_binary_crlf_unicode_names_and_executable_blobs_remain_data(repository):
    files = {'specroad.json': CONFIG, 'attachments/Grüße.bin': b'\x00\xffraw\r\n',
             'attachments/run.py': ('100755', b'raise RuntimeError("must not execute")\n')}
    repository.commit(files)
    source = GitObjectSource(repository.root, 'HEAD')
    assert source.read_bytes('attachments/Grüße.bin') == b'\x00\xffraw\r\n'
    assert source.read_bytes('attachments/run.py') == files['attachments/run.py'][1]


def test_attributes_filters_hooks_pager_and_fsmonitor_do_not_execute(repository):
    marker = repository.root / 'executed'
    script = repository.git / 'hooks/fixture'
    script.write_text('#!/bin/sh\nprintf executed > "' + str(marker) + '"\n')
    script.chmod(0o700)
    for hook in ('post-checkout', 'post-merge', 'post-index-change', 'pre-auto-gc'):
        path = repository.git / 'hooks' / hook
        path.write_bytes(script.read_bytes()); path.chmod(0o700)
    with (repository.git / 'config').open('a') as output:
        output.write('\n[core]\npager = ' + str(script) + '\nfsmonitor = ' + str(script)
                     + '\nautocrlf = true\n[filter "hostile"]\nsmudge = ' + str(script)
                     + '\nclean = ' + str(script) + '\nprocess = ' + str(script)
                     + '\n[diff "hostile"]\ntextconv = ' + str(script) + '\n')
    files = {'specroad.json': CONFIG, '.gitattributes': b'* filter=hostile diff=hostile text\n',
             'attachments/bytes.bin': b'raw\r\n\x00\xff'}
    repository.commit(files)
    (repository.root / '.gitattributes').write_bytes(files['.gitattributes'])
    before = repository.capture()
    assert GitObjectSource(repository.root, 'HEAD').read_bytes('attachments/bytes.bin') == files['attachments/bytes.bin']
    assert not marker.exists() and repository.capture() == before


def test_inherited_git_directory_index_trace_and_config_do_not_redirect_or_write(repository, tmp_path, monkeypatch):
    other = GitFixture(tmp_path / 'other')
    other.commit({'specroad.json': b'foreign'})
    trace = tmp_path / 'trace'
    monkeypatch.setenv('GIT_DIR', str(other.git))
    monkeypatch.setenv('GIT_WORK_TREE', str(other.root))
    monkeypatch.setenv('GIT_INDEX_FILE', str(other.git / 'index'))
    monkeypatch.setenv('GIT_TRACE', str(trace))
    monkeypatch.setenv('GIT_CONFIG_COUNT', '1')
    monkeypatch.setenv('GIT_CONFIG_KEY_0', 'core.bare')
    monkeypatch.setenv('GIT_CONFIG_VALUE_0', 'true')
    before, foreign = repository.capture(), other.capture()
    assert GitObjectSource(repository.root, 'HEAD').read_bytes('specroad.json') == CONFIG
    assert not trace.exists() and repository.capture() == before and other.capture() == foreign


def test_replace_refs_do_not_substitute_a_different_commit(repository):
    first = (repository.git / 'refs/heads/main').read_text().strip()
    second = repository.commit({'specroad.json': b'replacement'}, ref=None)
    repository.ref('refs/replace/' + first, second)
    source = GitObjectSource(repository.root, first)
    assert source.commit_id == first and source.read_bytes('specroad.json') == CONFIG


def test_annotated_tag_peels_to_the_bound_commit(repository):
    commit = (repository.git / 'refs/heads/main').read_text().strip()
    tag = repository.object('tag', b'object ' + commit.encode()
        + b'\ntype commit\ntag v1\ntagger Fixture <fixture@example.invalid> 1 +0000\n\nfixture\n')
    repository.ref('refs/tags/v1', tag)
    source = GitObjectSource(repository.root, 'v1')
    assert source.commit_id == commit and source.read_bytes('specroad.json') == CONFIG


def test_missing_committed_file_never_falls_back_to_working_tree(repository):
    (repository.root / 'missing.json').write_bytes(b'present only in working tree')
    source = GitObjectSource(repository.root, 'HEAD')
    with pytest.raises(ModelError) as caught:
        source.read_bytes('missing.json')
    assert caught.value.reason == 'git_path_missing' and caught.value.path == 'missing.json'


@pytest.mark.parametrize('path', ['../secret', '/etc/passwd', 'a/../b', 'a//b', 'a\\b', 'a\x00b'])
def test_unsafe_resource_paths_are_rejected(repository, path):
    source = GitObjectSource(repository.root, 'HEAD')
    with pytest.raises(ModelError) as caught:
        source.read_bytes(path)
    assert caught.value.reason == 'unsafe_path'


@pytest.mark.parametrize('mode', ['120000', '160000'])
def test_symlink_and_gitlink_entries_are_never_followed(repository, mode):
    commit = (repository.git / 'refs/heads/main').read_text().strip()
    content = b'../../foreign.txt' if mode == '120000' else commit
    repository.commit({'specroad.json': CONFIG, 'attachments/link': (mode, content)})
    source = GitObjectSource(repository.root, 'HEAD')
    with pytest.raises(SafetyViolation):
        source.read_bytes('attachments/link')
    assert source.read_bytes('specroad.json') == CONFIG


def test_nested_project_files_are_not_combined(repository):
    repository.commit({'specroad.json': CONFIG, 'nested/specroad.json': CONFIG, 'nested/data': b'foreign'})
    source = GitObjectSource(repository.root, 'HEAD')
    with pytest.raises(SafetyViolation):
        source.read_bytes('nested/data')


def test_source_binding_is_immutable(repository):
    source = GitObjectSource(repository.root, 'HEAD')
    with pytest.raises(FrozenInstanceError):
        source.commit_id = '0' * 40
    assert type(source.paths) is tuple and type(source.read_bytes('specroad.json')) is bytes


def test_missing_blob_is_a_controlled_failure_without_fetch(repository):
    source = GitObjectSource(repository.root, 'HEAD')
    oid = repository.object('blob', CONFIG)
    (repository.git / 'objects' / oid[:2] / oid[2:]).unlink()
    before = repository.capture()
    with pytest.raises(ModelError) as caught:
        source.read_bytes('specroad.json')
    assert caught.value.reason == 'git_object_read_failed'
    assert repository.capture() == before


def test_wrong_blob_bytes_under_an_expected_object_name_are_rejected(repository):
    source = GitObjectSource(repository.root, 'HEAD')
    oid = repository.object('blob', CONFIG)
    raw = b'blob 5\0wrong'
    (repository.git / 'objects' / oid[:2] / oid[2:]).write_bytes(zlib.compress(raw))
    with pytest.raises(ModelError) as caught:
        source.read_bytes('specroad.json')
    assert caught.value.reason == 'git_object_identity_mismatch'


@pytest.mark.parametrize('reference', ['', '--help', '../main', 'HEAD:specroad.json', 'main\nHEAD'])
def test_non_reference_inputs_are_rejected_before_git(repository, reference):
    before = repository.capture()
    with pytest.raises(ModelError) as caught:
        GitObjectSource(repository.root, reference)
    assert caught.value.reason == 'git_reference_required' and repository.capture() == before
