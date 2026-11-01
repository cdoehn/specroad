"""Passive PYZ identity checked against the trusted running Core payload."""
import ast
from hashlib import sha256
from importlib.resources import files
from io import BytesIO
import json
import stat
from zipfile import ZipFile, BadZipFile

from .. import __version__, _build
from ..runtime.distribution import distribution_identity
from ..storage.archive import validate_portable_archive_paths
from ._files import PassiveFile, require


MAIN = b'from specroad.cli import main\nraise SystemExit(main())\n'
ALGORITHM = 'specroad-dev-payload-v1'
_RESOURCES = frozenset(('profile_data/profiles.json', 'profile_data/core.json',
    'profile_data/software-de.json', 'profile_data/software-en.json', 'language_data/registry.txt',
    'language_data/snapshot.json', 'language_data/packages.json', 'language_data/minimum_corpus.json',
    *('language_data/packages/' + tag + '.json' for tag in
      ('de', 'en', 'hi', 'id', 'pt', 'es', 'ru', 'ja', 'zh-Hans'))))


def payload_hash(payload):
    hashes = {name: sha256(raw).hexdigest() for name, raw in payload.items()
              if name != 'specroad/_build.py'}
    raw = json.dumps(hashes, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()
    return sha256(ALGORITHM.encode() + b'\0' + raw).hexdigest()


def current_payload():
    result = {'__main__.py': MAIN}
    pending = [('', files('specroad'))]
    while pending:
        prefix, root = pending.pop()
        for item in root.iterdir():
            name = prefix + item.name
            if item.is_dir():
                if item.name != '__pycache__':
                    pending.append((name + '/', item))
            elif name.endswith('.py') or name in _RESOURCES:
                if name != '_build.py':
                    result['specroad/' + name] = item.read_bytes()
    return result


def _record(raw):
    tree = ast.parse(raw.decode('utf-8'))
    require(len(tree.body) == 2 and isinstance(tree.body[0], ast.Expr)
            and isinstance(tree.body[0].value, ast.Constant)
            and type(tree.body[0].value.value) is str
            and isinstance(tree.body[1], ast.Assign)
            and len(tree.body[1].targets) == 1
            and isinstance(tree.body[1].targets[0], ast.Name)
            and tree.body[1].targets[0].id == 'BUILD_METADATA', 'invalid_core_build_record')
    return ast.literal_eval(tree.body[1].value)


def core_artifact(path, digest):
    captured = PassiveFile(path, expected_sha256=digest)
    try:
        with ZipFile(BytesIO(captured.raw)) as archive:
            infos = archive.infolist()
            require(len(infos) < 10000, 'core_artifact_limit')
            names = [i.filename.rstrip('/') for i in infos]
            require(len(names) == len(set(names)), 'core_artifact_collision')
            validate_portable_archive_paths([i.filename for i in infos if not i.is_dir()])
            for info in infos:
                if info.is_dir():
                    validate_portable_archive_paths([info.filename.rstrip('/')])
            require(sum(i.file_size for i in infos) <= 256 * 1024 * 1024, 'core_artifact_limit')
            payload = {}
            for info in infos:
                kind = stat.S_IFMT(info.external_attr >> 16)
                require(kind in ((0, stat.S_IFDIR) if info.is_dir() else (0, stat.S_IFREG))
                        and not info.flag_bits & 1, 'unsafe_core_artifact')
                if not info.is_dir():
                    payload[info.filename] = archive.read(info)
        require('specroad/_build.py' in payload, 'core_build_record_missing')
        record = _record(payload['specroad/_build.py'])
        identity = distribution_identity(record, loader=None)
        current = current_payload()
        require({n: b for n, b in payload.items() if n != 'specroad/_build.py'} == current,
                'core_distribution_mismatch')
        require(identity['build_sha256'] == payload_hash(payload) == payload_hash(current),
                'core_build_hash_mismatch')
        if _build.BUILD_METADATA is not None:
            own = distribution_identity(_build.BUILD_METADATA, loader=None)
            require(own['build_sha256'] == identity['build_sha256'], 'running_core_build_mismatch')
    except (BadZipFile, SyntaxError, UnicodeError, ValueError, KeyError) as error:
        from .snapshots import TransportFailure
        if isinstance(error, TransportFailure):
            raise
        raise TransportFailure(7, reason='invalid_core_artifact', cause_type=type(error).__name__) from error
    captured.verify_current()
    return captured, {'path': 'runtime/specroad.pyz', 'tool_version': __version__,
        'artifact_sha256': captured.sha256, 'build_hash_algorithm': ALGORITHM,
        'build_sha256': identity['build_sha256'],
        'supported_cpython': ['3.10', '3.11', '3.12', '3.13', '3.14'],
        'platform_profile': 'linux-x86_64'}
