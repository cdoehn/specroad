"""Portable exact environment identity; also executed standalone on remote hosts."""
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import sqlite3
import ssl
import sys
import sysconfig
import zlib


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


def probe():
    return {'environment': environment(), 'hostname': platform.node(),
            'account': account(),
            'uid': os.getuid(), 'tools': {n: bool(shutil.which(n)) for n in ('rsync', 'git', 'ionice')},
            'python': sys.executable}


def account():
    return digest({'machine_id': Path('/etc/machine-id').read_text().strip(), 'uid': os.getuid()})


if __name__ == '__main__':
    print(json.dumps(probe(), sort_keys=True))
