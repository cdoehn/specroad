"""Complete portable schema-transition history, never live publication proof."""
from dataclasses import dataclass
from ..changes.schema_transition_values import TransitionJournal, FORMAT, request_receipt, transaction_receipt
from ..changes._schema_transition_proof import _backup, verify_owned_images
from ..storage.json_syntax import parse_json_object
from .plan_values import require


@dataclass(frozen=True)
class HistoricalMigrationJournal:
    original: TransitionJournal

    @property
    def source_bytes(self): return self.original.source_bytes
    @property
    def data(self): return self.original.data
    @property
    def plan(self): return self.original.plan


def completed_migration_receipts(files, project_id):
    """Own full archived source, images, journal and request/transaction receipt.

    A historical host identity is retained as data, never matched to a new
    filesystem or admitted to an active writer/retry constructor by this API.
    """
    journals, claimed = [], set()
    for path, raw in sorted(files.items()):
        if not path.startswith('.specroad/transactions/receipts/') or not path.endswith('/journal.json'):
            continue
        if parse_json_object(raw).get('format_version') != FORMAT:
            continue
        journal = TransitionJournal(raw)
        prefix = journal.receipt_root
        require(path == prefix + '/journal.json' and journal.data['state'] == 'committed'
                and journal.data['project_id'] == project_id, 'migration_receipt_binding_changed', exit_code=6)
        owned = {p[len(prefix)+1:]: b for p, b in files.items() if p.startswith(prefix + '/')}
        require('source.zip' in owned, 'migration_receipt_source_missing', exit_code=6)
        backup = _backup(journal, owned['source.zip'])
        verify_owned_images(owned, journal, backup)
        require(owned.get('transaction.json') == transaction_receipt(journal),
                'migration_receipt_changed', exit_code=6)
        names = {prefix + '/' + name for name in owned}
        request = request_receipt(journal)
        if request is not None:
            require(files.get(request.path) == request.source_bytes,
                    'migration_request_receipt_changed', exit_code=6)
            names.add(request.path)
        require(not claimed.intersection(names), 'migration_receipt_multiple_owners', exit_code=6)
        claimed.update(names)
        journals.append(HistoricalMigrationJournal(journal))
    return tuple(journals), claimed
