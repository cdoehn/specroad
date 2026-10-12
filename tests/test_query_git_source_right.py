"""Adversarial configuration and availability preserve bound, read-only input."""
import errno
import os
from pathlib import Path
import stat
import zlib

import pytest

from specroad.graph.comparison import ComparisonInputs
from specroad.model.errors import ModelError
from specroad.query import GitObjectSource, compare_semantic
from specroad.query import git_source
from specroad.security import SafetyViolation
from support.git_objects import GitFixture
from test_query_git_source import ARTIFACT, CONFIG, repository


def configure(repository, raw):
    with (repository.git / 'config').open('a') as output:
        output.write('\n' + raw + '\n')


@pytest.mark.parametrize('reference', [None, True, 7, b'HEAD', '--config-env=core.pager=ATTACK',
    'main;touch injected', '$(touch injected)', 'main\x00other', 'refs//heads/main',
    'refs/heads/.hidden', 'main.lock', 'HEAD^{tree}'])
def test_hostile_ref_values_fail_before_executable_lookup(repository, reference, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('Invalid source selection must not discover an executable')
    monkeypatch.setattr(git_source.shutil, 'which', forbidden)
    before = repository.capture()
    with pytest.raises(ModelError) as caught:
        GitObjectSource(repository.root, reference)
    assert caught.value.reason == 'git_reference_required'
    assert repository.capture() == before


def test_missing_git_is_environmental_and_non_git_comparison_remains_available(repository, monkeypatch):
    monkeypatch.setattr(git_source.shutil, 'which', lambda *args, **kwargs: None)
    before = repository.capture()
    with pytest.raises(OSError) as caught:
        GitObjectSource(repository.root, 'main')
    assert caught.value.errno == errno.ENOENT
    assert compare_semantic(ComparisonInputs('sample', ()), ComparisonInputs('sample', ())).data['changed'] is False
    assert repository.capture() == before


@pytest.mark.parametrize('failure', [errno.ENOENT, errno.EACCES, errno.ENOEXEC])
def test_executable_start_failures_preserve_state_and_expose_only_environmental_contract(repository, monkeypatch, failure):
    def failed(*args, **kwargs):
        raise OSError(failure, 'untrusted child diagnostic', 'private-source-bytes')
    monkeypatch.setattr(git_source.subprocess, 'run', failed)
    before = repository.capture()
    with pytest.raises(OSError) as caught:
        GitObjectSource(repository.root, 'main')
    assert caught.value.errno == failure and caught.value.filename is None
    assert repository.capture() == before


@pytest.mark.parametrize('worktree', ['foreign', 'missing', 'linked'])
def test_local_core_worktree_cannot_redirect_the_explicit_source(repository, tmp_path, worktree):
    foreign = GitFixture(tmp_path / 'foreign')
    foreign.commit({'specroad.json': b'foreign source'})
    target = foreign.root
    if worktree == 'missing':
        target = tmp_path / 'absent'
    elif worktree == 'linked':
        target = tmp_path / 'linked'
        target.symlink_to(foreign.root, target_is_directory=True)
    configure(repository, '[core]\nworktree = ' + str(target))
    before, outside = repository.capture(), foreign.capture()
    assert GitObjectSource(repository.root, 'main').read_bytes('specroad.json') == CONFIG
    assert repository.capture() == before and foreign.capture() == outside


def test_local_aliases_pager_and_hook_paths_never_execute(repository, tmp_path):
    marker = tmp_path / 'executed'
    script = tmp_path / 'external-helper'
    script.write_text('#!/bin/sh\nprintf executed > "' + str(marker) + '"\n')
    script.chmod(0o700)
    configure(repository, '[alias]\nrev-parse = !' + str(script) + '\nls-tree = !' + str(script)
        + '\ncat-file = !' + str(script) + '\n[core]\nhooksPath = ' + str(script.parent)
        + '\n[pager]\nrev-parse = ' + str(script) + '\nls-tree = ' + str(script)
        + '\ncat-file = ' + str(script))
    before = repository.capture()
    assert GitObjectSource(repository.root, 'main').read_bytes('specroad.json') == CONFIG
    assert not marker.exists() and repository.capture() == before


def test_promisor_remote_cannot_fetch_or_execute_a_helper_for_a_missing_blob(repository, tmp_path):
    marker = tmp_path / 'fetch-executed'
    script = tmp_path / 'remote-helper'
    script.write_text('#!/bin/sh\nprintf fetched > "' + str(marker) + '"\n')
    script.chmod(0o700)
    configure(repository, '[remote "origin"]\nurl = ext::' + str(script)
        + '\npromisor = true\npartialclonefilter = blob:none\n[protocol "ext"]\nallow = always')
    source = GitObjectSource(repository.root, 'main')
    oid = repository.object('blob', CONFIG)
    (repository.git / 'objects' / oid[:2] / oid[2:]).unlink()
    before = repository.capture()
    with pytest.raises(ModelError) as caught:
        source.read_bytes('specroad.json')
    assert caught.value.reason == 'git_object_read_failed'
    assert not marker.exists() and repository.capture() == before


def test_inherited_config_parameters_alternates_and_trace2_are_ignored(repository, tmp_path, monkeypatch):
    trace = tmp_path / 'trace2'
    config = tmp_path / 'external-config'
    config.write_text('[core]\nrepositoryformatversion = 999999\n')
    monkeypatch.setenv('GIT_CONFIG_GLOBAL', str(config))
    monkeypatch.setenv('GIT_CONFIG_SYSTEM', str(config))
    monkeypatch.setenv('GIT_CONFIG_PARAMETERS', "'core.repositoryformatversion=999999'")
    monkeypatch.setenv('GIT_ALTERNATE_OBJECT_DIRECTORIES', str(tmp_path / 'absent-objects'))
    monkeypatch.setenv('GIT_OBJECT_DIRECTORY', str(tmp_path / 'absent-objects'))
    monkeypatch.setenv('GIT_TRACE2_EVENT', str(trace))
    before = repository.capture()
    assert GitObjectSource(repository.root, 'main').read_bytes('specroad.json') == CONFIG
    assert not trace.exists() and repository.capture() == before


@pytest.mark.parametrize('configuration', ['[broken', '[core]\nrepositoryformatversion = 999999',
    '[core]\nrepositoryformatversion = 1\n[extensions]\nobjectformat = unrecognized'])
def test_invalid_local_configuration_is_controlled_and_preserves_files(repository, configuration):
    configure(repository, configuration)
    before = repository.capture()
    with pytest.raises(ModelError) as caught:
        GitObjectSource(repository.root, 'main')
    assert caught.value.reason == 'git_object_read_failed'
    assert repository.capture() == before


def test_ambiguous_short_ref_is_rejected_but_explicit_branch_is_usable(repository):
    branch = (repository.git / 'refs/heads/main').read_text().strip()
    other = repository.commit({'specroad.json': b'tag'}, ref='refs/tags/main')
    assert branch != other
    before = repository.capture()
    with pytest.raises(ModelError) as caught:
        GitObjectSource(repository.root, 'main')
    assert caught.value.reason == 'git_object_read_failed'
    assert GitObjectSource(repository.root, 'refs/heads/main').read_bytes('specroad.json') == CONFIG
    assert repository.capture() == before


@pytest.mark.parametrize('name', ['commondir', 'info/grafts', 'objects/info/alternates', 'objects/info/http-alternates'])
def test_indirect_object_stores_are_rejected_without_touching_foreign_data(repository, tmp_path, name):
    foreign = tmp_path / 'foreign-bytes'
    foreign.write_bytes(b'unchanged foreign data')
    path = repository.git / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(foreign))
    before = repository.capture()
    with pytest.raises(SafetyViolation):
        GitObjectSource(repository.root, 'main')
    assert foreign.read_bytes() == b'unchanged foreign data' and repository.capture() == before


@pytest.mark.parametrize('directory', [False, True])
def test_linked_git_storage_is_rejected(repository, tmp_path, directory):
    foreign = tmp_path / 'outside'
    if directory:
        foreign.mkdir()
    else:
        foreign.write_bytes(b'foreign')
    (repository.git / 'objects/linked').symlink_to(foreign, target_is_directory=directory)
    with pytest.raises(SafetyViolation):
        GitObjectSource(repository.root, 'main')
    assert foreign.is_dir() if directory else foreign.read_bytes() == b'foreign'


def test_special_git_storage_is_rejected_without_opening_it(repository):
    fifo = repository.git / 'objects/pipe'
    os.mkfifo(fifo)
    with pytest.raises(SafetyViolation):
        GitObjectSource(repository.root, 'main')
    assert stat.S_ISFIFO(fifo.lstat().st_mode)


def test_replaced_git_directory_invalidates_an_existing_source(repository):
    source = GitObjectSource(repository.root, 'main')
    repository.git.rename(repository.root / 'saved-git')
    repository.git.mkdir()
    with pytest.raises(SafetyViolation):
        source.read_bytes('specroad.json')
    assert (repository.root / 'saved-git/index').read_bytes().startswith(b'owned pre-existing')


def test_corrupt_tree_cannot_supply_an_unbound_inventory(repository):
    tree = repository.tree({'specroad.json': CONFIG, ARTIFACT: b'{"version":"old"}\n'})
    (repository.git / 'objects' / tree[:2] / tree[2:]).write_bytes(zlib.compress(b'tree 0\0'))
    before = repository.capture()
    with pytest.raises(ModelError) as caught:
        GitObjectSource(repository.root, 'main')
    assert caught.value.reason == 'git_object_identity_mismatch'
    assert repository.capture() == before


def test_repository_with_read_only_files_and_directories_remains_usable(repository):
    paths = [repository.root, *repository.root.rglob('*')]
    modes = {p: stat.S_IMODE(p.stat().st_mode) for p in paths}
    try:
        for p in paths:
            p.chmod(0o555 if p.is_dir() else 0o444)
        before = repository.capture()
        assert GitObjectSource(repository.root, 'main').read_bytes('specroad.json') == CONFIG
        assert repository.capture() == before
    finally:
        for p, mode in modes.items():
            p.chmod(mode)
