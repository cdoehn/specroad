"""21.e1.W: actual semantic commands and receipts, never fabricated approval."""
from base64 import b64decode
from copy import deepcopy
from pathlib import Path
import json
import pytest
from specroad.authoring.native_generic import author_generic
from specroad.authoring.native_plan import author_plan
from specroad.cli.results import thaw
from specroad.cli.application import execute_request
from specroad.cli.commands import builtin_registry
from specroad.cli.invocation_context import InvocationContextBuilder
from specroad.model.authoring_command_ids import COMMANDS as AUTHOR
from specroad.model.plan_command_ids import COMMANDS as PLAN
from specroad.model.errors import ModelError
from specroad.model.canonical import canonical_json_bytes as jcs
from support.force_cases import fixture, files, ACTOR, ALLOW
from support.native_plan_authoring import example, proposal_input

AI = dict(actor_type='ai', actor_id='synthetic-explicit-force')


def product(root):
    return {p: b for p, b in files(root).items() if not p.startswith('.specroad/')}


def assert_target(root, before, result):
    expected = dict(before)
    for operation in result['audit']['plan']['operations']:
        path = operation['path']; value = operation['target']
        if value.get('delete'): expected.pop(path, None)
        else: expected[path] = b64decode(value['bytes_base64'], validate=True)
    assert product(root) == expected
    assert result['write_state'] == 'committed'
    assert result['completion']['commit_completed']
    assert result['approval_granted'] is False


@pytest.mark.parametrize('name', (*AUTHOR, *PLAN))
def test_every_native_semantic_command_retains_explicit_ai_and_complete_target(tmp_path, name):
    # Existing small native examples supply complete domain inputs; no gate is
    # replaced with a passing callback. The only callback is real host authority.
    registry = builtin_registry()
    command = next(c for c in registry.commands if c.command_id == name)
    root = tmp_path/'project'
    request = example(root, command)
    root = Path(request['options']['--project'])
    request['force'] = True
    request['force_reason'] = 'Explicit synthetic semantic override'
    request['options'].update({'--actor-type': AI['actor_type'], '--actor-id': AI['actor_id']})
    before = files(root)
    dry = execute_request(request, cwd=root).result
    assert dry.exit_code == 0, dry.as_dict()
    assert files(root) == before
    outcome = dry.result['outcome']
    intent = thaw(outcome['audit']['plan']['native_intent']['intent'])
    call = author_plan if name.startswith('plan.') else author_generic
    actual = call(root, intent, actor=AI, request_id='force-domain', authority=ALLOW,
        force=True, force_reason=request['force_reason'])
    assert actual['status'] == 'forced' and actual['force']['used']
    assert actual['audit']['plan']['actor'] == AI
    assert actual['audit']['plan']['native_intent']['intent'] == intent
    assert actual['force']['overrides']
    assert_target(root, {p: b for p, b in before.items() if not p.startswith('.specroad/')}, actual)
    after = files(root)
    retry = call(root, intent, actor=AI, request_id='force-domain', authority=ALLOW,
        force=True, force_reason=request['force_reason'])
    assert retry['replayed'] and retry['completion']['current_target_verified'] is False
    assert retry['plan_sha256'] == actual['plan_sha256'] and files(root) == after


def test_stale_guards_and_requested_approval_label_keep_negative_observations(tmp_path):
    root, path = fixture(tmp_path/'project')
    old = json.loads((root/path).read_bytes())
    intent = dict(command_id='artifact.update', target=old['id'], expected_revision=999,
        patch=[dict(op='replace', path='/maturity', value='approved')])
    before = files(root)
    with pytest.raises(ModelError): author_generic(root, intent, actor=ACTOR, authority=ALLOW)
    assert files(root) == before
    result = author_generic(root, intent, actor=ACTOR, authority=ALLOW, force=True, request_id='force-stale')
    assert result['status'] == 'forced'
    assert json.loads((root/path).read_bytes())['maturity'] == 'approved'
    assert result['validation_status'] == result['report']['validation_status']
    from specroad.changes.force_target import assess_files
    current = assess_files(files(root))
    assert current['validation_status'] in ('invalid', 'unknown')
    assert any(r['gate_id'] == 'stale:expected_revision' for r in result['force']['overrides'])
    assert not result['approval_granted']


def test_force_noop_receipt_is_idempotent_and_not_a_fictional_effect(tmp_path):
    root, path = fixture(tmp_path/'project'); old = json.loads((root/path).read_bytes())
    intent = dict(command_id='artifact.update', target=old['id'], expected_revision=old['revision'],
        patch=[dict(op='test', path='/title', value=old['title'])])
    before = product(root)
    result = author_generic(root, intent, actor=ACTOR, force=True, authority=ALLOW, request_id='force-noop')
    assert result['audit']['plan']['operations'] == []
    assert product(root) == before and result['completion']['commit_completed']
    receipt = json.loads((root/result['completion']['receipts']['transaction']['path']).read_bytes())
    assert receipt['write']['files'] == []
    replay = author_generic(root, intent, actor=ACTOR, force=True, authority=ALLOW, request_id='force-noop')
    assert replay['replayed'] and replay['plan_sha256'] == result['plan_sha256']


def test_proposal_redirection_preserves_inner_intent_without_applying_it(tmp_path):
    root, path = fixture(tmp_path/'project'); old = json.loads((root/path).read_bytes())
    intent = dict(command_id='artifact.update', target=old['id'], expected_revision=999,
        patch=[dict(op='replace', path='/title', value='Requested inner title')])
    before = product(root)
    result = author_generic(root, intent, actor=AI, force=True, authority=ALLOW,
        request_id='force-proposal', as_proposal=True, proposal_fields=proposal_input())
    assert (root/path).read_bytes() == before[path]
    proposals = list(root.glob('spec/proposals/*.json')); assert len(proposals) == 1
    value = json.loads(proposals[0].read_bytes())
    assert value['reviews'] == [] and value['proposal_status'] == 'draft'
    inner = value['change_plan']
    assert inner['native_intent']['intent'] == intent
    assert any(json.loads(b64decode(op['target']['bytes_base64']))['title'] == 'Requested inner title'
        for op in inner['operations'] if op['path'] == path)
    assert result['approval_granted'] is False


def test_completed_negative_read_observation_stays_negative_under_force(tmp_path):
    from support.production_validation import inputs, write_project
    from support.domain import domain_value
    root = tmp_path/'project'
    # The real language policy rejects this otherwise structured requirement.
    # Its completed negative finding must remain observable after Force.
    write_project(root, inputs([domain_value('requirement', language='de')]))
    before = files(root)
    request = {'command_id': 'validate', 'options': {'--project': str(root), '--format': 'json'}}
    normal = execute_request(request, cwd=root).result
    forced = execute_request({**request, 'force': True}, cwd=root).result
    assert normal.complete and normal.exit_code == 1, normal.as_dict()
    assert forced.complete and forced.exit_code == 0 and forced.status.value == 'forced'
    assert forced.result == normal.result and forced.diagnostics == normal.diagnostics
    assert forced.validation_status == 'invalid' and forced.force['used']
    assert files(root) == before
