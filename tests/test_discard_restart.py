"""Prepared restart discard derives its basis from files, not retained objects."""
from hashlib import sha256
import copy
import json

import pytest

from specroad.changes import (DiscardPreflight, PreparedJournal, BuildingJournal,
    CommittingJournal, JournalError, RecoveryError, RecoveryAuthority,
    prepare_discard_recovery, project_lock, verify_building_journal,
    verify_prepared_journal, verify_committing_journal)
from specroad.model.canonical import canonical_json_bytes
from specroad.model.paths import artifact_path
from support.discard_restart import child
from support.folds import goal
from support.publication import TRANSACTION, files
from support.recovery import pending, recovery_options, discard, tree


def prepare(root, journal, **kwargs):
    return prepare_discard_recovery(root, TRANSACTION,
        expected_project_id=kwargs.pop('expected_project_id', 'sample'),
        expected_journal_sha256=kwargs.pop('expected_journal_sha256', journal.sha256), **kwargs)


@pytest.mark.parametrize('ending', ['released', 'abrupt'])
@pytest.mark.parametrize('variant', ['update', 'create', 'noop', 'resources', 'package'])
def test_prepared_discard_after_fresh_process_restart(tmp_path, ending, variant):
    original = child(tmp_path, 'writer', ending, variant, exit_code=23 if ending == 'abrupt' else 0)
    work = tmp_path / '.specroad/transactions' / TRANSACTION
    before = {p.relative_to(work).as_posix(): p.read_bytes() for p in work.rglob('*') if p.is_file()}
    recovered = child(tmp_path, 'recover')
    assert original['pid'] != recovered['pid']
    assert {p: sha256(b).hexdigest() for p, b in files(tmp_path).items()} == original['files']
    assert recovered['preflight']['base_model_root_sha256'] == original['base_model_root_sha256']
    assert recovered['status']['base_verified'] and recovered['status']['permitted_actions'] == ['discard']
    result = recovered['result']
    assert result['discard_completed'] and result['normative_writes'] == 0
    assert result['base_model_root_sha256'] == original['base_model_root_sha256']
    assert recovered['native_normative_writes'] == [] and recovered['next_writer_allowed']
    assert not work.exists()
    audit = tmp_path / result['audit_path']
    assert (audit / 'journal.before.json').read_bytes() == before.pop('journal.json')
    assert all((audit / 'work' / name).read_bytes() == raw for name, raw in before.items())
    receipt = tmp_path / result['receipt']['path']
    assert sha256(receipt.read_bytes()).hexdigest() == result['receipt']['sha256']


def test_preparation_is_read_only_detached_and_not_authority(tmp_path):
    m, p, check, journal = pending(tmp_path, 'prepared')
    before = tree(tmp_path)
    proof = prepare(tmp_path, journal)
    value = proof.data
    assert value['base_model_root_sha256'] == p.data['base']['model_root_sha256']
    assert value['observed_paths'] == sorted(m.source_files)
    assert not value['write_authorized'] and not value['project_lock_acquired']
    value['observed_paths'].clear()
    assert proof.data['observed_paths'] == sorted(m.source_files)
    assert copy.deepcopy(proof).data == proof.data
    with pytest.raises(TypeError):
        bool(proof)
    with pytest.raises(TypeError):
        DiscardPreflight()
    assert tree(tmp_path) == before
    for authorization in (False, 1, None):
        with project_lock(tmp_path, **recovery_options(check)) as held:
            locked = tree(tmp_path)
            with pytest.raises(RecoveryError) as error:
                discard(proof, journal, held, authority=RecoveryAuthority('deny', '1', lambda r: authorization))
            assert error.value.exit_code == 7 and not error.value.mutation_possible
            assert tree(tmp_path) == locked


@pytest.mark.parametrize('change', ['additional', 'changed', 'missing', 'staging', 'before', 'foreign_work'])
def test_changed_inputs_are_rejected_without_recovery_writes(tmp_path, change):
    m, p, check, journal = pending(tmp_path, 'prepared')
    entry = journal.data['files'][0]
    if change == 'additional':
        value = goal(2)
        (tmp_path / artifact_path('goal', value['id'], 'SR')).write_bytes(canonical_json_bytes(value))
    elif change == 'changed':
        path = tmp_path / entry['path']; path.write_bytes(path.read_bytes() + b' ')
    elif change == 'missing':
        (tmp_path / entry['path']).unlink()
    elif change in ('staging', 'before'):
        path = tmp_path / entry['staging_path' if change == 'staging' else 'before_image_path']
        path.write_bytes(path.read_bytes()[:17])
    else:
        (tmp_path / journal.path).with_name('foreign.bin').write_bytes(b'Foreign evidence')
    before = tree(tmp_path)
    with pytest.raises(RecoveryError) as error:
        prepare(tmp_path, journal)
    assert not error.value.mutation_possible and tree(tmp_path) == before


def test_self_consistent_before_hashes_do_not_replace_independent_basis_root(tmp_path):
    m, p, check, journal = pending(tmp_path, 'prepared')
    value = journal.data
    entry = value['files'][0]
    path = tmp_path / entry['path']
    artifact = json.loads(path.read_bytes()); artifact['statement'] = 'Changed independently'
    raw = canonical_json_bytes(artifact)
    path.write_bytes(raw); (tmp_path / entry['before_image_path']).write_bytes(raw)
    entry.update(before_sha256=sha256(raw).hexdigest(), before_size=len(raw))
    changed = PreparedJournal(canonical_json_bytes(value))
    (tmp_path / changed.path).write_bytes(changed.source_bytes)
    before = tree(tmp_path)
    with pytest.raises(RecoveryError) as error:
        prepare(tmp_path, changed)
    assert error.value.reason == 'discard_basis_root_mismatch'
    assert tree(tmp_path) == before


@pytest.mark.parametrize('scope', ['committing', 'legacy'])
def test_unproven_or_out_of_scope_restart_is_not_guessed(tmp_path, scope):
    m, p, check, journal = pending(tmp_path, 'building' if scope == 'building' else 'prepared')
    if scope != 'building':
        value = journal.data
        if scope == 'committing':
            value['state'] = 'committing'
            journal = CommittingJournal(canonical_json_bytes(value))
        else:
            value.pop('discard_basis')
            journal = PreparedJournal(canonical_json_bytes(value))
        (tmp_path / journal.path).write_bytes(journal.source_bytes)
    before = tree(tmp_path)
    with pytest.raises(RecoveryError) as error:
        prepare(tmp_path, journal)
    assert error.value.reason == ('discard_restart_basis_required' if scope == 'legacy' else 'discard_restart_prepared_required')
    assert tree(tmp_path) == before
    if scope == 'legacy':
        verify_prepared_journal(journal, check)
        building = journal.data; building['state'] = 'building'
        verify_building_journal(BuildingJournal(canonical_json_bytes(building)), check)
        committing = journal.data; committing['state'] = 'committing'
        verify_committing_journal(CommittingJournal(canonical_json_bytes(committing)), check)
        with project_lock(tmp_path, **recovery_options(check)) as held:
            assert discard(check, journal, held).data['discard_completed']


@pytest.mark.parametrize('change', ['basis', 'journal', 'project', 'authority'])
def test_detached_preflight_never_skips_fresh_mutation_guards(tmp_path, change):
    m, p, check, journal = pending(tmp_path, 'prepared')
    proof = prepare(tmp_path, journal)
    path = tmp_path / journal.data['files'][0]['path']
    if change == 'basis':
        path.write_bytes(path.read_bytes() + b' ')
    if change == 'journal':
        (tmp_path / journal.path).write_bytes(journal.source_bytes + b' ')
    if change == 'project':
        other = tmp_path / 'other'; other.mkdir()
        _, _, other_check, other_journal = pending(other, 'prepared')
        with project_lock(other, **recovery_options(other_check)) as held:
            before = tree(other)
            with pytest.raises(RecoveryError):
                discard(proof, other_journal, held)
            assert tree(other) == before
        return
    def allowed(request):
        if change == 'authority':
            path.write_bytes(path.read_bytes() + b' ')
        return True
    with project_lock(tmp_path, **recovery_options(check)) as held:
        work_before = tree((tmp_path / journal.path).parent)
        with pytest.raises(RecoveryError) as error:
            discard(proof, journal, held, authority=RecoveryAuthority('host', '1', allowed))
        assert not error.value.mutation_possible
        assert tree((tmp_path / journal.path).parent) == work_before
        assert not (tmp_path / '.specroad/recovery/transaction-audit').exists()


@pytest.mark.parametrize('override', [{'expected_project_id': 'other'},
    {'expected_journal_sha256': '0' * 64}, {'expected_project_id': ''},
    {'expected_journal_sha256': None}])
def test_explicit_preparation_bindings_are_required(tmp_path, override):
    m, p, check, journal = pending(tmp_path, 'prepared')
    before = tree(tmp_path)
    with pytest.raises(RecoveryError):
        prepare(tmp_path, journal, **override)
    assert tree(tmp_path) == before


@pytest.mark.parametrize('invalid', [None, {},
    {'format_version': 'discard-basis-v1', 'profile_chain': [], 'attachments': [], 'language_package_paths': []},
    {'format_version': 'discard-basis-v1', 'profile_chain': ['core@1.2.0'], 'attachments': [], 'language_package_paths': ['../escape']},
    {'format_version': 'discard-basis-v1', 'profile_chain': ['core@1.2.0'], 'attachments': [{}], 'language_package_paths': []}])
def test_invalid_persistent_basis_contract_cannot_become_a_journal(tmp_path, invalid):
    m, p, check, journal = pending(tmp_path, 'prepared')
    value = journal.data; value['discard_basis'] = invalid
    with pytest.raises(JournalError):
        PreparedJournal(canonical_json_bytes(value))
