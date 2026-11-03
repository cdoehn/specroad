"""Byte-preserving, read-only reference-0.1/1.0.1 inventory.

The source schema family is compiled Core data. No current artifact loader,
writer, project provider, migration registration or approval is used here.
"""
from dataclasses import dataclass
from hashlib import sha256
from importlib import resources
import json
import re
import unicodedata

from ...model._schema import validate_builtin
from ...model.canonical import canonical_json_bytes, canonical_json_sha256
from ...model.errors import ModelError
from ...storage.json_syntax import parse_json_object
from ...security.paths import ProjectBoundary
from ...security.resource_access import directory_entries
from ...storage.operational_preflight import observe_operational_preflight

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
    seen = set()
    for name in names:
        path_name(name)
        key = unicodedata.normalize('NFC', name).casefold()
        require(key not in seen, 'source_identity_conflict', name, 'portable_path_collision')
        seen.add(key)


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
    return ('immutable_legacy' if kind in ('evidence', 'baseline', 'relation_review')
        or kind == 'proposal' and value['proposal_status'] in ('applied', 'rejected', 'stale')
        else 'mutable')


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


class _Reader:
    def __init__(self, files):
        require(type(files) is dict and all(type(k) is str and type(v) is bytes
            for k, v in files.items()), 'source_schema_invalid', detail='owned_byte_mapping_required')
        paths(files)
        self.files = dict(files)
        self.assets = _assets()
        self.snapshots = {}
        self.active = set()
        self.payloads = {}
        self.originals = []
        self.project_id = None

    def needed(self, name, *, raw_sha=None, size=None):
        path_name(name)
        require(name in self.files, 'source_payload_missing', name)
        raw = self.files[name]
        require((raw_sha is None or sha256(raw).hexdigest() == raw_sha)
                and (size is None or len(raw) == size), 'source_hash_mismatch', name)
        return raw

    def qualify(self, files, *, baseline=None):
        paths(files)
        require('specroad.json' in files, 'source_closure_incomplete', 'specroad.json')
        config = parsed(files['specroad.json'], 'specroad.json')
        require('source_contract' in config, 'source_contract_required', 'specroad.json')
        require(config['source_contract'] == {'contract_id': CONTRACT_ID,
                'contract_version': CONTRACT_VERSION}, 'unsupported_source_contract', 'specroad.json')
        _schema(config, 'project.json', self.assets, 'specroad.json')
        if self.project_id is None:
            self.project_id = config['project_id']
        require(config['project_id'] == self.project_id, 'source_identity_conflict', 'specroad.json')
        require('profiles/core-reference01.json' in files, 'source_closure_incomplete')
        profile = parsed(files['profiles/core-reference01.json'], 'profiles/core-reference01.json')
        _schema(profile, 'profile.json', self.assets, 'profiles/core-reference01.json')
        values = {'specroad.json': config, 'profiles/core-reference01.json': profile}
        index, roles, attachments = {}, {'specroad.json': 'configuration',
                                        'profiles/core-reference01.json': 'profile'}, {}
        from .semantics import local_fields, references
        for name, raw in sorted(files.items(), key=lambda row: row[0].encode('utf-8')):
            if name in values:
                continue
            if name.startswith(('profiles/', 'rules/', 'mappings/')):
                raise SourceError('source_resource_unsupported', path=name)
            if not name.startswith('spec/'):
                continue
            require(name.endswith('.json'), 'source_resource_unsupported', name)
            data = parsed(raw, name)
            kind = data.get('artifact_type')
            require(type(kind) is str and kind in self.assets['artifact_types'],
                    'source_schema_invalid', name, 'unknown_artifact_type')
            shape = self.assets['artifact_types'][kind]
            _schema(data, shape['schema'].removeprefix('schemas/'), self.assets, name)
            identity = data['id']
            require(identity.startswith(config['id_prefix'] + '-') and
                    name == 'spec/' + shape['directory'] + '/' + identity + '.json'
                    and identity not in index, 'source_identity_conflict', name)
            values[name] = data; index[identity] = (name, data); roles[name] = 'artifact'
            local_fields(data, name, self.assets)
            for item in data.get('attachments', ()) if kind == 'evidence' else ():
                path_name(item['path'])
                require(item['path'] not in roles and not item['path'].startswith(
                    ('spec/', 'profiles/', 'rules/', 'mappings/', '.git/', '.specroad/', 'generated/'))
                    and item['path'] != 'specroad.json', 'source_identity_conflict', item['path'])
                require(item['path'] not in attachments or attachments[item['path']] == item,
                        'source_identity_conflict', item['path'])
                attachments[item['path']] = item
        require(sum(v.get('document_role') == 'primary_specification' for v in values.values()) == 1,
                'source_closure_incomplete', detail='exactly_one_primary_document')
        for name, data in index.values():
            if data['artifact_type'] == 'code_ref':
                path = data['path']; path_name(path)
                historical = 'git_commit' in data or 'git_blob' in data
                actual = ('archive/objects/' + data['file_sha256'][:2] + '/' + data['file_sha256']
                          if historical else path)
                raw = self.needed(actual, raw_sha=data['file_sha256']) if baseline is None else files.get(path)
                require(raw is not None and sha256(raw).hexdigest() == data['file_sha256'],
                        'source_payload_missing', path)
                if historical:
                    self.payloads[actual] = raw
                if path not in roles:
                    item = {'path': path, 'media_type': 'application/octet-stream', 'size': len(raw),
                            'sha256': data['file_sha256']}
                    require(path not in attachments or attachments[path] == item,
                            'source_identity_conflict', path)
                    attachments[path] = item
                    files = {**files, path: raw}
                from .semantics import code_selection
                code_selection(data, raw, name)
        from .semantics import prose_payloads
        for name, value in index.values():
            for payload_path in prose_payloads(value, name):
                raw = files.get(payload_path)
                if raw is None and baseline is None:
                    raw = self.needed(payload_path)
                require(raw is not None, 'source_payload_missing', payload_path)
                require(payload_path not in roles, 'source_identity_conflict', payload_path)
                if payload_path not in attachments:
                    attachments[payload_path] = {'path': payload_path, 'media_type': 'application/octet-stream',
                        'size': len(raw), 'sha256': sha256(raw).hexdigest()}
                files = {**files, payload_path: raw}
        for name, item in attachments.items():
            raw = files.get(name)
            if raw is None and baseline is None:
                raw = self.needed(name)
            require(raw is not None, 'source_payload_missing', name)
            require(len(raw) == item['size'] and sha256(raw).hexdigest() == item['sha256'],
                    'source_hash_mismatch', name)
            roles[name] = 'attachment'; files = {**files, name: raw}
        entries = []
        for name, role in sorted(roles.items(), key=lambda row: row[0].encode('utf-8')):
            raw = files[name]; value = values.get(name, {})
            entries.append({'path': name, 'role': role, 'artifact_id': value.get('id'),
                'revision': value.get('revision'), 'media_type': 'application/json' if role != 'attachment'
                else attachments[name]['media_type'], 'size': len(raw), 'byte_sha256': sha256(raw).hexdigest(),
                'canonical_sha256': canonical_json_sha256(value) if role != 'attachment' else None})
        root = model_root(config['project_id'], entries)
        if baseline is not None:
            require(entries == baseline['manifest'] and root == baseline['model_root_sha256'],
                    'source_hash_mismatch', detail='snapshot_manifest_or_root')
            require(baseline['project_id'] == config['project_id'] and baseline['id'] not in index,
                    'source_snapshot_cycle', detail='snapshot_self_reference')
        key = canonical_json_sha256(entries)
        require(key not in self.active, 'source_snapshot_cycle')
        if key in self.snapshots:
            return self.snapshots[key]
        self.active.add(key)
        snapshot = {'root': root, 'entries': entries, 'index': index, 'configuration': config,
                    'files': {name: files[name] for name in roles}}
        # Current and historical tuple resolution happens after complete traversal.
        references(snapshot, self.assets)
        from .stored_plans import proposal_basis
        snapshot['proposal_basis'] = proposal_basis(snapshot)
        for name, data in index.values():
            if data['artifact_type'] != 'baseline':
                continue
            manifest = data['manifest']; paths(row['path'] for row in manifest)
            require([r['path'] for r in manifest] == sorted((r['path'] for r in manifest),
                    key=lambda p: p.encode('utf-8')), 'source_schema_invalid', name)
            historical_files = {}
            for row in manifest:
                _schema(row, 'manifest-entry.json', self.assets, name)
                address = 'archive/objects/' + row['byte_sha256'][:2] + '/' + row['byte_sha256']
                raw = self.needed(address, raw_sha=row['byte_sha256'], size=row['size'])
                self.payloads[address] = raw
                historical_files[row['path']] = raw
            previous = self.qualify(historical_files, baseline=data)
            if data['baseline_kind'] == 'release':
                from .semantics import release_selection
                release_selection(data, previous)
        self.active.remove(key)
        self.snapshots[key] = snapshot
        for row in entries:
            self.originals.append(SourceOriginal(row['path'], files[row['path']], row['role'],
                'referenced_payload' if row['role'] == 'attachment' else classification(values[row['path']]), root))
        return snapshot

    def read(self):
        current = self.qualify(self.files)
        from .semantics import historical_bindings
        historical_bindings(tuple(self.snapshots.values()), self.assets)
        result = object.__new__(SourceInventory)
        object.__setattr__(result, 'originals', tuple(self.originals))
        object.__setattr__(result, 'payloads', tuple(sorted(self.payloads.items())))
        object.__setattr__(result, '_encoded', canonical_json_bytes({
            'contract_id': CONTRACT_ID, 'contract_version': CONTRACT_VERSION,
            'contract_manifest_sha256': self.assets['contract_manifest_sha256'], 'legacy_reader_id': READER_ID,
            'project_id': self.project_id, 'model_root_sha256': current['root'],
            'scope_descriptor': SCOPE, 'entries': current['entries'],
            'proposal_basis_sha256': current['proposal_basis'],
            'proposal_bindings': [{'snapshot_root': s['root'], 'proposal_id': value['id'],
                'revision': value['revision'], 'base_model_root_sha256': value['base']['model_root_sha256'],
                'basis_matches_observed_snapshot': value['base']['model_root_sha256'] == s['proposal_basis']}
                for s in self.snapshots.values() for _, value in s['index'].values()
                if value['artifact_type'] == 'proposal'],
            'snapshot_roots': sorted({s['root'] for s in self.snapshots.values()}),
            'originals': [{'path': o.path, 'snapshot_root': o.snapshot_root,
                          'byte_sha256': o.byte_sha256, 'classification': o.classification}
                         for o in self.originals],
            'validation_scope': 'reference_source_schema_and_original_integrity',
            'historical_compatibility_claimed': False, 'human_authority_verified': False,
            'current_readiness_verified': False, 'approval_granted': False,
            'write_authorized': False, 'migration_performed': False}))
        return result


def inventory_bytes(files):
    """Qualify an explicitly owned complete source snapshot, never guess a version."""
    return _Reader(files).read()


def inventory_project(root):
    """Descriptor-bound reads with preflight and full membership/byte rechecks."""
    boundary = ProjectBoundary(root)
    def preflight():
        state = observe_operational_preflight(boundary)
        require(state['consistency_state'] == 'consistent', 'source_state_invalid',
                detail='operational_preflight_requires_completed_state')
    def scan():
        found = []
        pending = ['spec', 'profiles', 'rules', 'mappings', 'archive/objects']
        while pending:
            parent = pending.pop()
            rows = directory_entries(boundary, parent, missing_ok=True)
            if rows is None:
                continue
            paths(name for name, _ in rows)
            for name, directory in rows:
                path = parent + '/' + name
                if directory:
                    pending.append(path)
                else:
                    found.append(path)
        return tuple(sorted(['specroad.json', *found]))
    preflight(); names = scan()
    files = {name: boundary.read_bytes(name) for name in names}
    # Only known typed descriptors can request additional payloads; no arbitrary
    # recursive string scan, URL resolver or import of source code is involved.
    assets = _assets()
    for name in names:
        if not name.startswith('spec/'):
            continue
        value = parsed(files[name], name)
        kind = value.get('artifact_type')
        if kind not in assets['artifact_types']:
            continue
        _schema(value, assets['artifact_types'][kind]['schema'].removeprefix('schemas/'), assets, name)
        from .semantics import prose_payloads
        needed = [a['path'] for a in value.get('attachments', ())] if kind == 'evidence' else []
        needed.extend(prose_payloads(value, name))
        if kind == 'code_ref' and 'git_commit' not in value and 'git_blob' not in value:
            needed.append(value['path'])
        for path in needed:
            path_name(path)
            if path not in files:
                files[path] = boundary.read_bytes(path)
    result = inventory_bytes(files)
    preflight()
    require(scan() == names, 'source_state_invalid', detail='inventory_membership_changed')
    for path, raw in files.items():
        if boundary.read_bytes(path) != raw:
            raise SourceError('source_state_invalid', path=path, detail='source_changed', exit_code=6)
    return result
