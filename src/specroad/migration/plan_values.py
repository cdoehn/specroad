"""Owned read-only migration observations, never publication authority."""
from dataclasses import dataclass
from hashlib import sha256
import base64
from ..model.errors import ModelError
from ..model.canonical import canonical_json_bytes as jcs, canonical_json_sha256 as digest
from ..model.paths import project_path
from ..storage.json_syntax import parse_json_object
from .reference01.values import paths

POLICY = 'migration-metadata-v1'
STEP = 'reference01-to-current.v1'
SOURCE_CONTRACT = {'schema_version': '0.1.0', 'contract_sha256':
    '7c4af8bb230fed758267a9a45c4957b26e015e0f112c8ad5d0f42b9b93fee72e'}
MANIFEST_PATH = 'mappings/legacy-manifest.json'


class MigrationPlanError(ModelError):
    def __init__(self, reason, *, path=None, pointer='', exit_code=3):
        super().__init__(reason, path=path, pointer=pointer)
        self.exit_code = exit_code


def require(ok, reason, *, path=None, exit_code=3):
    if not ok:
        raise MigrationPlanError(reason, path=path, exit_code=exit_code)


def b64(raw):
    return base64.b64encode(raw).decode('ascii')


def unb64(value):
    require(type(value) is str, 'migration_bytes_encoding')
    try:
        raw = base64.b64decode(value, validate=True)
    except (ValueError, UnicodeError) as error:
        raise MigrationPlanError('migration_bytes_encoding') from error
    require(b64(raw) == value, 'migration_bytes_encoding')
    return raw


def safe_path(name):
    project_path(name)
    require(not any(part.casefold() in ('.git', '.specroad', '.codex', '.agents', '.aws', '.ssh')
                    for part in name.split('/')), 'migration_protected_path', path=name)
    return name


def source_path(name):
    if name.startswith(".specroad/"):
        from ..model.operational_paths import PASSIVE_ROOTS, PASSIVE_JOURNAL_DIRECTORIES
        roots = tuple(PASSIVE_ROOTS) + tuple(".specroad/" + a + "/" + b for a, b in PASSIVE_JOURNAL_DIRECTORIES)
        require(any(name.startswith(r + "/") for r in roots), "migration_protected_path", path=name)
        safe_path(name[len(".specroad/"):])
        return name
    return safe_path(name)


def owned_files(files, *, passive=False):
    require(type(files) is dict and all(type(n) is str and type(b) is bytes
            for n, b in files.items()), 'migration_file_bytes_required')
    paths(files)
    for name in files:
        (source_path if passive else safe_path)(name)
    names = set(files)
    require(not any('/'.join(n.split('/')[:i]) in names for n in names
                    for i in range(1, len(n.split('/')))), 'migration_path_overlap')
    return dict(files)


def file_bindings(files):
    return [{'path': p, 'size': len(raw), 'sha256': sha256(raw).hexdigest()}
            for p, raw in sorted(files.items(), key=lambda row: row[0].encode('utf-8'))]


def changes(before, after):
    rows = []
    for name in sorted(set(before) | set(after), key=lambda p: p.encode('utf-8')):
        old, new = before.get(name), after.get(name)
        if old == new:
            continue
        rows.append({'path': name, 'before_sha256': None if old is None else sha256(old).hexdigest(),
            'after_sha256': None if new is None else sha256(new).hexdigest(),
            'after_bytes_base64': None if new is None else b64(new)})
    return rows


@dataclass(frozen=True, init=False)
class MigrationPlanning:
    _encoded: bytes

    @classmethod
    def _create(cls, value):
        result = object.__new__(cls)
        object.__setattr__(result, '_encoded', jcs(value))
        return result

    @property
    def data(self):
        return parse_json_object(self._encoded)

    @property
    def canonical_bytes(self):
        return self._encoded

    @property
    def ready(self):
        return self.data['ready']

    @property
    def change_plan(self):
        from ..changes.values import ChangePlan
        value = self.data['change_plan']
        return None if value is None else ChangePlan(jcs(value))

    @property
    def write_authorized(self):
        return False

    def __bool__(self):
        raise TypeError('Inspect ready and blockers explicitly; a plan is not approval')
