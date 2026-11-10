"""Explicit future collect-only subprocess; never called by status or export."""
from verification_support.catalog_check import CollectionProbe
from verification_support.collection_identity import test_identity
from verification_support.common import read_object
from verification_support.identity import source_identity

from .common import write_json


def pytest_arguments(root):
    return ['-c', str(root / 'pyproject.toml'), '--rootdir', str(root),
            '--confcutdir', str(root), '-o', 'addopts=', '--disable-plugin-autoload',
            '-p', 'no:cacheprovider', '-p', 'no:doctest']


def collect(root, request_path, output):
    import pytest

    class Probe(CollectionProbe):
        @pytest.hookimpl(trylast=True)
        def pytest_collection_modifyitems(self, items):
            # Overlapping user selections are a union, not a request to repeat.
            unique = {}
            for item in items:
                previous = unique.get(item.nodeid)
                if previous is not None and test_identity(previous) != test_identity(item):
                    raise ValueError('Conflicting test identities')
                unique[item.nodeid] = item
            items[:] = unique.values()

    request, _ = read_object(request_path)
    probe, before = Probe(), source_identity(root)
    args = pytest_arguments(root) + ['--collect-only', '-qq']
    for option, field in (('-k', 'keyword'), ('-m', 'marker')):
        if request[field]:
            args += [option, request[field]]
    args += [str(root / selector.split('::', 1)[0]) +
             ('::' + selector.split('::', 1)[1] if '::' in selector else '')
             for selector in request['selectors']]
    code = int(pytest.main(args, plugins=[probe]))
    pairs = dict(probe.pairs)
    valid = (code == 0 and not probe.collection_failed and probe.tests_started == 0
             and bool(pairs) and len(pairs) == len(probe.pairs)
             and len(set(pairs.values())) == len(pairs)
             and source_identity(root) == before == request['source_sha256'])
    write_json(output, dict(valid=valid, exit_code=code, tests_started=probe.tests_started,
                            source_sha256=before, pairs=pairs))
    return 0 if valid else 1
