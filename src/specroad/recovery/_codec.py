"""Closed restore-plan-v1 wire checks and independent byte/hash domains."""
from base64 import b64decode, b64encode
from binascii import Error as Base64Error
from hashlib import sha256
from pathlib import PurePosixPath
import re
import unicodedata

from ..changes.target_model import _default_scope
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.paths import project_path
from ..storage.json_syntax import parse_json_object
from .values import RestoreError, require

FIELDS = frozenset(('format_version', 'policy_version', 'project_id', 'project_root',
    'source', 'source_snapshot_root', 'source_descriptor', 'inventory', 'preserved',
    'target', 'expected_target_root', 'backup', 'objects', 'restore_plan_sha256'))
FILE_FIELDS = frozenset(('path', 'size', 'sha256'))
REASONS = frozenset(('source_baseline', 'source_archive', 'protected_history', 'protected_dependency'))


def closed(value, fields):
    require(type(value) is dict and set(value) == set(fields), 'restore_fields_invalid')


def digest(value):
    require(type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None,
            'restore_sha256_invalid')


def size(value):
    require(type(value) is int and value >= 0, 'restore_size_invalid')


def safe_path(value):
    try:
        return project_path(value)
    except Exception as error:
        from ..model.errors import ModelError
        if not isinstance(error, ModelError):
            raise
        raise RestoreError('restore_unsafe_path', exit_code=7) from error


def root_path(value):
    require(type(value) is str and value.startswith('/') and str(PurePosixPath(value)) == value
            and not value.startswith('//'), 'restore_canonical_root_required', exit_code=7)
    if value != '/':
        safe_path(value[1:])
    return value


def ordered(values, key):
    require(type(values) is list, 'restore_array_required')
    keys = [key(value) for value in values]
    require(keys == sorted(set(keys)), 'restore_order_or_duplicate_invalid')


def namespace(paths):
    """Files and directories share the same portable, case-insensitive space."""
    aliases = {}
    for path in paths:
        safe_path(path)
        for i in range(1, len(path.split('/')) + 1):
            prefix = '/'.join(path.split('/')[:i])
            alias = unicodedata.normalize('NFC', prefix).casefold()
            require(alias not in aliases or aliases[alias] == prefix,
                    'restore_path_collision', exit_code=7)
            aliases[alias] = prefix


def file_row(path, raw):
    return {'path': path, 'size': len(raw), 'sha256': sha256(raw).hexdigest()}


def file_table(files):
    entries = [file_row(p, files[p]) for p in sorted(files, key=lambda p: p.encode('utf-8'))]
    return {'entries': entries, 'sha256': canonical_json_sha256(entries)}


def check_file_rows(rows, *, reasons=False):
    require(type(rows) is list, 'restore_array_required')
    for row in rows:
        closed(row, FILE_FIELDS | ({'reasons'} if reasons else set()))
        safe_path(row['path']); size(row['size']); digest(row['sha256'])
        if reasons:
            values = row['reasons']
            require(type(values) is list and values and all(type(v) is str and v in REASONS for v in values),
                    'restore_preservation_reason_invalid')
            ordered(values, lambda v: v)
    ordered(rows, lambda row: row['path'].encode('utf-8'))
    paths = {row['path'] for row in rows}
    namespace(paths)
    require(not any('/'.join(p.split('/')[:i]) in paths for p in paths
                    for i in range(1, len(p.split('/')))), 'restore_file_directory_collision', exit_code=7)


def minimal_roots(roots):
    paths = sorted(set(roots), key=lambda p: p.encode('utf-8'))
    namespace(paths)
    return [p for p in paths if not any(p.startswith(q + '/') for q in paths if p != q)]


def check_inventory(inventory):
    closed(inventory, ('roots', 'entries', 'sha256'))
    roots, rows = inventory['roots'], inventory['entries']
    require(type(roots) is list and roots, 'restore_inventory_roots_required')
    for path in roots:
        safe_path(path)
    require(roots == minimal_roots(roots), 'restore_inventory_roots_invalid')
    require(type(rows) is list, 'restore_array_required')
    for row in rows:
        require(type(row) is dict and type(row.get('kind')) is str
                and row['kind'] in ('file', 'directory', 'missing'), 'restore_inventory_kind_invalid')
        closed(row, FILE_FIELDS | {'kind'} if row['kind'] == 'file' else ('path', 'kind'))
        safe_path(row['path'])
        if row['kind'] == 'file':
            size(row['size']); digest(row['sha256'])
        require(row['kind'] != 'missing' or row['path'] in roots, 'restore_missing_descendant_invalid')
    ordered(rows, lambda row: row['path'].encode('utf-8'))
    by_path = {row['path']: row for row in rows}
    namespace(by_path)
    require(set(roots) <= by_path.keys(), 'restore_inventory_root_missing')
    for path, row in by_path.items():
        covering = [p for p in roots if path == p or path.startswith(p + '/')]
        require(len(covering) == 1, 'restore_inventory_coverage_invalid')
        base = covering[0]
        while path != base:
            path = path.rsplit('/', 1)[0]
            require(path in by_path and by_path[path]['kind'] == 'directory',
                    'restore_inventory_parent_missing')
    digest(inventory['sha256'])
    require(inventory['sha256'] == canonical_json_sha256({'roots': roots, 'entries': rows}),
            'restore_inventory_hash_mismatch')


def decode(raw):
    require(type(raw) is bytes, 'restore_plan_bytes_required')
    data = parse_json_object(raw)
    closed(data, FIELDS)
    require(raw == canonical_json_bytes(data), 'restore_plan_not_canonical')
    require(data['format_version'] == 'restore-plan-v1' and data['policy_version'] == 'restore-preserve-v1',
            'restore_version_invalid')
    require(type(data['project_id']) is str and data['project_id'], 'restore_project_id_required')
    root_path(data['project_root'])
    for key in ('source_snapshot_root', 'expected_target_root', 'restore_plan_sha256'):
        digest(data[key])
    require(data['source_descriptor'] == _default_scope(), 'restore_full_project_scope_required')
    source = data['source']
    closed(source, ('kind', 'root', 'path', 'size', 'sha256', 'dependencies'))
    require(type(source['kind']) is str and source['kind'] in ('baseline', 'project_bundle'),
            'restore_source_kind_invalid')
    root_path(source['root']); safe_path(source['path']); size(source['size']); digest(source['sha256'])
    check_file_rows(source['dependencies'])
    require(source['kind'] != 'project_bundle' or not source['dependencies'], 'restore_bundle_dependencies_invalid')
    check_inventory(data['inventory'])
    check_file_rows(data['preserved'], reasons=True)
    for key in ('target', 'backup'):
        closed(data[key], ('entries', 'sha256'))
        check_file_rows(data[key]['entries']); digest(data[key]['sha256'])
        require(data[key]['sha256'] == canonical_json_sha256(data[key]['entries']), 'restore_file_table_hash_mismatch')
    objects = {}
    require(type(data['objects']) is list, 'restore_array_required')
    for row in data['objects']:
        closed(row, ('sha256', 'size', 'data_base64'))
        digest(row['sha256']); size(row['size'])
        require(type(row['data_base64']) is str, 'restore_object_encoding_invalid')
        try:
            content = b64decode(row['data_base64'], validate=True)
        except (ValueError, Base64Error) as error:
            raise RestoreError('restore_object_encoding_invalid') from error
        require(b64encode(content).decode('ascii') == row['data_base64'], 'restore_object_encoding_invalid')
        require(len(content) == row['size'] and sha256(content).hexdigest() == row['sha256'],
                'restore_object_bytes_mismatch')
        objects[row['sha256']] = content
    ordered(data['objects'], lambda row: row['sha256'])
    references = [source, *source['dependencies'], *data['target']['entries'], *data['backup']['entries']]
    require({r['sha256'] for r in references} == objects.keys(), 'restore_object_set_mismatch')
    for row in references:
        require(len(objects[row['sha256']]) == row['size'], 'restore_reference_size_mismatch')
    require(data['restore_plan_sha256'] == canonical_json_sha256(
        {k: v for k, v in data.items() if k != 'restore_plan_sha256'}), 'restore_plan_hash_mismatch')
    return data, objects
