"""Pure journal successor rules drive the allowed publication order.

No filesystem decisions select the next target. A validated committing journal
contains exactly the acknowledged prefix; each durable successor advances by one.
The committed/receipt transition is intentionally absent from this phase.
"""
from ..model.canonical import canonical_json_bytes
from .committing_values import CommittingJournal, CommitPublicationError


def _initial_committing(prepared):
    value = prepared.data
    value['state'] = 'committing'
    return CommittingJournal(canonical_json_bytes(value))


def _acknowledge(journal, index):
    value = journal.data
    if index != value['published_count'] or index >= len(value['files']):
        raise CommitPublicationError('out_of_order_publication_acknowledgement')
    value['files'][index]['published'] = True
    value['published_count'] += 1
    return CommittingJournal(canonical_json_bytes(value))


def next_publication(journal):
    """The next index follows the journal, not an independently advanced loop."""
    value = journal.data
    count = value['published_count']
    return None if count == len(value['files']) else count
