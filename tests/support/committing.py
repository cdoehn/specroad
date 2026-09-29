"""Owned native temporary transactions; test-only host authority."""
from contextlib import contextmanager
from specroad.changes import (project_lock, begin_building_journal,
    stage_building_journal, publish_prepared_journal)
from .publication import prepared, options, ALLOW, TRANSACTION


@contextmanager
def staged(root, **kwargs):
    model, plan, preflight = prepared(root, **kwargs)
    with project_lock(root, **options(preflight)) as held:
        building = begin_building_journal(preflight, held_lock=held,
                         transaction_id=TRANSACTION, authority=ALLOW)
        journal = stage_building_journal(preflight, building, held_lock=held, authority=ALLOW)
        yield model, plan, preflight, held, journal


def publish(preflight, journal, held, **kwargs):
    return publish_prepared_journal(preflight, journal, held_lock=held,
        authority=kwargs.pop('authority', ALLOW), **kwargs)
