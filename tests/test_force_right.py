"""Source, byte-target, interruption and proof faults through the actual writer."""
import base64
import json
from hashlib import sha256
import pytest
from specroad.changes import prepare_change_plan, read_force_completion, PublicationAuthority
from specroad.changes.force_receipts import receipt_group, validate_transaction
from specroad.changes.force_write import apply_force_plan
from specroad.authoring.native_saved import apply_saved
from specroad.cli.application import execute_request
from specroad.cli.invocation_context import InvocationContextBuilder
from specroad.force import ForceRequest, ForceContractError, operations_hash
from specroad.model.canonical import canonical_json_bytes as jcs
from specroad.model.errors import ModelError
from support.force_cases import fixture, replacement, files, ACTOR, ALLOW


def apply(root, plan, authority=ALLOW):
    return apply_saved(root, {'command_id': 'change.apply', 'plan_bytes': plan.source_bytes},
        actor=ACTOR, request_id=plan.data['request_id'], force=True,
        force_reason=plan.data['force']['reason'], authority=authority)


def changed(plan, **fields):
    value = plan.data; value.pop('change_plan_sha256'); value.update(fields)
    return prepare_change_plan(value)


def test_observed_source_hash_mismatch_is_recorded_with_exact_target(tmp_path):
    root, path = fixture(tmp_path/'p'); original = (root/path).read_bytes()
    plan = replacement(root, path, b'not project json', expected='1'*64)
    result = apply(root, plan)
    override = next(v for v in result['force']['overrides'] if v['gate_id'] == 'hash:resource_precondition')
    assert override['observed_binding'] == sha256(original).hexdigest()
    assert override['requested_binding'] == '1'*64 and override['subject'] == path
    assert (root/path).read_bytes() == b'not project json'
    resources = {r['path']: r for r in result['report']['resources']}
    assert resources[path]['parse_status'] == 'unparseable'
    assert resources['specroad.json']['parse_status'] == 'parsed'
    assert result['report']['checks_complete'] is False and result['validation_status'] == 'unknown'


@pytest.mark.parametrize('raw', [b'', b'\x00\xff\r\n', None])
def test_new_replacement_and_delete_use_explicit_complete_bytes(tmp_path, raw):
    root, path = fixture(tmp_path/'p')
    path = 'owned/explicit.bin'
    if raw is None:
        (root/'owned').mkdir(); (root/path).write_bytes(b'delete exactly this')
    before = files(root); plan = replacement(root, path, raw)
    result = apply(root, plan)
    assert result['complete'] and result['completion']['commit_completed']
    assert (root/path).exists() is (raw is not None)
    if raw is not None: assert (root/path).read_bytes() == raw
    assert all(files(root)[p] == b for p, b in before.items() if p != path)


def test_broken_configuration_repair_uses_previously_explicit_identity(tmp_path):
    root, path = fixture(tmp_path/'p'); config = (root/'specroad.json').read_bytes()
    plan = replacement(root, 'specroad.json', config, expected=sha256(b'{broken').hexdigest())
    (root/'specroad.json').write_bytes(b'{broken')
    result = apply(root, plan)
    assert (root/'specroad.json').read_bytes() == config and result['complete']
    assert result['completion']['project_id'] == json.loads(config)['project_id']


def test_stale_semantic_root_is_a_bound_observation_not_a_rebased_plan(tmp_path):
    root, path = fixture(tmp_path/'p'); plan = replacement(root, path, b'{}')
    stale = changed(plan, base={**plan.data['base'], 'model_root_sha256': '0'*64})
    assert operations_hash(stale.data) != operations_hash(plan.data)
    result = apply(root, stale)
    row = next(r for r in result['force']['overrides'] if r['gate_id'] == 'hash:base_model_root')
    assert row['requested_binding'] == '0'*64 and row['observed_binding'] != '0'*64
    assert result['audit']['plan'] == stale.data


def test_source_change_during_host_check_stops_before_publication(tmp_path):
    root, path = fixture(tmp_path/'p'); plan = replacement(root, path, b'target')
    def other_writer(request):
        (root/path).write_bytes(b'external new source')
        return True
    with pytest.raises(ModelError) as error:
        apply(root, plan, PublicationAuthority('explicit-race', '1', other_writer))
    assert error.value.exit_code == 6
    assert (root/path).read_bytes() == b'external new source'
    attempt = error.value.authoring_attempt
    assert attempt['outcome'] == 'failed'
    assert any(v['gate_id'] == 'hash:live_source' for v in attempt['force']['overrides'])
    assert not list((root/'.specroad/receipts').rglob('committed.json')) if (root/'.specroad/receipts').exists() else True


def test_failed_native_io_is_not_forced_completion(tmp_path, monkeypatch):
    root, path = fixture(tmp_path/'p'); original = (root/path).read_bytes()
    plan = replacement(root, path, b'{}')
    from specroad.changes import guarded_write
    def fail(event):
        if event == 'marker_synced': raise OSError('synthetic disk failure')
    monkeypatch.setattr(guarded_write, '_checkpoint', fail)
    with pytest.raises(ModelError) as error: apply(root, plan)
    assert error.value.exit_code == 5 and (root/path).read_bytes() == original
    assert error.value.authoring_attempt['write_state'] == 'unknown'
    assert (root/'.specroad/write-state/pending.json').is_file()
    retained = files(root)
    with pytest.raises(ModelError): apply(root, plan)
    assert files(root) == retained


@pytest.mark.parametrize('tamper', ['target', 'negative', 'namespace', 'missing'])
def test_rehashed_but_inconsistent_receipt_and_missing_originals_are_rejected(tmp_path, tamper):
    root, path = fixture(tmp_path/'p'); plan = replacement(root, path, b'{}')
    result = apply(root, plan); proof = result['completion']; txpath = proof['receipts']['transaction']['path']
    if tamper in ('target', 'negative'):
        write = json.loads((root/txpath).read_bytes())['write']
        if tamper == 'target':
            write['operations'][0]['target'] = {'bytes_base64': base64.b64encode(b'different').decode()}
            value = write['plan']; value.pop('change_plan_sha256'); new = prepare_change_plan(value)
            write['plan'] = new.data; write['marker']['plan_sha256'] = new.sha256
            write['operations_sha256'] = operations_hash(new.data)
        else:
            write['force']['overrides'] = []; write['force']['used'] = False
            write['marker']['force'] = write['force']
        for p, raw in receipt_group(write).items(): (root/p).write_bytes(raw)
    elif tamper == 'namespace':
        (root/txpath).parent.joinpath('unknown.json').write_bytes(b'{}')
    else:
        (root/proof['receipts']['request']['path']).unlink()
    before = files(root)
    with pytest.raises(ModelError): read_force_completion(root, proof['transaction_id'], project_id=plan.data['project_id'])
    assert files(root) == before


def test_normal_and_forced_saved_requests_do_not_share_success(tmp_path):
    root, path = fixture(tmp_path/'p')
    from specroad.authoring.native_generic import author_generic
    goal = json.loads((root/path).read_bytes())
    preview = author_generic(root, {'command_id': 'artifact.update', 'target': goal['id'],
        'expected_revision': goal['revision'], 'patch': [{'op': 'replace', 'path': '/title', 'value': 'Normal'}]},
        actor=ACTOR, request_id='normal-id', dry_run=True)
    apply_saved(root, {'command_id': 'change.apply', 'plan_bytes': jcs(preview['plan'])},
        actor=ACTOR, request_id='normal-id', authority=ALLOW)
    plan = replacement(root, path, b'{}', request_id='normal-id'); before = files(root)
    with pytest.raises(ModelError) as error: apply(root, plan)
    assert error.value.exit_code == 6 and files(root) == before


def test_cli_real_host_failure_retains_requested_force_and_negative_findings(tmp_path):
    root, path = fixture(tmp_path/'p'); plan = replacement(root, path, b'{}')
    original = (root/path).read_bytes()
    saved = tmp_path/'plan.json'; saved.write_bytes(plan.source_bytes)
    req = {'command_id': 'change.apply', 'force': True, 'arguments': {'plan_file': str(saved)},
        'options': {'--actor-type': 'human', '--actor-id': ACTOR['actor_id'], '--request-id': plan.data['request_id']}}
    result = execute_request(req, cwd=root, context_builder=InvocationContextBuilder(
        publication_authority=PublicationAuthority('host-refusal', '1', lambda request: False))).result
    assert result.exit_code == 7 and result.as_dict()['status'] == 'failed'
    assert result.as_dict()['summary']['force']['requested'] is True
    assert result.as_dict()['summary']['force']['used'] is True
    assert result.details['authoring_attempt']['write_state'] == 'not_committed'
    assert (root/path).read_bytes() == original
    assert not (root/'.specroad/write-state/pending.json').exists()
    assert not list((root/'.specroad/receipts').rglob('*.json'))


def test_force_reason_requires_valid_unicode():
    with pytest.raises(ForceContractError): ForceRequest(True, '\ud800')


def test_blocked_dependent_stages_are_unknown_not_passing(tmp_path):
    root, path = fixture(tmp_path/'p')
    value = json.loads((root/path).read_bytes())
    from support.relations import edge, aid
    value['relations'] = [edge('references', aid('goal', 998), number=998)]
    result = apply(root, replacement(root, path, jcs(value)))
    assert result['validation_status'] in ('invalid', 'unknown') and result['force']['used']
    assert result['report']['checks_complete'] is False
    assert (root/path).read_bytes() == jcs(value)
    proof = read_force_completion(root, result['completion']['transaction_id'], project_id=json.loads((root/'specroad.json').read_bytes())['project_id'])
    assert proof.data['validation_status'] != 'valid' and proof.data['approval_granted'] is False


@pytest.mark.parametrize('record', ['transaction', 'request', 'completion'])
def test_force_completion_requires_each_original_record(tmp_path, record):
    root, path = fixture(tmp_path/'p'); plan = replacement(root, path, b'{}')
    proof = apply(root, plan)['completion']
    target = (proof['receipts']['transaction']['path'].rsplit('/', 1)[0] + '/committed.json'
        if record == 'completion' else proof['receipts'][record]['path'])
    (root/target).unlink()
    before = files(root)
    with pytest.raises(ModelError) as error:
        read_force_completion(root, proof['transaction_id'], project_id=plan.data['project_id'])
    assert error.value.exit_code == 6
    assert files(root) == before


@pytest.mark.parametrize('fault', ['disappearing', 'permission'])
def test_force_original_read_fault_is_structured_and_preserves_evidence(tmp_path, monkeypatch, fault):
    root, path = fixture(tmp_path/'p'); plan = replacement(root, path, b'{}')
    proof = apply(root, plan)['completion']
    request = root/proof['receipts']['request']['path']
    before = files(root)
    from specroad.changes import _journal_io
    original_read = _journal_io._read
    def read(fd, name, **options):
        if name == request.name:
            if fault == 'disappearing': request.unlink()
            else: raise PermissionError('synthetic unreadable original')
        return original_read(fd, name, **options)
    monkeypatch.setattr(_journal_io, '_read', read)
    with pytest.raises(ModelError) as error:
        read_force_completion(root, proof['transaction_id'], project_id=plan.data['project_id'])
    assert error.value.exit_code == (6 if fault == 'disappearing' else 5)
    if fault == 'disappearing': before.pop(proof['receipts']['request']['path'])
    assert files(root) == before


@pytest.mark.parametrize('response', ['false', 'non_boolean', 'changed_request'])
def test_force_host_refusal_before_publication_is_known_not_committed(tmp_path, response):
    root, path = fixture(tmp_path/'p'); plan = replacement(root, path, b'{}')
    original = (root/path).read_bytes()
    def refuse(request):
        if response == 'changed_request': object.__setattr__(request, 'source_bytes', b'{}')
        return False if response == 'false' else (1 if response == 'non_boolean' else True)
    with pytest.raises(ModelError) as error:
        apply(root, plan, PublicationAuthority('explicit-host-refusal', '1', refuse))
    attempt = error.value.authoring_attempt
    assert error.value.exit_code == 7 and attempt['write_state'] == 'not_committed'
    assert attempt['force']['requested'] and attempt['force']['used']
    assert attempt['outcome'] == 'failed' and attempt['approval_granted'] is False
    assert (root/path).read_bytes() == original
    assert not (root/'.specroad/write-state/pending.json').exists()
    assert not list((root/'.specroad/receipts').rglob('*.json'))


def test_force_host_refusal_after_publication_stays_unknown(tmp_path, monkeypatch):
    root, path = fixture(tmp_path/'p'); plan = replacement(root, path, b'{}')
    from specroad.changes import guarded_write
    published = []
    def observe(event):
        if event.startswith('effect_synced:'): published.append(event)
    monkeypatch.setattr(guarded_write, '_checkpoint', observe)
    with pytest.raises(ModelError) as error:
        apply(root, plan, PublicationAuthority('late-host-refusal', '1', lambda request: not published))
    assert published and (root/path).read_bytes() == b'{}'
    assert error.value.exit_code == 7
    attempt = error.value.authoring_attempt
    assert attempt['write_state'] == 'unknown' and attempt['recovery_required'] is True
    assert attempt['force']['used'] and attempt['outcome'] == 'failed'
    assert (root/'.specroad/write-state/pending.json').is_file()
    assert not list((root/'.specroad/receipts').rglob('committed.json'))
