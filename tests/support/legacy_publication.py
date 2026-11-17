"""Synthetic retained legacy journals for read-only integrity checks, never repair."""
import os
from pathlib import Path
from unittest.mock import patch
import pytest
from specroad.changes import CommitPublicationError, CommittingJournal
from specroad.model.canonical import canonical_json_bytes
from support.receipts import published
from support.committing import staged, publish
from support.folds import goal, edit

def crash_after_last_target(root):
    with published(root) as (model, plan, preflight, held, journal):
        data = journal.data
        assert data['published_count'] == len(data['files']) == 1
        data['published_count'] = 0
        data['files'][0]['published'] = False
        crashed = CommittingJournal(canonical_json_bytes(data))
        Path(root, journal.path).write_bytes(crashed.source_bytes)
        target = {item['path']: Path(root, item['path']).read_bytes()
                  for item in data['target_inventory']}
    return model, plan, preflight, crashed, target

def partial_commit(root, *, operations=None, artifacts=None):
    if operations is None and artifacts is None:
        a, b = goal(1), goal(2)
        artifacts = [a, b]
        operations = [edit(a, 'A'), edit(b, 'B')]
    with staged(root, operations=operations, artifacts=artifacts) as (model, plan, preflight, held, prepared):
        original_replace = os.replace
        targets = []
        def replace(src, dst, **kwargs):
            if dst != 'journal.json' and targets:
                raise OSError(5, 'stop before second target')
            result = original_replace(src, dst, **kwargs)
            if dst != 'journal.json':
                targets.append(dst)
            return result
        with patch.object(os, 'replace', side_effect=replace):
            with pytest.raises(CommitPublicationError):
                publish(preflight, prepared, held)
        journal = CommittingJournal(Path(root, prepared.path).read_bytes())
    return model, plan, journal
