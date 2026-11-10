"""Profiles the exact frozen selection within the existing native xdist runner."""
import cProfile
import os
from pathlib import Path
import pstats
import threading
import time

import pytest

from verification_support.collection_identity import test_identity
from verification_support.common import read_object
from .common import digest, encoded, test_key, write_json
from .lines import LineTrace
from .resources import phase_snapshot
from .store import Store


def pytest_addoption(parser):
    parser.addoption('--sr-profile-request', type=Path)


@pytest.hookimpl(trylast=True)
def pytest_configure(config):
    path = config.getoption('sr_profile_request')
    if path is None or config.getoption('collectonly'):
        raise pytest.UsageError('Profiling needs an explicit execution request')
    request, _ = read_object(path)
    root = Path(config.rootpath).resolve()
    import specroad
    from verification_support import pytest_backend
    if (root != Path(request['snapshot']) or
            not Path(specroad.__file__).resolve().is_relative_to(root / 'src') or
            not Path(pytest_backend.__file__).resolve().is_relative_to(root / 'tools') or
            digest(request['pairs']) != request['selection_sha256']):
        raise pytest.UsageError('Profiling imports or selection differ from the frozen snapshot')
    config._sr_profile = request
    if not hasattr(config, 'workerinput'):
        if config.getoption('numprocesses') != len(request['cpus']):
            raise pytest.UsageError('Profiling worker count changed')
        return
    worker = config.workerinput['workerid']
    if not worker.startswith('gw') or not worker[2:].isdigit():
        raise pytest.UsageError('Profiling requires native local xdist workers')
    cpu = request['cpus'][int(worker[2:])]
    if cpu not in os.sched_getaffinity(0):
        raise pytest.UsageError('Selected profiling CPU is no longer available')
    os.sched_setaffinity(0, {cpu})
    config._sr_profile_store = Store(request['database'], Path(request['repository']))
    write_json(Path(request['directory']) / 'raw' / f'worker-{worker}.json',
               dict(worker=worker, cpu=cpu, **phase_snapshot(), root=str(root),
                    package=str(Path(specroad.__file__).resolve()),
                    nice=os.getpriority(os.PRIO_PROCESS, 0)))


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(config, items):
    expected = config._sr_profile['pairs']
    indexed = {item.nodeid: item for item in items}
    if (len(indexed) != len(items) or any(node not in indexed or
            test_identity(indexed[node]) != identity for node, identity in expected.items())):
        raise pytest.UsageError('Collected tests differ from the frozen profiling selection')
    omitted = [item for item in items if item.nodeid not in expected]
    items[:] = [indexed[node] for node in expected]
    config.hook.pytest_deselected(items=omitted)


@pytest.hookimpl(wrapper=True, tryfirst=True)
def pytest_runtest_protocol(item):
    config, stamp = item.config, time.time_ns()
    request, store = config._sr_profile, config._sr_profile_store
    cpu, = os.sched_getaffinity(0)
    store.begin_test(request['run'], item.nodeid, config.workerinput['workerid'],
                     os.getpid(), threading.get_native_id(), cpu, stamp)
    directory = Path(request['directory']) / 'raw' / 'tests' / test_key(item.nodeid)
    directory.mkdir(parents=True)
    lines = None
    try:
        lines = LineTrace(item, directory)
        return (yield)
    finally:
        try:
            if lines is not None:
                lines.close()
        finally:
            store.end_test(request['run'], item.nodeid, time.time_ns())


def phase(item, name):
    config = item.config
    request, store = config._sr_profile, config._sr_profile_store
    directory = Path(request['directory']) / 'raw' / 'tests' / test_key(item.nodeid)
    directory.mkdir(parents=True, exist_ok=True)
    before, profiler = phase_snapshot(), cProfile.Profile()
    profiler.enable()
    try:
        return (yield)
    finally:
        profiler.disable()
        after = phase_snapshot()
        profiler.dump_stats(str(directory / (name + '.pstats')))
        # Retain independent raw bounds even if the SQL write is interrupted.
        write_json(directory / (name + '.json'),
                   dict(nodeid=item.nodeid, phase=name, before=before, after=after))
        store.phase(request['run'], item.nodeid, name, before, after,
                    pstats.Stats(profiler).stats, Path(request['snapshot']))


@pytest.hookimpl(wrapper=True, tryfirst=True)
def pytest_runtest_setup(item):
    return (yield from phase(item, 'setup'))


@pytest.hookimpl(wrapper=True, tryfirst=True)
def pytest_runtest_call(item):
    return (yield from phase(item, 'call'))


@pytest.hookimpl(wrapper=True, tryfirst=True)
def pytest_runtest_teardown(item):
    return (yield from phase(item, 'teardown'))


@pytest.hookimpl(wrapper=True, trylast=True)
def pytest_runtest_makereport(item, call):
    report = yield
    config, request = item.config, item.config._sr_profile
    config._sr_profile_store.phase_outcome(request['run'], item.nodeid, report.when, report.outcome)
    with (Path(request['directory']) / 'raw' / f'reports-{os.getpid()}.jsonl').open('a') as stream:
        stream.write(encoded(dict(nodeid=item.nodeid, phase=report.when,
                                  outcome=report.outcome, time_ns=time.time_ns())) + '\n')
    return report


def pytest_unconfigure(config):
    store = getattr(config, '_sr_profile_store', None)
    if store is not None:
        store.close()
