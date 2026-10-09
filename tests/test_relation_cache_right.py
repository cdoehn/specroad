"""Native cache faults and cheap fallback without changing original inputs."""

from contextlib import contextmanager
import errno
import json
import os
from pathlib import Path
import tempfile
import tracemalloc
from unittest.mock import patch

import pytest

from specroad.graph.indices import RelationIndex
from specroad.model.canonical import canonical_json_bytes
from specroad.model.errors import ModelError
from specroad.storage import _relation_cache as adapter
from specroad.storage.project import ProjectSource
from specroad.storage.relation_index import build_project_relation_index, relation_index_cache_bytes
from support.model import configuration_file, put
from support.processes import run_core
from support.read_only import inventory, no_write_attempts
from support.relations import aid, artifact, edge
from test_relation_index import save
from test_relation_cache_work import project, recorded_build, install_cache, read


@pytest.mark.parametrize('block', [1, 17, 65536])
def test_native_short_reads_keep_a_real_hit_with_exact_total_allowance(project, recorded_build, block):
    root, source = project
    cache = install_cache(project)
    expected = read(source, strategy='scan')
    original = os.read
    calls = []
    def short(fd, amount):
        raw = original(fd, min(amount, block))
        calls.append((amount, len(raw)))
        return raw
    before = inventory(root)
    with patch.object(adapter.os, 'read', side_effect=short), no_write_attempts(), \
            patch.object(RelationIndex, '__init__', side_effect=AssertionError('not a hit')):
        actual = read(source, cache='read', cache_max_bytes=cache.stat().st_size)
    assert actual == expected
    assert sum(n for requested, n in calls) == cache.stat().st_size
    assert all(0 < actual <= requested <= 65536 for requested, actual in calls)
    assert inventory(root) == before


@pytest.mark.parametrize('shape', ['deep_array', 'deep_object', 'wide_array'])
def test_excessive_optional_structure_is_skipped_before_json_decode(project, recorded_build, shape):
    root, source = project
    cache = install_cache(project)
    if shape == 'deep_array':
        raw = b'{"extra":' + b'[' * 50 + b'0' + b']' * 50 + b'}'
    elif shape == 'deep_object':
        raw = b'{"extra":' * 50 + b'0' + b'}' * 50
    else:
        raw = b'{"extra":[' + b'0,' * 20000 + b'0]}'
    cache.write_bytes(raw)
    expected = read(source)
    before = inventory(root)
    with patch.object(adapter, 'parse_json_object', side_effect=AssertionError('expensive decode')), no_write_attempts():
        assert read(source, cache='read') == expected
    assert inventory(root) == before


def test_quoted_brackets_escaped_quotes_and_slashes_across_blocks_reach_strict_decoder(project, recorded_build):
    root, source = project
    cache = install_cache(project)
    entry = json.loads(cache.read_bytes())
    entry['unknown'] = ('[{}],:' + '"' + '\\') * 100
    cache.write_bytes(canonical_json_bytes(entry))
    decode = adapter.parse_json_object
    native_read = os.read
    decoded = []
    def decoding(raw, **kwargs):
        decoded.append(decode(raw, **kwargs))
        return decoded[-1]
    with patch.object(adapter.os, 'read', side_effect=lambda fd, n: native_read(fd, min(n, 1))), \
            patch.object(adapter, 'parse_json_object', side_effect=decoding), no_write_attempts():
        assert read(source, cache='read') == read(source, strategy='scan')
    assert decoded == [entry]


@pytest.mark.parametrize('raw', [b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":Infinity}', b'{"a":"\xff"}',
                                 b'{"a":"\\ud800"}', b'{"a":1}{}', b'[]', b'{"a":'])
def test_malformed_cache_values_remain_local_misses(project, recorded_build, raw):
    root, source = project
    cache = install_cache(project)
    cache.write_bytes(raw)
    before = inventory(root)
    with no_write_attempts():
        assert read(source, cache='read') == read(source, strategy='scan')
    assert inventory(root) == before


@pytest.mark.parametrize('change', ['replace', 'truncate', 'grow', 'remove', 'same_size_mtime'])
def test_cache_change_during_native_read_discards_the_observation(project, recorded_build, change):
    root, source = project
    cache = install_cache(project)
    original = os.read
    changed = []
    def racing(fd, amount):
        raw = original(fd, amount)
        if not changed:
            prior = cache.stat()
            if change == 'replace':
                replacement = root / 'replacement-cache.json'
                replacement.write_bytes(cache.read_bytes())
                os.replace(replacement, cache)
            elif change == 'truncate':
                cache.write_bytes(b'{}')
            elif change == 'grow':
                with cache.open('ab') as stream:
                    stream.write(b' ')
            elif change == 'remove':
                cache.unlink()
            else:
                old = cache.read_bytes()
                new = old.replace(b'"policy"', b'"policz"')
                assert new != old and len(new) == len(old)
                cache.write_bytes(new)
                os.utime(cache, ns=(prior.st_atime_ns, prior.st_mtime_ns))
            changed.append(inventory(root))
        return raw
    expected = read(source, strategy='scan')
    with patch.object(adapter.os, 'read', side_effect=racing), \
            patch.object(adapter, 'parse_json_object', side_effect=AssertionError('changed cache decoded')):
        assert read(source, cache='read') == expected
    assert len(changed) == 1 and inventory(root) == changed[0]


def test_original_source_change_during_cache_read_stays_an_error(project, recorded_build):
    root, source = project
    install_cache(project)
    original = os.read
    changed = []
    def racing(fd, amount):
        raw = original(fd, amount)
        if not changed:
            save(root, artifact(number=77, relations=[edge(target=aid(number=3), number=77)]))
            changed.append(inventory(root))
        return raw
    with patch.object(adapter.os, 'read', side_effect=racing), pytest.raises(ModelError) as caught:
        read(source, cache='read')
    assert caught.value.reason == 'relation_index_membership_changed'
    assert inventory(root) == changed[0]


@pytest.mark.parametrize('stage', ['allocation', 'read', 'decode', 'verify_order'])
def test_optional_memory_failure_releases_descriptors_and_rebuilds_once(project, recorded_build, stage):
    root, source = project
    install_cache(project)
    expected = read(source)
    original = adapter.opened_resource
    descriptors = []
    @contextmanager
    def opened(*args, **kwargs):
        with original(*args, **kwargs) as pair:
            descriptors.append(pair[0])
            yield pair
    target, name = {'allocation': (adapter, 'bytearray'), 'read': (adapter.os, 'read'),
                    'decode': (adapter, 'parse_json_object'), 'verify_order': (RelationIndex, 'from_order')}[stage]
    before = inventory(root)
    with patch.object(adapter, 'opened_resource', opened), \
            patch.object(target, name, create=stage == 'allocation', side_effect=MemoryError('labelled optional failure')) as failed, \
            no_write_attempts():
        assert read(source, cache='read') == expected
    assert failed.call_count == 1 and len(descriptors) == 1
    with pytest.raises(OSError) as caught:
        os.fstat(descriptors[0])
    assert caught.value.errno == errno.EBADF
    assert inventory(root) == before


@pytest.mark.parametrize('failure', [PermissionError(errno.EACCES, 'denied'), OSError(errno.EIO, 'IO'),
                                    OSError(errno.EMFILE, 'descriptors'), OSError(errno.ENOMEM, 'memory')])
def test_optional_native_api_errors_do_not_retry_or_write(project, recorded_build, failure):
    root, source = project
    install_cache(project)
    expected = read(source)
    before = inventory(root)
    native = os.read
    consumed = []
    def failing(fd, count):
        consumed.append(native(fd, min(count, 11)))
        raise failure
    with patch.object(adapter.os, 'read', side_effect=failing), no_write_attempts():
        assert read(source, cache='read') == expected
    assert len(consumed) == 1 and len(consumed[0]) == 11
    assert inventory(root) == before


@pytest.mark.parametrize('failure', [RuntimeError('bug'), TypeError('bug'), KeyboardInterrupt()],
                         ids=['runtime', 'type', 'interrupt'])
def test_programming_errors_and_interrupts_propagate_without_cache_retry(project, recorded_build, failure):
    root, source = project
    install_cache(project)
    before = inventory(root)
    with patch.object(adapter.os, 'read', side_effect=failure) as failed, no_write_attempts(), \
            pytest.raises(type(failure)) as caught:
        read(source, cache='read')
    assert caught.value is failure and failed.call_count == 1
    assert inventory(root) == before


def test_budget_smaller_than_cache_extent_does_not_consume_or_decode_it(project, recorded_build):
    root, source = project
    cache = install_cache(project)
    before = inventory(root)
    with patch.object(adapter.os, 'read', side_effect=AssertionError('unnecessary native read')), \
            patch.object(adapter, 'parse_json_object', side_effect=AssertionError('unnecessary decode')), no_write_attempts():
        assert read(source, cache='read', cache_max_bytes=cache.stat().st_size - 1) == read(source)
    assert inventory(root) == before


def test_one_byte_short_reads_do_not_retain_one_object_per_fragment(project, recorded_build):
    root, source = project
    cache = install_cache(project)
    raw = b'{"padding":"' + b'x' * (160 * 1024) + b'"}'
    cache.write_bytes(raw)
    native = os.read
    calls = 0
    def short(fd, amount):
        nonlocal calls
        calls += 1
        return native(fd, min(amount, 1))
    # Measures only this owned adapter allocation window, not process RSS,
    # source loading, JSON decoding or an asserted host memory capacity.
    # A plain function avoids Mock recording every read in the measured window.
    with patch.object(adapter.os, 'read', short):
        tracemalloc.start()
        try:
            actual = adapter._read_cache(source.boundary, len(raw), 256)
            current, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
    assert actual == raw and calls == len(raw)
    assert peak < 1024 * 1024


def test_empty_project_has_a_valid_complete_cache(project, recorded_build):
    root, source = project
    with tempfile.TemporaryDirectory() as directory:
        empty = Path(directory)
        configuration_file(empty)
        current = ProjectSource(empty)
        index = build_project_relation_index(current)
        raw = relation_index_cache_bytes(index)
        put(empty, adapter.CACHE_PATH, raw)
        from specroad.storage._relation_snapshot import _capture_sources
        from specroad.graph.references import RelationReferences
        snapshot = _capture_sources(current)
        with no_write_attempts(), patch.object(RelationIndex, '__init__', side_effect=AssertionError('rebuild')):
            result = adapter.read_cache(current, snapshot, RelationReferences(snapshot.records), len(raw))
        assert result is not None and result.references.sources == () and result.references.relations == ()


_NATIVE = '''
from contextlib import contextmanager
import errno, json, os, resource
from specroad import _build
from specroad.storage import _relation_cache as adapter
from specroad.storage.project import ProjectSource
from specroad.storage.relation_index import read_project_relation_views
_build.BUILD_METADATA = {'format_version': 1, 'hash_algorithm': 'specroad-dev-payload-v1', 'build_sha256': 'a' * 64}
source = ProjectSource('.')
expected = read_project_relation_views(source, TARGET, strategy='scan')
native = adapter.opened_resource
observed = []
'''


def test_real_descriptor_refusal_is_cache_miss_after_limit_restoration(project, recorded_build):
    root, source = project
    install_cache(project)
    before = inventory(root)
    body = 'TARGET = ' + repr(aid(number=3)) + '\n' + _NATIVE + '''
@contextmanager
def opened(*args, **kwargs):
    previous = resource.getrlimit(resource.RLIMIT_NOFILE)
    try:
        resource.setrlimit(resource.RLIMIT_NOFILE, (0, previous[1]))
        with native(*args, **kwargs) as value:
            yield value
    except OSError as error:
        observed.append(error.errno)
        raise
    finally:
        resource.setrlimit(resource.RLIMIT_NOFILE, previous)
adapter.opened_resource = opened
actual = read_project_relation_views(source, TARGET, cache='read')
assert actual == expected and observed == [errno.EMFILE]
print(json.dumps({'same_result': True, 'native_errno': observed}))
'''
    completed = run_core(body, root, capture=True)
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout) == {'same_result': True, 'native_errno': [errno.EMFILE]}
    assert inventory(root) == before


def test_real_permission_denial_does_not_block_original_project(recorded_build):
    with tempfile.TemporaryDirectory(prefix='specroad-cache-denied-') as directory:
        root = Path(directory)
        root.chmod(0o755)
        configuration_file(root)
        save(root, artifact(number=1, relations=[edge(target=aid(number=2))]))
        save(root, artifact(number=2))
        source = ProjectSource(root)
        cache = install_cache((root, source))
        before = inventory(root)
        mode = cache.stat().st_mode & 0o777
        cache.chmod(0)
        body = 'TARGET = ' + repr(aid(number=2)) + '\n' + _NATIVE + '''
if os.geteuid() == 0:
    import pwd
    nobody = pwd.getpwnam('nobody')
    os.setgroups([])
    os.setgid(nobody.pw_gid)
    os.setuid(nobody.pw_uid)
@contextmanager
def opened(*args, **kwargs):
    try:
        with native(*args, **kwargs) as value:
            yield value
    except OSError as error:
        observed.append(error.errno)
        raise
adapter.opened_resource = opened
actual = read_project_relation_views(source, TARGET, cache='read')
assert actual == expected and observed == [errno.EACCES]
print(json.dumps({'same_result': True, 'native_errno': observed}))
'''
        try:
            completed = run_core(body, root, capture=True)
        finally:
            cache.chmod(mode)
        assert completed.returncode == 0, completed.stderr
        assert json.loads(completed.stdout) == {'same_result': True, 'native_errno': [errno.EACCES]}
        assert inventory(root) == before


def test_real_refused_allocation_in_labelled_cache_allocator_falls_back(project, recorded_build):
    root, source = project
    install_cache(project)
    before = inventory(root)
    body = 'TARGET = ' + repr(aid(number=3)) + '\n' + _NATIVE + '''
def refused():
    # Labelled stand-in: a native failed allocation under this child's limit,
    # not a claim that the real cache initializer needs one TiB of memory.
    previous = resource.getrlimit(resource.RLIMIT_AS)
    try:
        resource.setrlimit(resource.RLIMIT_AS, (0, previous[1]))
        bytearray(1 << 40)
    except MemoryError:
        observed.append('native_allocation_refused')
        raise
    finally:
        resource.setrlimit(resource.RLIMIT_AS, previous)
adapter.bytearray = refused
actual = read_project_relation_views(source, TARGET, cache='read')
assert actual == expected and observed == ['native_allocation_refused']
print(json.dumps({'same_result': True, 'observed': observed}))
'''
    completed = run_core(body, root, capture=True)
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout) == {'same_result': True, 'observed': ['native_allocation_refused']}
    assert inventory(root) == before
