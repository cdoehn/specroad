"""Resource/configuration normalization through real native durability boundaries."""
import json
from unittest.mock import patch
import pytest
from specroad.changes import (CommittingJournal, TransactionReceipt, RequestReceipt,
    publish_prepared_journal, finalize_committing_journal, cleanup_completed_transaction,
    prepare_format_target, dry_run_change, project_lock, begin_building_journal,
    PublicationCheckError, transaction_preflight, request_receipt_path)
from specroad.cli.contracts import CommandClass
from specroad.model.canonical import canonical_object_sha256
from support.normalization_scope import prepared, staged, GATES
from support.normalization import FIELDS
from support.publication import files, options, ALLOW, TRANSACTION
from support.targets import POLICY, ACTOR
from support.recovery import RECOVER
from support.automatic_recovery import fresh_process
from support.read_only import inventory


def test_full_scope_is_published_and_cleaned_without_value_or_metadata_changes(tmp_path):
    with staged(tmp_path) as (m, p, c, held, ready):
        expected = {**m.source_files, **{d.path:d.content for d in c.request.documents}}
        assert set(c.request.data['changed_paths']) == set(m.source_files)
        done = publish_prepared_journal(c, ready, held_lock=held, authority=ALLOW, gates=GATES)
        assert done.data['all_files_published'] and done.data['target_root_verified']
        journal = CommittingJournal((tmp_path / ready.path).read_bytes())
        completion = finalize_committing_journal(c, journal, held_lock=held,
                                                 authority=ALLOW, gates=GATES)
        assert completion.data['commit_completed'] and completion.data['current_target_verified']
        cleanup = cleanup_completed_transaction(c, TRANSACTION, held_lock=held, authority=ALLOW)
        assert cleanup.data['cleanup_completed'] and files(tmp_path) == expected
        for path, old in m.source_files.items():
            assert old != expected[path]
            assert json.loads(old) == json.loads(expected[path])
            assert canonical_object_sha256(old) == canonical_object_sha256(expected[path])
        receipt = TransactionReceipt((tmp_path / completion.data['receipts']['transaction']['path']).read_bytes())
        request = RequestReceipt((tmp_path / completion.data['receipts']['request']['path']).read_bytes())
        assert receipt.data['operations'] == p.data['operations']
        assert request.data['base_model_root_sha256'] == request.data['target_model_root_sha256']


@pytest.mark.parametrize('path', ['specroad.json', 'profiles/core.json', 'rules/sample.json', 'mappings/sample.json'])
def test_stale_resource_bytes_block_before_building_journal(tmp_path, path):
    m, _, c = prepared(tmp_path)
    target = tmp_path / path
    target.write_bytes(b' ' + target.read_bytes())
    before = files(tmp_path)
    with project_lock(tmp_path, **options(c)) as held:
        with pytest.raises(PublicationCheckError):
            begin_building_journal(c, held_lock=held, transaction_id=TRANSACTION,
                                  authority=ALLOW, gates=GATES)
    assert files(tmp_path) == before and not (tmp_path / '.specroad/transactions').exists()


def test_foreign_configuration_change_in_authorization_is_not_adopted(tmp_path):
    from specroad.changes import PublicationAuthority
    m, _, c = prepared(tmp_path)
    def interfere(request):
        (tmp_path / 'specroad.json').write_bytes(b' ' + m.configuration_bytes)
        return True
    with project_lock(tmp_path, **options(c)) as held:
        with pytest.raises(PublicationCheckError):
            begin_building_journal(c, held_lock=held, transaction_id=TRANSACTION,
                authority=PublicationAuthority('interfering-test-host', '1', interfere), gates=GATES)
    assert files(tmp_path) == {**m.source_files, 'specroad.json': b' ' + m.configuration_bytes}
    assert not (tmp_path / '.specroad/transactions').exists()


def test_second_format_plan_is_a_real_noop_after_native_publication(tmp_path):
    from specroad.changes._target_materialization import materialize_target
    with staged(tmp_path) as (m, _, c, held, ready):
        publish_prepared_journal(c, ready, held_lock=held, authority=ALLOW, gates=GATES)
        j = CommittingJournal((tmp_path / ready.path).read_bytes())
        finalize_committing_journal(c, j, held_lock=held, authority=ALLOW, gates=GATES)
        cleanup_completed_transaction(c, TRANSACTION, held_lock=held, authority=ALLOW)
    current = materialize_target(m, c.request.documents)
    before = inventory(tmp_path)
    assessment = prepare_format_target(current, policy=POLICY, gates=GATES,
        **{**FIELDS, 'request_id':'second-format'})
    result = dry_run_change(assessment.plan, current, policy=POLICY, gates=GATES, fail_on_change=True)
    assert result.data['would_change'] is False and result.data['exit_code'] == 0
    assert inventory(tmp_path) == before


CRASH = '''
from unittest.mock import patch
from support.normalization_scope import prepared, GATES
from support.model import configuration_value
from support.publication import options, ALLOW, TRANSACTION
from specroad.changes import (project_lock, begin_building_journal, stage_building_journal,
    publish_prepared_journal, finalize_committing_journal, CommittingJournal)
state = sys.argv[3]
m, p, c = prepared(root, config=configuration_value(transaction_policy={'auto_recover': True}))
target = {**m.source_files, **{d.path:d.content for d in c.request.documents}}
print(json.dumps({'before':{p:b.hex() for p,b in m.source_files.items()},
                  'after':{p:b.hex() for p,b in target.items()}}), flush=True)
with project_lock(root, **options(c)) as held:
    j = begin_building_journal(c, held_lock=held, transaction_id=TRANSACTION, authority=ALLOW, gates=GATES)
    if state == 'building': os._exit(0)
    j = stage_building_journal(c, j, held_lock=held, authority=ALLOW, gates=GATES)
    if state == 'prepared': os._exit(0)
    native = os.replace
    seen = []
    def replace(src, dst, **kw):
        if dst != 'journal.json' and state == 'partial' and seen: os._exit(0)
        result = native(src, dst, **kw)
        if dst != 'journal.json': seen.append(dst)
        if dst == 'specroad.json' and state == 'configuration_move': os._exit(0)
        return result
    with patch.object(os, 'replace', side_effect=replace):
        publish_prepared_journal(c, j, held_lock=held, authority=ALLOW, gates=GATES)
    if state == 'committed':
        j = CommittingJournal((root / j.path).read_bytes())
        finalize_committing_journal(c, j, held_lock=held, authority=ALLOW, gates=GATES)
    os._exit(0)
'''


def crash(root, state):
    value = fresh_process(root, CRASH, state)
    return {side:{p:bytes.fromhex(raw) for p,raw in values.items()} for side,values in value.items()}


@pytest.mark.parametrize('state', ['building', 'prepared', 'partial', 'configuration_move', 'committed'])
def test_fresh_process_recovery_reaches_exact_base_or_target_and_requires_new_request(tmp_path, state):
    expected = crash(tmp_path, state)
    result = transaction_preflight(tmp_path, command_class=CommandClass.NORMATIVE_WRITE,
        request_id='next-format', expected_project_id='sample', actor=ACTOR, authority=RECOVER).data
    assert result['exit_code'] == 5 and result['recovery_completed'] and result['requires_new_invocation']
    assert not result['request_consumed'] and not result['normal_operation_started']
    target = state in ('configuration_move', 'committed')
    assert files(tmp_path) == expected['after' if target else 'before']
    assert not (tmp_path / request_receipt_path('next-format')).exists()
    assert (tmp_path / request_receipt_path(FIELDS['request_id'])).exists() is target
    again = transaction_preflight(tmp_path, command_class=CommandClass.READ_ONLY).data
    assert again['exit_code'] == 0 and not again['recovery_required']


@pytest.mark.parametrize('change', ['third_representation', 'policy_value'])
def test_recovery_rejects_unbound_live_configuration_without_altering_evidence(tmp_path, change):
    expected = crash(tmp_path, 'partial')
    raw = expected['before']['specroad.json']
    if change == 'third_representation':
        raw = b' ' + raw
    else:
        from specroad.model.canonical import canonical_json_bytes
        value = json.loads(raw)
        value['project_name'] = 'Foreign policy context'
        raw = canonical_json_bytes(value)
    (tmp_path / 'specroad.json').write_bytes(raw)
    before = inventory(tmp_path)
    result = transaction_preflight(tmp_path, command_class=CommandClass.NORMATIVE_WRITE,
        request_id='next-format', expected_project_id='sample', actor=ACTOR, authority=RECOVER).data
    assert result['exit_code'] != 0 and not result['recovery_completed']
    assert not result['request_consumed'] and inventory(tmp_path) == before
