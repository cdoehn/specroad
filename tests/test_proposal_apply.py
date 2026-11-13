"""The real atomic Proposal Apply writer and its public read/write contracts."""
import json
from base64 import b64decode
from hashlib import sha256

import pytest

from specroad.cli.application import dispatch_result, execute_request
from specroad.cli.invocation_context import InvocationContextBuilder
from specroad.cli.result_schemas import validate_result_document
from specroad.model.canonical import canonical_json_bytes as jcs, canonical_json_sha256
from specroad.model.errors import ModelError
from specroad.proposals.apply import apply_project
from specroad.proposals.history import assess_proposal
from support.proposal_apply import ApplyCase
from support.proposal_decisions import ReviewCase
from support.read_only import inventory, no_write_attempts


@pytest.mark.parametrize('changed', [True, False])
def test_real_apply_commits_exact_inner_results_and_one_control_revision(tmp_path, changed):
    case = ApplyCase(tmp_path / 'project', changed=changed)
    approved = case.original
    before = case.before.source_files
    result = case.apply()
    inputs, model = case.completion_inputs()
    applied = inputs.originals[-1]
    assert applied.binding == approved.binding
    assert applied.data['revision'] == approved.data['revision'] + 1
    assert applied.data['proposal_status'] == applied.data['maturity'] == 'applied'
    assert applied.data['change_plan'] == approved.data['change_plan']
    assert applied.data['reviews'] == approved.data['reviews']
    assert applied.data['control_history'][:-1] == approved.data['control_history']
    operation = case.requests[-1].plan.data['operations'][-1]
    raw = b64decode(operation['apply_check']['assessment_bytes_base64'], validate=True)
    proof = json.loads(raw)
    assert proof['format_version'] == 'proposal-apply-assessment-v1'
    assert proof['history']['current_approval'] and proof['history']['observed_status'] == 'approved'
    assert proof['result_sha256'] == canonical_json_sha256({k: v for k, v in proof.items() if k != 'result_sha256'})
    assert applied.data['control_history'][-1]['result_sha256'] == sha256(raw).hexdigest()
    expected = dict(before)
    for row in approved.data['change_plan']['result_artifacts']:
        artifact = row['artifact']
        path = next(d.path for d in model.documents if json.loads(d.content)['id'] == artifact['id'])
        assert json.loads(model.source_files[path]) == artifact
        # Inner author/time are preserved although the Apply actor/time differ.
        assert artifact['updated_by']['actor_id'] == 'synthetic-author'
        assert artifact['updated_at'] != applied.data['updated_at']
        expected[path] = jcs(artifact)
    expected[applied.path] = applied.source_bytes
    assert model.source_files == expected
    observed = assess_proposal(applied, inputs, model, services=case.services)
    assert observed['historical_valid'] and observed['observed_status'] == 'applied'
    assert not observed['write_authorized'] and not observed['apply_performed']
    assert result['completion']['current_target_verified'] is True
    assert result['project_writes_performed'] and not result['replayed']
    assert not result['approval_granted'] and not result['write_authorized']
    assert result['audit']['created_ids'] == result['audit']['removed_ids'] == []
    assert approved.data['id'] in result['audit']['changed_ids']
    assert result['audit']['base'] == approved.data['base']
    validate_result_document('proposal-apply-v1', result)


def test_dry_run_checks_real_approval_without_any_write_or_process(tmp_path):
    case = ApplyCase(tmp_path / 'project')
    before = inventory(case.root)
    with no_write_attempts():
        result = case.apply(dry_run=True, authority=None, request_id=None)
    assert inventory(case.root) == before
    assert result['dry_run'] and not result['replayed'] and not result['project_writes_performed']
    assert result['completion'] is None and result['proposal_status'] == 'applied'
    assert case.original.data['proposal_status'] == 'approved'
    assert not case.requests


@pytest.mark.parametrize('structured', [False, True])
def test_public_entrypoints_preserve_cwd_and_dry_run_schema(tmp_path, structured):
    case = ApplyCase(tmp_path / 'project')
    options = {'--project': str(case.root), '--expected-revision': str(case.original.data['revision']),
        '--actor-type': 'human', '--actor-id': 'synthetic-applier', '--dry-run': True}
    operand = 'project/' + case.original.path
    context = InvocationContextBuilder(restore_services=case.services)
    before = inventory(tmp_path)
    with no_write_attempts():
        if structured:
            value = execute_request({'command_id': 'proposal.apply', 'arguments': {'proposal': operand},
                'options': options}, cwd=tmp_path, context_builder=context).result
        else:
            args = ['proposal', 'apply', operand]
            for key, val in options.items():
                args.extend([key] if val is True else [key, val])
            value = dispatch_result(args, cwd=tmp_path, context_builder=context)
    assert value.exit_code == 0, value.as_dict()
    assert value.result['dry_run'] and value.result['audit']['outcome'] == 'dry_run'
    validate_result_document('proposal-apply-v1', value.as_dict()['result'])
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('actor_type', ['human', 'ai', 'ci'])
def test_public_real_apply_requires_host_authority_and_binds_request(tmp_path, actor_type):
    case = ApplyCase(tmp_path / 'project')
    context = InvocationContextBuilder(restore_services=case.services, publication_authority=case.authority)
    value = dispatch_result(['proposal', 'apply', case.original.data['id'], '--expected-revision',
        str(case.original.data['revision']), '--actor-type', actor_type, '--actor-id', 'synthetic-applier',
        '--request-id', 'public-apply'], cwd=case.root, context_builder=context)
    assert value.exit_code == 0, value.as_dict()
    assert value.result['project_writes_performed']
    assert case.requests[-1].plan.data['request_id'] == 'public-apply'
    assert case.requests[-1].plan.data['actor']['actor_type'] == actor_type
    assert json.loads((case.root / case.original.path).read_bytes())['proposal_status'] == 'applied'


@pytest.mark.parametrize('state', ['draft', 'in_review', 'rejected'])
def test_nonapproved_states_fail_without_a_normative_write(tmp_path, state):
    case = ReviewCase(tmp_path / 'project', minimum=1, start=state != 'draft')
    if state == 'rejected':
        case.decide(decision='rejected')
    before = inventory(case.root)
    with no_write_attempts(), pytest.raises(ModelError) as failed:
        apply_project(case.root, case.original.data['id'], expected_revision=case.original.data['revision'],
            actor={'actor_type': 'human', 'actor_id': 'synthetic-applier'}, planned_at='2026-11-13T00:00:00Z',
            change_plan_id='apply', transaction_id='apply', services=case.services, dry_run=True)
    assert failed.value.reason == 'proposal_apply_requires_approved'
    assert failed.value.exit_code == 3 and inventory(case.root) == before


@pytest.mark.parametrize('change', ['basis', 'revision', 'quorum', 'authority'])
def test_stale_or_unqualified_apply_never_modifies_the_approved_original(tmp_path, change):
    from specroad.changes import PublicationAuthority
    case = ApplyCase(tmp_path / 'project')
    changes = {}
    if change == 'basis':
        path = next(d.path for d in case.before.documents if json.loads(d.content)['artifact_type'] == 'goal')
        value = json.loads((case.root / path).read_bytes()); value['title'] = 'Changed current basis'
        (case.root / path).write_bytes(jcs(value))
    elif change == 'revision':
        changes['expected_revision'] = 1
    elif change == 'quorum':
        case.current_decisions = False
    else:
        changes['authority'] = PublicationAuthority('synthetic-denied-apply', '1', lambda request: False)
    before = inventory(case.root)
    with pytest.raises(ModelError) as failed:
        case.apply(**changes)
    assert failed.value.exit_code == {'basis': 6, 'revision': 6, 'quorum': 3, 'authority': 7}[change]
    assert (case.root / case.original.path).read_bytes() == case.original.source_bytes
    # Lock bookkeeping is operational; no active transaction or request success appears.
    assert not list((case.root / '.specroad/transactions').glob('*/journal.json'))
    assert all((case.root / path).read_bytes() == raw for path, raw in case.before.source_files.items()
               if change != 'basis' or path == case.original.path)
    if change == 'revision':
        assert inventory(case.root) == before


@pytest.mark.parametrize('actor_type', ['ai', 'ci'])
def test_nonhuman_real_apply_without_request_is_rejected_before_publication(tmp_path, actor_type):
    case = ApplyCase(tmp_path / 'project')
    before = inventory(case.root)
    with no_write_attempts(), pytest.raises(ModelError):
        case.apply(actor={'actor_type': actor_type, 'actor_id': 'synthetic-agent'}, request_id=None)
    assert inventory(case.root) == before and not case.requests


def test_missing_authority_and_cli_error_audit_are_explicit(tmp_path):
    case = ApplyCase(tmp_path / 'project')
    before = inventory(case.root)
    value = dispatch_result(['proposal', 'apply', case.original.data['id'], '--expected-revision',
        str(case.original.data['revision']), '--actor-type', 'human', '--actor-id', 'synthetic-applier'],
        cwd=case.root, context_builder=InvocationContextBuilder(restore_services=case.services))
    assert value.exit_code == 7, value.as_dict()
    assert inventory(case.root) == before
    assert 'proposal_host_publication_authority_required' in str(value.as_dict())
    assert 'audit' in str(value.as_dict())


def test_multi_operation_plan_preserves_chosen_ids_order_and_untouched_user_files(tmp_path):
    from support.proposal_apply import multiple_change
    case = ApplyCase(tmp_path / 'project', plan_factory=multiple_change)
    sentinel = case.root / 'user-owned.bin'
    sentinel.write_bytes(b'never part of the normative transaction\x00\xff')
    original = case.original
    result = case.apply()
    inputs, model = case.completion_inputs()
    assert case.requests[-1].plan.data['operations'][:-1] == original.data['change_plan']['operations']
    expected = {v['artifact']['id']: v['artifact'] for v in original.data['change_plan']['result_artifacts']}
    assert all(next(a for a in model.artifacts if a['id'] == key) == value for key, value in expected.items())
    created = original.data['change_plan']['operations'][0]['result_id']
    assert result['audit']['created_ids'] == [created]
    assert created not in result['audit']['changed_ids']
    assert sentinel.read_bytes() == b'never part of the normative transaction\x00\xff'
    assert not (case.root / '.git').exists()
    assert assess_proposal(inputs.originals[-1], inputs, model, services=case.services)['historical_valid']


def test_configured_two_human_quorum_is_required_before_real_apply(tmp_path):
    case = ReviewCase(tmp_path / 'project', minimum=2)
    case.decide('first-human')
    def options():
        return dict(expected_revision=case.original.data['revision'],
            actor={'actor_type': 'human', 'actor_id': 'synthetic-applier'}, planned_at='2026-11-13T00:00:00Z',
            change_plan_id='two-human-plan', transaction_id='two-human-apply', authority=case.authority,
            request_id='two-human-request', services=case.services)
    for duplicate in (False, True):
        if duplicate: case.decide('first-human')
        before = inventory(case.root)
        with no_write_attempts(), pytest.raises(ModelError):
            apply_project(case.root, case.original.data['id'], **{**options(), 'dry_run': True})
        assert inventory(case.root) == before
    case.decide('second-human')
    value = apply_project(case.root, case.original.data['id'], **options())
    assert value['proposal_status'] == 'applied' and value['completion']['current_target_verified']
    assert len(json.loads((case.root / case.original.path).read_bytes())['reviews']) == 3
