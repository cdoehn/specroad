"""Preserve actual native recovery completions without reauthorizing them."""
from pathlib import Path

import pytest

from specroad.changes import project_lock
from specroad.recovery import RestoreError, prepare_restore_plan, execute_restore
from specroad.recovery._receipt_history import receipt_history
from support.model import put
from support.read_only import no_write_attempts, inventory
from support.recovery import pending, recovery_options, discard, tree
from support.restore import restore_case
from test_restore_invocation import authority
from test_transaction_recovery_rollback import partial_commit, recover


def actual_history(root, state):
    if state == 'rollback':
        _, _, journal = partial_commit(root)
        recover(root, journal)
    else:
        _, _, check, journal = pending(root, state)
        with project_lock(root, **recovery_options(check)) as held:
            discard(check, journal, held)
    return {p: raw for p, raw in tree(root).items()
            if p.startswith(('.specroad/transactions/receipts/', '.specroad/recovery/transaction-audit/'))}


@pytest.mark.parametrize('state', ['building', 'prepared', 'rollback'])
def test_native_negative_completion_is_retained_without_becoming_a_published_effect(tmp_path, state):
    originals = actual_history(tmp_path / 'native', state)
    with no_write_attempts():
        retained, published = receipt_history(originals, 'sample')
    assert retained == originals and published == ()
    (tmp_path / 'restore').mkdir()
    options, _, _ = restore_case(tmp_path / 'restore')
    for path, raw in originals.items():
        put(options['project_root'], path, raw)
    plan = prepare_restore_plan(**options)
    result = execute_restore(plan.source_bytes, expected_target_root=plan.data['expected_target_root'],
        authority=authority(), actor={'actor_type': 'human', 'actor_id': 'synthetic-owner'})
    assert result.data['result'] == 'restored'
    assert all((options['project_root'] / p).read_bytes() == raw for p, raw in originals.items())


@pytest.mark.parametrize('state', ['prepared', 'rollback'])
@pytest.mark.parametrize('damage', ['missing', 'altered', 'project'])
def test_original_negative_recovery_proofs_are_checked_before_a_restore(tmp_path, state, damage):
    originals = actual_history(tmp_path / 'native', state)
    proof_path = next(p for p in originals if p.endswith('/intent.json') or p.endswith('/rollback.json'))
    if damage == 'missing':
        del originals[proof_path]
    elif damage == 'altered':
        originals[proof_path] = b'{}'
    with no_write_attempts(), pytest.raises(Exception) as caught:
        receipt_history(originals, 'foreign-project' if damage == 'project' else 'sample')
    from specroad.model.errors import ModelError
    assert isinstance(caught.value, ModelError)


@pytest.mark.parametrize('folder', ['lock-audit', 'init-bootstrap', 'bundle-bootstrap'])
def test_passive_operational_originals_are_preserved_not_promoted_to_authority(tmp_path, folder):
    options, _, _ = restore_case(tmp_path)
    path = '.specroad/recovery/' + folder + '/original.json'
    raw = b'Uninterpreted historical original\x00\xff'
    put(options['project_root'], path, raw)
    before = inventory(tmp_path)
    with no_write_attempts():
        plan = prepare_restore_plan(**options)
    assert inventory(tmp_path) == before
    assert path not in {r['path'] for r in plan.data['target']['entries']}
    result = execute_restore(plan.source_bytes, expected_target_root=plan.data['expected_target_root'],
        authority=authority(), actor={'actor_type': 'human', 'actor_id': 'synthetic-owner'})
    assert result.data['result'] == 'restored'
    assert (options['project_root'] / path).read_bytes() == raw
