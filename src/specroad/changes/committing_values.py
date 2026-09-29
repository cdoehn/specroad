"""Publication progress is neither an audit receipt nor a completed transaction."""
from dataclasses import dataclass
from hashlib import sha256
from ..model.canonical import canonical_json_bytes
from ..model.errors import ModelError
from ..storage.json_syntax import parse_json_object
from .journal_values import BuildingJournal, JournalError
from ._journal_codec import journal_path


class CommitPublicationError(JournalError):
    """Do not retry/rollback: a failed system call may already have changed disk."""
    def __init__(self, reason, *, path=None, exit_code=3, mutation_possible=False,
                 publication_possible=False, published_count=0):
        super().__init__(reason, path=path, exit_code=exit_code,
                         mutation_possible=mutation_possible)
        self.publication_possible = publication_possible
        self.published_count = published_count
        if publication_possible:
            self.write_state = 'unknown'

    def diagnostic(self):
        return {**super().diagnostic(),
                'normative_publication_started': self.publication_possible,
                'published_count_acknowledged': self.published_count,
                'recovery_required': True, 'commit_completed': False,
                'retry_safe': False}


@dataclass(frozen=True, init=False)
class CommittingJournal:
    """Strict prefix acknowledgement, without proving any corresponding file exists."""
    _raw: bytes

    def __init__(self, raw):
        if type(raw) is not bytes:
            raise CommitPublicationError('committing_bytes_required', exit_code=2)
        try:
            value = parse_json_object(raw)
        except ModelError as error:
            raise CommitPublicationError('invalid_committing_json', exit_code=3) from error
        if value.get('state') != 'committing':
            raise CommitPublicationError('committing_state_required')
        count, entries = value.get('published_count'), value.get('files')
        if (type(count) is not int or type(entries) is not list
                or not 0 <= count <= len(entries)):
            raise CommitPublicationError('invalid_publication_count')
        for index, entry in enumerate(entries):
            if type(entry) is not dict or type(entry.get('published')) is not bool:
                raise CommitPublicationError('invalid_publication_flag')
            if entry['published'] is not (index < count):
                raise CommitPublicationError('publication_prefix_required')
            entry['published'] = False
        value.update(state='building', published_count=0)
        try:
            BuildingJournal(canonical_json_bytes(value))
        except JournalError as error:
            raise CommitPublicationError(error.reason, path=error.path, exit_code=error.exit_code) from error
        object.__setattr__(self, '_raw', raw)

    @property
    def data(self): return parse_json_object(self._raw)
    @property
    def source_bytes(self): return self._raw
    @property
    def sha256(self): return sha256(self._raw).hexdigest()
    @property
    def path(self): return journal_path(self.data['transaction_id'])
    def __bool__(self):
        raise TypeError('Publication progress is not a transaction receipt')


@dataclass(frozen=True, init=False)
class PublishedFiles:
    """C.2 steps 1–4 only. C.2 receipts MUST precede the later committed marker."""
    _raw: bytes

    @classmethod
    def _create(cls, journal, root):
        obj = object.__new__(cls)
        object.__setattr__(obj, '_raw', canonical_json_bytes({
            'format_version': 'published-files-v1', 'state': 'committing',
            'transaction_id': journal.data['transaction_id'],
            'journal_path': journal.path, 'journal_sha256': journal.sha256,
            'request_sha256': journal.data['request_sha256'],
            'target_model_root_sha256': root,
            'published_count': journal.data['published_count'],
            'all_files_published': True, 'target_root_verified': True,
            'receipt_written': False, 'commit_completed': False,
            'finalization_required': True, 'write_authorized': False,
            'atomic_snapshot': False}))
        return obj

    def __init__(self, *args, **kwargs):
        raise TypeError('Use publish_prepared_journal')
    @property
    def data(self): return parse_json_object(self._raw)
    def __bool__(self):
        raise TypeError('Published files still require transaction receipts and finalization')
