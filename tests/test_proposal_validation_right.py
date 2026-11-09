"""Status observations, failure binding and adversarial read boundaries."""
from hashlib import sha256
import json

import pytest

from specroad.cli.application import dispatch_result, execute_request
from specroad.cli.result_schemas import validate_result_document
from specroad.model.canonical import canonical_json_bytes, canonical_json_sha256
from specroad.model.record_contracts import SPECIAL_STATES
from specroad.proposals.project_validation import validate_proposal_project
from support.model import put
from support.proposal_validation import validation_project, replace_proposal
from support.read_only import inventory, no_write_attempts
from support.records import ref


@pytest.mark.parametrize('status', list(SPECIAL_STATES['proposal'][1]))
@pytest.mark.parametrize('invalid', [False, True])
def test_actual_observed_status_survives_valid_and_invalid_checks_without_grants(tmp_path, status, invalid):
    _, original = validation_project(tmp_path)
    fields = dict(proposal_status=status, maturity=SPECIAL_STATES['proposal'][1][status])
    if invalid:
        fields['content_sha256'] = '0' * 64
    value = replace_proposal(tmp_path, original, **fields)
    raw = (tmp_path / original.path).read_bytes()
    before = inventory(tmp_path)
    with no_write_attempts():
        result = validate_proposal_project(tmp_path, original.data['id'])
    assert result.exit_code == (3 if invalid else 0), result.as_dict()
    payload = result.as_dict()['result']
    assert payload['observed_status'] == status and payload['passed'] is not invalid
    assert payload['eligible_transition'] == ('validated' if not invalid and status == 'draft' else None)
    assert payload['revision'] == value['revision']
    assert payload['proposal_sha256'] == sha256(raw).hexdigest()
    assert payload['write_authorized'] is payload['approval_granted'] is False
    validate_result_document('proposal-validation-v1', payload)
    digest = payload.pop('result_sha256')
    assert digest == canonical_json_sha256(payload)
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('raw', [b'{', b'[]', b'\xff', b'{"proposal_status":"draft","proposal_status":"approved"}',
    b'{"proposal_status":{"invented":true},"revision":true}'])
def test_malformed_external_input_does_not_invent_status_or_content_binding(tmp_path, raw):
    root = tmp_path / 'project'; validation_project(root)
    path = tmp_path / 'input.json'; path.write_bytes(raw)
    before = inventory(tmp_path)
    with no_write_attempts():
        result = validate_proposal_project(root, str(path))
    assert result.exit_code == 3, result.as_dict()
    payload = result.as_dict()['result']
    assert payload['observed_status'] is payload['binding'] is payload['context_sha256'] is None
    assert payload['eligible_transition'] is None and payload['passed'] is False
    assert payload['proposal_sha256'] == sha256(raw).hexdigest()
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('kind,expected', [('missing', 5), ('alias', 7), ('parent_alias', 7),
    ('managed_alias', 3), ('wrong_id', 3), ('stdin', 2), ('control_path', 7)])
def test_explicit_input_boundaries_never_fall_back_or_publish(tmp_path, kind, expected):
    root = tmp_path / 'project'; _, original = validation_project(root)
    path = root / original.path
    if kind == 'missing':
        operand = str(tmp_path / 'absent.json')
    elif kind == 'alias':
        alias = tmp_path / 'alias.json'; alias.symlink_to(path); operand = str(alias)
    elif kind == 'parent_alias':
        alias = tmp_path / 'linked'; alias.symlink_to(path.parent, target_is_directory=True)
        operand = str(alias / path.name)
    elif kind == 'managed_alias':
        alias = root / 'proposal-copy.json'; alias.write_bytes(original.source_bytes); operand = str(alias)
    elif kind == 'wrong_id':
        value = original.data; value['id'] = 'SR-PROP-' + '1' * 26
        path.write_bytes(canonical_json_bytes(value)); operand = original.data['id']
    elif kind == 'control_path':
        operand = str(tmp_path / 'invalid\x00parent' / 'input.json')
    else:
        operand = '-'
    before = inventory(tmp_path)
    with no_write_attempts():
        result = validate_proposal_project(root, operand)
    assert result.exit_code == expected, result.as_dict()
    assert result.as_dict()['result']['eligible_transition'] is None
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('structured', [False, True])
@pytest.mark.parametrize('flag,value', [('--configuration', 'selected'), ('--expected-revision', '1'),
    ('--actor-type', 'human'), ('--dry-run', True)])
def test_read_command_does_not_accept_writer_or_variant_options(tmp_path, structured, flag, value):
    _, original = validation_project(tmp_path)
    before = inventory(tmp_path)
    with no_write_attempts():
        if structured:
            result = execute_request({'command_id': 'proposal.validate',
                'arguments': {'proposal': original.data['id']}, 'options': {flag: value}}, cwd=tmp_path).result
        else:
            args = ['proposal', 'validate', original.data['id'], flag]
            if value is not True:
                args.append(value)
            result = dispatch_result(args, cwd=tmp_path)
    assert result.exit_code == 2, result.as_dict()
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('changed', ['proposal', 'basis', 'inventory'])
@pytest.mark.parametrize('invalid', [False, True])
def test_change_during_validation_is_a_conflict_even_on_invalid_candidate(tmp_path, monkeypatch, changed, invalid):
    from specroad.proposals import project_validation
    from specroad.proposals.errors import ProposalError
    _, original = validation_project(tmp_path, changed=True)
    observed = []
    native = project_validation.validate_proposal
    def change(context):
        if changed == 'proposal':
            (tmp_path / original.path).write_bytes(original.source_bytes + b'\n')
        elif changed == 'basis':
            goal = next(p for p in tmp_path.rglob('SR-GOAL-*.json'))
            goal.write_bytes(goal.read_bytes() + b'\n')
        else:
            put(tmp_path, 'spec/issues/' + ref('ISSUE') + '.json', b'{}')
        observed.append(inventory(tmp_path))
        if invalid:
            raise ProposalError('synthetic_invalid_candidate')
        return native(context)
    monkeypatch.setattr(project_validation, 'validate_proposal', change)
    result = validate_proposal_project(tmp_path, original.data['id'])
    assert result.exit_code == 6, result.as_dict()
    assert result.as_dict()['result']['passed'] is False
    assert result.as_dict()['result']['eligible_transition'] is None
    assert inventory(tmp_path) == observed[0]  # Preserve the concurrent writer's exact bytes.


def test_external_input_is_rechecked_after_native_validation(tmp_path, monkeypatch):
    from specroad.proposals import project_validation
    root = tmp_path / 'project'; _, original = validation_project(root)
    path = tmp_path / 'outside.json'; path.write_bytes(original.source_bytes)
    native = project_validation.validate_proposal
    def change(context):
        result = native(context)
        path.write_bytes(original.source_bytes + b'\n')
        return result
    monkeypatch.setattr(project_validation, 'validate_proposal', change)
    before = inventory(root)
    result = validate_proposal_project(root, str(path))
    assert result.exit_code == 6, result.as_dict()
    assert inventory(root) == before
    assert path.read_bytes() == original.source_bytes + b'\n'


@pytest.mark.parametrize('exists', [False, True])
def test_explanation_requirement_references_resolve_in_native_basis(tmp_path, exists):
    from specroad.proposals import prepare_proposal_for_model
    from support.domain import domain_value
    from support.records import record_value
    from test_proposal_basis import project, planned_change
    requirement = domain_value('requirement')
    artifacts = [record_value('document'), domain_value('goal'), record_value('configuration')]
    if exists:
        artifacts.append(requirement)
    model = project(tmp_path, artifacts=artifacts)
    fields = planned_change(model)
    fields['changes'][0]['requirement_or_issue_ids'] = [requirement['id']]
    original = prepare_proposal_for_model(model, **fields).original
    put(tmp_path, original.path, original.source_bytes)
    before = inventory(tmp_path)
    with no_write_attempts():
        result = validate_proposal_project(tmp_path, original.data['id'])
    assert result.exit_code == (0 if exists else 3), result.as_dict()
    if not exists:
        assert result.as_dict()['result']['failure_reason'] == 'proposal_requirement_reference_missing'
    assert inventory(tmp_path) == before
