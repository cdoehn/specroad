"""Native complete resource observations shared by snapshot consumers.

Returns the existing ResourceInventory together with original file/edge bindings;
no merge classification, target authorization or filesystem writes occur here.
"""
from hashlib import sha256

from ..bundles._payload_model import owned_payload_model
from ..migration.model_inputs import records as model_records
from ..model.canonical import canonical_json_bytes as jcs, canonical_json_sha256 as digest
from ..model.errors import ModelError
from ..model.language_package_values import LanguagePackage
from ..model.manifest_resources import project_json_resource
from ..model.paths import PathClass, classify_path
from ..model.resource_inventory import ResourceEntry, ResourceInventory
from ..storage.json_syntax import parse_json_object


def _identity(kind, identifier, version=None):
    return {'kind': kind, 'id': identifier, 'version': version}


def _present(path, raw, *, value=None, domain='json-v1', pointer='', owner=None,
             scheme=None, storage='current'):
    return {'state': 'present', 'path': path, 'pointer': pointer,
        'size': len(raw), 'byte_sha256': sha256(raw).hexdigest(),
        'value_sha256': sha256(raw).hexdigest() if domain == 'bytes-v1' else digest(value),
        'value_domain': domain, 'owner_id': owner, 'id_scheme': scheme,
        'storage_class': storage}


def source_resource_rows(source):
    """Use native resource identities; keep every actual file and relation."""
    rows, inventory, _ = _source_resource_details(source)
    return rows, inventory


def _source_resource_details(source):
    """Share one qualified model's records with the immediate native caller.

    This does not cache a model or replace the caller's live source check.
    Returned values belong to this observation only.
    """
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
    return rows, inventory, tuple(records.values())
