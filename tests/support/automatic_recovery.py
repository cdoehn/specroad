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
def writer(root, state='prepared', *, auto_recover=True, on_basis=None):
    root.mkdir(parents=True, exist_ok=True)
    inode = root.stat()
    policy = {} if auto_recover is None else {'auto_recover': auto_recover}
    source = model([goal(1), goal(2)], config=configuration_value(transaction_policy=policy),
        binding=ProjectReadBinding('sample', str(root), (inode.st_dev, inode.st_ino)))
    for path, raw in source.source_files.items():
        put(root, path, raw)
    if on_basis is not None:
        on_basis(source)
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


def current_model(root):
    """Fresh actual bytes for this fixture's complete two-artifact project."""
    from specroad.changes import TargetModel
    from specroad.profiles import ProfileResource, compose_profiles
    from specroad.storage.project import ProjectSource
    from specroad.validation import ModelDocument
    source = ProjectSource(root, expected_project_id='sample')
    raw = source.read_normative('profiles/core.json')
    profile = ProfileResource(raw)
    documents = [ModelDocument(p.relative_to(root).as_posix(), p.read_bytes())
                 for p in sorted((root / 'spec').rglob('*.json'))]
    return TargetModel(source.configuration_bytes,
        ProjectReadBinding('sample', str(root), source.boundary._root_identity), documents,
        profile=compose_profiles([profile], core_key=profile.key),
        resource_files=[ModelDocument('profiles/core.json', raw)])


def fresh_process(root, body, *arguments):
    """New interpreter, explicit source/test imports and one JSON observation."""
    import json
    from pathlib import Path
    import subprocess
    import sys
    repository = Path(__file__).resolve().parents[2]
    bootstrap = '''import sys, json, os
from pathlib import Path
sys.path[:0] = [str(Path(sys.argv[1])/p) for p in ('src','tests')]
root = Path(sys.argv[2])
'''
    child = subprocess.run([sys.executable, '-I', '-B', '-c', bootstrap + body,
        str(repository), str(root), *arguments], capture_output=True, text=True, check=False)
    assert child.returncode == 0, child.stderr
    return json.loads(child.stdout)
