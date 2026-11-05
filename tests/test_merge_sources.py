"""17.a.W: complete three-source observations, preserving native roots and bytes."""
from contextlib import contextmanager
from dataclasses import FrozenInstanceError
from hashlib import sha256
import io
import json
import os
from pathlib import Path
import stat
import subprocess
from unittest.mock import patch

import pytest

from specroad.bundles import prepare_project_bundle
from specroad.merge import MergeSources, SourceRequest, SourceSnapshot, load_merge_sources
from specroad.model.canonical import canonical_json_bytes
from specroad.model.errors import ModelError
from specroad.query.baseline_source import baseline_source
from support.git_objects import GitFixture
from support.model import put
from support.read_only import inventory, no_write_attempts
from test_project_bundle import project, baseline_project


KINDS = ('local', 'git', 'baseline', 'bundle')


@contextmanager
def read_only_sources():
    """Trap writes while permitting only the adapter's read-only Git commands."""
    popen = subprocess.Popen
    open_io = io.open

    def read_git(argv, *args, **kwargs):
        assert Path(argv[0]).name in ('git', 'git.exe')
        assert kwargs.get('shell') is False
        assert 'protocol.allow=never' in argv
        assert kwargs['env']['GIT_OPTIONAL_LOCKS'] == '0'
        arguments = iter(argv[1:]); command = None
        for argument in arguments:
            if argument == '-c':
                next(arguments)
            elif not argument.startswith('-'):
                command = argument; break
        assert command in ('rev-parse', 'cat-file', 'ls-tree')
        standard_input = kwargs.get('stdin')
        assert standard_input in (subprocess.DEVNULL, subprocess.PIPE)
        assert kwargs.get('stdout') == kwargs.get('stderr') == subprocess.PIPE
        if standard_input == subprocess.DEVNULL:
            # Popen otherwise opens the null device with O_RDWR internally.
            kwargs['stdin'] = null_input
        guarded_open = io.open

        def pipe_open(file, mode='r', *open_args, **open_kwargs):
            # Only Popen's anonymous input-pipe plumbing may open for writing.
            # Paths and regular file descriptors still reach the write trap.
            if (standard_input == subprocess.PIPE and type(file) is int
                    and mode == 'wb' and stat.S_ISFIFO(os.fstat(file).st_mode)):
                return open_io(file, mode, *open_args, **open_kwargs)
            return guarded_open(file, mode, *open_args, **open_kwargs)

        with patch.object(io, 'open', pipe_open):
            return popen(argv, *args, **kwargs)

    # Acquire a genuinely read-only null input before installing project traps.
    with open(os.devnull, 'rb') as null_input, no_write_attempts(), \
            patch.object(subprocess, 'Popen', read_git):
        yield



def sources(tmp_path):
    origin = tmp_path / 'history'
    operation = baseline_project(origin)
    record = operation['record']
    historical = baseline_source(origin, record['id'], None)
    files = dict(historical.resources)
    local = tmp_path / 'local'; local.mkdir()
    for path, raw in files.items():
        put(local, path, raw)
    git = GitFixture(tmp_path / 'git')
    commit = git.commit(files)
    bundle = prepare_project_bundle(local)
    filename = tmp_path / 'project.zip'; filename.write_bytes(bundle.source_bytes)
    requests = {'local': SourceRequest(local), 'git': SourceRequest(git.root, 'git', commit),
        'baseline': SourceRequest(origin, 'baseline', record['id']), 'bundle': SourceRequest(filename, 'bundle')}
    return requests, files, record, git


@pytest.mark.parametrize('kind', KINDS)
@pytest.mark.parametrize('position', range(3))
def test_every_source_kind_in_every_role_keeps_native_root_and_full_inventory(tmp_path, kind, position):
    requests, files, record, git = sources(tmp_path)
    selected = [requests['local']] * 3; selected[position] = requests[kind]
    before = inventory(tmp_path)
    with read_only_sources():
        result = load_merge_sources(*selected)
    assert inventory(tmp_path) == before
    for role in ('base', 'ours', 'theirs'):
        snapshot = getattr(result, role)
        assert snapshot.project_id == json.loads(files['specroad.json'])['project_id']
        assert snapshot.schema_version == '0.2.0'
        assert snapshot.files == files
        assert snapshot.binding['scope_descriptor'] == record['scope_descriptor']
        assert snapshot.binding['model_root_sha256'] == record['model_root_sha256']
        assert snapshot.binding['resources'] == [
            {'path': p, 'size': len(raw), 'sha256': sha256(raw).hexdigest()}
            for p, raw in sorted(files.items())]
        assert not any(snapshot.binding[key] for key in
                       ('atomic_snapshot', 'full_semantic_validation', 'approval_granted', 'write_authorized'))
    assert getattr(result, ('base', 'ours', 'theirs')[position]).kind == kind
    assert len(result.sha256) == 64


def test_three_different_sources_preserve_each_independent_resource_change(tmp_path):
    base_root = tmp_path / 'base'; base = project(base_root)
    ours = dict(base.raw); theirs = dict(base.raw)
    goal = next(p for p in ours if p.startswith('spec/goals/'))
    value = json.loads(ours[goal]); value['title'] = 'Our independent title'
    ours[goal] = canonical_json_bytes(value)
    theirs['mappings/export.json'] += b'\n'
    ours_root = tmp_path / 'ours'; ours_root.mkdir()
    for path, raw in ours.items(): put(ours_root, path, raw)
    filename = tmp_path / 'theirs.zip'
    theirs_root = tmp_path / 'theirs'; theirs_root.mkdir()
    for path, raw in theirs.items(): put(theirs_root, path, raw)
    filename.write_bytes(prepare_project_bundle(theirs_root).source_bytes)
    git = GitFixture(tmp_path / 'git'); commit = git.commit(base.raw)
    before = inventory(tmp_path)
    with read_only_sources():
        result = load_merge_sources(SourceRequest(git.root, 'git', commit),
            SourceRequest(ours_root), SourceRequest(filename, 'bundle'))
    assert result.base.files == base.raw and result.ours.files == ours and result.theirs.files == theirs
    assert result.ours.binding['model_root_sha256'] != result.base.binding['model_root_sha256']
    assert result.theirs.binding['model_root_sha256'] == result.base.binding['model_root_sha256']
    assert result.theirs.files['attachments/owned.bin'] == b'\x00\xffattachment bytes\r\n'
    assert inventory(tmp_path) == before


def test_owned_snapshots_and_returned_bindings_cannot_be_changed_through_callers(tmp_path):
    root = tmp_path / 'source'; original = project(root)
    result = load_merge_sources(*(SourceRequest(root) for _ in range(3)))
    digest = result.sha256
    result.base.files.clear(); result.ours.binding['resources'].clear()
    result.binding['theirs']['scope_descriptor']['scope_kind'] = 'release'
    (root / 'specroad.json').unlink()
    assert result.base.files == original.raw and result.sha256 == digest
    with pytest.raises(FrozenInstanceError): result.base.kind = 'foreign'
    with pytest.raises(FrozenInstanceError): result.base = result.ours


def test_git_source_ignores_mutable_ref_and_current_worktree_without_checkout(tmp_path):
    root = tmp_path / 'source'; original = project(root)
    git = GitFixture(tmp_path / 'git'); commit = git.commit(original.raw)
    put(git.root, 'specroad.json', b'not a current project')
    put(git.root, '.specroad/transactions/pending/journal.json', b'not the selected Git snapshot')
    before = git.capture()
    with read_only_sources():
        source = SourceSnapshot(SourceRequest(git.root, 'git', 'main'))
    assert source.commit_id == commit and source.files == original.raw
    assert git.capture() == before
    changed = dict(original.raw); changed['specroad.json'] += b'\n'
    git.commit(changed)
    assert source.commit_id == commit and source.files == original.raw


def test_baseline_uses_archived_originals_without_current_project_fallback(tmp_path):
    requests, files, record, _ = sources(tmp_path)
    put(requests['baseline'].root, 'specroad.json', b'invalid current project')
    before = inventory(tmp_path)
    with read_only_sources(): source = SourceSnapshot(requests['baseline'])
    assert source.files == files and source.binding['model_root_sha256'] == record['model_root_sha256']
    assert source.binding['baseline']['snapshot_integrity_verified']
    assert source.binding['baseline']['historical_full_validation_verified'] is False
    assert inventory(tmp_path) == before


def test_full_project_keeps_baseline_archive_and_raw_binary_resources(tmp_path):
    root = tmp_path / 'source'; operation = baseline_project(root)
    before = inventory(tmp_path)
    with read_only_sources(): source = SourceSnapshot(SourceRequest(root))
    for row in operation['objects']:
        assert row['path'] in source.files
        assert source.files[row['path']] == (root / row['path']).read_bytes()
    assert inventory(tmp_path) == before


def test_native_package_and_language_registry_bytes_remain_in_all_full_sources(tmp_path):
    from specroad.cli.application import dispatch_result
    root = tmp_path / 'source'
    assert dispatch_result(['init', str(root)]).exit_code == 0
    bundle = prepare_project_bundle(root)
    filename = tmp_path / 'source.zip'; filename.write_bytes(bundle.source_bytes)
    git = GitFixture(tmp_path / 'git'); commit = git.commit(bundle.files)
    before = inventory(tmp_path)
    with read_only_sources():
        result = load_merge_sources(SourceRequest(root), SourceRequest(git.root, 'git', commit),
                                    SourceRequest(filename, 'bundle'))
    assert len([p for p in bundle.files if p.startswith('profiles/language-data/packages/')]) == 9
    for source in (result.base, result.ours, result.theirs):
        assert source.files == bundle.files
        assert source.binding['model_root_sha256'] == bundle.manifest['bundle_model_root_sha256']
    assert inventory(tmp_path) == before


def test_foreign_project_cannot_become_one_branch_of_the_merge(tmp_path):
    root = tmp_path / 'source'; project(root)
    foreign = tmp_path / 'foreign'; project(foreign)
    configuration = json.loads((foreign / 'specroad.json').read_bytes())
    configuration['project_id'] = 'foreign'
    put(foreign, 'specroad.json', canonical_json_bytes(configuration))
    with read_only_sources(), pytest.raises(ModelError) as error:
        load_merge_sources(SourceRequest(root), SourceRequest(foreign), SourceRequest(root))
    assert error.value.reason == 'merge_project_mismatch'


def test_merge_sources_require_real_owned_source_snapshots():
    with pytest.raises(ModelError) as error:
        MergeSources({}, {}, {})
    assert error.value.reason == 'merge_source_snapshot_required'
