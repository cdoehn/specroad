"""Closed building-journal schema and safe logical references."""
import unicodedata
from ..model.canonical import canonical_json_sha256
from ..model.errors import ModelError
from ..model.paths import project_path
from ..model.audit_fields import _valid_utc
from .authoring import normalize_authoring_actor, prepare_authoring_request
from .request_ids import normalize_request_id
from .journal_values import JournalError,JOURNAL_VERSION
from ._journal_state import require_building

def _hash(value):
    return type(value) is str and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def _text(value):
    return (type(value) is str and bool(value) and value == value.strip()
            and all(ord(c) >= 32 and ord(c) != 127 for c in value))


def _transaction(value):
    if (type(value) is not str or not 1 <= len(value) <= 128
            or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-' for c in value)
            or value.casefold() == 'receipts'):
        raise JournalError('invalid_transaction_path', exit_code=2)
    try:
        project_path(value)
    except ModelError as e:
        raise JournalError('invalid_transaction_path', exit_code=2) from e
    return value


def journal_path(transaction_id):
    return '.specroad/transactions/' + _transaction(transaction_id) + '/journal.json'


def _target_path(value):
    if type(value) is not str:
        raise JournalError('invalid_journal_target_path')
    try:
        project_path(value)
    except ModelError as e:
        raise JournalError('invalid_journal_target_path') from e
    if any(p.casefold() == '.specroad' for p in value.split('/')):
        raise JournalError('operational_path_is_not_a_target')
    parts = value.split('/')
    supported = (value == 'specroad.json' or
        (parts[0] in ('spec','profiles','rules','mappings') and len(parts)>1 and value.endswith('.json')) or
        (parts[0] == 'attachments' and len(parts)>1))
    if not supported:
        raise JournalError('journal_target_not_current_normative_resource')
    return value


def validate_building_document(value):
    fields = {'format_version', 'state', 'transaction_id', 'project_id', 'root_identity',
              'change_plan_id', 'request_id', 'actor', 'planned_at', 'plan_sha256',
              'plan_bytes_sha256', 'request_sha256', 'authoring_binding',
              'authoring_sha256', 'base_model_root_sha256',
              'target_model_root_sha256', 'target_inventory', 'files', 'published_count'}
    if type(value) is not dict or set(value) != fields or value['format_version'] != JOURNAL_VERSION:
        raise JournalError('invalid_journal_schema')
    txn = _transaction(value['transaction_id'])
    require_building(value['state'], value['published_count'])
    if not all(_text(value[k]) for k in ('project_id','change_plan_id')) or not _valid_utc(value['planned_at']):
        raise JournalError('invalid_journal_identity')
    try:
        normalize_authoring_actor(value['actor'])
        normalize_request_id(value['request_id'])
    except ModelError as e:
        raise JournalError('invalid_journal_authoring') from e
    if value['actor']['actor_type'] in ('ai','ci') and value['request_id'] is None:
        raise JournalError('journal_request_id_required')
    ident = value['root_identity']
    if (type(ident) is not list or len(ident) != 2
            or any(type(x) is not int or x < 0 for x in ident)):
        raise JournalError('invalid_journal_root_identity')
    if not all(_hash(value[k]) for k in ('plan_sha256','plan_bytes_sha256','request_sha256',
                                       'authoring_sha256','base_model_root_sha256',
                                       'target_model_root_sha256')):
        raise JournalError('invalid_journal_hash')
    authoring = value['authoring_binding']
    try:
        if type(authoring) is not dict:
            raise JournalError('invalid_journal_authoring_binding')
        rebuilt = prepare_authoring_request(command_id=authoring.get('command_id'),
            actor=authoring.get('actor'), operations=authoring.get('operations'),
            request_id=authoring.get('request_id'), dry_run=authoring.get('dry_run'),
            as_proposal=authoring.get('as_proposal'))
        expected = {**rebuilt.data, 'plan_sha256': value['plan_sha256'],
                    'base_model_root_sha256': value['base_model_root_sha256'],
                    'scope_descriptor': authoring.get('scope_descriptor')}
        if (authoring != expected or authoring['actor'] != value['actor']
                or authoring['request_id'] != value['request_id']
                or authoring['command_id'] != 'change apply'
                or authoring['route'] != 'direct' or authoring['dry_run']
                or authoring['as_proposal']
                or canonical_json_sha256(authoring) != value['authoring_sha256']):
            raise JournalError('invalid_journal_authoring_binding')
    except (ModelError, JournalError, KeyError, TypeError, ValueError) as e:
        if isinstance(e, JournalError): raise
        raise JournalError('invalid_journal_authoring_binding') from e
    inventory = value['target_inventory']
    if type(inventory) is not list:
        raise JournalError('invalid_journal_target_inventory')
    target_names, target_aliases, targets = [], set(), {}
    for item in inventory:
        if (type(item) is not dict or set(item) != {'path','size','sha256'}
                or type(item['size']) is not int or item['size'] < 0
                or not _hash(item['sha256'])):
            raise JournalError('invalid_journal_target_inventory')
        try:
            path = project_path(item['path'])
        except ModelError as e:
            raise JournalError('invalid_journal_target_inventory') from e
        if any(part.casefold() == '.specroad' for part in path.split('/')):
            raise JournalError('invalid_journal_target_inventory')
        alias = unicodedata.normalize('NFC', path).casefold()
        if alias in target_aliases:
            raise JournalError('invalid_journal_target_inventory')
        target_aliases.add(alias); target_names.append(path); targets[path] = item
    if target_names != sorted(target_names, key=lambda p:p.encode('utf-8')):
        raise JournalError('invalid_journal_target_inventory')
    if type(value['files']) is not list:
        raise JournalError('invalid_journal_inventory')
    names, aliases = [], set()
    entry_fields = {'path','existed_before','before_sha256','before_size', 'after_sha256',
                    'after_size','staging_path','before_image_path','published'}
    for i, item in enumerate(value['files']):
        if type(item) is not dict or set(item) != entry_fields:
            raise JournalError('invalid_journal_file_entry')
        path = _target_path(item['path']); names.append(path)
        alias = unicodedata.normalize('NFC', path).casefold()
        if alias in aliases:
            raise JournalError('duplicate_journal_target')
        aliases.add(alias)
        if type(item['existed_before']) is not bool or type(item['published']) is not bool:
            raise JournalError('invalid_journal_boolean')
        if item['published']:
            raise JournalError('building_has_publications')
        if (not _hash(item['after_sha256']) or type(item['after_size']) is not int
                or item['after_size'] < 0):
            raise JournalError('invalid_journal_after_image')
        prefix = '.specroad/transactions/' + txn
        if item['staging_path'] != prefix + '/staging/' + str(i) + '.bin':
            raise JournalError('invalid_staging_reference')
        if item['existed_before']:
            if (not _hash(item['before_sha256']) or type(item['before_size']) is not int
                    or item['before_size'] < 0
                    or item['before_image_path'] != prefix + '/before/' + str(i) + '.bin'):
                raise JournalError('invalid_before_image_reference')
        elif any(item[k] is not None for k in ('before_sha256','before_size','before_image_path')):
            raise JournalError('nonexistent_before_image')
    for item in value['files']:
        target = targets.get(item['path'])
        if (target is None or target['size'] != item['after_size']
                or target['sha256'] != item['after_sha256']):
            raise JournalError('journal_target_inventory_mismatch')
    if names != sorted(names, key=lambda p:p.encode('utf-8')):
        raise JournalError('journal_inventory_not_ordered')
    # Distinct files cannot be a file and that file's child at the same time.
    for name in names:
        parts = name.split('/')
        if any(unicodedata.normalize('NFC','/'.join(parts[:i])).casefold() in aliases
               for i in range(1,len(parts))):
            raise JournalError('journal_target_parent_collision')


