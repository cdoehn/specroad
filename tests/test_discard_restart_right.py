"""Unpublished restart, interrupted discard, and preserved hostile evidence."""
from base64 import b64encode
from hashlib import sha256
import json
import os

import pytest

from specroad.changes import (BuildingJournal, PreparedJournal, DiscardedJournal,
    JournalError, RecoveryError, RecoveryAuthority, project_lock,
    verify_building_journal, verify_prepared_journal)
from specroad.model.canonical import canonical_json_bytes
from specroad.model.paths import artifact_path
from support.discard_restart import child, journal_at
from support.folds import goal
from support.publication import TRANSACTION, files
from support.recovery import pending, tree, discard, recovery_options
from test_discard_restart import prepare


def work_bytes(root):
    return tree(root / '.specroad/transactions' / TRANSACTION)


def assert_preserved(root, original, before, result):
    assert {p: sha256(b).hexdigest() for p, b in files(root).items()} == original['files']
    assert result['preflight']['base_model_root_sha256'] == original['base_model_root_sha256']
    assert result['result']['discard_completed'] and result['result']['normative_writes'] == 0
    assert result['native_normative_writes'] == [] and result['next_writer_allowed']
    audit = root / result['result']['audit_path']
    assert (audit / 'journal.before.json').read_bytes() == before['journal.json']
    for name, raw in before.items():
        if name != 'journal.json':
            assert (audit / 'work' / name).read_bytes() == raw


@pytest.mark.parametrize('ending', ['released', 'abrupt'])
@pytest.mark.parametrize('state', ['building', 'before_prefix', 'staging_prefix', 'prepared_prefix', 'complete_images'])
def test_building_restart_accepts_only_its_bound_preparation_bytes(tmp_path, state, ending):
    original = child(tmp_path, 'writer', ending, 'update', state, exit_code=23 if ending == 'abrupt' else 0)
    before = work_bytes(tmp_path)
    if state.endswith('_prefix'):
        assert any(len(raw) == 17 for raw in before.values())
    recovered = child(tmp_path, 'recover')
    assert original['pid'] != recovered['pid']
    assert recovered['status']['base_verified'] and recovered['status']['permitted_actions'] == ['discard']
    assert_preserved(tmp_path, original, before, recovered)


@pytest.mark.parametrize('ending', ['released', 'abrupt'])
@pytest.mark.parametrize('variant', ['create', 'noop', 'resources', 'package'])
def test_building_restart_handles_full_resource_selection(tmp_path, variant, ending):
    original = child(tmp_path, 'writer', ending, variant, 'building' if variant == 'noop' else 'staging_prefix',
                     exit_code=23 if ending == 'abrupt' else 0)
    before = work_bytes(tmp_path)
    assert_preserved(tmp_path, original, before, child(tmp_path, 'recover'))


BOUNDARIES = [('marker', 'prefix'), ('marker', 'link_after'), ('replace', 'before'), ('replace', 'after'),
    ('receipt', 'prefix'), ('receipt', 'link_after'), ('barrier', 'prefix'), ('barrier', 'link_after'),
    ('rename', 'before'), ('rename', 'after'), ('archive_sync', 'after'),
    ('completed', 'prefix'), ('completed', 'link_after'), ('unlink', 'before'), ('unlink', 'after')]


@pytest.mark.parametrize('ending', ['released', 'abrupt'])
@pytest.mark.parametrize('state', ['staging_prefix', 'prepared'])
@pytest.mark.parametrize('site,mode', BOUNDARIES)
def test_fresh_process_resumes_each_discard_completion_boundary(tmp_path, state, ending, site, mode):
    original = child(tmp_path, 'writer', 'released', 'update', state)
    before = work_bytes(tmp_path)
    failed = child(tmp_path, 'recover', site, mode, ending, exit_code=23 if ending == 'abrupt' else 0)
    if ending == 'released':
        assert failed['failure']['mutation_possible'] and not failed['failure']['discard_completed']
        assert failed['native_normative_writes'] == []
    else:
        assert failed['interrupted'] == site
    audits = tree(tmp_path / '.specroad/recovery/transaction-audit')
    journal = journal_at(tmp_path)
    event = journal.data.get('discard', {}).get('event_id')
    marker = tmp_path / '.specroad/transactions' / TRANSACTION / 'journal.discard'
    if marker.exists():
        event = json.loads(marker.read_bytes())['discard']['event_id']
    recovered = child(tmp_path, 'recover')
    assert failed['pid'] != recovered['pid']
    assert_preserved(tmp_path, original, before, recovered)
    if event is not None:
        assert recovered['result']['event_id'] == event
    after = tree(tmp_path / '.specroad/recovery/transaction-audit')
    assert all(after[name] == raw for name, raw in audits.items())
    completed = tree(tmp_path)
    repeated = child(tmp_path, 'recover')
    assert repeated['result'] == recovered['result'] and repeated['native_normative_writes'] == []
    assert tree(tmp_path) == completed


@pytest.mark.parametrize('site', ['original', 'intent'])
@pytest.mark.parametrize('mode', ['empty', 'prefix', 'link_after'])
def test_interrupted_audit_preparation_preserves_prior_evidence(tmp_path, site, mode):
    original = child(tmp_path, 'writer', 'released', 'update')
    before = work_bytes(tmp_path)
    failed = child(tmp_path, 'recover', site, mode)
    assert failed['failure']['mutation_possible']
    retained = tree(tmp_path / '.specroad/recovery/transaction-audit')
    recovered = child(tmp_path, 'recover')
    assert_preserved(tmp_path, original, before, recovered)
    after = tree(tmp_path / '.specroad/recovery/transaction-audit')
    assert all(after[name] == raw for name, raw in retained.items())


@pytest.mark.parametrize('state', ['staging_prefix', 'prepared'])
@pytest.mark.parametrize('variant', ['resources', 'package'])
@pytest.mark.parametrize('change', ['missing', 'changed', 'additional'])
def test_changed_full_resource_basis_blocks_restart_without_mutation(tmp_path, state, variant, change):
    child(tmp_path, 'writer', 'released', variant, state)
    journal = journal_at(tmp_path)
    selection = journal.data['discard_basis']
    if change == 'additional':
        item = goal(7)
        path = tmp_path / artifact_path('goal', item['id'], 'SR')
        path.write_bytes(canonical_json_bytes(item))
    else:
        path = tmp_path / (selection['attachments'][0]['path'] if variant == 'resources'
                           else selection['language_package_paths'][0])
        if change == 'missing':
            path.unlink()
        else:
            path.write_bytes(path.read_bytes() + b' ')
    before = tree(tmp_path)
    with pytest.raises(RecoveryError) as error:
        prepare(tmp_path, journal)
    assert not error.value.mutation_possible and tree(tmp_path) == before


@pytest.mark.parametrize('change', ['foreign_prefix', 'oversized', 'foreign_file', 'symlink', 'hardlink', 'missing_proof'])
def test_unproven_building_images_remain_blocked(tmp_path, change):
    child(tmp_path, 'writer', 'released', 'update', 'staging_prefix')
    journal = journal_at(tmp_path)
    path = tmp_path / journal.data['files'][0]['staging_path']
    if change == 'foreign_prefix': path.write_bytes(b'foreign evidence')
    if change == 'oversized': path.write_bytes(b'x' * (journal.data['files'][0]['after_size'] + 1))
    if change == 'foreign_file': path.with_name('foreign.bin').write_bytes(b'foreign evidence')
    if change in ('symlink', 'hardlink'):
        other = tmp_path / 'kept-original.bin'; path.rename(other)
        if change == 'symlink': path.symlink_to(other)
        else: os.link(other, path)
    if change == 'missing_proof':
        value = journal.data; value['discard_basis'].pop('staging_images')
        value['discard_basis']['format_version'] = 'discard-basis-v1'
        journal = BuildingJournal(canonical_json_bytes(value))
        (tmp_path / journal.path).write_bytes(journal.source_bytes)
    before = tree(tmp_path)
    with pytest.raises(RecoveryError): prepare(tmp_path, journal)
    assert tree(tmp_path) == before


@pytest.mark.parametrize('change', ['original', 'intent', 'receipt', 'work', 'terminal', 'short_marker'])
def test_conflicting_discard_completion_evidence_is_never_repaired(tmp_path, change):
    child(tmp_path, 'writer', 'released', 'update')
    child(tmp_path, 'recover', 'replace', 'before' if change == 'short_marker' else 'after')
    journal = journal_at(tmp_path)
    if change == 'short_marker':
        path = (tmp_path / journal.path).with_name('journal.discard')
    else:
        audit = tmp_path / journal.data['discard']['audit_path']
        if change == 'original': path = audit / 'journal.before.json'
        if change == 'intent': path = audit / 'intent.json'
        if change == 'receipt':
            from specroad.changes import transaction_receipt_path
            path = tmp_path / transaction_receipt_path(TRANSACTION)
            path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(b'foreign receipt')
        if change == 'work': path = tmp_path / journal.data['files'][0]['staging_path']
        if change == 'terminal':
            value = journal.data; value['target_model_root_sha256'] = '0' * 64
            journal = DiscardedJournal(canonical_json_bytes(value))
            path = tmp_path / journal.path; path.write_bytes(journal.source_bytes)
    if change not in ('receipt', 'terminal'):
        path.write_bytes(path.read_bytes()[:17])
    before = tree(tmp_path)
    with pytest.raises(RecoveryError): prepare(tmp_path, journal)
    assert tree(tmp_path) == before


@pytest.mark.parametrize('change', ['missing', 'duplicate', 'foreign', 'hash', 'noncanonical', 'extra'])
def test_staging_proof_has_closed_inventory_and_exact_bytes(tmp_path, change):
    _, _, _, journal = pending(tmp_path)
    value = journal.data; images = value['discard_basis']['staging_images']
    if change == 'missing': images.clear()
    if change == 'duplicate': images.append(images[0].copy())
    if change == 'foreign': images[0]['path'] = 'spec/foreign.json'
    if change == 'hash': images[0]['bytes_base64'] = b64encode(b'wrong target').decode()
    if change == 'noncanonical': images[0]['bytes_base64'] += '\n'
    if change == 'extra': images[0]['extra'] = True
    with pytest.raises(JournalError): BuildingJournal(canonical_json_bytes(value))


def test_v1_prepared_restart_and_independent_journal_verification_remain_supported(tmp_path):
    _, _, check, journal = pending(tmp_path, 'prepared')
    value = journal.data; value['discard_basis'].pop('staging_images')
    value['discard_basis']['format_version'] = 'discard-basis-v1'
    journal = PreparedJournal(canonical_json_bytes(value))
    (tmp_path / journal.path).write_bytes(journal.source_bytes)
    verify_prepared_journal(journal, check)
    building = journal.data; building['state'] = 'building'
    verify_building_journal(BuildingJournal(canonical_json_bytes(building)), check)
    proof = prepare(tmp_path, journal)
    with project_lock(tmp_path, **recovery_options(check)) as held:
        assert discard(proof, journal, held).data['discard_completed']


def test_terminal_restart_rechecks_audit_after_authorization(tmp_path):
    child(tmp_path, 'writer', 'released', 'update')
    child(tmp_path, 'recover', 'replace', 'after')
    journal = journal_at(tmp_path)
    proof = prepare(tmp_path, journal)
    intent = tmp_path / journal.data['discard']['audit_path'] / 'intent.json'
    def authorize(request):
        intent.write_bytes(intent.read_bytes() + b' ')
        return True
    with project_lock(tmp_path, kind='recovery', project_id='sample', command='recover discard',
                      transaction_id=TRANSACTION, request_id=journal.data['request_id']) as held:
        before = work_bytes(tmp_path)
        with pytest.raises(RecoveryError) as error:
            discard(proof, journal, held, authority=RecoveryAuthority('host', '1', authorize))
        assert not error.value.mutation_possible and work_bytes(tmp_path) == before


@pytest.mark.parametrize('state', ['building', 'prepared'])
@pytest.mark.parametrize('owner_state', ['alive', 'foreign', 'unverifiable', 'pid_reused'])
def test_restart_proof_does_not_authorize_an_unsafe_owner_takeover(tmp_path, state, owner_state):
    from specroad.changes import LockRecord, ProjectLockError, transaction_recovery_lock
    from support.project_locks import Probe
    from support.targets import ACTOR
    child(tmp_path, 'writer', 'abrupt', 'update', state, exit_code=23)
    journal = journal_at(tmp_path)
    proof = prepare(tmp_path, journal)
    assert not proof.data['write_authorized']
    lock = LockRecord((tmp_path / '.specroad/locks/project.json').read_bytes())
    owner = lock.owner
    probe = {'alive': Probe(owner.host_id, 'alive', owner.process_start_id),
             'foreign': Probe('another-host', 'absent'),
             'unverifiable': Probe(None, 'absent'),
             'pid_reused': Probe(owner.host_id, 'alive', 'different-start')}[owner_state]
    before = tree(tmp_path)
    with pytest.raises((RecoveryError, ProjectLockError)) as error:
        with transaction_recovery_lock(tmp_path, TRANSACTION, project_id='sample',
                request_id=journal.data['request_id'], command='recover discard',
                expected_lock_sha256=lock.sha256, expected_journal_sha256=journal.sha256,
                authority=RecoveryAuthority('host', '1', lambda r: True), actor=ACTOR,
                reason='Explicit recovery', force=True, owner_probe=probe):
            pytest.fail('Unproven owner accepted')
    assert not error.value.mutation_possible and tree(tmp_path) == before


def test_self_consistent_staging_hash_cannot_contradict_the_bound_target_root(tmp_path):
    _, _, _, journal = pending(tmp_path)
    value = journal.data
    entry = value['files'][0]
    from base64 import b64decode
    artifact = json.loads(b64decode(value['discard_basis']['staging_images'][0]['bytes_base64']))
    artifact['statement'] = 'Conflicting persisted target'
    raw = canonical_json_bytes(artifact)
    value['discard_basis']['staging_images'][0]['bytes_base64'] = b64encode(raw).decode()
    entry.update(after_sha256=sha256(raw).hexdigest(), after_size=len(raw))
    target = next(item for item in value['target_inventory'] if item['path'] == entry['path'])
    target.update(size=len(raw), sha256=sha256(raw).hexdigest())
    journal = BuildingJournal(canonical_json_bytes(value))
    (tmp_path / journal.path).write_bytes(journal.source_bytes)
    before = tree(tmp_path)
    with pytest.raises(RecoveryError) as error: prepare(tmp_path, journal)
    assert error.value.reason == 'discard_staging_root_mismatch' and tree(tmp_path) == before
