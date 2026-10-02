"""Failure, race and publication boundaries of unpublished recovery."""
from hashlib import sha256
import json
import os
from pathlib import Path
from uuid import UUID
import pytest
from specroad.changes import (RecoveryError, RecoveryAuthority, BuildingJournal,
    CommittingJournal, project_lock, inspect_recovery, TargetModel)
from specroad.model.canonical import canonical_json_bytes
from specroad.security import ProjectBoundary
from specroad.storage._read_only_inputs import _operational_metadata
from support.publication import TRANSACTION, options, files
from support.recovery import pending, recovery_options, discard, tree
from support.committing import staged, publish


def _fdpath(fd):
    return os.readlink('/proc/self/fd/' + str(fd))


def _retained(root, raw):
    return any(p.read_bytes() == raw for p in (root / '.specroad').rglob('*') if p.is_file())


@pytest.mark.parametrize('folder,length', [('staging', 0), ('staging', 7), ('before', 1), ('before', None)])
def test_building_partial_images_are_archived_not_lost(tmp_path, folder, length):
    m, p, c, j = pending(tmp_path)
    entry = j.data['files'][0]
    content = c.request.documents[0].content if folder == 'staging' else m.source_files[entry['path']]
    partial = content if length is None else content[:length]
    image = tmp_path / entry[folder + '_image_path' if folder == 'before' else 'staging_path']
    image.parent.mkdir(); image.write_bytes(partial)
    status = inspect_recovery(tmp_path, preflight=c).data['transactions'][0]
    assert status['permitted_actions'] == ['discard']
    with project_lock(tmp_path, **recovery_options(c)) as held:
        result = discard(c, j, held).data
    assert (tmp_path / result['archive_path'] / folder / image.name).read_bytes() == partial
    assert files(tmp_path) == m.source_files


@pytest.mark.parametrize('length', [0, 19, None])
def test_interrupted_prepared_marker_is_preserved(tmp_path, length):
    m, p, c, j = pending(tmp_path)
    value = j.data; value['state'] = 'prepared'; raw = canonical_json_bytes(value)
    partial = raw if length is None else raw[:length]
    marker = (tmp_path / j.path).with_name('journal.prepared'); marker.write_bytes(partial)
    with project_lock(tmp_path, **recovery_options(c)) as held:
        result = discard(c, j, held).data
    assert (tmp_path / result['archive_path'] / 'journal.prepared').read_bytes() == partial
    assert files(tmp_path) == m.source_files


@pytest.mark.parametrize('partial', [b'not-an-image', b'x' * 2048])
def test_unbound_or_oversized_partial_image_blocks_without_audit(tmp_path, partial):
    m, p, c, j = pending(tmp_path)
    image = tmp_path / j.data['files'][0]['staging_path']; image.parent.mkdir(); image.write_bytes(partial)
    with project_lock(tmp_path, **recovery_options(c)) as held:
        before = tree(tmp_path)
        with pytest.raises(RecoveryError) as error: discard(c, j, held)
        assert not error.value.mutation_possible and tree(tmp_path) == before


def test_one_of_multiple_preparations_is_discarded_without_touching_others(tmp_path):
    m, p, c, j = pending(tmp_path)
    other = j.data; other['transaction_id'] = 'second-preparation'
    for entry in other['files']:
        for key in ('staging_path', 'before_image_path'):
            if entry[key] is not None: entry[key] = entry[key].replace(TRANSACTION, other['transaction_id'])
    second = BuildingJournal(canonical_json_bytes(other))
    path = tmp_path / second.path; path.parent.mkdir(); path.write_bytes(second.source_bytes)
    rows = inspect_recovery(tmp_path, preflight=c).data['transactions']
    assert len(rows) == 2 and all(r['permitted_actions'] == ['discard'] for r in rows)
    with project_lock(tmp_path, **recovery_options(c)) as held:
        outcome = discard(c, j, held).data
    assert outcome['remaining_active_paths'] == ['.specroad/transactions/second-preparation']
    assert path.read_bytes() == second.source_bytes and files(tmp_path) == m.source_files
    assert _operational_metadata(ProjectBoundary(tmp_path))['recovery_required']


@pytest.mark.parametrize('state', ['committing', 'rolling_back', 'corrupt', 'rolled_back'])
def test_later_states_never_authorize_discard_even_with_matching_hash(tmp_path, state):
    m, p, c, j = pending(tmp_path)
    value = j.data; value['state'] = state
    raw = canonical_json_bytes(value); (tmp_path / j.path).write_bytes(raw)
    row = inspect_recovery(tmp_path, preflight=c).data['transactions'][0]
    # Changing only the state does not create a valid rollback journal;
    # missing rollback metadata is reported as corruption, with the claimed
    # state retained separately for diagnosis. Discard remains forbidden.
    expected_state = 'corrupt' if state in ('rolling_back', 'rolled_back') else state
    assert row['state'] == expected_state and row['observed_state'] == state
    assert row['permitted_actions'] == []
    with project_lock(tmp_path, **recovery_options(c)) as held:
        before = tree(tmp_path)
        with pytest.raises(RecoveryError) as error:
            discard(c, j, held, expected_journal_sha256=sha256(raw).hexdigest())
        assert not error.value.mutation_possible and tree(tmp_path) == before


def test_real_published_targets_and_before_images_survive_rejected_discard(tmp_path):
    with staged(tmp_path) as (m, p, c, held, prepared_journal):
        result = publish(c, prepared_journal, held)
        assert result.data['all_files_published']
    journal = CommittingJournal((tmp_path / prepared_journal.path).read_bytes())
    row = inspect_recovery(tmp_path, preflight=c).data['transactions'][0]
    assert row['state'] == 'committing' and row['published_count'] == 1
    assert row['published_entries'] == [journal.data['files'][0]['path']]
    assert row['permitted_actions'] == []
    with project_lock(tmp_path, **recovery_options(c)) as held:
        before = tree(tmp_path)
        with pytest.raises(RecoveryError): discard(c, journal, held)
        assert tree(tmp_path) == before
    assert files(tmp_path) != m.source_files


@pytest.mark.parametrize('change', ['configuration', 'target-before-ack', 'new-json', 'same-size-byte'])
def test_any_basis_deviation_blocks_without_operational_write(tmp_path, change):
    m, p, c, j = pending(tmp_path, 'prepared')
    target = tmp_path / j.data['files'][0]['path']
    if change == 'configuration': (tmp_path / 'specroad.json').write_bytes(b'{}')
    elif change == 'target-before-ack': target.write_bytes(c.request.documents[0].content)
    elif change == 'new-json': target.with_name('unexpected.json').write_bytes(b'{}')
    else:
        raw = target.read_bytes(); target.write_bytes(b'X' + raw[1:])
    with project_lock(tmp_path, **recovery_options(c)) as held:
        before = tree(tmp_path)
        with pytest.raises(RecoveryError) as error: discard(c, j, held)
        assert not error.value.mutation_possible and tree(tmp_path) == before
    assert inspect_recovery(tmp_path, preflight=c).data['transactions'][0]['permitted_actions'] == []


@pytest.mark.parametrize('field,wrong', [('published_count', 1), ('published_count', True), ('files', [])])
def test_self_consistent_or_forged_journal_is_not_base_proof(tmp_path, field, wrong):
    m, p, c, j = pending(tmp_path)
    value = j.data; value[field] = wrong
    raw = canonical_json_bytes(value); (tmp_path / j.path).write_bytes(raw)
    with project_lock(tmp_path, **recovery_options(c)) as held:
        before = tree(tmp_path)
        with pytest.raises(RecoveryError): discard(c, j, held, expected_journal_sha256=sha256(raw).hexdigest())
        assert tree(tmp_path) == before


def test_preflight_from_another_project_inode_is_not_accepted(tmp_path):
    root = tmp_path / 'first'; root.mkdir()
    m, p, c, j = pending(root)
    other = tmp_path / 'second'; other.mkdir()
    _, _, wrong, _ = pending(other)
    with project_lock(root, **recovery_options(c)) as held:
        before = tree(tmp_path)
        with pytest.raises(RecoveryError): discard(wrong, j, held)
        assert tree(tmp_path) == before


@pytest.mark.parametrize('kind', ['request-mutation', 'exception', 'base-mutation', 'work-mutation'])
def test_authority_cannot_bypass_post_callback_binding_checks(tmp_path, kind):
    m, p, c, j = pending(tmp_path, 'prepared')
    target = tmp_path / j.data['files'][0]['path']
    marker = (tmp_path / j.path).with_name('foreign-evidence')
    def check(request):
        if kind == 'request-mutation': request['reason'] = 'different request'
        elif kind == 'exception': raise RuntimeError('denied by host')
        elif kind == 'base-mutation': target.write_bytes(b'changed externally')
        else: marker.write_bytes(b'concurrent evidence')
        return True
    with project_lock(tmp_path, **recovery_options(c)) as held:
        with pytest.raises(RecoveryError) as error:
            discard(c, j, held, authority=RecoveryAuthority('host', '1', check))
        assert not error.value.mutation_possible
        assert (tmp_path / j.path).read_bytes() == j.source_bytes
        assert not (tmp_path / '.specroad/recovery/transaction-audit').exists()
    if kind == 'base-mutation': assert target.read_bytes() == b'changed externally'
    elif kind == 'work-mutation': assert marker.read_bytes() == b'concurrent evidence'


@pytest.mark.parametrize('entry,kind', [('journal', 'symlink'), ('image', 'symlink'),
                                      ('journal', 'hardlink'), ('image', 'hardlink')])
def test_linked_journal_or_evidence_is_never_followed_for_discard(tmp_path, entry, kind):
    root = tmp_path / 'project'; root.mkdir()
    m, p, c, j = pending(root, 'prepared')
    target = root / (j.path if entry == 'journal' else j.data['files'][0]['before_image_path'])
    outside = tmp_path / 'external-evidence'; outside.write_bytes(target.read_bytes())
    target.unlink()
    if kind == 'symlink': target.symlink_to(outside)
    else: os.link(outside, target)
    with project_lock(root, **recovery_options(c)) as held:
        before = tree(tmp_path)
        with pytest.raises(RecoveryError) as error: discard(c, j, held)
        assert not error.value.mutation_possible and tree(tmp_path) == before
    assert outside.exists()


@pytest.mark.parametrize('failure', ['intent.json', 'journal.discard', '/transactions', 'completed.json'])
def test_interrupted_durability_never_claims_success_or_loses_proof(tmp_path, monkeypatch, failure):
    m, p, c, j = pending(tmp_path, 'prepared')
    real = os.fsync; fired = False
    def fsync(fd):
        nonlocal fired
        if not fired and _fdpath(fd).endswith(failure):
            fired = True
            raise OSError('injected local durability failure')
        return real(fd)
    with project_lock(tmp_path, **recovery_options(c)) as held:
        monkeypatch.setattr(os, 'fsync', fsync)
        with pytest.raises(RecoveryError) as error: discard(c, j, held)
        assert error.value.mutation_possible and error.value.diagnostic()['discard_completed'] is False
    assert fired and files(tmp_path) == m.source_files
    assert _retained(tmp_path, j.source_bytes)
    for doc in c.request.documents: assert _retained(tmp_path, doc.content)


def test_missing_archive_after_supposed_rename_cannot_be_success(tmp_path, monkeypatch):
    m, p, c, j = pending(tmp_path, 'prepared')
    with project_lock(tmp_path, **recovery_options(c)) as held:
        monkeypatch.setattr(os, 'rename', lambda *a, **kw: None)
        with pytest.raises(RecoveryError) as error: discard(c, j, held)
        assert error.value.mutation_possible
    assert files(tmp_path) == m.source_files and _retained(tmp_path, j.source_bytes)
    assert not list((tmp_path / '.specroad/recovery/transaction-audit').rglob('completed.json'))


def test_existing_audit_event_is_never_overwritten(tmp_path, monkeypatch):
    m, p, c, j = pending(tmp_path)
    event = UUID('8172c747-6481-4d45-9d61-08e402994bc1')
    audit = tmp_path / '.specroad/recovery/transaction-audit' / str(event)
    audit.mkdir(parents=True); (audit / 'prior.json').write_bytes(b'prior audit')
    with project_lock(tmp_path, **recovery_options(c)) as held:
        before = tree(tmp_path)
        monkeypatch.setattr('specroad.changes.recovery.uuid4', lambda: event)
        with pytest.raises(RecoveryError): discard(c, j, held)
        assert tree(tmp_path) == before


def test_work_swap_after_intent_is_detected_and_preserved(tmp_path, monkeypatch):
    m, p, c, j = pending(tmp_path, 'prepared')
    image = tmp_path / j.data['files'][0]['staging_path']
    real = os.fsync; fired = False
    def fsync(fd):
        nonlocal fired
        real(fd)
        if not fired and _fdpath(fd).endswith('/intent.json'):
            fired = True
            original = image.read_bytes(); replacement = image.with_name('replacement')
            replacement.write_bytes(original); os.replace(replacement, image)
    with project_lock(tmp_path, **recovery_options(c)) as held:
        monkeypatch.setattr(os, 'fsync', fsync)
        with pytest.raises(RecoveryError) as error: discard(c, j, held)
        assert error.value.mutation_possible
    assert fired and (tmp_path / j.path).read_bytes() == j.source_bytes
    assert files(tmp_path) == m.source_files and image.exists()


def test_status_refuses_a_journal_changed_during_observation(tmp_path, monkeypatch):
    m, p, c, j = pending(tmp_path)
    original = TargetModel.snapshot; fired = False
    def snapshot(self):
        nonlocal fired
        if not fired:
            fired = True
            (tmp_path / j.path).write_bytes(j.source_bytes + b'\n')
        return original(self)
    monkeypatch.setattr(TargetModel, 'snapshot', snapshot)
    with pytest.raises(RecoveryError) as error: inspect_recovery(tmp_path, preflight=c)
    assert fired and error.value.exit_code == 6
    assert (tmp_path / j.path).read_bytes() == j.source_bytes + b'\n'


def test_successful_discard_unblocks_a_real_native_writer(tmp_path):
    m, p, c, j = pending(tmp_path, 'prepared')
    with project_lock(tmp_path, **recovery_options(c)) as held: discard(c, j, held)
    before = tree(tmp_path)
    with project_lock(tmp_path, **options(c)) as held: assert held.check()
    assert tree(tmp_path) == before


def test_passive_audit_reservation_requires_a_real_directory(tmp_path):
    path = tmp_path / '.specroad/recovery/transaction-audit'
    path.parent.mkdir(parents=True); path.write_bytes(b'not a directory')
    assert _operational_metadata(ProjectBoundary(tmp_path))['recovery_required']


@pytest.mark.parametrize('wrong_state', [None, [], {}, 7])
def test_malformed_state_is_diagnosed_without_raw_type_error(tmp_path, wrong_state):
    m, p, c, j = pending(tmp_path)
    value = j.data; value['state'] = wrong_state
    raw = canonical_json_bytes(value); (tmp_path / j.path).write_bytes(raw)
    before = tree(tmp_path)
    row = inspect_recovery(tmp_path).data['transactions'][0]
    assert row['permitted_actions'] == [] and not row['journal_schema_validated']
    assert tree(tmp_path) == before


def test_intent_binds_exact_preserved_partial_image_hashes(tmp_path):
    m, p, c, j = pending(tmp_path)
    image = tmp_path / j.data['files'][0]['staging_path']; image.parent.mkdir()
    partial = c.request.documents[0].content[:13]; image.write_bytes(partial)
    with project_lock(tmp_path, **recovery_options(c)) as held:
        result = discard(c, j, held).data
    intent = json.loads((tmp_path / result['audit_path'] / 'intent.json').read_bytes())
    manifest = {e['path']: e for e in intent['work_files']}
    assert manifest['journal.json']['sha256'] == j.sha256
    assert manifest['staging/0.bin']['size'] == 13
    assert manifest['staging/0.bin']['sha256'] == sha256(partial).hexdigest()
    assert intent['actor']['actor_type'] == 'human' and intent['phase'] == 'intent'


def test_archive_corruption_during_completion_is_not_reported_successful(tmp_path, monkeypatch):
    m, p, c, j = pending(tmp_path, 'prepared')
    real = os.fsync; fired = False
    def fsync(fd):
        nonlocal fired
        real(fd)
        path = Path(_fdpath(fd))
        if not fired and path.name == 'completed.json':
            fired = True
            (path.parent / 'journal.before.json').write_bytes(b'externally changed')
    with project_lock(tmp_path, **recovery_options(c)) as held:
        monkeypatch.setattr(os, 'fsync', fsync)
        with pytest.raises(RecoveryError) as error: discard(c, j, held)
        assert error.value.mutation_possible
    assert fired and files(tmp_path) == m.source_files
