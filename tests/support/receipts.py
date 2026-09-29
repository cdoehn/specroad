"""Native temporary publications with explicit test-only authorization."""
from contextlib import contextmanager
from pathlib import Path
from specroad.changes import (CommittingJournal, prepare_publication_check,
    begin_building_journal, stage_building_journal, project_lock,
    finalize_committing_journal)
from support.publication import prepared, options, ALLOW, TRANSACTION
from support.committing import publish
from support.targets import plan, POLICY


@contextmanager
def published(root, *, request_id='request-1', **kwargs):
    model, original, preflight = prepared(root, **kwargs)
    selected = plan(model, original.data['operations'], request_id=request_id)
    preflight = prepare_publication_check(selected, model, policy=POLICY)
    with project_lock(root, **options(preflight)) as held:
        building = begin_building_journal(preflight, held_lock=held,
            transaction_id=TRANSACTION, authority=ALLOW)
        ready = stage_building_journal(preflight, building, held_lock=held, authority=ALLOW)
        publish(preflight, ready, held)
        journal = CommittingJournal((Path(root) / ready.path).read_bytes())
        yield model, selected, preflight, held, journal


def finish(preflight, held, journal, **kwargs):
    return finalize_committing_journal(preflight, journal, held_lock=held,
        authority=kwargs.pop('authority', ALLOW), **kwargs)
