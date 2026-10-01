"""Recovery state/data contracts and actual audited local filesystem effects."""
import copy
from hashlib import sha256
import json
from pathlib import Path
from unittest.mock import patch
import pytest
from specroad.changes import (RecoveryError, RecoveryAuthority, DiscardedJournal,
    inspect_recovery, project_lock, inspect_project_lock)
from specroad.security import ProjectBoundary
from specroad.storage._read_only_inputs import _operational_metadata
from support.publication import TRANSACTION, files
from support.recovery import pending, recovery_options, discard, tree


@pytest.mark.parametrize('state', ['building', 'prepared'])
def test_status_is_read_only_and_reports_bound_unpublished_state(tmp_path, state):
    m, p, c, j = pending(tmp_path, state)
    before = tree(tmp_path)
    status = inspect_recovery(tmp_path, preflight=c, expected_project_id='sample')
    row = status.data['transactions'][0]
    assert row['state'] == state and row['journal_sha256'] == j.sha256
    assert row['base_model_root_sha256'] == p.data['base']['model_root_sha256']
    assert row['target_model_root_sha256'] == c.request.data['target_root_sha256']
    assert row['published_count'] == 0 and row['published_entries'] == []
    assert row['permitted_actions'] == ['discard'] and row['base_verified'] is True
    assert status.data['model_loaded'] is False and status.data['write_authorized'] is False
    assert tree(tmp_path) == before


@pytest.mark.parametrize('state', ['building', 'prepared'])
def test_discard_preserves_base_and_archives_all_evidence(tmp_path, state):
    m, p, c, j = pending(tmp_path, state)
    before = files(tmp_path)
    workdir = (tmp_path / j.path).parent
    evidence = {f.relative_to(workdir).as_posix(): f.read_bytes()
                for f in workdir.rglob('*') if f.is_file()}
    with project_lock(tmp_path, **recovery_options(c)) as held:
        result = discard(c, j, held).data
        assert result['discard_completed'] and result['state'] == 'rolled_back'
        assert result['normative_writes'] == 0 and result['evidence_preserved']
        assert result['model_loaded'] is False
        assert held.check()
    assert files(tmp_path) == before
    assert not workdir.exists()
    audit = tmp_path / result['audit_path']
    assert (audit / 'journal.before.json').read_bytes() == j.source_bytes
    terminal = DiscardedJournal((audit / 'work/journal.json').read_bytes())
    assert terminal.data['discard']['previous_state'] == state
    assert terminal.data['discard']['journal_before_sha256'] == j.sha256
    assert terminal.sha256 == result['journal_sha256']
    assert sha256((audit / 'intent.json').read_bytes()).hexdigest() == result['intent_sha256']
    for relative, raw in evidence.items():
        if relative != 'journal.json': assert (audit / 'work' / relative).read_bytes() == raw
    assert json.loads((audit / 'completed.json').read_bytes())['state'] == 'rolled_back'
    assert inspect_project_lock(tmp_path).data['journal_paths'] == []
    assert inspect_recovery(tmp_path).data['transactions'] == []
    assert _operational_metadata(ProjectBoundary(tmp_path))['consistency_state'] == 'consistent'


def test_discard_noop_has_no_normative_or_request_write(tmp_path):
    m, p, c, j = pending(tmp_path, 'prepared', operations=[])
    with project_lock(tmp_path, **recovery_options(c)) as held:
        outcome = discard(c, j, held).data
    assert outcome['discard_completed'] and files(tmp_path) == m.source_files
    assert not (tmp_path / '.specroad/requests').exists()


def test_status_without_base_proof_does_not_grant_discard(tmp_path):
    m, p, c, j = pending(tmp_path)
    row = inspect_recovery(tmp_path).data['transactions'][0]
    assert row['state'] == 'building' and row['permitted_actions'] == []
    assert not row['base_verified']


def test_status_does_not_load_even_broken_configuration(tmp_path):
    m, p, c, j = pending(tmp_path)
    (tmp_path / 'specroad.json').write_bytes(b'not JSON')
    before = tree(tmp_path)
    with patch('specroad.storage.project.ProjectSource.__init__', side_effect=AssertionError('model load')):
        value = inspect_recovery(tmp_path, expected_project_id='sample').data
    assert value['transactions'][0]['state'] == 'building'
    assert value['model_loaded'] is False and tree(tmp_path) == before


def test_empty_status_creates_no_operational_files(tmp_path):
    before = tree(tmp_path)
    assert inspect_recovery(tmp_path).data['transactions'] == []
    assert tree(tmp_path) == before and list(tmp_path.iterdir()) == []


def test_corrupt_journal_is_visible_and_never_removed(tmp_path):
    m, p, c, j = pending(tmp_path)
    (tmp_path / j.path).write_bytes(b'{broken')
    before = tree(tmp_path)
    value = inspect_recovery(tmp_path).data['transactions'][0]
    assert value['journal_sha256'] == sha256(b'{broken').hexdigest()
    assert value['permitted_actions'] == [] and value['diagnostic'] is not None
    assert tree(tmp_path) == before


@pytest.mark.parametrize('state', ['committing', 'prepared'])
def test_publication_or_changed_base_never_discards(tmp_path, state):
    m, p, c, j = pending(tmp_path, 'prepared')
    if state == 'committing':
        data = j.data; data['state'] = 'committing'
        (tmp_path / j.path).write_text(json.dumps(data))
    else:
        (tmp_path / j.data['files'][0]['path']).write_bytes(c.request.documents[0].content)
    with project_lock(tmp_path, **recovery_options(c)) as held:
        before = tree(tmp_path)
        with pytest.raises(RecoveryError) as caught: discard(c, j, held)
        assert not caught.value.mutation_possible and tree(tmp_path) == before
    assert (tmp_path / j.path).exists()


@pytest.mark.parametrize('allow', [False, 1, None])
def test_denied_or_nonboolean_authority_creates_no_audit(tmp_path, allow):
    m, p, c, j = pending(tmp_path)
    with project_lock(tmp_path, **recovery_options(c)) as held:
        before = tree(tmp_path)
        with pytest.raises(RecoveryError) as error:
            discard(c, j, held, authority=RecoveryAuthority('deny', '1', lambda r: allow))
        assert error.value.exit_code == 7 and not error.value.mutation_possible
        assert tree(tmp_path) == before


def test_changed_expected_journal_hash_has_no_effect(tmp_path):
    m, p, c, j = pending(tmp_path)
    with project_lock(tmp_path, **recovery_options(c)) as held:
        before = tree(tmp_path)
        with pytest.raises(RecoveryError): discard(c, j, held, expected_journal_sha256='0' * 64)
        assert tree(tmp_path) == before


def test_wrong_recovery_lock_is_not_permission(tmp_path):
    m, p, c, j = pending(tmp_path)
    with project_lock(tmp_path, **recovery_options(c, command='recover run')) as held:
        before = tree(tmp_path)
        with pytest.raises(RecoveryError): discard(c, j, held)
        assert tree(tmp_path) == before


def test_unknown_work_files_remain_recovery_blockers(tmp_path):
    m, p, c, j = pending(tmp_path)
    (tmp_path / j.path).with_name('unknown.bin').write_bytes(b'evidence')
    with project_lock(tmp_path, **recovery_options(c)) as held:
        before = tree(tmp_path)
        with pytest.raises(RecoveryError): discard(c, j, held)
        assert tree(tmp_path) == before
    assert inspect_project_lock(tmp_path).data['journal_paths']


def test_returned_observation_is_detached_and_not_a_boolean(tmp_path):
    m, p, c, j = pending(tmp_path)
    result = inspect_recovery(tmp_path, preflight=c)
    value = result.data; value['transactions'][0]['permitted_actions'].clear()
    assert result.data['transactions'][0]['permitted_actions'] == ['discard']
    assert copy.deepcopy(result).data == result.data
    with pytest.raises(TypeError): bool(result)


def test_archival_audit_is_not_accepted_as_an_active_transaction(tmp_path):
    m, p, c, j = pending(tmp_path)
    with project_lock(tmp_path, **recovery_options(c)) as held:
        result = discard(c, j, held).data
    audit = tmp_path / result['audit_path']
    before = tree(tmp_path)
    status = inspect_recovery(tmp_path, transaction_id=TRANSACTION)
    assert status.data['transactions'][0]['permitted_actions'] == []
    assert status.data['transactions'][0]['diagnostic'] == 'recovery_journal_missing'
    assert tree(tmp_path) == before and (audit / 'completed.json').exists()


def test_arbitrary_recovery_directory_still_blocks_normal_loading(tmp_path):
    (tmp_path / '.specroad/recovery/not-an-audit').mkdir(parents=True)
    value = _operational_metadata(ProjectBoundary(tmp_path))
    assert value['recovery_required'] and value['unresolved_paths'] == ['.specroad/recovery/not-an-audit']
