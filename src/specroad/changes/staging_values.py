"""Prepared metadata is an observation, never a commit or permission to publish."""
from dataclasses import dataclass
from hashlib import sha256
from ..storage.json_syntax import parse_json_object
from ..model.errors import ModelError
from .journal_values import BuildingJournal, JournalError
from ._journal_codec import journal_path


class StagingError(JournalError):
    """Retain all operational bytes, including a possibly installed prepared record."""
    def __init__(self, reason, *, path=None, exit_code=3,
                 mutation_possible=False, prepared_possible=False):
        super().__init__(reason, path=path, exit_code=exit_code,
                         mutation_possible=mutation_possible)
        self.prepared_possible = prepared_possible

    def diagnostic(self):
        return {**super().diagnostic(), 'prepared_record_possible': self.prepared_possible,
                'recovery_required': self.mutation_possible,
                'commit_completed': False}


@dataclass(frozen=True, init=False)
class PreparedJournal:
    """Strict raw prepared record; construction performs no file or authority checks."""
    _raw: bytes

    def __init__(self, raw):
        if type(raw) is not bytes:
            raise StagingError('prepared_journal_bytes_required', exit_code=2)
        try:
            value = parse_json_object(raw)
            if value.get('state') != 'prepared':
                raise StagingError('prepared_journal_state_required')
            # The common inventory is unchanged. Do not weaken the building
            # codec to accept publication flags or later transaction states.
            from ..model.canonical import canonical_json_bytes
            value['state'] = 'building'
            BuildingJournal(canonical_json_bytes(value))
        except JournalError:
            raise
        except (ModelError, ValueError, TypeError, KeyError, RecursionError) as error:
            raise StagingError('invalid_prepared_journal') from error
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
        raise TypeError('Prepared metadata is not a committed transaction')
