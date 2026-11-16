"""Complete owned legacy fixtures before using their historical retry proof."""
from contextlib import contextmanager
import json

from specroad.changes import cleanup_completed_transaction
from support.receipts import published as legacy_publication, finish
from support.publication import ALLOW, TRANSACTION


@contextmanager
def published(root, **options):
    with legacy_publication(root, **options) as values:
        yield values
        _, _, preflight, held, journal = values
        path = held._files.boundary.root / journal.path
        if path.exists() and json.loads(path.read_bytes())['state'] == 'committed':
            cleanup_completed_transaction(preflight, TRANSACTION, held_lock=held, authority=ALLOW)
