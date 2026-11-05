"""Complete, read-only merge inventory; not a resolved or executable change plan."""
from dataclasses import dataclass
from hashlib import sha256

from ..bundles._payload_model import owned_payload_model
from ..migration.model_inputs import records as model_records
from ..model.canonical import canonical_json_bytes as jcs, canonical_json_sha256 as digest
from ..model.errors import ModelError
from ..model.identity_tokens import decode128
from ..model.language_package_values import LanguagePackage
from ..model.manifest_resources import project_json_resource
from ..model.paths import PathClass, classify_path
from ..model.resource_inventory import ResourceEntry, ResourceInventory
from ..storage.json_syntax import parse_json_object
from .sources import MergeSources


ROLES = ('base', 'ours', 'theirs')
FORMAT = 'merge-inventory-v1'
BINDING_FIELDS = ('path', 'pointer', 'size', 'byte_sha256', 'value_sha256',
                  'value_domain', 'owner_id', 'id_scheme', 'storage_class')


def _plan_id(value):
    if type(value) is not str or not value.startswith('MP-'):
        raise ModelError('merge_inventory_plan_id')
    decode128(value[3:])
    return value


def _identity(kind, identifier, version=None):
    return {'kind': kind, 'id': identifier, 'version': version}


def _present(path, raw, *, value=None, domain='json-v1', pointer='', owner=None,
             scheme=None, storage='current'):
    return {'state': 'present', 'path': path, 'pointer': pointer,
        'size': len(raw), 'byte_sha256': sha256(raw).hexdigest(),
        'value_sha256': sha256(raw).hexdigest() if domain == 'bytes-v1' else digest(value),
        'value_domain': domain, 'owner_id': owner, 'id_scheme': scheme,
        'storage_class': storage}


def _absent():
    return {'state': 'absent', **dict.fromkeys(BINDING_FIELDS)}


def _source_rows(source):
    """Use native resource identities; keep every actual file and relation."""
    files, binding = source.files, source.binding
    keys = tuple(binding['baseline']['profile_keys']) if source.kind == 'baseline' else None
    model = owned_payload_model(files, source_label='merge-inventory:' + source.source_root,
                                profile_keys=keys)
    records = {record.path: record for record in model_records(model)}
    registry = model.configuration.data.get('language_registry')
    registry_path = None if registry is None else registry['path']
    rows, entries = {}, []

    def add(identity, observation):
        key = jcs(identity)
        if key in rows:
            raise ModelError('merge_inventory_duplicate_identity', path=observation['path'])
        rows[key] = (identity, observation)

    for path, raw in sorted(files.items(), key=lambda item: item[0].encode('utf-8')):
        kind = classify_path(path, model.configuration)
        if path == 'specroad.json':
            identity = _identity('configuration', model.configuration.project_id)
            observation = _present(path, raw, value=parse_json_object(raw))
        elif kind is PathClass.ARTIFACT:
            record = records[path]
            identity = _identity('artifact', record.identity.id)
            observation = _present(path, raw, value=record.data,
                scheme=record.identity.id_scheme, storage=record.storage_class)
            for index, relation in enumerate(record.relations):
                add(_identity('relation', relation.identity.id),
                    _present(path, raw, value=relation.data, domain='relation-navigation-v1',
                        pointer='/relations/'+str(index), owner=record.identity.id,
                        scheme=relation.identity.id_scheme, storage=record.storage_class))
        elif path == registry_path:
            identity = _identity('language_registry', registry['registry_id'], model.language_registry.version)
            observation = _present(path, raw, domain='bytes-v1')
        elif kind in (PathClass.ATTACHMENT, PathClass.ARCHIVE_OBJECT):
            identity = _identity('attachment' if kind is PathClass.ATTACHMENT else 'archive', path)
            observation = _present(path, raw, domain='bytes-v1')
        elif kind in (PathClass.PROFILE, PathClass.RULE, PathClass.MAPPING):
            value = parse_json_object(raw, path=path)
            if kind is PathClass.PROFILE and 'package_id' in value:
                package = LanguagePackage(raw)
                identity = _identity('language_package', package.package_id, package.version)
            else:
                native = project_json_resource(model.configuration, path, raw, model.binding).data
                identity = _identity(native['kind'], native['id'], native['version'])
            observation = _present(path, raw, value=value)
        else:
            raise ModelError('merge_inventory_unclassified_resource', path=path)
        add(identity, observation)
        entries.append(ResourceEntry(path, identity['kind'], len(raw), observation['byte_sha256'],
            None if observation['value_domain'] == 'bytes-v1' else observation['value_sha256']))
    inventory = ResourceInventory(source.project_id, tuple(entries), source.source_root, (0, 0))
    actual = [{'path': entry.path, 'size': entry.size, 'sha256': entry.sha256}
              for entry in inventory.entries]
    if (actual != binding['resources']
            or binding['project_id'] != model.configuration.project_id
            or binding['schema_version'] != model.configuration.data['schema_version']
            or any(binding[name] != getattr(source, name)
                   for name in ('kind', 'source_root', 'commit_id', 'project_id', 'schema_version'))
            or model.manifest(model.artifacts, binding['scope_descriptor']).sha256
               != binding['model_root_sha256']):
        raise ModelError('merge_inventory_source_binding_mismatch')
    return rows, inventory


def _signature(identity, observation):
    if observation['state'] == 'absent':
        return None
    names = (('value_sha256', 'owner_id', 'id_scheme', 'storage_class')
             if identity['kind'] == 'relation' else
             ('path', 'byte_sha256', 'value_domain', 'id_scheme', 'storage_class'))
    return tuple(observation[name] for name in names)


@dataclass(frozen=True, init=False)
class MergeInventory:
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
    def sha256(self):
        return sha256(self._encoded).hexdigest()

    @property
    def ready(self):
        return False

    @property
    def write_authorized(self):
        return False

    def __bool__(self):
        raise TypeError('A merge inventory is not a resolved merge or write authority')


def build_merge_inventory(sources, *, plan_id):
    """Bind all original files and native relations without inventing deletions."""
    if type(sources) is not MergeSources:
        raise ModelError('merge_sources_required')
    _plan_id(plan_id)
    observed = {}
    for role in ROLES:
        source = getattr(sources, role)
        source.verify_current()
        observed[role], _ = _source_rows(source)
    rows = []
    for key in sorted(set().union(*(set(observed[role]) for role in ROLES))):
        identity = next(observed[role][key][0] for role in ROLES if key in observed[role])
        values = {role: observed[role][key][1] if key in observed[role] else _absent() for role in ROLES}
        signatures = [_signature(identity, values[role]) for role in ROLES]
        same = all(value is not None for value in signatures) and signatures[0] == signatures[1] == signatures[2]
        reasons = [] if same else ['semantic_planning_required']
        if any(values[role]['state'] == 'absent' for role in ROLES):
            reasons.append('absence_not_deletion')
        rows.append({'identity': identity, **values,
            'target_classification': 'unchanged_ours' if same else 'conflict',
            'pending_reasons': reasons})
    bindings = sources.binding
    files = [getattr(sources, role).files for role in ROLES]
    roots = [bindings[role]['model_root_sha256'] for role in ROLES]
    expected = roots[1] if files[0] == files[1] == files[2] and roots[0] == roots[1] == roots[2] else None
    for role in ROLES:
        getattr(sources, role).verify_current()
    return MergeInventory._create({'inventory_format_version': FORMAT, 'plan_id': plan_id,
        'metadata_policy_version': 'merge-metadata-v1', 'project_id': sources.ours.project_id,
        'schema_version': sources.ours.schema_version, 'source_bindings': bindings,
        'source_bindings_sha256': digest(bindings), 'resources': rows,
        'inventory_sha256': digest(rows), 'expected_target_model_root_sha256': expected,
        'ready': False, 'write_authorized': False})


def read_merge_inventory(raw, sources):
    """Rebuild against original native sources; rehashed claims are not proof."""
    if type(raw) is not bytes:
        raise ModelError('merge_inventory_bytes_required')
    value = parse_json_object(raw)
    if value.get('inventory_format_version') != FORMAT:
        raise ModelError('merge_inventory_version')
    expected = build_merge_inventory(sources, plan_id=value.get('plan_id'))
    # Comparing exact canonical bytes also rejects extra/missing fields, false
    # versus zero, reordered rows, duplicate keys and noncanonical encodings.
    if raw != expected.canonical_bytes:
        raise ModelError('merge_inventory_binding_mismatch')
    return expected
