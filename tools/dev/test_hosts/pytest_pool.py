"""Small adapter between the existing verification hooks and host execution."""
import os
import platform

import pytest

from verification_support.identity import source_identity
from .config import read_json
from .environment import digest
from .history import HistoryServer
from .lease import Lease, io_priority
from .contract import public_proof, validate_profile


class RemoteBootstrap:
    """One controller-local hook; xdist's native hook takes no arguments."""

    @pytest.hookimpl(tryfirst=True)
    def pytest_xdist_getremotemodule(self):
        from . import remote_worker
        return remote_worker


def configure(config, root):
    path = config.getoption('sr_host_run')
    worker = getattr(config, 'workerinput', {}).get('sr_pool_worker')
    if path is None and worker is None:
        return
    if config.getoption('collectonly') or config.getoption('sr_ci_plan') is not None or config.getoption('sr_gate'):
        raise ValueError('Host pools belong only to selected Apply execution')
    if worker is not None:
        from verification_support.cpu_capacity import available_cpus
        if available_cpus() != worker['resources']['available_cpus']:
            raise ValueError('Host CPU capacity changed after preparation')
        config._sr_pool_lease = Lease(worker['budget'])
        config._sr_pool_io = io_priority()
        return
    if os.environ.get('SPECROAD_NESTED_TEST_RUN') == '1':
        raise ValueError('Nested test runners cannot open a host pool')
    profile = validate_profile(read_json(path))
    if profile['format_version'] != 1 or profile['source_sha256'] != source_identity(root) or not profile['workers']:
        raise ValueError('Stale or invalid host run')
    config._sr_host_profile = profile
    config.pluginmanager.register(RemoteBootstrap(), "specroad-host-bootstrap")
    config._sr_pool_servers = []
    config._sr_pool_outputs = {}
    config.option.numprocesses = len(profile['workers'])
    config.option.tx = [profile['workers'][name]['spec'] for name in sorted(profile['workers'], key=lambda n: int(n[2:]))]
    config.option.px = profile['proxies']
    config.option.maxworkerrestart = 0


def setup_node(node, state):
    profile = getattr(node.config, '_sr_host_profile', None)
    if profile is None:
        return
    row = profile['workers'][node.gateway.id]
    node.workerinput['sr_host_resources'] = row['resources']
    node.workerinput['sr_pool_worker'] = {**row, 'source_sha256': profile['source_sha256'],
        'snapshot_sha256': profile['snapshot_sha256'], 'selected': list(profile['selected'])}
    channel = node.gateway.newchannel()
    server = HistoryServer(channel, state.history_root, state.history_run, node.gateway.id,
                           row['host'], row['environment_sha256'], profile['selected'])
    channel.setcallback(server.receive, endmarker=None)
    node.config._sr_pool_servers.append(server)
    node.workerinput['sr_history_channel'] = channel


def worker_proof(config, resources):
    row = config.workerinput['sr_pool_worker']
    from .environment import environment, account
    from .snapshot import inventory, fingerprint
    if (source_identity(row['root']) != row['source_sha256']
            or fingerprint(inventory(row['root'])) != row['snapshot_sha256']
            or digest(environment()) != row['environment_sha256']):
        raise ValueError('Worker source or environment changed during tests')
    return {k: row[k] for k in ('host', 'environment_sha256', 'source_sha256', 'snapshot_sha256')} | {
        'hostname': platform.node(),
        'account': account(),
        'resources': resources, 'io_priority': config._sr_pool_io, 'slot': config._sr_pool_lease.slot}


def observation(config):
    profile = getattr(config, '_sr_host_profile', None)
    if profile is None:
        return None
    return {'binding': public_proof(profile), 'workers': config._sr_pool_outputs,
            'errors': [e for server in config._sr_pool_servers for e in server.errors]}


def close(config):
    lease = getattr(config, '_sr_pool_lease', None)
    if lease is not None:
        lease.close()
