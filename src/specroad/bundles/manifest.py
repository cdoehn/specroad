"""E.1.1 field/type bindings, not semantic closure or receipt verification.

Values are supplied explicitly. Native descriptor and boundary constructors
own their existing contracts; no hashes or provenance are inferred here.
"""
import json
import re

from ..graph.boundaries import BoundaryReference
from ..graph.scope_descriptors import ScopeDescriptor
from ..model._bundle_scope_contract import IDEMPOTENCY_SCOPES, KINDS, PROJECT
from ..model.canonical import canonical_json_bytes
from ..model.errors import ModelError
from ..model.versions import SCHEMA_VERSION
from ..storage.archive import _inventory, validate_portable_archive_paths
from ..storage.json_syntax import parse_json_object
from .errors import BundleError

MANIFEST_NAME = 'bundle-manifest.json'
FORMAT_VERSION = '1.0.0'
_HASHES = ('origin_model_root_sha256', 'bundle_model_root_sha256',
           'profile_sha256', 'configuration_sha256')
_FIELDS = frozenset(('bundle_format_version', 'bundle_kind', 'read_only',
    'project_id', 'tool_version', 'schema_version', 'scope_descriptor',
    'boundary_references', 'excluded_contents', 'idempotency_scope', *_HASHES))
_EXCLUSION_REASONS = ('outside_scope', 'operational_receipts_excluded',
                      'unreferenced_archive_object')


def require(condition, reason, *, code='SRV002'):
    if not condition:
        raise BundleError(reason, code=code)


def require_hash(value):
    require(type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None,
            'invalid_bundle_hash')


def _text(value):
    require(type(value) is str and bool(value.strip()) and '\0' not in value,
            'invalid_bundle_identity')


def metadata_bytes(value):
    """Return owned canonical bytes of exactly the fourteen metadata fields."""
    require(type(value) is dict and set(value) == _FIELDS, 'bundle_metadata_fields')
    # Native JSON validation rejects foreign conversion hooks/cycles/Unicode.
    encoded = canonical_json_bytes(value)
    _check_versions_and_identity(value)
    kind = _check_scope(value)
    _check_boundaries(value['boundary_references'], kind)
    _check_exclusions(value['excluded_contents'], kind, value['idempotency_scope'])
    return encoded


def _check_versions_and_identity(value):
    for field in ('bundle_format_version', 'schema_version'):
        require(type(value[field]) is str, 'bundle_version_type')
    require(value['bundle_format_version'] == FORMAT_VERSION
            and value['schema_version'] == SCHEMA_VERSION,
            'unsupported_bundle_version', code='SRV003')
    for field in ('project_id', 'tool_version'):
        _text(value[field])
    for field in _HASHES:
        require_hash(value[field])


def _check_scope(value):
    require(type(value['read_only']) is bool, 'bundle_read_only_type')
    descriptor = ScopeDescriptor(value['scope_descriptor']).data
    kind = value['bundle_kind']
    require(type(kind) is str and kind in KINDS, 'bundle_kind')
    require(type(value['idempotency_scope']) is str
            and value['idempotency_scope'] in IDEMPOTENCY_SCOPES, 'bundle_idempotency_scope')
    rule = KINDS[kind]
    require(value['read_only'] is rule.read_only and rule.matches_scope(descriptor),
            'bundle_scope_combination')
    if rule is PROJECT:
        require(value['origin_model_root_sha256'] == value['bundle_model_root_sha256'],
                'bundle_project_root_mismatch')
    else:
        require(value['idempotency_scope'] in rule.idempotency_scopes, 'bundle_partial_idempotency')
    return kind


def _check_boundaries(boundaries, kind):
    require(type(boundaries) is list, 'bundle_boundary_list')
    keys = [BoundaryReference(item).order_key for item in boundaries]
    require(keys == sorted(set(keys)), 'bundle_boundary_order')
    require(kind != 'project' or not boundaries, 'bundle_project_boundary')


def _check_exclusions(exclusions, kind, idempotency_scope):
    require(type(exclusions) is list, 'bundle_exclusion_list')
    paths = []
    for item in exclusions:
        require(type(item) is dict and set(item) == {'path', 'reason'}, 'bundle_exclusion_fields')
        require(type(item['path']) is str, 'bundle_exclusion_path_type')
        require(type(item['reason']) is str and item['reason'] in _EXCLUSION_REASONS,
                'bundle_exclusion_reason')
        validate_portable_archive_paths([item['path']])
        require(item['path'] != MANIFEST_NAME, 'recursive_bundle_exclusion')
        if item['reason'] == 'outside_scope':
            require(kind == 'partial', 'bundle_project_scope_exclusion')
        if item['reason'] == 'operational_receipts_excluded':
            require(idempotency_scope == 'local_only', 'bundle_receipt_exclusion')
        paths.append(item['path'])
    require(paths == sorted(set(paths), key=lambda p: p.encode('utf-8')), 'bundle_exclusion_order')
    validate_portable_archive_paths(paths)


def check_entries(entries):
    require(type(entries) is list, 'bundle_entries_type')
    for item in entries:
        require(type(item) is dict and set(item) == {'path', 'size', 'media_type', 'sha256'},
                'bundle_entry_fields')
        require(type(item['path']) is str, 'bundle_entry_path_type')
        validate_portable_archive_paths([item['path']])
        require(type(item['size']) is int and item['size'] >= 0, 'bundle_entry_size')
        require(type(item['media_type']) is str, 'bundle_entry_media_type')
        require_hash(item['sha256'])
    # Length, order, types and hashes are then compared with actual inventory.


def check_payload_binding(metadata, files):
    exclusions = {item['path'] for item in metadata['excluded_contents']}
    require(not exclusions.intersection(files), 'bundle_excluded_payload')
    validate_portable_archive_paths([MANIFEST_NAME, *files, *exclusions])
    require('specroad.json' in files, 'bundle_configuration_missing', code='SRV060')
    # Check only the manifest's direct identity/schema binding. Full native
    # configuration validity, model roots, closure and receipts are later gates.
    configuration = parse_json_object(files['specroad.json'])
    require(configuration.get('project_id') == metadata['project_id']
            and configuration.get('schema_version') == metadata['schema_version'],
            'bundle_configuration_binding', code='SRV060')


def owned_metadata(value):
    try:
        return json.loads(metadata_bytes(value))
    except ModelError as error:
        raise BundleError(error.reason) from error


def check_manifest_bytes(manifest_raw, files):
    """Check the transported manifest against the shared codec's inventory.

    Keep field validation before canonical-byte and payload comparisons;
    these checks establish container integrity, not semantic completeness.
    """
    try:
        manifest = parse_json_object(manifest_raw)
    except ModelError as error:
        code = 'SRV060' if error.reason in ('invalid_utf8', 'invalid_json') else 'SRV002'
        raise BundleError(error.reason, code=code) from error
    require('entries' in manifest, 'bundle_entries_missing')
    check_entries(manifest['entries'])
    metadata = owned_metadata({k: v for k, v in manifest.items() if k != 'entries'})
    require(canonical_json_bytes(manifest) == manifest_raw,
            'noncanonical_bundle_manifest', code='SRV060')
    require(canonical_json_bytes(manifest['entries']) == canonical_json_bytes(_inventory(files)),
            'bundle_inventory_mismatch', code='SRV060')
    check_payload_binding(metadata, files)
