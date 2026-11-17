"""Test-only native writer cuts; every child owns its temporary project.

The production writer receives no fault option. Real syscalls run before a
selected boundary terminates the interpreter without exceptions or finalizers.
This measures process interruption on the current Linux filesystem, not power
loss or a claim about another filesystem's durability guarantees.
"""
import json
import os
from pathlib import Path
import subprocess
import sys

from specroad.changes import BuildingJournal, PreparedJournal, CommittingJournal, CommittedJournal, RollingBackJournal, RolledBackJournal, DiscardedJournal, LockRecord, project_lock, begin_building_journal, stage_building_journal, publish_prepared_journal, finalize_committing_journal, cleanup_completed_transaction, prepare_publication_check, transaction_preflight, completion_marker_path, transaction_receipt_path
from specroad.cli.contracts import CommandClass
from specroad.model.model_manifest import ProjectReadBinding
from .automatic_recovery import current_model
from .native_boundaries import CRASH_EXIT, WriterBoundaryProbe
from .folds import goal, edit, create
from .model import configuration_value, put
from .publication import ALLOW, TRANSACTION, options, files
from .recovery import RECOVER, tree
from .targets import ACTOR, TIME, POLICY, SCOPE, model, plan

PHASES = ('building', 'staging', 'publishing', 'receipts', 'cleanup')
SENTINEL = 'notes/user-owned.bin'
SENTINEL_BYTES = b'User data outside the normative inventory\x00\xff'


def fixture(root, variant='single'):
    assert variant in ('single', 'multi')
    root.mkdir(parents=True, exist_ok=True)
    inode = root.stat()
    source = model([goal(1), goal(2)] if variant == 'single' else [goal(1), goal(2), goal(3)],
        config=configuration_value(transaction_policy={'retain_receipts': True}),
        binding=ProjectReadBinding('sample', str(root), (inode.st_dev, inode.st_ino)))
    for path, raw in source.source_files.items():
        put(root, path, raw)
    put(root, SENTINEL, SENTINEL_BYTES)
    operations = [edit(source.artifacts[0], 'Durable target')]
    if variant == 'multi':
        operations += [edit(source.artifacts[1], 'Second durable target'),
            create(goal(0, revision=1, created_at=TIME, updated_at=TIME,
                        created_by=ACTOR, updated_by=ACTOR))]
    change = plan(source, operations)
    return source, change, prepare_publication_check(change, source, policy=POLICY)


def writer(root, phase='', ordinal='-1', variant='single'):
    source, change, check = fixture(root, variant)
    before = {**source.source_files, SENTINEL: SENTINEL_BYTES}
    after = {**before, **{d.path: d.content for d in check.request.documents}}
    print(json.dumps({'pid': os.getpid(),
        'before': {p: b.hex() for p, b in before.items()},
        'after': {p: b.hex() for p, b in after.items()},
        'base_root': change.data['base']['model_root_sha256'],
        'target_root': change.data['expected_result']['model_root_sha256']}), flush=True)
    with project_lock(root, **options(check)) as held:
        with WriterBoundaryProbe(root, phase, int(ordinal)) as probe:
            probe.phase = 'building'
            journal = begin_building_journal(check, held_lock=held,
                transaction_id=TRANSACTION, authority=ALLOW)
            probe.phase = 'staging'
            journal = stage_building_journal(check, journal, held_lock=held, authority=ALLOW)
            probe.phase = 'publishing'
            publish_prepared_journal(check, journal, held_lock=held, authority=ALLOW)
            journal = CommittingJournal((root / journal.path).read_bytes())
            probe.phase = 'receipts'
            result = finalize_committing_journal(check, journal, held_lock=held, authority=ALLOW)
            assert result.data['commit_completed']
            probe.phase = 'cleanup'
            result = cleanup_completed_transaction(check, TRANSACTION,
                held_lock=held, authority=ALLOW)
            assert result.data['cleanup_completed']
    assert not phase, 'Selected native boundary was not reached'
    assert files(root) == after
    print(json.dumps({'pid': os.getpid(), 'events': probe.events,
                      'completed': result.data}), flush=True)


def journal_at(root):
    path = root / '.specroad/transactions' / TRANSACTION / 'journal.json'
    if not path.exists():
        path = root / completion_marker_path(TRANSACTION)
    if not path.exists():
        path = path.with_name('rolled_back.json')
    if not path.exists():
        path = root / transaction_receipt_path(TRANSACTION)
        if not path.exists():
            return None
        value = json.loads(path.read_bytes())
        assert value['action'] == 'discard'
        from specroad.model.canonical import canonical_json_bytes
        return DiscardedJournal(canonical_json_bytes(value['journal']))
    raw = path.read_bytes()
    value = json.loads(raw)
    if value['state'] == 'rolled_back' and 'discard' in value:
        return DiscardedJournal(raw)
    cls = {'building': BuildingJournal, 'prepared': PreparedJournal,
           'committing': CommittingJournal, 'committed': CommittedJournal,
           'rolling_back': RollingBackJournal, 'rolled_back': RolledBackJournal}
    return cls[value['state']](raw)






def child(root, action, *arguments, exit_code=0):
    repository = Path(__file__).resolve().parents[2]
    bootstrap = '''import sys
from pathlib import Path
sys.path[:0] = [str(Path(sys.argv[1])/p) for p in ('src', 'tests')]
from support.writer_boundaries import writer
assert sys.argv[3] == 'writer'
writer(Path(sys.argv[2]), *sys.argv[4:])
'''
    result = subprocess.run([sys.executable, '-I', '-B', '-c', bootstrap,
        str(repository), str(root), action, *map(str, arguments)],
        stdin=subprocess.DEVNULL, capture_output=True, text=True, check=False)
    assert result.returncode == exit_code, (arguments, result.returncode, result.stdout, result.stderr)
    return [json.loads(line) for line in result.stdout.splitlines()]
