"""Byte-preserving, read-only reference-0.1/1.0.1 inventory.

The source schema family is compiled Core data. No current artifact loader,
writer, project provider, migration registration or approval is used here.
"""
from dataclasses import dataclass
from functools import lru_cache
from hashlib import sha256
from importlib import resources
import unicodedata

from ...model._schema import validate_builtin
from ...model.canonical import canonical_json_bytes, canonical_json_sha256
from ...model.errors import ModelError
from ...model.history_protection import protected_record
from ...storage.json_syntax import parse_json_object

CONTRACT_ID = 'specroad-reference-0.1'
CONTRACT_VERSION = '1.0.1'
READER_ID = 'specroad.reference01.v1_0_1'
SCOPE = {'scope_version': 'reference01-scope-v1', 'scope_kind': 'project',
         'selector': {}, 'configuration_id': None, 'boundary_policy': 'closed'}
CONTEXT_EXCLUDED = frozenset(('revision', 'created_at', 'created_by', 'updated_at',
    'updated_by', 'maturity', 'implementation_status', 'verification_plan_status',
    'verification_waiver', 'relations', 'tags', 'proposal_status', 'evidence_state',
    'baseline_state', 'review_state'))


class SourceError(ModelError):
    exit_code = 3

    def __init__(self, reason, *, path=None, pointer='', detail=None, exit_code=3):
        super().__init__(reason, path=path, pointer=pointer)
        self.detail = detail
        self.exit_code = exit_code

    def diagnostic(self):
        return {**super().diagnostic(), 'detail': self.detail, 'exit_code': self.exit_code}


def require(ok, reason, path=None, detail=None):
    if not ok:
        raise SourceError(reason, path=path, detail=detail)


def path_name(value):
    require(type(value) is str and bool(value) and not value.startswith('/')
            and '\\' not in value and '\0' not in value
            and all(p not in ('', '.', '..') for p in value.split('/')),
            'source_schema_invalid', detail='relative_posix_path_required')
    try:
        value.encode('utf-8')
    except UnicodeError as error:
        raise SourceError('source_schema_invalid', detail='invalid_path_unicode') from error
    return value


def paths(names):
    seen, prefixes = set(), {}
    for name in names:
        path_name(name)
        key = unicodedata.normalize('NFC', name).casefold()
        require(key not in seen, 'source_identity_conflict', name, 'portable_path_collision')
        seen.add(key)
        parts = name.split('/')
        for index in range(1, len(parts) + 1):
            original = '/'.join(parts[:index])
            portable = unicodedata.normalize('NFC', original).casefold()
            require(portable not in prefixes or prefixes[portable] == original,
                    'source_identity_conflict', name, 'portable_directory_collision')
            prefixes[portable] = original


def parsed(raw, path=None):
    try:
        value = parse_json_object(raw, path=path)
        canonical_json_bytes(value)
        return value
    except ModelError as error:
        raise SourceError('source_schema_invalid', path=path, pointer=error.pointer,
                          detail=error.reason) from error


def context_sha256(value):
    return canonical_json_sha256({k: v for k, v in value.items() if k not in CONTEXT_EXCLUDED})


def model_root(project_id, entries):
    return canonical_json_sha256({'algorithm': 'reference01-model-root-v1',
        'project_id': project_id, 'scope_descriptor': SCOPE,
        'entries': [{k: v for k, v in row.items()
                     if row['role'] == 'attachment' or k not in ('size', 'byte_sha256')}
                    for row in entries]})


def classification(value):
    kind = value.get('artifact_type')
    return 'immutable_legacy' if kind is not None and protected_record(value) else 'mutable'


@dataclass(frozen=True)
class SourceOriginal:
    path: str
    source_bytes: bytes
    role: str
    classification: str
    snapshot_root: str

    @property
    def data(self):
        if self.role == 'attachment':
            raise TypeError('Opaque payloads have no source-model projection')
        return parsed(self.source_bytes, self.path)

    @property
    def byte_sha256(self):
        return sha256(self.source_bytes).hexdigest()

    @property
    def canonical_sha256(self):
        return None if self.role == 'attachment' else canonical_json_sha256(self.data)


@dataclass(frozen=True, init=False)
class SourceInventory:
    """Owned originals and detached observations; never a target/write ticket."""
    originals: tuple
    payloads: tuple
    _encoded: bytes

    @property
    def data(self):
        return parsed(self._encoded)

    @property
    def model_root_sha256(self):
        return self.data['model_root_sha256']

    @property
    def write_authorized(self):
        return False

    @property
    def approval_granted(self):
        return False

    def __bool__(self):
        raise TypeError('A source inventory is not migration or release approval')


@lru_cache(maxsize=1)
def _assets():
    raw = resources.files('specroad.reference01_data').joinpath('contract.json').read_bytes()
    value = parsed(raw)
    # Bound by the installed Core, never a project-selected resource path.
    from ._binding import RESOURCE_SHA256
    require(sha256(raw).hexdigest() == RESOURCE_SHA256,
            'unsupported_source_contract', detail='installed_resource_changed')
    return value


def _schema(value, name, assets, path):
    try:
        validate_builtin(value, assets['schemas'][name])
    except ModelError as error:
        reason = 'source_state_invalid' if error.pointer.startswith(('/maturity', '/proposal_status',
            '/baseline_state', '/evidence_state', '/review_state')) else 'source_schema_invalid'
        raise SourceError(reason, path=path, pointer=error.pointer, detail=error.reason) from error
