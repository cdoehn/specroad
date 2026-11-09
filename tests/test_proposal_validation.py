"""Native structure/applicability, public CLI, and unchanged complete inventories."""
from dataclasses import FrozenInstanceError
from hashlib import sha256
import json

import pytest

from specroad.cli.application import dispatch_result, execute_request
from specroad.cli.commands import builtin_registry
from specroad.cli.result_schemas import validate_result_document
from specroad.cli.registry import CommandClass, EffectScope
from specroad.model.canonical import canonical_json_sha256
from specroad.proposals import ProposalContext, ProposalValidation, validate_proposal
from specroad.proposals.project_validation import validate_proposal_project
from support.proposal_validation import validation_project, replace_proposal
from support.read_only import inventory, no_write_attempts


@pytest.mark.parametrize('changed,bundled', [(False, False), (True, False), (False, True)])
def test_native_validation_binds_actual_original_and_basis_without_a_control_write(tmp_path, changed, bundled):
    model, original = validation_project(tmp_path, changed=changed, bundled=bundled)
    before = inventory(tmp_path)
    context = ProposalContext(original, model)
    with no_write_attempts():
        report = validate_proposal(context)
    value = report.data
    assert type(report) is ProposalValidation
    assert value['passed'] and value['observed_status'] == 'draft'
    assert value['eligible_transition'] == 'validated'
    assert value['proposal_sha256'] == sha256(original.source_bytes).hexdigest()
    assert value['context_sha256'] == context.sha256
    assert value['binding'] == original.binding.data
    digest = value.pop('result_sha256')
    assert digest == canonical_json_sha256(value)
    assert all(value[key] is False for key in ('write_authorized', 'approval_granted', 'full_semantic_validation'))
    validate_result_document('proposal-validation-v1', report.data)
    assert inventory(tmp_path) == before
    assert json.loads((tmp_path / original.path).read_bytes())['proposal_status'] == 'draft'


def test_validation_result_is_owned_and_not_an_operation(tmp_path):
    model, original = validation_project(tmp_path)
    report = validate_proposal(ProposalContext(original, model))
    value = report.data
    value['binding']['content_revision'] = 99
    assert report.data['binding'] == original.binding.data
    with pytest.raises(FrozenInstanceError):
        report.canonical_bytes = b'{}'


@pytest.mark.parametrize('spelling', ['id', 'relative', 'absolute', 'external'])
def test_public_argv_and_structured_requests_use_same_native_read_contract(tmp_path, spelling):
    root = tmp_path / 'project'
    _, original = validation_project(root, changed=True)
    operands = dict(id=original.data['id'], relative=original.path,
                    absolute=str(root / original.path), external=str(tmp_path / 'review.json'))
    (tmp_path / 'review.json').write_bytes(original.source_bytes)
    operand = operands[spelling]
    before = inventory(tmp_path)
    with no_write_attempts():
        argv = dispatch_result(['proposal', 'validate', operand], cwd=root)
        request = execute_request({'command_id': 'proposal.validate',
            'arguments': {'proposal': operand}}, cwd=root).result
    assert argv.exit_code == request.exit_code == 0, (argv.as_dict(), request.as_dict())
    assert argv.as_dict()['result'] == request.as_dict()['result']
    assert argv.as_dict()['result']['observed_status'] == 'draft'
    assert inventory(tmp_path) == before


def test_registry_advertises_only_implemented_read_operation():
    commands = {c.command_id: c for c in builtin_registry().commands}
    command = commands['proposal.validate']
    assert command.command_class is CommandClass.READ_ONLY
    assert command.effect_scope is EffectScope.NONE
    assert command.protocol.result_schema == 'proposal-validation-v1'
    assert command.protocol.lock_kind == 'none'
    assert 'proposal.review.start' not in commands and 'proposal.apply' not in commands


@pytest.mark.parametrize('invalid', ['json', 'content', 'basis', 'target', 'explanation'])
def test_invalid_proposal_or_plan_never_changes_project(tmp_path, invalid):
    from specroad.changes import prepare_change_plan
    from specroad.model.canonical import canonical_json_bytes
    from specroad.proposals.content import content_sha256
    root = tmp_path / 'project'
    model, original = validation_project(root, changed=True)
    value = original.data
    if invalid == 'json':
        raw = b'{'
    else:
        if invalid == 'content':
            value['content_sha256'] = '0' * 64
        elif invalid in ('basis', 'target'):
            plan = value['change_plan']; plan.pop('change_plan_sha256')
            if invalid == 'basis':
                plan['base']['model_root_sha256'] = '0' * 64
                value['base']['model_root_sha256'] = '0' * 64
            else:
                plan['expected_result']['model_root_sha256'] = '0' * 64
            value['change_plan'] = prepare_change_plan(plan).data
            value['content_sha256'] = content_sha256(value)
        else:
            value['changes'][0]['targets'] = []
            value['content_sha256'] = content_sha256(value)
        raw = canonical_json_bytes(value)
    (root / original.path).write_bytes(raw)
    before = inventory(tmp_path)
    with no_write_attempts():
        result = validate_proposal_project(root, original.data['id'])
    assert result.exit_code == (6 if invalid == 'basis' else 3), result.as_dict()
    assert inventory(tmp_path) == before


def test_structure_validation_does_not_run_full_check_or_any_project_program(tmp_path, monkeypatch):
    from specroad.proposals import history
    from specroad.recovery import _validation
    _, original = validation_project(tmp_path, changed=True)
    def forbidden(*args, **kwargs):
        raise AssertionError('Full qualification is a distinct command')
    monkeypatch.setattr(history, 'native_check', forbidden)
    monkeypatch.setattr(_validation, 'validate_project', forbidden)
    with no_write_attempts():
        result = validate_proposal_project(tmp_path, original.data['id'])
    assert result.exit_code == 0, result.as_dict()
    assert result.as_dict()['result']['full_semantic_validation'] is False
