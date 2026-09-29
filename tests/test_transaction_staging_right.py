"""Adversarial native staging effects and full staged-target revalidation."""
from hashlib import sha256
import json
import os
from pathlib import Path
import stat
from unittest.mock import patch
import pytest
import specroad.changes.staging as staging
from specroad.changes import (PreparedJournal, StagingError, JournalError,
    PublicationAuthority, project_lock, begin_building_journal, stage_building_journal,
    read_prepared_journal, prepare_publication_check)
from specroad.model.canonical import canonical_json_bytes
from specroad.storage.project import ProjectSource
from support.publication import prepared, options, files, ALLOW, TRANSACTION
from support.folds import goal, edit
from support.targets import gate, POLICY
from support.processes import run_core, run_python
from support.portable import build_distribution


def begin(c, h):
    return begin_building_journal(c, held_lock=h, transaction_id=TRANSACTION, authority=ALLOW)


def finish(c, j, h, **kwargs):
    return stage_building_journal(c, j, held_lock=h,
        authority=kwargs.pop('authority', ALLOW), **kwargs)


def late(c, j, h, action):
    calls = []
    def authorize(request):
        calls.append(request.sha256)
        if len(calls) == 2:
            action()
        return True
    return finish(c, j, h, authority=PublicationAuthority('late-check', '1', authorize))


def test_partial_writes_are_completed_and_images_are_private(tmp_path):
    m, p, c = prepared(tmp_path)
    real = os.write
    with project_lock(tmp_path, **options(c)) as h:
        j = begin(c, h)
        with patch.object(os, 'write', side_effect=lambda fd, b: real(fd, b[:7])):
            result = finish(c, j, h)
        for entry in result.data['files']:
            for key in ('staging_path', 'before_image_path'):
                f = tmp_path / entry[key]
                assert stat.S_IMODE(f.stat().st_mode) == 0o600
                assert stat.S_IMODE(f.parent.stat().st_mode) == 0o700
        assert read_prepared_journal(ProjectSource(tmp_path), TRANSACTION, preflight=c).data == result.data
    assert files(tmp_path) == m.source_files


@pytest.mark.parametrize('count', [0, -1, True, None])
def test_invalid_short_write_reports_leave_building(tmp_path, count):
    m, p, c = prepared(tmp_path)
    with project_lock(tmp_path, **options(c)) as h:
        j = begin(c, h)
        with patch.object(os, 'write', return_value=count):
            with pytest.raises(StagingError) as error:
                finish(c, j, h)
        assert error.value.mutation_possible and not error.value.prepared_possible
        assert (tmp_path / j.path).read_bytes() == j.source_bytes
    assert files(tmp_path) == m.source_files


@pytest.mark.parametrize('fail_at', range(1, 10))
def test_each_durable_boundary_failure_has_no_normative_publication(tmp_path, fail_at):
    m, p, c = prepared(tmp_path)
    real = os.fsync
    count = 0
    with project_lock(tmp_path, **options(c)) as h:
        j = begin(c, h)
        def sync(fd):
            nonlocal count
            count += 1
            if count == fail_at:
                raise OSError(5, 'injected sync failure')
            return real(fd)
        with patch.object(os, 'fsync', side_effect=sync):
            with pytest.raises(StagingError) as error:
                finish(c, j, h)
        assert count == fail_at
        assert error.value.mutation_possible
        state = json.loads((tmp_path / j.path).read_bytes())['state']
        assert state == ('prepared' if fail_at == 9 else 'building')
        assert error.value.prepared_possible == (fail_at == 9)
    assert files(tmp_path) == m.source_files


def test_rename_that_succeeds_then_raises_is_not_retried(tmp_path):
    m, p, c = prepared(tmp_path)
    real = os.replace
    calls = []
    with project_lock(tmp_path, **options(c)) as h:
        j = begin(c, h)
        def rename(*args, **kwargs):
            calls.append(args)
            real(*args, **kwargs)
            raise OSError(5, 'lost rename result')
        with patch.object(os, 'replace', side_effect=rename):
            with pytest.raises(StagingError) as error:
                finish(c, j, h)
        assert len(calls) == 1 and error.value.prepared_possible
        assert PreparedJournal((tmp_path / j.path).read_bytes()).data['state'] == 'prepared'
    assert files(tmp_path) == m.source_files


@pytest.mark.parametrize('kind', ['short', 'same-size', 'missing', 'extra', 'symlink', 'hardlink', 'fifo'])
@pytest.mark.parametrize('side', ['staging_path', 'before_image_path'])
def test_corrupt_image_sets_cannot_be_prepared(tmp_path, kind, side):
    m, p, c = prepared(tmp_path)
    with project_lock(tmp_path, **options(c)) as h:
        j = begin(c, h)
        f = tmp_path / j.data['files'][0][side]
        def change():
            data = f.read_bytes()
            old = f.stat()
            if kind == 'short':
                f.write_bytes(data[:-1])
            elif kind == 'same-size':
                f.write_bytes(b'X' + data[1:])
                os.utime(f, ns=(old.st_atime_ns, old.st_mtime_ns))
            elif kind == 'missing':
                f.unlink()
            elif kind == 'extra':
                f.with_name('unexpected.bin').write_bytes(b'extra')
            else:
                f.unlink()
                if kind == 'symlink': f.symlink_to(tmp_path / m.documents[0].path)
                elif kind == 'hardlink': os.link(tmp_path / m.documents[0].path, f)
                else: os.mkfifo(f)
        with pytest.raises(StagingError) as error:
            late(c, j, h, change)
        assert error.value.mutation_possible and not error.value.prepared_possible
        assert (tmp_path / j.path).read_bytes() == j.source_bytes
    assert files(tmp_path) == m.source_files


def test_equivalent_journal_replacement_is_detected(tmp_path):
    m, p, c = prepared(tmp_path)
    with project_lock(tmp_path, **options(c)) as h:
        j = begin(c, h)
        def change():
            f = tmp_path / j.path
            replacement = f.with_name('replacement')
            replacement.write_bytes(j.source_bytes)
            os.replace(replacement, f)
        with pytest.raises(StagingError): late(c, j, h, change)
    assert files(tmp_path) == m.source_files


def test_replaced_staging_directory_is_not_treated_as_same_namespace(tmp_path):
    m, p, c = prepared(tmp_path)
    with project_lock(tmp_path, **options(c)) as h:
        j = begin(c, h)
        def change():
            f = (tmp_path / j.data['files'][0]['staging_path']).parent
            previous = f.with_name('previous')
            f.rename(previous); f.mkdir()
            for item in previous.iterdir(): (f / item.name).write_bytes(item.read_bytes())
            # Retain the old directory as recovery information outside this transaction.
            previous.rename(tmp_path / '.saved-original-staging')
        with pytest.raises(StagingError) as error: late(c, j, h, change)
        assert error.value.exit_code == 6 and not error.value.prepared_possible
        assert (tmp_path / j.path).read_bytes() == j.source_bytes


def test_another_recovery_entry_blocks_own_journal_exception(tmp_path):
    m, p, c = prepared(tmp_path)
    with project_lock(tmp_path, **options(c)) as h:
        j = begin(c, h)
        def change(): (tmp_path / '.specroad/transactions/another').mkdir()
        with pytest.raises(StagingError) as error: late(c, j, h, change)
        assert error.value.reason == 'staging_recovery_set_changed'
        assert (tmp_path / j.path).read_bytes() == j.source_bytes
    assert files(tmp_path) == m.source_files


def test_source_change_in_late_authority_is_not_hidden(tmp_path):
    m, p, c = prepared(tmp_path)
    with project_lock(tmp_path, **options(c)) as h:
        j = begin(c, h)
        def change():
            f = tmp_path / m.documents[0].path
            b = f.read_bytes(); info = f.stat(); f.write_bytes(b'X' + b[1:])
            os.utime(f, ns=(info.st_atime_ns, info.st_mtime_ns))
        with pytest.raises(StagingError): late(c, j, h, change)
        assert (tmp_path / j.path).read_bytes() == j.source_bytes
        assert not (tmp_path / Path(j.path).parent / 'journal.prepared').exists()


def test_actual_staged_target_includes_unchanged_documents(tmp_path):
    m, p, c = prepared(tmp_path, artifacts=[goal(1), goal(2)], operations=[edit(goal(1), 'new')])
    real = staging.validate_model
    observed = []
    with project_lock(tmp_path, **options(c)) as h:
        j = begin(c, h)
        def validate(documents, **kwargs):
            observed.append({d.path: d.content for d in documents})
            e = j.data['files'][0]
            assert observed[-1][e['path']] == (tmp_path / e['staging_path']).read_bytes()
            assert len(observed[-1]) == 2
            return real(documents, **kwargs)
        with patch.object(staging, 'validate_model', side_effect=validate): finish(c, j, h)
    assert len(observed) == 1 and files(tmp_path) == m.source_files


def test_staged_target_validation_failure_preserves_building(tmp_path):
    m, p, c = prepared(tmp_path)
    stage = tmp_path / '.specroad/transactions' / TRANSACTION / 'staging'
    def validate(context):
        findings = [{'severity': 'error', 'reason': 'test_policy_denied'}] if stage.exists() else []
        return context.result(diagnostics=findings)
    g = gate(check=validate)
    c = prepare_publication_check(p, m, policy=POLICY, gates=(g,))
    with project_lock(tmp_path, **options(c)) as h:
        j = begin_building_journal(c, held_lock=h, transaction_id=TRANSACTION,
                                  authority=ALLOW, gates=(g,))
        with pytest.raises(StagingError) as error: finish(c, j, h, gates=(g,))
        assert error.value.reason == 'staging_materialized_target_invalid'
        assert (tmp_path / j.path).read_bytes() == j.source_bytes
    assert files(tmp_path) == m.source_files


def test_changed_target_manifest_is_detected_before_prepared(tmp_path):
    m, p, c = prepared(tmp_path)
    with project_lock(tmp_path, **options(c)) as h:
        j = begin(c, h)
        # The actual immutable target-root check is independent from image hashing.
        from specroad.changes.target_model import TargetModel
        original = TargetModel.manifest
        def manifest(self, artifacts, scope):
            answer = original(self, artifacts, scope)
            if any(a.get('statement') == 'Changed' for a in artifacts):
                # Return a small explicit wrong-root observation, not a valid target.
                class Wrong:
                    sha256 = '0' * 64
                return Wrong()
            return answer
        # Patch just the staged materializer call, not earlier plan verification.
        original_materialize = staging._materialized_target
        def materialize(*args):
            with patch.object(TargetModel, 'manifest', manifest): original_materialize(*args)
        with patch.object(staging, '_materialized_target', side_effect=materialize):
            with pytest.raises(StagingError) as error: finish(c, j, h)
        assert error.value.reason == 'staging_target_root_mismatch'
    assert files(tmp_path) == m.source_files


def test_noop_rechecks_explicit_command_gate(tmp_path):
    m, p, c = prepared(tmp_path, operations=[])
    visits = []
    g = gate(check=lambda context: (visits.append(context.subjects), context.result())[1])
    c = prepare_publication_check(p, m, policy=POLICY, gates=(g,))
    with project_lock(tmp_path, **options(c)) as h:
        j = begin_building_journal(c, held_lock=h, transaction_id=TRANSACTION, authority=ALLOW, gates=(g,))
        visits.clear()
        finish(c, j, h, gates=(g,))
        assert visits and all(set(ids) == {a['id'] for a in m.artifacts} for ids in visits)
    assert files(tmp_path) == m.source_files


@pytest.mark.parametrize('kind', ['bytes', 'missing', 'extra', 'hardlink'])
def test_prepared_reader_rechecks_all_required_images(tmp_path, kind):
    m, p, c = prepared(tmp_path)
    with project_lock(tmp_path, **options(c)) as h: j = finish(c, begin(c, h), h)
    f = tmp_path / j.data['files'][0]['before_image_path']
    if kind == 'bytes': f.write_bytes(b'bad')
    elif kind == 'missing': f.unlink()
    elif kind == 'extra': f.with_name('extra').write_bytes(b'unexpected')
    else: os.link(f, f.with_name('extra-hardlink'))
    with pytest.raises(StagingError): read_prepared_journal(ProjectSource(tmp_path), TRANSACTION, preflight=c)
    assert files(tmp_path) == m.source_files


def test_image_changed_during_prepared_read_is_rejected(tmp_path):
    m, p, c = prepared(tmp_path)
    with project_lock(tmp_path, **options(c)) as h: j = finish(c, begin(c, h), h)
    f = tmp_path / j.data['files'][0]['staging_path']
    real = os.read; changed = []
    def read(fd, size):
        b = real(fd, size)
        if os.readlink('/proc/self/fd/' + str(fd)) == str(f) and b and not changed:
            changed.append(True); data = f.read_bytes(); f.write_bytes(b'X' + data[1:])
        return b
    with patch.object(os, 'read', side_effect=read):
        with pytest.raises(StagingError): read_prepared_journal(ProjectSource(tmp_path), TRANSACTION)
    assert changed and files(tmp_path) == m.source_files


def test_prepared_does_not_allow_generic_publication(tmp_path):
    m, p, c = prepared(tmp_path)
    with project_lock(tmp_path, **options(c)) as h:
        j = finish(c, begin(c, h), h)
        from specroad.changes.lock_values import ProjectLockError
        with pytest.raises(ProjectLockError):
            h.require_publication(ProjectSource(tmp_path), command='change apply',
                request_id=c.request.data['request_id'], transaction_id=TRANSACTION)
    with pytest.raises(ProjectLockError):
        with project_lock(tmp_path, **options(c)): pass
    assert files(tmp_path) == m.source_files


def test_abrupt_child_exit_retains_images_without_normative_publication(tmp_path):
    root = tmp_path / 'project'
    root.mkdir()
    body = '''
import sys, os
sys.path.insert(0, TESTS)
from pathlib import Path
from support.publication import prepared, options, ALLOW, TRANSACTION
from specroad.changes import project_lock, begin_building_journal, stage_building_journal
root=Path(ROOT)
m,p,c=prepared(root)
import json, hashlib
(root.parent/'expected.json').write_text(json.dumps({p:hashlib.sha256(b).hexdigest() for p,b in m.source_files.items()}))
with project_lock(root,**options(c)) as h:
    j=begin_building_journal(c,held_lock=h,transaction_id=TRANSACTION,authority=ALLOW)
    sync=os.fsync
    def crash(fd):
        sync(fd)
        if '/staging/' in os.readlink('/proc/self/fd/'+str(fd)):
            os._exit(41)
    os.fsync=crash
    stage_building_journal(c,j,held_lock=h,authority=ALLOW)
'''.replace('TESTS', repr(str(Path(__file__).parent.resolve()))).replace('ROOT', repr(str(root)))
    result = run_core(body, tmp_path, capture=True)
    assert result.returncode == 41
    transaction = root / '.specroad/transactions' / TRANSACTION
    assert json.loads((transaction / 'journal.json').read_bytes())['state'] == 'building'
    assert list((transaction / 'staging').iterdir())
    expected = json.loads((tmp_path / 'expected.json').read_text())
    assert expected and {p:sha256(b).hexdigest() for p,b in files(root).items()} == expected
    from specroad.changes.lock_values import ProjectLockError
    with pytest.raises(ProjectLockError):
        with project_lock(root, kind='writer', command='change apply',
                          project_id='sample', transaction_id=TRANSACTION, request_id='request-1'): pass


def test_forked_handle_cannot_prepare_parents_journal(tmp_path):
    tests = str(Path(__file__).parent.resolve())
    body = f"""import sys, os
sys.path.insert(0,{tests!r})
from pathlib import Path
from support.publication import prepared, options, ALLOW, TRANSACTION, files
from specroad.changes import project_lock, begin_building_journal, stage_building_journal, StagingError
root=Path({str(tmp_path)!r})
m,p,c=prepared(root)
with project_lock(root,**options(c)) as h:
 j=begin_building_journal(c,held_lock=h,transaction_id=TRANSACTION,authority=ALLOW)
 pid=os.fork()
 if pid==0:
  try: stage_building_journal(c,j,held_lock=h,authority=ALLOW)
  except StagingError: os._exit(0)
  except BaseException: os._exit(3)
  os._exit(2)
 _,status=os.waitpid(pid,0)
 assert os.waitstatus_to_exitcode(status)==0
 assert (root/j.path).read_bytes()==j.source_bytes
 assert not (root/Path(j.path).parent/'staging').exists()
 assert h.check()
assert files(root)==m.source_files
"""
    result = run_core(body, tmp_path, capture=True)
    assert result.returncode == 0, result.stderr


def test_large_inventory_is_not_truncated(tmp_path):
    artifacts = [goal(i) for i in range(1, 152)]
    m, p, c = prepared(tmp_path, artifacts=artifacts, operations=[edit(a, 'new') for a in artifacts])
    with project_lock(tmp_path, **options(c)) as h:
        j = finish(c, begin(c, h), h)
        assert len(j.data['files']) == 151
        assert len(list((tmp_path / Path(j.path).parent / 'staging').iterdir())) == 151
        assert len(list((tmp_path / Path(j.path).parent / 'before').iterdir())) == 151
        assert read_prepared_journal(ProjectSource(tmp_path), TRANSACTION, preflight=c).data == j.data
    assert files(tmp_path) == m.source_files


def test_module_and_zipapp_remain_portable(tmp_path):
    distribution = build_distribution(tmp_path / 'delivery')
    tests = str(Path(__file__).parent.resolve())
    for index, original in enumerate(distribution):
        moved = tmp_path / ('moved-' + str(index) + ('.pyz' if original.suffix == '.pyz' else ''))
        original.rename(moved)
        root = tmp_path / ('project-' + str(index)); root.mkdir()
        body = f'''import sys
sys.path[:0]=[{str(moved)!r},{tests!r}]
from pathlib import Path
from support.publication import prepared,options,ALLOW,TRANSACTION,files
from specroad.changes import project_lock,begin_building_journal,stage_building_journal,read_prepared_journal
from specroad.storage.project import ProjectSource
root=Path({str(root)!r})
m,p,c=prepared(root)
with project_lock(root,**options(c)) as h:
 j=begin_building_journal(c,held_lock=h,transaction_id=TRANSACTION,authority=ALLOW)
 r=stage_building_journal(c,j,held_lock=h,authority=ALLOW)
 assert read_prepared_journal(ProjectSource(root),TRANSACTION,preflight=c).data==r.data
assert files(root)==m.source_files
'''
        result = run_python(['-I', '-S', '-B', '-c', body], tmp_path, capture=True)
        assert result.returncode == 0, result.stderr.decode()


@pytest.mark.parametrize('raw', [b'{', b'[]', b'{} {}', b'{"state":"prepared","state":"building"}', b'\xff'])
def test_invalid_prepared_bytes_do_not_fabricate_a_record(raw):
    with pytest.raises(JournalError): PreparedJournal(raw)


def test_saved_record_in_a_project_copy_is_not_transferable(tmp_path):
    import shutil
    root = tmp_path / 'first'
    m, p, c = prepared(root)
    with project_lock(root, **options(c)) as h: j = finish(c, begin(c, h), h)
    copy = tmp_path / 'copy'
    shutil.copytree(root, copy)
    with pytest.raises(StagingError) as error:
        read_prepared_journal(ProjectSource(copy), TRANSACTION, expected_sha256=j.sha256)
    assert error.value.reason == 'prepared_project_binding_mismatch'
    assert (copy / j.path).read_bytes() == j.source_bytes


def test_empty_project_target_has_no_vacuous_command_gate_success(tmp_path):
    from support.targets import model, plan
    from specroad.model.model_manifest import ProjectReadBinding
    info = tmp_path.stat()
    m = model([], binding=ProjectReadBinding('sample', str(tmp_path), (info.st_dev, info.st_ino)))
    for name, raw in m.source_files.items():
        f = tmp_path / name; f.parent.mkdir(parents=True, exist_ok=True); f.write_bytes(raw)
    p = plan(m, [])
    called = []
    g = gate(check=lambda context: (called.append(context.subjects), context.result())[1])
    c = prepare_publication_check(p, m, policy=POLICY, gates=(g,))
    with project_lock(tmp_path, **options(c)) as h:
        j = begin_building_journal(c, held_lock=h, transaction_id=TRANSACTION,
                                  authority=ALLOW, gates=(g,))
        called.clear()
        result = finish(c, j, h, gates=(g,))
        assert result.data['files'] == []
        assert len(called) == 3 and all(ids == () for ids in called)
    assert files(tmp_path) == m.source_files


def test_unbound_validation_report_keeps_recovery_state(tmp_path):
    from specroad.validation import ModelDocument
    m, p, c = prepared(tmp_path)
    real = staging.validate_model
    with project_lock(tmp_path, **options(c)) as h:
        j = begin(c, h)
        with patch.object(staging, 'validate_model', side_effect=lambda docs, **kw:
                real((ModelDocument(docs[0].path, b'{'),), **kw)):
            with pytest.raises(StagingError) as error: finish(c, j, h)
        assert error.value.exit_code == 4 and error.value.mutation_possible
        assert not error.value.prepared_possible
        assert (tmp_path / j.path).read_bytes() == j.source_bytes
    assert files(tmp_path) == m.source_files
