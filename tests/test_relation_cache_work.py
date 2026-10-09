"""Optional native cache hints must preserve complete fresh relation results."""

import json
import os
import subprocess
import sys
from unittest.mock import patch

import pytest

from specroad import _build
from specroad.graph.indices import RelationIndex
from specroad.model.canonical import canonical_json_bytes, canonical_json_sha256
from specroad.model.errors import ModelError
from specroad.storage import _relation_cache as cache_adapter
from specroad.storage.project import ProjectSource
from specroad.storage.relation_index import (
    build_project_relation_index, read_project_relation_views, relation_index_cache_bytes,
)
from support.model import configuration_file, put
from support.portable import build_distribution, files_under
from support.relations import aid, artifact, edge, rid
from test_relation_index import save


@pytest.fixture
def project(tmp_path):
    configuration_file(tmp_path)
    values = [artifact(number=1, relations=[edge('refines', aid(number=2), 1),
              edge('supersedes', aid(number=3), 2), edge('conflicts_with', aid(number=4), 3)]),
              artifact(number=2, relations=[edge('refines', aid(number=3), 4)]),
              artifact(number=3), artifact(number=4), artifact(number=5)]
    for value in values:
        save(tmp_path, value)
    return tmp_path, ProjectSource(tmp_path)


@pytest.fixture
def recorded_build(monkeypatch):
    # Explicit unit fixture, not evidence of an actual build. Portable-build
    # integration below exercises real generated module/zipapp identities.
    record = {'format_version': 1, 'hash_algorithm': 'specroad-dev-payload-v1', 'build_sha256': 'a' * 64}
    monkeypatch.setattr(_build, 'BUILD_METADATA', record)
    return record


def install_cache(project):
    root, source = project
    raw = relation_index_cache_bytes(build_project_relation_index(source))
    assert type(raw) is bytes
    return put(root, cache_adapter.CACHE_PATH, raw)


def read(source, *, number=3, **options):
    return read_project_relation_views(source, aid(number=number), **options)


@pytest.mark.parametrize('direction', ['outgoing', 'incoming', 'both'])
def test_actual_cache_hit_matches_independent_scan_for_every_source(project, recorded_build, direction):
    root, source = project
    install_cache(project)
    before = files_under(root)
    expected = [read(source, number=number, strategy='scan', direction=direction) for number in range(1, 6)]
    with patch.object(RelationIndex, '__init__', side_effect=AssertionError('unexpected rebuild')):
        actual = [read(source, number=number, cache='read', direction=direction) for number in range(1, 6)]
    assert actual == expected
    assert files_under(root) == before
    assert all(result.source_count == 5 and result.relation_count == 4 for result in actual)


@pytest.mark.parametrize('mode', ['off', 'scan', 'zero', 'unrecorded'])
def test_disabled_or_unbound_cache_does_not_open_any_cache(project, recorded_build, monkeypatch, mode):
    root, source = project
    install_cache(project)
    expected = read(source)
    options = {'cache': 'read'}
    if mode == 'off':
        options['cache'] = 'off'
    elif mode == 'scan':
        options['strategy'] = 'scan'
    elif mode == 'zero':
        options['cache_max_bytes'] = 0
    else:
        monkeypatch.setattr(_build, 'BUILD_METADATA', None)
        assert relation_index_cache_bytes(build_project_relation_index(source)) is None
    with patch.object(cache_adapter, 'opened_resource', side_effect=AssertionError('unexpected cache access')):
        assert read(source, **options) == expected


def test_missing_and_deleted_cache_never_create_cache_or_recovery_state(project, recorded_build):
    root, source = project
    before = files_under(root)
    expected = read(source, cache='read')
    assert not (root / '.specroad').exists()
    assert files_under(root) == before
    cache = install_cache(project)
    assert read(source, cache='read') == expected
    cache.unlink()
    after_delete = files_under(root)
    assert read(source, cache='read') == expected
    assert files_under(root) == after_delete
    assert list((root / '.specroad').iterdir()) == [root / '.specroad/cache']


@pytest.mark.parametrize('field', ['tool', 'schema', 'policy', 'runtime', 'configuration', 'content', 'membership'])
def test_each_cache_binding_is_required_before_order_is_used(project, recorded_build, field):
    root, source = project
    cache = install_cache(project)
    entry = json.loads(cache.read_bytes())
    if field == 'tool':
        entry['binding']['tool']['build_sha256'] = 'b' * 64
    elif field == 'schema':
        entry['binding']['schema_version'] = 'future'
    elif field == 'policy':
        entry['binding']['policy'] = 'other'
    elif field == 'runtime':
        entry['binding']['runtime']['implementation'] = 'foreign'
    elif field == 'configuration':
        entry['binding']['dependencies']['configuration_sha256'] = 'c' * 64
    elif field == 'content':
        entry['binding']['dependencies']['resources'][0]['sha256'] = 'd' * 64
    else:
        entry['binding']['dependencies']['resources'].pop()
    cache.write_bytes(canonical_json_bytes(entry))
    before = files_under(root)
    expected = read(source, strategy='scan')
    with patch.object(RelationIndex, 'from_order', side_effect=AssertionError('unbound cache was used')):
        assert read(source, cache='read') == expected
    assert files_under(root) == before


@pytest.mark.parametrize('damage', ['missing', 'duplicate', 'unknown', 'reverse', 'wrong_source',
                                    'missing_isolated', 'extra_source', 'wrong_shape', 'unhashable'])
def test_rehashed_order_cannot_change_edges_direction_coverage_or_order(project, recorded_build, damage):
    root, source = project
    cache = install_cache(project)
    entry = json.loads(cache.read_bytes())
    outgoing = entry['order']['outgoing']
    names = outgoing[aid(number=1)]
    if damage == 'missing':
        names.pop()
    elif damage == 'duplicate':
        names.append(names[0])
    elif damage == 'unknown':
        names[0] = rid(999)
    elif damage == 'reverse':
        names.reverse()
    elif damage == 'wrong_source':
        outgoing[aid(number=5)].append(names.pop())
    elif damage == 'missing_isolated':
        del outgoing[aid(number=5)]
    elif damage == 'extra_source':
        outgoing[aid(number=99)] = []
    elif damage == 'wrong_shape':
        entry['order']['incoming'] = []
    else:
        names[0] = {'relation_id': names[0]}
    entry['order_sha256'] = canonical_json_sha256(entry['order'])
    cache.write_bytes(canonical_json_bytes(entry))
    before = files_under(root)
    for number in range(1, 6):
        assert read(source, number=number, cache='read') == read(source, number=number, strategy='scan')
    assert files_under(root) == before


@pytest.mark.parametrize('damage', ['json', 'hash', 'format', 'oversized', 'link'])
def test_unusable_optional_entry_is_ignored_without_repair(project, recorded_build, damage):
    root, source = project
    cache = install_cache(project)
    expected = read(source, strategy='scan')
    options = {}
    if damage == 'json':
        cache.write_bytes(b'{broken')
    elif damage in ('hash', 'format'):
        entry = json.loads(cache.read_bytes())
        entry['order_sha256' if damage == 'hash' else 'format'] = 'invalid'
        cache.write_bytes(canonical_json_bytes(entry))
    elif damage == 'oversized':
        options['cache_max_bytes'] = cache.stat().st_size - 1
    else:
        target = root / 'passive-cache.json'
        cache.rename(target)
        cache.symlink_to(target)
    before = files_under(root)
    assert read(source, cache='read', **options) == expected
    assert files_under(root) == before
    if damage == 'link':
        assert cache.is_symlink()


def test_cache_does_not_hide_same_size_and_mtime_source_changes(project, recorded_build):
    root, source = project
    install_cache(project)
    path = save(root, artifact(number=2, relations=[edge('refines', aid(number=3), 4)]))
    metadata = path.stat()
    before = path.read_bytes()
    after = before.replace(aid(number=3).encode(), aid(number=4).encode())
    assert len(after) == len(before) and after != before
    path.write_bytes(after)
    os.utime(path, ns=(metadata.st_atime_ns, metadata.st_mtime_ns))
    current = read(source, cache='read')
    assert current == read(source, strategy='scan')
    assert {view.relation_id for view in current.views} == {rid(2)}


def test_new_unselected_source_and_removed_source_invalidate_cache(project, recorded_build):
    root, source = project
    install_cache(project)
    new = save(root, artifact(number=77, relations=[edge('refines', aid(number=3), 77)]))
    added = read(source, cache='read')
    assert added == read(source, strategy='scan')
    assert rid(77) in {view.relation_id for view in added.views}
    new.unlink()
    assert read(source, cache='read') == read(source, strategy='scan')


@pytest.mark.parametrize('damage', ['invalid', 'unreadable', 'missing_endpoint', 'noncanonical'])
def test_cache_never_masks_original_source_failure(project, recorded_build, damage):
    root, source = project
    install_cache(project)
    if damage == 'invalid':
        save(root, artifact(number=1)).write_bytes(b'broken')
    elif damage == 'missing_endpoint':
        save(root, artifact(number=1, relations=[edge(target=aid(number=99))]))
    elif damage == 'noncanonical':
        save(root, artifact(number=5, relations=[edge('conflicts_with', aid(number=1), 9)]))
    expected = PermissionError if damage == 'unreadable' else ModelError
    context = patch.object(source, 'read_normative', side_effect=PermissionError('original input'))
    if damage == 'unreadable':
        with context, pytest.raises(expected):
            read(source, cache='read')
    else:
        with pytest.raises(expected):
            read(source, cache='read')


@pytest.mark.parametrize('options', [{'cache': 'write'}, {'cache': True}, {'cache_max_bytes': -1},
                                   {'cache_max_bytes': True}, {'cache_max_bytes': 1.5}])
def test_cache_options_reject_invalid_contracts(project, options):
    with pytest.raises(ModelError):
        read(project[1], **options)


def test_real_recorded_module_and_zipapp_use_same_cache_after_distribution_move(project, tmp_path):
    root, source = project
    output = tmp_path / 'built'
    build_distribution(output)
    moved = tmp_path / 'moved-build'
    output.rename(moved)
    code = '''import sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, sys.argv[1])
from specroad.graph.indices import RelationIndex
from specroad.storage.project import ProjectSource
from specroad.storage.relation_index import build_project_relation_index, read_project_relation_views, relation_index_cache_bytes
root = Path(sys.argv[2])
source = ProjectSource(root)
path = root / '.specroad/cache/relation-index-v1.json'
if not path.exists():
    raw = relation_index_cache_bytes(build_project_relation_index(source))
    assert type(raw) is bytes
    path.parent.mkdir(parents=True)
    path.write_bytes(raw)
before = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}
expected = read_project_relation_views(source, sys.argv[3], strategy='scan')
with patch.object(RelationIndex, '__init__', side_effect=AssertionError('cache miss')):
    assert read_project_relation_views(source, sys.argv[3], cache='read') == expected
assert {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()} == before
'''
    for distribution in (moved / 'module', moved / 'specroad.pyz'):
        completed = subprocess.run([sys.executable, '-I', '-S', '-B', '-c', code,
                                    str(distribution), str(root), aid(number=3)],
                                   stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                   stderr=subprocess.PIPE, check=False)
        assert completed.returncode == 0, completed.stderr.decode()
