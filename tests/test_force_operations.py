"""21.e2: real own attempts preserve original blockers and exact owner authority."""
from hashlib import sha256
import json
import os
import pytest

from specroad.changes import PublicationAuthority
from specroad.changes.force_write import apply_force_plan, bind_force_plan
from specroad.changes.force_operational_receipts import read_force_attempt
from specroad.changes.normal_access import require_normal_access
from specroad.changes.locking import project_lock
from specroad.changes._lock_files import LockFiles
from specroad.force import operations_hash
from specroad.model.canonical import canonical_json_bytes as jcs
from specroad.model.errors import ModelError
from support.force_cases import fixture, replacement, files, ACTOR, ALLOW


def operational(plan, owners=()):
    return bind_force_plan(plan, project_id=plan.data['project_id'], force=True,
        reason=plan.data['force']['reason'], operational_binding={'owners': list(owners)})


def apply(root, plan, **options):
    return apply_force_plan(root, plan, actor=ACTOR, request_id=plan.data['request_id'],
        force=True, force_reason=plan.data['force']['reason'], authority=options.pop('authority', ALLOW), **options)


def marker(root, path='.specroad/write-state/pending.json'):
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b'original interrupted attempt, no invented success')
    return path, target.read_bytes(), target.stat().st_ino


def test_old_marker_stays_blocking_after_exact_force_effect_and_replay(tmp_path):
    root, path = fixture(tmp_path / 'project')
    plan = operational(replacement(root, path, b'explicit invalid bytes'))
    old, raw, inode = marker(root)
    before = files(root)
    with pytest.raises(ModelError): require_normal_access(root)
    preview = apply(root, plan, dry_run=True)
    assert files(root) == before and preview['write_state'] == 'not_committed'
    assert preview['force']['used'] and preview['validation_status'] == 'unknown'
    done = apply(root, plan)
    assert done['status'] == 'forced' and done['complete'] and not done['approval_granted']
    assert (root / path).read_bytes() == b'explicit invalid bytes'
    assert (root / old).read_bytes() == raw and (root / old).stat().st_ino == inode
    assert all(files(root)[p] == b for p, b in before.items() if p != path)
    tx = done['completion']['transaction_id']
    own = root / '.specroad/write-state/force-attempts' / tx
    assert set(p.name for p in own.iterdir()) == {'owner.json', 'before.json', 'complete.json', 'receipts'}
    stamp = json.loads((own / 'before.json').read_bytes())
    observed = next(row for row in stamp['observation']['operational_inventory'] if row['path'] == old)
    assert observed == {'path': old, 'size': len(raw), 'sha256': sha256(raw).hexdigest()}
    assert stamp['observation']['foreign_operation_completed'] is False
    proof = read_force_attempt(root, tx, expected_project_id=plan.data['project_id']).data
    assert proof['receipt_verified'] and not proof['current_target_verified'] and not proof['approval_granted']
    retained = files(root)
    replay = apply(root, plan)
    assert replay['replayed'] and files(root) == retained
    with pytest.raises(ModelError): require_normal_access(root)
    assert files(root) == retained


@pytest.mark.parametrize('selected', ['absent', 'wrong', 'exact'])
@pytest.mark.parametrize('dry_run', [False, True])
def test_live_kernel_lock_requires_exact_selected_owner_without_unlocking(tmp_path, selected, dry_run):
    root, path = fixture(tmp_path / 'project')
    original = (root / path).read_bytes()
    base = replacement(root, path, b'own target')
    with project_lock(root, kind='writer', command='change apply', project_id=base.data['project_id'],
            request_id='other-request', transaction_id='other-transaction') as other:
        raw = (root / '.specroad/locks/project.json').read_bytes()
        owners = [] if selected == 'absent' else [{'path': '.specroad/locks/project.json',
            'sha256': sha256(raw).hexdigest() if selected == 'exact' else '0' * 64}]
        plan = operational(base, owners)
        before = files(root)
        if selected != 'exact':
            with pytest.raises(ModelError) as error: apply(root, plan, dry_run=dry_run)
            assert error.value.exit_code == 6 and files(root) == before
        else:
            result = apply(root, plan, dry_run=dry_run)
            assert result['force']['used']
            assert any(v['gate_id'] == 'lock:exclusive_access' and
                v['observed_binding']['exclusive_access_proven'] is False for v in result['force']['overrides'])
            assert (root / path).read_bytes() == (original if dry_run else b'own target')
            if dry_run: assert files(root) == before
            else:
                own = root / '.specroad/write-state/force-attempts' / result['completion']['transaction_id']
                assert json.loads((own / 'before.json').read_bytes())['observation']['exclusive_access_proven'] is False
        assert (root / '.specroad/locks/project.json').read_bytes() == raw
        other.check()
        with LockFiles(root) as probe:
            with probe.observe_mutex() as busy: assert busy


@pytest.mark.parametrize('record', ['before.json', 'owner.json', 'complete.json', 'receipts/request.json', 'receipts/transaction.json', 'receipts/committed.json'])
def test_missing_own_original_never_becomes_historical_success(tmp_path, record):
    root, path = fixture(tmp_path / 'project'); marker(root)
    plan = operational(replacement(root, path, b'new bytes'))
    done = apply(root, plan)
    own = root / '.specroad/write-state/force-attempts' / done['completion']['transaction_id']
    (own / record).unlink()
    before = files(root)
    with pytest.raises((ModelError, OSError)):
        read_force_attempt(root, done['completion']['transaction_id'], expected_project_id=plan.data['project_id'])
    assert files(root) == before


def test_changed_old_marker_does_not_inherit_previous_success(tmp_path):
    root, path = fixture(tmp_path / 'project'); old, _, _ = marker(root)
    plan = operational(replacement(root, path, b'new bytes'))
    apply(root, plan)
    (root / old).write_bytes(b'another observation')
    before = files(root)
    with pytest.raises(ModelError) as error: apply(root, plan)
    assert error.value.exit_code == 6 and files(root) == before


def test_unbound_original_change_during_host_check_cannot_finish_own_attempt(tmp_path):
    root, path = fixture(tmp_path / 'project'); old, _, _ = marker(root)
    original = (root / path).read_bytes()
    plan = operational(replacement(root, path, b'new bytes'))
    def changed(request):
        (root / old).write_bytes(b'foreign concurrent bytes')
        return True
    with pytest.raises(ModelError) as error:
        apply(root, plan, authority=PublicationAuthority('current-owner-race', '1', changed))
    assert error.value.exit_code == 6 and (root / path).read_bytes() == original
    assert not list((root / '.specroad/write-state/force-attempts').glob('*/complete.json'))
    assert any(v['gate_id'] == 'hash:operational_source' for v in error.value.authoring_attempt['force']['overrides'])


@pytest.mark.parametrize('event', ['marker_synced', 'effect_synced:0', 'before_attempt_completion'])
def test_real_io_failure_retains_original_and_own_incomplete_state(tmp_path, monkeypatch, event):
    root, path = fixture(tmp_path / 'project'); old, raw, inode = marker(root)
    plan = operational(replacement(root, path, b'own new bytes'))
    def fail(current):
        if current == event: raise OSError('injected native storage failure')
    monkeypatch.setattr('specroad.changes.guarded_write._checkpoint', fail)
    with pytest.raises(ModelError) as error: apply(root, plan)
    assert error.value.exit_code == 5
    assert error.value.authoring_attempt['write_state'] == 'unknown'
    assert (root / old).read_bytes() == raw and (root / old).stat().st_ino == inode
    own = next((root / '.specroad/write-state/force-attempts').iterdir())
    assert not (own / 'complete.json').exists()
    with pytest.raises((ModelError, OSError)):
        read_force_attempt(root, own.name, expected_project_id=plan.data['project_id'])
    with pytest.raises(ModelError): require_normal_access(root)


def test_operational_owner_is_bound_in_both_hashes_and_not_inherited(tmp_path):
    from specroad.model.schema_catalog import SchemaCatalog
    from specroad.force_operations import current, scope
    from specroad.force import ForceDecisions, ForceRequest
    root, path = fixture(tmp_path / 'project'); plain = replacement(root, path, b'changed')
    one = operational(plain)
    two = operational(plain, [{'path': '.specroad/locks/project.json', 'sha256': '1' * 64}])
    assert plain.data['format_version'] == '1.3.0' and one.data['format_version'] == '1.5.0'
    assert len({plain.sha256, one.sha256, two.sha256}) == 3
    assert len({operations_hash(p.data) for p in (plain, one, two)}) == 3
    SchemaCatalog().validate('urn:specroad:schema:1.5.0:change-plan', two.data)
    assert current() is None
    with pytest.raises(RuntimeError):
        with scope(ForceDecisions(ForceRequest(True)), two.data['operational_binding']):
            assert current() is not None
            raise RuntimeError('caller failure')
    assert current() is None


def test_operational_request_cannot_be_reused_by_normal_authoring(tmp_path):
    from specroad.authoring.native_generic import author_generic
    root, path = fixture(tmp_path / 'project')
    value = json.loads((root / path).read_bytes())
    value['title'] = 'Own operational publication'
    plan = operational(replacement(root, path, jcs(value)))
    apply(root, plan)
    before = files(root)
    intent = dict(command_id='artifact.update', target=value['id'], expected_revision=value['revision'],
        patch=[dict(op='replace', path='/title', value='Normal request')])
    with pytest.raises(ModelError):
        author_generic(root, intent, actor=ACTOR, request_id=plan.data['request_id'], authority=ALLOW)
    assert files(root) == before


def test_saved_owner_selection_cannot_silently_replace_explicit_call_selection(tmp_path):
    from specroad.force_operations import scope
    from specroad.force import ForceDecisions, ForceRequest
    root, path = fixture(tmp_path / 'project')
    plan = operational(replacement(root, path, b'unchanged by refusal'))
    before = files(root)
    with scope(ForceDecisions(ForceRequest(True)), {'owners': [
            {'path': '.specroad/locks/project.json', 'sha256': '1' * 64}]}):
        with pytest.raises(ModelError) as error: apply(root, plan)
    assert error.value.exit_code == 6 and files(root) == before


@pytest.mark.parametrize('selected', [False, True])
def test_sibling_bootstrap_marker_is_bound_and_never_cleared(tmp_path, selected):
    from specroad.authoring.bootstrap_guard import names
    root, path = fixture(tmp_path / 'project')
    pending, owner = names(root)
    raw = b'original interrupted bootstrap with unknown owner'
    original = root.parent / pending; original.write_bytes(raw)
    plan = operational(replacement(root, path, b'explicit bytes'), [] if not selected else [
        {'path': 'bootstrap-root.owner', 'sha256': sha256(raw).hexdigest()}])
    before = files(root)
    with pytest.raises(ModelError): require_normal_access(root)
    if not selected:
        with pytest.raises(ModelError) as error: apply(root, plan)
        assert error.value.exit_code == 6 and files(root) == before
    else:
        result = apply(root, plan)
        assert result['complete'] and result['force']['used'] and (root / path).read_bytes() == b'explicit bytes'
        assert any(v['gate_id'] == 'write_marker:bootstrap_retained' for v in result['force']['overrides'])
        tx = result['completion']['transaction_id']
        assert read_force_attempt(root, tx, expected_project_id=plan.data['project_id']).data['receipt_verified']
        with pytest.raises(ModelError): require_normal_access(root)
    assert original.read_bytes() == raw and not (root.parent / owner).exists()
