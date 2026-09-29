"""Building journals: complete byte inventories, never normative publication.

This first native journal step owns only the building record. Staging payloads,
prepared/committing transitions, receipts and recovery are separate later steps.
"""
from dataclasses import dataclass
from hashlib import sha256
import unicodedata
from ..model.canonical import canonical_json_bytes
from ..model.errors import ModelError
from ..model.paths import project_path
from ..model.audit_fields import _valid_utc
from ..storage.json_syntax import parse_json_object
from ..storage.project import ProjectSource
from ..security import SafetyViolation
from .authoring import normalize_authoring_actor
from .request_ids import normalize_request_id
from .publication_values import PublicationPreflight
from .publication_check import recheck_publication
from .locking import HeldProjectLock
from .execution_values import ChangeExecutionError

JOURNAL_VERSION = 'transaction-journal-v1'
STATES = ('building', 'prepared', 'committing', 'committed', 'rolling_back', 'rolled_back', 'corrupt')


class JournalError(ChangeExecutionError):
    """Preserve partial operational files; no inferred rollback or safe retry."""
    def __init__(self, reason, *, path=None, exit_code=3, mutation_possible=False):
        super().__init__(reason, exit_code=exit_code, write_state='not_committed')
        self.path = path
        self.mutation_possible = mutation_possible

    def diagnostic(self):
        return {**super().diagnostic(), 'path': self.path,
                'mutation_possible': self.mutation_possible,
                'normative_publication_started': False, 'write_authorized': False}


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


def _validate(value):
    fields = {'format_version', 'state', 'transaction_id', 'project_id', 'root_identity',
              'change_plan_id', 'request_id', 'actor', 'planned_at', 'plan_sha256',
              'plan_bytes_sha256', 'request_sha256', 'base_model_root_sha256',
              'target_model_root_sha256', 'files', 'published_count'}
    if type(value) is not dict or set(value) != fields or value['format_version'] != JOURNAL_VERSION:
        raise JournalError('invalid_journal_schema')
    txn = _transaction(value['transaction_id'])
    if value['state'] not in STATES:
        raise JournalError('invalid_journal_state')
    if value['state'] != 'building':
        raise JournalError('journal_state_not_supported_by_building_codec')
    if type(value['published_count']) is not int or value['published_count'] != 0:
        raise JournalError('building_has_publications')
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
                                       'base_model_root_sha256','target_model_root_sha256')):
        raise JournalError('invalid_journal_hash')
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
    if names != sorted(names, key=lambda p:p.encode('utf-8')):
        raise JournalError('journal_inventory_not_ordered')
    # Distinct files cannot be a file and that file's child at the same time.
    for name in names:
        parts = name.split('/')
        if any(unicodedata.normalize('NFC','/'.join(parts[:i])).casefold() in aliases
               for i in range(1,len(parts))):
            raise JournalError('journal_target_parent_collision')


@dataclass(frozen=True, init=False)
class BuildingJournal:
    """Parsed journal bytes. Structure is not authenticity or publication proof."""
    _raw: bytes

    def __init__(self, raw):
        if type(raw) is not bytes:
            raise JournalError('journal_bytes_required', exit_code=2)
        try:
            value = parse_json_object(raw)
            _validate(value)
        except JournalError:
            raise
        except (ModelError, ValueError, TypeError, KeyError, RecursionError) as e:
            raise JournalError('invalid_journal_document') from e
        object.__setattr__(self, '_raw', raw)

    @property
    def data(self): return parse_json_object(self._raw)
    @property
    def source_bytes(self): return self._raw
    @property
    def sha256(self): return sha256(self._raw).hexdigest()
    @property
    def path(self): return journal_path(self.data['transaction_id'])
    def __bool__(self): raise TypeError('A journal is not a successful transaction')


def prepare_building_journal(preflight, *, transaction_id):
    """Pure complete file inventory derived from the checked publication request.

    Only the current adapter's changed artifact bytes are supported. No phantom
    entries for unchanged sources; no assumed delete or specialized operations.
    No live reads, no staging, no time/identity generation and no write permission.
    """
    if type(preflight) is not PublicationPreflight:
        raise JournalError('publication_preflight_required', exit_code=2)
    transaction_id = _transaction(transaction_id)
    request = preflight.request
    model, p = preflight._model, request.plan
    data, pv = request.data, p.data
    old = model.source_files
    documents = sorted(request.documents, key=lambda d:d.path.encode('utf-8'))
    if len({d.path for d in documents}) != len(documents) or set(data['changed_paths']) != {d.path for d in documents}:
        raise JournalError('publication_inventory_mismatch')
    target = {item['path']:item['sha256'] for item in data['target_files']}
    entries=[]; prefix='.specroad/transactions/'+transaction_id
    for i,d in enumerate(documents):
        before = old.get(d.path)
        if d.path not in target or target[d.path] != sha256(d.content).hexdigest() or before == d.content:
            raise JournalError('publication_target_binding_mismatch')
        entries.append({'path':d.path, 'existed_before':before is not None,
            'before_sha256':None if before is None else sha256(before).hexdigest(),
            'before_size':None if before is None else len(before),
            'after_sha256':sha256(d.content).hexdigest(),'after_size':len(d.content),
            'staging_path':prefix+'/staging/'+str(i)+'.bin',
            'before_image_path':None if before is None else prefix+'/before/'+str(i)+'.bin',
            'published':False})
    value={'format_version':JOURNAL_VERSION,'state':'building','transaction_id':transaction_id,
           'project_id':model.binding.project_id,'root_identity':list(model.binding.root_identity),
           'change_plan_id':pv['change_plan_id'],'request_id':pv['request_id'],
           'actor':pv['actor'],'planned_at':pv['planned_at'],'plan_sha256':p.sha256,
           'plan_bytes_sha256':sha256(p.source_bytes).hexdigest(),'request_sha256':request.sha256,
           'base_model_root_sha256':pv['base']['model_root_sha256'],
           'target_model_root_sha256':data['target_root_sha256'],
           'files':entries,'published_count':0}
    return BuildingJournal(canonical_json_bytes(value))


def verify_building_journal(journal, preflight):
    """Bind the entire inventory to independent plan/source/target observations."""
    if type(journal) is not BuildingJournal:
        raise JournalError('building_journal_required', exit_code=2)
    expected = prepare_building_journal(preflight,transaction_id=journal.data['transaction_id'])
    if canonical_json_bytes(journal.data) != canonical_json_bytes(expected.data):
        raise JournalError('journal_plan_inventory_mismatch',exit_code=6,path=journal.path)
    return None


def begin_building_journal(preflight, *, held_lock, transaction_id, authority, gates=()):
    """Revalidate under the native writer lock, then fsync a new building record.

    Only operational directories/journal are created. On failure retain all
    created files; a leftover namespace blocks normal writers until recovery.
    Never call a normative publisher, never mark prepared, never clean a blocker.
    """
    if type(held_lock) is not HeldProjectLock:
        raise JournalError('native_writer_lock_required',exit_code=2)
    journal=prepare_building_journal(preflight,transaction_id=transaction_id)
    # This gate requires no unresolved journal. Do not exempt an existing record
    # merely because it carries our transaction ID or says building/committed.
    recheck_publication(preflight,preflight.request,held_lock=held_lock,
                        transaction_id=transaction_id,authority=authority,gates=gates)
    from ._journal_io import persist_building_record
    persist_building_record(journal,held_lock)
    return journal


def read_building_journal(source, transaction_id, *, expected_sha256=None, preflight=None):
    """Read an existing record, not a recovery decision or a write capability."""
    if type(source) is not ProjectSource:
        raise JournalError('bound_project_source_required',exit_code=2)
    path=journal_path(transaction_id)
    if expected_sha256 is not None and not _hash(expected_sha256):
        raise JournalError('invalid_expected_journal_hash',exit_code=2)
    from ._journal_io import read_record
    source.check_current()
    raw=read_record(source,path)
    journal=BuildingJournal(raw); v=journal.data
    if (journal.path != path or v['project_id'] != source.configuration.project_id
            or v['root_identity'] != list(source.boundary._root_identity)):
        raise JournalError('journal_project_binding_mismatch',exit_code=6,path=path)
    if expected_sha256 is not None and journal.sha256 != expected_sha256:
        raise JournalError('journal_bytes_changed',exit_code=6,path=path)
    if preflight is not None:
        verify_building_journal(journal,preflight)
    source.check_current()
    return journal
