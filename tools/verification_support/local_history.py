"""Local runner history with one host/environment capture per process."""
import hashlib
import importlib.metadata
import json
import platform
import sqlite3
import ssl
import sysconfig
import zlib

from .runtime_history import RuntimeHistory


def environment():
    packages = {}
    for distribution in importlib.metadata.distributions():
        name = distribution.metadata['Name'].lower().replace('_', '-').replace('.', '-')
        if name in ('specroad', 'uv'):
            continue
        if name in packages and packages[name] != distribution.version:
            raise ValueError('Ambiguous installed distribution')
        packages[name] = distribution.version
    return dict(implementation=platform.python_implementation(), python=platform.python_version(),
                machine=platform.machine(), system=platform.system(),
                soabi=sysconfig.get_config_var('SOABI'),
                sqlite=sqlite3.sqlite_version, openssl=ssl.OPENSSL_VERSION, zlib=zlib.ZLIB_RUNTIME_VERSION,
                free_threaded=bool(sysconfig.get_config_var('Py_GIL_DISABLED')),
                packages=dict(sorted(packages.items())))

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

class LocalRuntimeHistory(RuntimeHistory):
    """Tag newly started local attempts without relabelling old measurements."""

    def __init__(self, root, *, path=None):
        self.local_host = platform.node()
        self.local_environment = digest(environment())
        if not isinstance(self.local_host, str) or not self.local_host.strip():
            raise ValueError('Local runtime history requires an observed hostname')
        super().__init__(root, path=path)

    def start(self, run, node, identity, worker):
        super().start(run, node, identity, worker,
                      host=self.local_host, environment=self.local_environment)
