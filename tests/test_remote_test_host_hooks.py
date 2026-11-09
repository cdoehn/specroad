"""Regression for the actual xdist registration and per-controller bootstrap."""
import pytest
import xdist.newhooks
import xdist.remote
from xdist.workermanage import WorkerController

from dev.test_hosts import remote_worker
from dev.test_hosts.pytest_pool import RemoteBootstrap
from verification_support import pytest_backend


def test_native_and_host_controllers_keep_independent_valid_bootstrap_hooks():
    def manager():
        result = pytest.PytestPluginManager()
        result.add_hookspecs(xdist.newhooks)
        # Register against the real hook specifications: the previous global
        # hook with a node argument failed here before any test could start.
        result.register(pytest_backend)
        result.register(WorkerController.RemoteHook())
        return result

    local, pool = manager(), manager()
    assert local.hook.pytest_xdist_getremotemodule() is xdist.remote
    hook = RemoteBootstrap()
    pool.register(hook, 'specroad-host-bootstrap')
    assert pool.hook.pytest_xdist_getremotemodule() is remote_worker
    assert local.hook.pytest_xdist_getremotemodule() is xdist.remote
    pool.unregister(hook)
    assert pool.hook.pytest_xdist_getremotemodule() is xdist.remote
