"""Test-only native writer cuts; every child owns its temporary project.

The production writer receives no fault option. Real syscalls run before a
selected boundary terminates the interpreter without exceptions or finalizers.
This measures process interruption on the current Linux filesystem, not power
loss or a claim about another filesystem's durability guarantees.
"""
from contextlib import ExitStack
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

from specroad.changes import (BuildingJournal, PreparedJournal, CommittingJournal,
    CommittedJournal, LockRecord, project_lock, begin_building_journal,
    stage_building_journal, publish_prepared_journal, finalize_committing_journal,
    cleanup_completed_transaction, prepare_publication_check,
    prepare_discard_recovery, discard_unpublished_transaction,
    complete_published_transaction, rollback_interrupted_transaction,
    cleanup_recovered_transaction, transaction_recovery_lock,
    transaction_preflight, completion_marker_path)
from specroad.cli.contracts import CommandClass
from specroad.model.model_manifest import ProjectReadBinding
from .automatic_recovery import current_model
from .folds import goal, edit
from .model import configuration_value, put
from .publication import ALLOW, TRANSACTION, options, files
from .recovery import RECOVER, tree
from .targets import ACTOR, POLICY, SCOPE, model, plan

PHASES = ('building', 'staging', 'publishing', 'receipts', 'cleanup')
CRASH_EXIT = 23
SENTINEL = 'notes/user-owned.bin'
SENTINEL_BYTES = b'User data outside the normative inventory\x00\xff'


class WriterBoundaryProbe:
    """Observe successful native calls, or stop after one phase-local call.

    Paths are descriptor-resolved before a move/removal and reported relative
    to this owned root. Each syscall retains its real return value and effects.
    """
    def __init__(self, root, phase='', ordinal=-1):
        self.root, self.selected_phase, self.ordinal = root, phase, ordinal
        self.phase = None
        self.events = []
        self.counts = {}

    def path(self, name, directory=None):
        if isinstance(name, int):
            value = Path(os.readlink('/proc/self/fd/' + str(name)))
        else:
            parent = Path.cwd() if directory is None else Path(
                os.readlink('/proc/self/fd/' + str(directory)))
            value = parent / os.fsdecode(name)
        return value.relative_to(self.root).as_posix()

    def boundary(self, operation, paths):
        index = self.counts.get(self.phase, 0)
        self.counts[self.phase] = index + 1
        event = dict(phase=self.phase, ordinal=index, operation=operation, paths=paths)
        self.events.append(event)
        if self.phase == self.selected_phase and index == self.ordinal:
            print(json.dumps({'pid': os.getpid(), 'cut': event}), flush=True)
            os._exit(CRASH_EXIT)

    def __enter__(self):
        self.stack = ExitStack()
        for name in ('fsync', 'mkdir', 'replace', 'rename', 'link', 'unlink', 'rmdir'):
            native = getattr(os, name)

            def call(*args, _name=name, _native=native, **kwargs):
                if _name in ('replace', 'rename', 'link'):
                    paths = [self.path(args[0], kwargs.get('src_dir_fd')),
                             self.path(args[1], kwargs.get('dst_dir_fd'))]
                else:
                    paths = [self.path(args[0], kwargs.get('dir_fd'))]
                result = _native(*args, **kwargs)
                self.boundary(_name, paths)
                return result

            self.stack.enter_context(patch.object(os, name, side_effect=call))
        return self

    def __exit__(self, *exception):
        return self.stack.__exit__(*exception)


def fixture(root):
    root.mkdir(parents=True, exist_ok=True)
    inode = root.stat()
    source = model([goal(1), goal(2)],
        config=configuration_value(transaction_policy={'auto_recover': True}),
        binding=ProjectReadBinding('sample', str(root), (inode.st_dev, inode.st_ino)))
    for path, raw in source.source_files.items():
        put(root, path, raw)
    put(root, SENTINEL, SENTINEL_BYTES)
    change = plan(source, [edit(source.artifacts[0], 'Durable target')])
    return source, change, prepare_publication_check(change, source, policy=POLICY)


def writer(root, phase='', ordinal='-1'):
    source, change, check = fixture(root)
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
        return None
    raw = path.read_bytes()
    cls = {'building': BuildingJournal, 'prepared': PreparedJournal,
           'committing': CommittingJournal, 'committed': CommittedJournal}
    return cls[json.loads(raw)['state']](raw)


def recover(root):
    """Only persisted bytes enter this interpreter; no original plan/check."""
    journal = journal_at(root)
    if journal is None:
        # Before the first complete journal, ownership cannot be guessed.
        before = tree(root)
        result = transaction_preflight(root, command_class=CommandClass.NORMATIVE_WRITE,
            expected_project_id='sample', request_id='following-request',
            authority=RECOVER, actor=ACTOR).data
        assert result['exit_code'] != 0 and not result['recovery_completed']
        assert tree(root) == before
        outcome = 'blocked_before_journal'
    else:
        original = journal.data['state']
        unpublished = original in ('building', 'prepared')
        proof = (prepare_discard_recovery(root, TRANSACTION, expected_project_id='sample',
            expected_journal_sha256=journal.sha256) if unpublished else None)
        lock = LockRecord((root / '.specroad/locks/project.json').read_bytes())
        with transaction_recovery_lock(root, TRANSACTION, project_id='sample',
                request_id=journal.data['request_id'],
                command='recover discard' if unpublished else 'recover run',
                expected_lock_sha256=lock.sha256, expected_journal_sha256=journal.sha256,
                authority=RECOVER, actor=ACTOR, reason='Native writer boundary test', force=True) as held:
            if unpublished:
                result = discard_unpublished_transaction(proof, TRANSACTION, held_lock=held,
                    authority=RECOVER, actor=ACTOR, reason='Native writer boundary test',
                    expected_journal_sha256=journal.sha256).data
                assert result['discard_completed']
                outcome = 'base'
            else:
                from specroad.changes._recovery_integrity import inspect_critical_inputs
                integrity = inspect_critical_inputs(held._files, journal)
                assert not integrity['blockers'], integrity['blockers']
                complete = original == 'committed' or integrity['complete_target_verified']
                if original != 'committed':
                    action = complete_published_transaction if complete else rollback_interrupted_transaction
                    result = action(TRANSACTION, held_lock=held, authority=RECOVER,
                        expected_journal_sha256=journal.sha256).data
                    assert result['commit_completed' if complete else 'rollback_completed']
                from specroad.changes._recovery_terminal import read_terminal_journal
                terminal = read_terminal_journal(held._files, TRANSACTION)
                result = cleanup_recovered_transaction(TRANSACTION, held_lock=held,
                    authority=RECOVER, expected_journal_sha256=terminal.sha256).data
                assert result['cleanup_completed']
                outcome = 'target' if complete else 'base'
        gate = transaction_preflight(root, command_class=CommandClass.READ_ONLY).data
        assert gate['exit_code'] == 0 and not gate['recovery_required'], gate
    # Independently reconstruct the actual normative model after recovery.
    current = current_model(root)
    print(json.dumps({'pid': os.getpid(), 'outcome': outcome,
        'files': {p: b.hex() for p, b in files(root).items()},
        'model_root': current.manifest(current.artifacts, SCOPE).sha256}), flush=True)


def child(root, action, *arguments, exit_code=0):
    repository = Path(__file__).resolve().parents[2]
    bootstrap = '''import sys
from pathlib import Path
sys.path[:0] = [str(Path(sys.argv[1])/p) for p in ('src', 'tests')]
from support.writer_boundaries import writer, recover
(writer if sys.argv[3] == 'writer' else recover)(Path(sys.argv[2]), *sys.argv[4:])
'''
    result = subprocess.run([sys.executable, '-I', '-B', '-c', bootstrap,
        str(repository), str(root), action, *map(str, arguments)],
        stdin=subprocess.DEVNULL, capture_output=True, text=True, check=False)
    assert result.returncode == exit_code, (arguments, result.returncode, result.stdout, result.stderr)
    return [json.loads(line) for line in result.stdout.splitlines()]
