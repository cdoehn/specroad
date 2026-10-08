"""Native transactions with policy fixed before the independent plan/basis bind."""
from contextlib import contextmanager
import os
from unittest.mock import patch

from specroad.changes import (CommitPublicationError, CommittingJournal, project_lock,
    prepare_publication_check, begin_building_journal, stage_building_journal,
    publish_prepared_journal, finalize_committing_journal)
from specroad.model.model_manifest import ProjectReadBinding
from .folds import goal, edit
from .model import configuration_value, put
from .publication import ALLOW, TRANSACTION, options
from .targets import POLICY, model, plan


@contextmanager
def writer(root, state='prepared', *, auto_recover=True):
    root.mkdir(parents=True, exist_ok=True)
    inode = root.stat()
    policy = {} if auto_recover is None else {'auto_recover': auto_recover}
    source = model([goal(1), goal(2)], config=configuration_value(transaction_policy=policy),
        binding=ProjectReadBinding('sample', str(root), (inode.st_dev, inode.st_ino)))
    for path, raw in source.source_files.items():
        put(root, path, raw)
    change = plan(source, [edit(source.artifacts[0], 'First target'), edit(source.artifacts[1], 'Second target')])
    check = prepare_publication_check(change, source, policy=POLICY)
    expected = dict(source.source_files)
    if state in ('complete', 'committed'):
        expected.update({d.path: d.content for d in check.request.documents})
    with project_lock(root, **options(check)) as held:
        journal = begin_building_journal(check, held_lock=held, transaction_id=TRANSACTION, authority=ALLOW)
        if state != 'building':
            journal = stage_building_journal(check, journal, held_lock=held, authority=ALLOW)
        if state in ('partial', 'complete', 'committed'):
            native = os.replace
            targets = []

            def replace(src, dst, **kwargs):
                if state == 'partial' and dst != 'journal.json' and targets:
                    raise OSError(5, 'Owned interruption before second target')
                result = native(src, dst, **kwargs)
                if dst != 'journal.json':
                    targets.append(dst)
                return result

            with patch.object(os, 'replace', side_effect=replace):
                try:
                    publish_prepared_journal(check, journal, held_lock=held, authority=ALLOW)
                except CommitPublicationError:
                    if state != 'partial' or len(targets) != 1:
                        raise
                else:
                    assert state != 'partial'
            journal = CommittingJournal((root / journal.path).read_bytes())
            if state == 'committed':
                finalize_committing_journal(check, journal, held_lock=held, authority=ALLOW)
        yield source, change, expected


def pending(root, state='prepared', *, auto_recover=True):
    with writer(root, state, auto_recover=auto_recover) as values:
        return values
