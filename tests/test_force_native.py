"""Actual common writer, exact raw bytes, CLI/API and original completion proof."""
import json
from hashlib import sha256
import pytest
from specroad.changes import ChangePlan, PublicationAuthority, read_force_completion, read_transaction_completion
from specroad.changes.force_write import apply_force_plan, bind_force_plan
from specroad.authoring.native_saved import apply_saved
from specroad.cli.application import execute, execute_request
from specroad.cli.invocation_context import InvocationContextBuilder
from specroad.force import operations_hash
from specroad.model.canonical import canonical_json_bytes as jcs
from specroad.model.errors import ModelError
from specroad.storage.project import ProjectSource
from support.force_cases import fixture, replacement, files, ACTOR, ALLOW


def apply(root, plan, **options):
    return apply_saved(root, {'command_id': 'change.apply', 'plan_bytes': plan.source_bytes},
        actor=ACTOR, request_id=plan.data['request_id'], authority=ALLOW, **options)


def test_normal_refusal_and_explicit_forced_invalid_bytes_are_not_validation_success(tmp_path):
    root, path = fixture(tmp_path/'project'); before = files(root)
    raw = b'{"incomplete":'
    plan = replacement(root, path, raw)
    with pytest.raises(ModelError):
        apply(root, plan)
    assert files(root) == before
    result = apply(root, plan, force=True)
    assert result['status'] == 'forced' and result['exit_code'] == 0 and result['complete'] is True
    assert result['validation_status'] == 'unknown' and result['target_model_root_sha256'] is None
    assert result['report']['checks_complete'] is False and result['diagnostics']
    assert (root/path).read_bytes() == raw and (root/'foreign.txt').read_bytes() == before['foreign.txt']
    assert all(files(root)[p] == b for p, b in before.items() if p != path)
    assert result['completion']['commit_completed'] and not result['approval_granted']
    assert not (root/'.specroad/write-state/pending.json').exists()
    proof = read_force_completion(root, result['completion']['transaction_id'], project_id=plan.data['project_id']).data
    assert proof['force'] == result['force'] and proof['validation_status'] == 'unknown'
    assert proof['current_target_verified'] is False and proof['approval_granted'] is False
    after = files(root)
    replay = apply(root, plan, force=True)
    assert replay['replayed'] is True and files(root) == after
    assert replay['force'] == result['force']


def test_real_cli_dry_run_and_write_keep_all_findings(tmp_path):
    root, path = fixture(tmp_path/'project')
    plan = replacement(root, path, b'\xff\x00not-json', reason='Deliberate malformed target')
    filename = tmp_path/'intent.json'; filename.write_bytes(plan.source_bytes)
    options = {'--actor-type': ACTOR['actor_type'], '--actor-id': ACTOR['actor_id'], '--request-id': plan.data['request_id']}
    request = {'command_id': 'change.apply', 'arguments': {'plan_file': str(filename)},
        'force': True, 'force_reason': plan.data['force']['reason'], 'options': {**options, '--dry-run': True}}
    before = files(root)
    dry = execute_request(request, cwd=root).result
    assert dry.exit_code == 0 and dry.as_dict()['status'] == 'forced'
    assert files(root) == before and dry.result['outcome']['write_state'] == 'not_committed'
    args = ['change', 'apply', str(filename), '--force', '--force-reason', plan.data['force']['reason'], '--format', 'json']
    for key, value in options.items(): args.extend((key, value))
    actual = execute(args, cwd=root, context_builder=InvocationContextBuilder(publication_authority=ALLOW)).result
    assert actual.exit_code == 0, actual.as_dict()
    assert actual.as_dict()['summary']['force'] == dry.as_dict()['summary']['force']
    assert actual.as_dict()['diagnostics'] == dry.as_dict()['diagnostics']
    assert actual.result['outcome']['audit']['operations_sha256'] == operations_hash(plan.data)
    assert (root/path).read_bytes() == b'\xff\x00not-json'


def test_no_blocker_force_records_request_without_inventing_override(tmp_path):
    root, path = fixture(tmp_path/'project')
    data = json.loads((root/path).read_bytes()); data['title'] = 'Explicit new title'
    plan = replacement(root, path, jcs(data))
    result = apply(root, plan, force=True)
    assert result['force'] == {'requested': True, 'used': False, 'reason': None, 'overrides': []}
    assert result['status'] == 'success' and result['validation_status'] == 'valid'
    assert result['target_model_root_sha256'] is not None
    observed = read_transaction_completion(ProjectSource(root), result['completion']['transaction_id']).data
    assert observed['force'] == result['force'] and observed['approval_granted'] is False


def test_same_request_cannot_replay_different_force_reason_or_operation(tmp_path):
    root, path = fixture(tmp_path/'project')
    first = replacement(root, path, b'{}', reason='First request')
    apply(root, first, force=True, force_reason='First request')
    after = files(root)
    with pytest.raises(ModelError):
        apply(root, first, force=True, force_reason='Different request')
    assert files(root) == after
    # The configuration remains parseable although the selected artifact does not.
    different = replacement(root, path, b'{"another":1}', reason='First request')
    assert operations_hash(different.data) != operations_hash(first.data)
    with pytest.raises(ModelError):
        apply(root, different, force=True, force_reason='First request')
    assert files(root) == after


@pytest.mark.parametrize('authority', [None, PublicationAuthority('deny-host', '1', lambda request: False)])
def test_real_host_authority_is_not_product_force_policy(tmp_path, authority):
    root, path = fixture(tmp_path/'project'); plan = replacement(root, path, b'{}'); before = files(root)
    with pytest.raises(ModelError) as error:
        apply_force_plan(root, plan, actor=ACTOR, request_id=plan.data['request_id'], force=True, authority=authority)
    assert error.value.exit_code == 7 and files(root) == before


def test_original_completion_tampering_cannot_authorize_replay(tmp_path):
    root, path = fixture(tmp_path/'project'); plan = replacement(root, path, b'{}')
    done = apply(root, plan, force=True)
    location = root/done['completion']['receipts']['transaction']['path']
    raw = json.loads(location.read_bytes()); raw['write']['force']['overrides'] = []
    location.write_bytes(jcs(raw)); before = files(root)
    with pytest.raises(ModelError): apply(root, plan, force=True)
    assert files(root) == before


def test_configured_registry_is_validated_and_missing_bytes_remain_unknown(tmp_path):
    from specroad.changes.force_target import assess_files
    root, _ = fixture(tmp_path / 'project')
    original = files(root)
    registry_path = json.loads(original['specroad.json'])['language_registry']['path']
    assert registry_path in original
    valid = assess_files(original)
    assert valid['validation_status'] == 'valid' and valid['checks_complete']
    assert valid['model_root_sha256'] is not None
    missing = assess_files({p: raw for p, raw in original.items() if p != registry_path})
    assert missing['validation_status'] == 'unknown' and not missing['checks_complete']
    assert missing['model_root_sha256'] is None
    assert any(d['reason'] == 'bundle_language_registry_missing' for d in missing['diagnostics'])
    corrupt = assess_files({**original, registry_path: b'{}'})
    assert corrupt['validation_status'] == 'unknown' and corrupt['diagnostics']
    assert files(root) == original
