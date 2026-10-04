"""Fresh-process prepared writers and recovery consumers for owned fixtures."""
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

from specroad.changes import (PreparedJournal, BuildingJournal, DiscardedJournal, RecoveryError, StagingError,
    RecoveryAuthority, TargetModel,
    begin_building_journal, stage_building_journal, prepare_publication_check,
    prepare_discard_recovery, discard_unpublished_transaction, inspect_recovery,
    project_lock, transaction_recovery_lock, LockRecord)
from support.publication import ALLOW, TRANSACTION, files, options, prepared
from support.targets import ACTOR, POLICY, SCOPE, TIME, model, plan
from support.folds import goal, edit, create


def child(root, mode, *arguments, exit_code=0):
    repo = Path(__file__).resolve().parents[2]
    bootstrap = ('import sys\nfrom pathlib import Path\n'
        'sys.path[:0] = [str(Path(sys.argv[1])/p) for p in ("src", "tests")]\n'
        'from support.discard_restart import writer, recover\n'
        '(writer if sys.argv[3] == "writer" else recover)(Path(sys.argv[2]), *sys.argv[4:])\n')
    result = subprocess.run([sys.executable, '-I', '-B', '-c', bootstrap,
        str(repo), str(root), mode, *arguments], capture_output=True, text=True, check=False)
    assert result.returncode == exit_code, result.stderr
    return json.loads(result.stdout)


def fixture(root, variant):
    m, p, check = prepared(root, artifacts=[goal(), goal(1)])
    if variant in ('create', 'noop'):
        created = goal(2, created_at=TIME, updated_at=TIME, created_by=ACTOR, updated_by=ACTOR)
        p = plan(m, [create(created)] if variant == 'create' else [])
        check = prepare_publication_check(p, m, policy=POLICY)
    elif variant == 'resources':
        from specroad.model.attachments import AttachmentDescriptor
        from specroad.validation import ModelDocument
        from support.profiles import profile_data
        raw = b'Bound attachment from original preparation'
        a = AttachmentDescriptor('attachments/source.bin', 'application/octet-stream',
                                 len(raw), sha256(raw).hexdigest())
        m = model([goal(), goal(1)], binding=m.binding,
            profiles=[profile_data(profile_id='core'), profile_data(profile_id='domain')],
            resource_files=[ModelDocument(a.path, raw)], attachments=[a])
        for name, content in m.source_files.items():
            path = root / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(content)
        p = plan(m, [edit(m.artifacts[0], 'Changed')])
        check = prepare_publication_check(p, m, policy=POLICY)
    elif variant == 'package':
        from importlib.resources import files as resources
        from specroad.model.language_package_values import LanguagePackage
        from specroad.profiles import ProfileResource, compose_profiles
        from specroad.validation import ModelDocument
        package = LanguagePackage(resources('specroad.language_data').joinpath('packages/de.json').read_bytes())
        profiles = [ProfileResource(d.content) for d in m.resource_files]
        profile = compose_profiles(profiles, core_key=profiles[0].key, language_packages=[package])
        m = TargetModel(m.configuration_bytes, m.binding, m.documents, profile=profile,
                        resource_files=m.resource_files, language_packages=[package])
        extra = ModelDocument('profiles/language-data/packages/de.json', package.source_bytes)
        path = root / extra.path; path.parent.mkdir(parents=True); path.write_bytes(extra.content)
        p = plan(m, [edit(m.artifacts[0], 'Changed')])
        check = prepare_publication_check(p, m, policy=POLICY, package_files=[extra])
    else:
        assert variant == 'update'
    return m, p, check


def writer(root, ending, variant, state='prepared'):
    m, p, check = fixture(root, variant)
    with project_lock(root, **options(check)) as held:
        journal = begin_building_journal(check, held_lock=held, transaction_id=TRANSACTION, authority=ALLOW)
        def report():
            print(json.dumps({'pid': os.getpid(), 'journal_sha256': journal.sha256,
                'base_model_root_sha256': m.manifest(m.artifacts, SCOPE).sha256,
                'files': {p: sha256(b).hexdigest() for p, b in files(root).items()}}), flush=True)
        if state == 'prepared':
            journal = stage_building_journal(check, journal, held_lock=held, authority=ALLOW)
        elif state != 'building':
            native_write = os.write
            fired = []
            def interrupted(fd, raw):
                path = Path(os.readlink('/proc/self/fd/' + str(fd)))
                selected = ((state == 'before_prefix' and path.parent.name == 'before')
                    or (state == 'staging_prefix' and path.parent.name == 'staging')
                    or (state in ('prepared_prefix', 'complete_images') and path.name == 'journal.prepared'))
                if not fired and selected:
                    fired.append(True)
                    if state != 'complete_images':
                        assert native_write(fd, raw[:17]) == 17
                    if ending == 'abrupt':
                        report()
                        os._exit(23)
                    raise OSError(5, 'Interrupted original preparation')
                return native_write(fd, raw)
            with patch.object(os, 'write', side_effect=interrupted):
                try:
                    stage_building_journal(check, journal, held_lock=held, authority=ALLOW)
                except StagingError:
                    assert fired
                else:
                    raise AssertionError('Preparation interruption was not reached')
        report()
        if ending == 'abrupt':
            os._exit(23)
        assert ending == 'released'


def journal_at(root):
    path = root / '.specroad/transactions' / TRANSACTION / 'journal.json'
    if path.exists():
        raw = path.read_bytes()
    else:
        from specroad.changes import transaction_receipt_path
        raw = json.dumps(json.loads((root / transaction_receipt_path(TRANSACTION)).read_bytes())['journal']).encode()
        from specroad.model.canonical import canonical_json_bytes
        raw = canonical_json_bytes(json.loads(raw))
    cls = {'building': BuildingJournal, 'prepared': PreparedJournal, 'rolled_back': DiscardedJournal}
    return cls[json.loads(raw)['state']](raw)


def recover(root, fault_site='', fault_mode='', ending='released'):
    journal = journal_at(root)
    # Observe actual native write calls as well as comparing resulting bytes.
    native = {name: getattr(os, name) for name in ('open', 'replace', 'rename', 'unlink')}
    writes = []

    def normative(path, fd=None):
        base = root if fd is None else Path(os.readlink('/proc/self/fd/' + str(fd)))
        target = base / os.fsdecode(path)
        if not target.is_relative_to(root):
            return False
        parts = target.relative_to(root).parts
        return bool(parts) and parts[0] in ('specroad.json', 'spec', 'profiles', 'rules', 'mappings', 'attachments')

    def opened(path, flags, *args, **kwargs):
        if flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC) and normative(path, kwargs.get('dir_fd')):
            writes.append('open')
        return native['open'](path, flags, *args, **kwargs)

    def moved(name):
        def operation(src, dst, *args, **kwargs):
            if normative(src, kwargs.get('src_dir_fd')) or normative(dst, kwargs.get('dst_dir_fd')):
                writes.append(name)
            return native[name](src, dst, *args, **kwargs)
        return operation

    def removed(path, *args, **kwargs):
        if normative(path, kwargs.get('dir_fd')):
            writes.append('unlink')
        return native['unlink'](path, *args, **kwargs)

    authority = RecoveryAuthority('restart-fixture-host', '1', lambda request: True)
    common = dict(project_id=journal.data['project_id'], request_id=journal.data['request_id'],
                  command='recover discard')
    lock_path = root / '.specroad/locks/project.json'
    if lock_path.exists():
        lock = LockRecord(lock_path.read_bytes())
        lock_context = transaction_recovery_lock(root, TRANSACTION, **common,
            expected_lock_sha256=lock.sha256, expected_journal_sha256=journal.sha256,
            authority=authority, actor=ACTOR, reason='Explicit recovery of stopped writer', force=True)
    else:
        lock_context = project_lock(root, kind='recovery', transaction_id=TRANSACTION, **common)
    with patch.object(TargetModel, '__init__', side_effect=AssertionError('No regular target model load')), \
            patch('specroad.changes.publication_check.prepare_publication_check', side_effect=AssertionError('No replanning')), \
            patch('specroad.storage.read_only.validate_project_read_only', side_effect=AssertionError('No ordinary load')), \
            patch.object(os, 'open', side_effect=opened), \
            patch.object(os, 'replace', side_effect=moved('replace')), \
            patch.object(os, 'rename', side_effect=moved('rename')), \
            patch.object(os, 'unlink', side_effect=removed):
        before = files(root)
        proof = prepare_discard_recovery(root, TRANSACTION, expected_project_id='sample',
                                         expected_journal_sha256=journal.sha256)
        rows = inspect_recovery(root, preflight=proof).data['transactions']
        status = next((row for row in rows if row.get('transaction_id') == TRANSACTION), None)
        from contextlib import nullcontext
        from support.discard_faults import DiscardFault
        fault = DiscardFault(root, fault_site, fault_mode, process_stop=ending == 'abrupt') if fault_site else None
        try:
            with lock_context as held, fault if fault is not None else nullcontext():
                result = discard_unpublished_transaction(proof, TRANSACTION, held_lock=held,
                    authority=authority, actor=ACTOR, reason='Explicit restart discard',
                    expected_journal_sha256=journal.sha256).data
        except RecoveryError as error:
            if fault is None or not fault.fired:
                raise
            assert files(root) == before
            print(json.dumps({'pid': os.getpid(), 'failure': error.diagnostic(),
                              'native_normative_writes': writes}))
            return
        assert fault is None, 'Requested recovery interruption was not reached'
        assert files(root) == before
    with project_lock(root, kind='writer', project_id='sample', request_id='next-request',
                      transaction_id='next-transaction', command='change apply'):
        pass
    print(json.dumps({'pid': os.getpid(), 'preflight': proof.data, 'status': status,
                      'result': result, 'native_normative_writes': writes, 'next_writer_allowed': True}))
