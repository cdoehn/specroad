"""Immutable building records and explicit operational failure outcomes."""
from dataclasses import dataclass
from hashlib import sha256
from ..storage.json_syntax import parse_json_object
from ..model.errors import ModelError
from .execution_values import ChangeExecutionError
JOURNAL_VERSION = 'transaction-journal-v1'

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


@dataclass(frozen=True, init=False)
class BuildingJournal:
    """Parsed journal bytes. Structure is not authenticity or publication proof."""
    _raw: bytes

    def __init__(self, raw):
        if type(raw) is not bytes:
            raise JournalError('journal_bytes_required', exit_code=2)
        try:
            value = parse_json_object(raw)
            from ._journal_codec import validate_building_document
            validate_building_document(value)
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
    def path(self):
        from ._journal_codec import journal_path
        return journal_path(self.data['transaction_id'])
    def __bool__(self): raise TypeError('A journal is not a successful transaction')


