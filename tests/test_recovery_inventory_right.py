"""Recovery rejects foreign inventories and preserves evidence at retry boundaries."""
from hashlib import sha256
import json
import os
from pathlib import Path

import pytest

from specroad.changes import (
    CommittedJournal, CommittingJournal, RecoveryAuthority, RecoveryError,
    RolledBackJournal, TargetModel, begin_building_journal,
    complete_published_transaction, inspect_recovery, prepare_publication_check,
    project_lock, rollback_interrupted_transaction, stage_building_journal,
)
from specroad.changes.receipt_projection import prepare_recovery_receipts
from specroad.model.canonical import canonical_json_bytes
from specroad.model.paths import artifact_path
from specroad.validation import ModelDocument
from support.committing import publish
from support.folds import edit, goal
from support.profiles import profile_data
from support.publication import ALLOW, TRANSACTION, options, prepared
from support.recovery import tree
from support.targets import POLICY, plan
from test_publication_check_right import package_model
from test_transaction_recovery_completion import crash_after_last_target, recovery_options
from test_transaction_recovery_completion_right import promoted
from test_transaction_recovery_rollback import partial_commit


RECOVER = RecoveryAuthority('inventory-test-authorizer', '1', lambda request: True)
ACTIONS = ('complete', 'rollback')
DAMAGE = ('extra_profile', 'extra_artifact', 'missing', 'changed', 'swap', 'configuration')


def _pending(root, action):
    if action == 'complete':
        model, _, _, journal, expected = crash_after_last_target(root)
    else:
        model, _, journal = partial_commit(root)
        expected = model.source_files
    return model, journal, expected


def _invoke(root, journal, action, *, authority=RECOVER):
    operation = (complete_published_transaction if action == 'complete'
                 else rollback_interrupted_transaction)
    with project_lock(root, **recovery_options(journal)) as held:
        return operation(TRANSACTION, held_lock=held, authority=authority,
                         expected_journal_sha256=journal.sha256)


def _without_lock(root):
    value = tree(root)
    value.pop('.specroad/locks/project.json', None)
    return value


def _damage(root, kind):
    """Change actual resources; return the paths that a diagnosis can identify."""
    profile = root / 'profiles/core.json'
    if kind == 'extra_profile':
        path = 'profiles/additional.json'
        raw = canonical_json_bytes(profile_data(profile_id='additional'))
    elif kind == 'extra_artifact':
        artifact = goal(99)
        path = artifact_path(artifact['artifact_type'], artifact['id'], 'SR')
        raw = canonical_json_bytes(artifact)
    elif kind == 'missing':
        profile.unlink()
        return {'profiles/core.json'}
    elif kind == 'changed':
        raw = profile.read_bytes()
        # Equal length and restored timestamps cannot conceal different bytes.
        stamp = profile.stat()
        profile.write_bytes(bytes((raw[0] ^ 1,)) + raw[1:])
        os.utime(profile, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
        return {'profiles/core.json'}
    elif kind == 'swap':
        replacement = root / 'profiles/replaced.json'
        profile.replace(replacement)
        return {'profiles/core.json', 'profiles/replaced.json'}
    elif kind == 'configuration':
        path = 'specroad.json'
        value = json.loads((root / path).read_bytes())
        value['managed_paths'].remove('profiles')
        raw = canonical_json_bytes(value)
    else:
        raise AssertionError(kind)
    destination = root / path
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(raw)
    return {path}


def _diagnosis(root):
    return inspect_recovery(root, transaction_id=TRANSACTION,
                            expected_project_id='sample').data


@pytest.mark.parametrize('action', ACTIONS)
@pytest.mark.parametrize('damage', DAMAGE)
def test_inventory_damage_blocks_before_any_recovery_write(tmp_path, action, damage):
    _, journal, _ = _pending(tmp_path, action)
    original_count = len(_without_lock(tmp_path))
    original_sizes = sorted(len(raw) for raw in _without_lock(tmp_path).values())
    affected = _damage(tmp_path, damage)
    before = _without_lock(tmp_path)
    if damage == 'swap':
        assert len(before) == original_count
        assert sorted(len(raw) for raw in before.values()) == original_sizes
    with pytest.raises(RecoveryError) as error:
        _invoke(tmp_path, journal, action)
    assert not error.value.mutation_possible
    assert _without_lock(tmp_path) == before
    status = _diagnosis(tmp_path)
    row = status['transactions'][0]
    assert status['corrupt_detected'] and row['state'] == 'corrupt'
    assert not row['critical_inputs_verified'] and not row['complete_target_verified']
    assert row['permitted_actions'] == []
    assert any(blocker.get('path') in affected for blocker in row['blockers'])
    assert _without_lock(tmp_path) == before


@pytest.mark.parametrize('action', ACTIONS)
@pytest.mark.parametrize('damage', ('extra_artifact', 'missing', 'configuration'))
def test_authority_inventory_change_is_rechecked_before_recovery_mutation(tmp_path, action, damage):
    _, journal, _ = _pending(tmp_path, action)
    after_callback = []

    def authorize(request):
        _damage(tmp_path, damage)
        after_callback.append(_without_lock(tmp_path))
        return True

    authority = RecoveryAuthority('changing-host', '1', authorize)
    with pytest.raises(RecoveryError) as error:
        _invoke(tmp_path, journal, action, authority=authority)
    assert len(after_callback) == 1
    assert not error.value.mutation_possible
    assert _without_lock(tmp_path) == after_callback[0]
    assert (tmp_path / journal.path).read_bytes() == journal.source_bytes


@pytest.mark.parametrize('action', ACTIONS)
def test_extra_member_after_enumeration_cannot_use_an_old_inventory(tmp_path, monkeypatch, action):
    from specroad.changes import _recovery_inventory as inventory

    _, journal, _ = _pending(tmp_path, action)
    original = inventory.current_json_paths
    after_change = []

    def enumerate_then_add(source):
        paths = original(source)
        if not after_change:
            _damage(tmp_path, 'extra_profile')
            after_change.append(_without_lock(tmp_path))
        return paths

    monkeypatch.setattr(inventory, 'current_json_paths', enumerate_then_add)
    with pytest.raises(RecoveryError) as error:
        _invoke(tmp_path, journal, action)
    assert after_change and not error.value.mutation_possible
    assert _without_lock(tmp_path) == after_change[0]


def test_extra_member_after_receipt_creation_preserves_receipts_and_reports_mutation(tmp_path, monkeypatch):
    from specroad.changes import recovery

    _, _, _, journal, target = crash_after_last_target(tmp_path)
    transaction, request, _ = prepare_recovery_receipts(promoted(journal))
    original = recovery._write_new
    before = _without_lock(tmp_path)
    fired = []

    def write_then_add(directory, name, raw):
        result = original(directory, name, raw)
        if raw == transaction.source_bytes:
            _damage(tmp_path, 'extra_artifact')
            fired.append(True)
        return result

    monkeypatch.setattr(recovery, '_write_new', write_then_add)
    with pytest.raises(RecoveryError) as error:
        _invoke(tmp_path, journal, 'complete')
    assert fired == [True] and error.value.mutation_possible
    assert (tmp_path / transaction.path).read_bytes() == transaction.source_bytes
    if (tmp_path / request.path).exists():
        assert (tmp_path / request.path).read_bytes() == request.source_bytes
    assert (tmp_path / journal.path).read_bytes() == journal.source_bytes
    assert all((tmp_path / path).read_bytes() == raw for path, raw in before.items())
    assert all((tmp_path / path).read_bytes() == raw for path, raw in target.items())
    assert _diagnosis(tmp_path)['transactions'][0]['state'] == 'corrupt'


@pytest.mark.parametrize('action', ACTIONS)
def test_terminal_retry_requires_current_complete_inventory(tmp_path, action):
    _, journal, _ = _pending(tmp_path, action)
    first = _invoke(tmp_path, journal, action)
    completed = 'commit_completed' if action == 'complete' else 'rollback_completed'
    assert first.data[completed]
    terminal_type = CommittedJournal if action == 'complete' else RolledBackJournal
    terminal = terminal_type((tmp_path / journal.path).read_bytes())
    _damage(tmp_path, 'extra_profile')
    before = _without_lock(tmp_path)
    with pytest.raises(RecoveryError) as error:
        _invoke(tmp_path, terminal, action)
    assert not error.value.mutation_possible
    assert _without_lock(tmp_path) == before
    assert _diagnosis(tmp_path)['transactions'][0]['state'] == 'corrupt'


@pytest.mark.parametrize('action', ACTIONS)
@pytest.mark.parametrize('damage', (None, 'extra_profile', 'missing', 'configuration'))
def test_diagnosis_never_loads_canonical_model_or_changes_evidence(tmp_path, monkeypatch, action, damage):
    from specroad.storage import inventory as model_inventory
    from specroad.storage.project import ProjectSource

    _pending(tmp_path, action)
    if damage is not None:
        _damage(tmp_path, damage)
    before = _without_lock(tmp_path)

    def model_load_forbidden(*args, **kwargs):
        raise AssertionError('Recovery attempted canonical model loading')

    monkeypatch.setattr(ProjectSource, 'load_resources', model_load_forbidden)
    monkeypatch.setattr(TargetModel, '__init__', model_load_forbidden)
    monkeypatch.setattr(model_inventory, 'inventory_project', model_load_forbidden)
    status = _diagnosis(tmp_path)
    row = status['transactions'][0]
    assert status['model_loaded'] is False and status['write_authorized'] is False
    assert row['state'] == ('committing' if damage is None else 'corrupt')
    assert row['critical_inputs_verified'] is (damage is None)
    assert _without_lock(tmp_path) == before


@pytest.mark.parametrize('action', ACTIONS)
def test_unreferenced_payloads_and_unmanaged_files_do_not_change_recovery_membership(tmp_path, action):
    _, journal, expected = _pending(tmp_path, action)
    extras = {
        'attachments/unreferenced.bin': b'unreferenced payload',
        'archive/objects/aa/' + 'a' * 64: b'unreferenced archive object',
        'outside/inventory.bin': b'unmanaged bytes',
    }
    for path, raw in extras.items():
        file = tmp_path / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes(raw)
    before = _without_lock(tmp_path)
    status = _diagnosis(tmp_path)
    assert status['transactions'][0]['critical_inputs_verified']
    assert _without_lock(tmp_path) == before
    result = _invoke(tmp_path, journal, action)
    completed = 'commit_completed' if action == 'complete' else 'rollback_completed'
    assert result.data[completed]
    assert all((tmp_path / path).read_bytes() == raw for path, raw in expected.items())
    assert all((tmp_path / path).read_bytes() == raw for path, raw in extras.items())


def _published_with_resource(root, kind):
    """Bind a real package or payload through the normal checked publication API."""
    if kind == 'package':
        model, selected, resource = package_model(root)
        package_files = [resource]
    else:
        from specroad.model.attachments import AttachmentDescriptor

        base, _, _ = prepared(root)
        raw = b'bound attachment bytes'
        descriptor = AttachmentDescriptor('attachments/bound.bin',
            'application/octet-stream', len(raw), sha256(raw).hexdigest())
        resource = ModelDocument(descriptor.path, raw)
        model = TargetModel(base.configuration_bytes, base.binding, base.documents,
            profile=base.profile, resource_files=[*base.resource_files, resource],
            attachments=[descriptor])
        destination = root / resource.path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(resource.content)
        selected = plan(model, [edit(model.artifacts[0], 'Changed')])
        package_files = []
    preflight = prepare_publication_check(selected, model, policy=POLICY,
                                         package_files=package_files)
    with project_lock(root, **options(preflight)) as held:
        building = begin_building_journal(preflight, held_lock=held,
            transaction_id=TRANSACTION, authority=ALLOW)
        ready = stage_building_journal(preflight, building, held_lock=held, authority=ALLOW)
        publish(preflight, ready, held)
    journal = CommittingJournal((root / ready.path).read_bytes())
    return journal, resource


@pytest.mark.parametrize('kind', ('package', 'attachment'))
@pytest.mark.parametrize('damage', (None, 'missing', 'changed'))
def test_explicit_package_and_payload_bytes_remain_recovery_bound(tmp_path, kind, damage):
    journal, resource = _published_with_resource(tmp_path, kind)
    path = tmp_path / resource.path
    if damage == 'missing':
        path.unlink()
    elif damage == 'changed':
        raw = path.read_bytes()
        path.write_bytes(bytes((raw[0] ^ 1,)) + raw[1:])
    before = _without_lock(tmp_path)
    row = _diagnosis(tmp_path)['transactions'][0]
    assert _without_lock(tmp_path) == before
    if damage is None:
        assert row['critical_inputs_verified'] and row['complete_target_verified']
        assert _invoke(tmp_path, journal, 'complete').data['commit_completed']
        assert path.read_bytes() == resource.content
    else:
        assert row['state'] == 'corrupt' and not row['complete_target_verified']
        assert any(item.get('path') == resource.path for item in row['blockers'])
        with pytest.raises(RecoveryError) as error:
            _invoke(tmp_path, journal, 'complete')
        assert not error.value.mutation_possible
        assert _without_lock(tmp_path) == before


def test_extra_member_after_rollback_terminal_write_cannot_be_reported_as_success(tmp_path, monkeypatch):
    from specroad.changes import _recovery_rollback as rollback

    model, _, journal = partial_commit(tmp_path)
    original = rollback.os.replace
    fired = []

    def replace_then_add(source, destination, **kwargs):
        result = original(source, destination, **kwargs)
        if destination == 'journal.json':
            state = json.loads((tmp_path / journal.path).read_bytes())['state']
            if state == 'rolled_back' and not fired:
                _damage(tmp_path, 'extra_profile')
                fired.append(True)
        return result

    monkeypatch.setattr(rollback.os, 'replace', replace_then_add)
    with pytest.raises(RecoveryError) as error:
        _invoke(tmp_path, journal, 'rollback')
    assert fired == [True] and error.value.mutation_possible
    assert all((tmp_path / path).read_bytes() == raw for path, raw in model.source_files.items())
    assert (tmp_path / 'profiles/additional.json').is_file()
    terminal = RolledBackJournal((tmp_path / journal.path).read_bytes())
    before = _without_lock(tmp_path)
    assert _diagnosis(tmp_path)['transactions'][0]['state'] == 'corrupt'
    with pytest.raises(RecoveryError) as retry_error:
        _invoke(tmp_path, terminal, 'rollback')
    assert not retry_error.value.mutation_possible
    assert _without_lock(tmp_path) == before


def test_failed_target_check_never_selects_rollback_of_proven_full_target(tmp_path, monkeypatch):
    from specroad.changes import _recovery_target as target

    _, _, _, journal, _ = crash_after_last_target(tmp_path)
    before = _without_lock(tmp_path)
    original = target._image
    calls = []

    def fail_once(*args, **kwargs):
        if not calls:
            calls.append(True)
            raise OSError(5, 'Interrupted target observation')
        return original(*args, **kwargs)

    monkeypatch.setattr(target, '_image', fail_once)
    with pytest.raises(RecoveryError) as error:
        _invoke(tmp_path, journal, 'rollback')
    assert error.value.reason == 'recovery_full_target_requires_completion'
    assert not error.value.mutation_possible
    assert _without_lock(tmp_path) == before
