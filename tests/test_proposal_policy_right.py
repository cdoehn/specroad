"""Native Proposal operations neither borrow Git powers nor trust declared approvals."""
import json
import os
import shlex
import subprocess

import pytest

from specroad.authoring._inspection_snapshot import InspectionSnapshot
from specroad.authoring.execution import apply_authoring_plan
from specroad.changes import PublicationAuthority, prepare_authoring_request
from specroad.cli.application import dispatch_result
from specroad.model.canonical import canonical_json_bytes as jcs
from specroad.model.errors import ModelError
from specroad.model.proposal_fields import MODEL_FIELDS
from specroad.proposals._apply_control import assessment, operation
from specroad.proposals.apply import apply_project
from specroad.proposals.check import check_proposal_project
from specroad.proposals.project_validation import validate_proposal_project
from specroad.proposals.review_start import review_start_project
from support.authoring_proposals import planned, metadata
from support.proposal_apply import ApplyCase
from support.proposal_decisions import ReviewCase
from support.proposal_policy import no_foreign_execution
from support.read_only import inventory, no_write_attempts


def git_fixture(root, outside):
    """A real owned Git repository, prepared before observing product effects."""
    root.mkdir(parents=True, exist_ok=True)
    env = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}
    env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull, GIT_TERMINAL_PROMPT='0')
    prefix = ['git', '-c', 'user.name=Synthetic fixture', '-c', 'user.email=fixture@example.invalid',
        '-c', 'commit.gpgsign=false', '-c', 'core.hooksPath=' + os.devnull]
    def git(*args):
        subprocess.run([*prefix, *args], cwd=root, env=env, check=True, capture_output=True)
    git('init', '--initial-branch=fixture')
    (root / 'tracked.txt').write_bytes(b'Committed external state\n')
    git('add', 'tracked.txt')
    git('commit', '-m', 'Owned fixture')
    git('branch', 'retained-branch')
    git('tag', 'retained-tag')
    git('remote', 'add', 'origin', 'file://' + str(outside / 'never-contacted'))
    hook = root / '.git/hooks/pre-commit'
    hook.write_text('#!/bin/sh\nprintf invoked > ' + shlex.quote(str(outside / 'hook-ran')) + '\n')
    hook.chmod(0o755)
    return inventory(root / '.git')


def test_full_proposal_lifecycle_preserves_git_and_external_files(tmp_path):
    root, outside = tmp_path / 'project', tmp_path / 'outside'
    outside.mkdir()
    (outside / 'untouched').write_bytes(b'External bytes\x00\xff')
    before_git = git_fixture(root, outside)
    before_outside = inventory(outside)
    with no_foreign_execution():
        case = ReviewCase(root, minimum=1, start=False)
        before_reads = inventory(root)
        for inspect in (validate_proposal_project, check_proposal_project):
            result = inspect(root, case.original.data['id'])
            assert result.exit_code == 0, result.as_dict()
            assert inventory(root) == before_reads
        started = review_start_project(root, case.original.data['id'], expected_revision=1,
            actor={'actor_type': 'ai', 'actor_id': 'synthetic-author'},
            planned_at='2026-11-11T01:00:00Z', change_plan_id='synthetic-start-plan',
            transaction_id='synthetic-start', request_id='synthetic-start-request', authority=case.authority)
        assert started['project_writes_performed']
        case.capture(start=True)
        reviewed = case.decide()
        assert reviewed['project_writes_performed']
        approved = case.original
        applied = apply_project(root, approved.data['id'], expected_revision=approved.data['revision'],
            actor={'actor_type': 'ci', 'actor_id': 'synthetic-applier'},
            planned_at='2026-11-13T00:00:00Z', change_plan_id='synthetic-apply-plan',
            transaction_id='synthetic-apply', request_id='synthetic-apply-request',
            authority=case.authority, services=case.services)
        assert applied['completion']['current_target_verified']
        assert applied['project_writes_performed'] and not applied['approval_granted']
        actual = json.loads((root / approved.path).read_bytes())
        assert actual['proposal_status'] == 'applied' and actual['reviews'] == approved.data['reviews']
    assert inventory(root / '.git') == before_git
    assert inventory(outside) == before_outside
    assert (root / 'tracked.txt').read_bytes() == b'Committed external state\n'


def test_agent_draft_publication_leaves_git_history_and_original_targets_unchanged(tmp_path):
    root, outside = tmp_path / 'project', tmp_path / 'outside'
    outside.mkdir()
    before_git = git_fixture(root, outside)
    before_outside = inventory(outside)
    with no_foreign_execution():
        model, plan, gates = planned(root, actor='ai')
        fields = metadata(plan)
        # Explicit synthetic input, not a measured confidence or a review.
        for row in fields['changes']:
            row['confidence'] = 0.5
        fields['model_provenance'] = {**{key: 'unknown' for key in MODEL_FIELDS},
            'unknown_reasons': {key: 'Synthetic fixture does not observe a model.' for key in MODEL_FIELDS}}
        fields['title'] = 'git push; $(touch forbidden) is inert proposal prose'
        result = apply_authoring_plan(plan, model, transaction_id='synthetic-draft-write',
            command_id='artifact.update', as_proposal=True, proposal_fields=fields, gates=gates,
            authority=PublicationAuthority('synthetic-draft-host', '1', lambda request: True))
    assert result['completion']['current_target_verified'] and result['write_state'] == 'committed'
    assert not result['approval_granted']
    assert result['proposal']['title'] == fields['title']
    assert result['proposal']['changes'] == fields['changes']
    assert all(result['proposal'][key] == value for key, value in fields['model_provenance'].items())
    assert result['proposal']['reviews'] == []
    assert result['proposal']['proposal_status'] == 'draft'
    assert all((root / path).read_bytes() == raw for path, raw in model.source_files.items())
    assert inventory(root / '.git') == before_git and inventory(outside) == before_outside


@pytest.fixture(scope='module')
def approved_operations(tmp_path_factory):
    # Only immutable native input bytes are shared by the pure parser variants.
    case = ApplyCase(tmp_path_factory.mktemp('proposal-policy') / 'project')
    raw = assessment(InspectionSnapshot(case.root, None), case.original, case.services)
    return jcs([*case.original.data['change_plan']['operations'], operation(case.original, raw)])


def apply_request(operations):
    return prepare_authoring_request(command_id='proposal apply', operations=operations,
        actor={'actor_type': 'ai', 'actor_id': 'synthetic-applier'}, request_id='synthetic-apply')


def test_complete_bound_apply_request_is_owned_but_never_write_authority(approved_operations):
    operations = json.loads(approved_operations)
    with no_write_attempts():
        request = apply_request(operations)
    assert request.data['operations'] == operations
    assert request.data['route'] == 'approved_proposal_apply'
    assert request.data['specialist_required']
    assert not request.data['actor_authenticated'] and not request.data['write_authorized']
    operations[-1]['apply_check']['assessment_bytes_base64'] = 'not evidence'
    assert request.data['operations'] == json.loads(approved_operations)


@pytest.mark.parametrize('mutation', ['missing_control', 'missing_proof', 'bad_base64',
    'duplicate_control', 'nonfinal_control', 'review_payload', 'unapproved_report'])
def test_apply_route_refuses_nonempty_unproved_or_misrouted_operations(approved_operations, mutation):
    from base64 import b64decode, b64encode
    from specroad.model.canonical import canonical_json_sha256
    operations = json.loads(approved_operations)
    control = operations[-1]
    if mutation == 'missing_control':
        operations.pop()
    elif mutation == 'missing_proof':
        control.pop('apply_check')
    elif mutation == 'bad_base64':
        control['apply_check']['assessment_bytes_base64'] = '!not-base64!'
    elif mutation == 'duplicate_control':
        operations.append(control.copy())
    elif mutation == 'nonfinal_control':
        operations.reverse()
    elif mutation == 'review_payload':
        control['review_decision'] = {'decision': 'approved'}
    else:
        report = json.loads(b64decode(control['apply_check']['assessment_bytes_base64'], validate=True))
        report['history']['current_approval'] = False
        report.pop('result_sha256')
        report['result_sha256'] = canonical_json_sha256(report)
        control['apply_check']['assessment_bytes_base64'] = b64encode(jcs(report)).decode('ascii')
    assert operations
    with no_write_attempts(), pytest.raises(ModelError):
        apply_request(operations)


def test_empty_actor_precheck_does_not_claim_a_validated_apply_payload():
    with no_write_attempts():
        request = apply_request([])
    assert request.data['specialist_required'] and not request.data['write_authorized']


def test_validated_request_cannot_replace_host_authority_or_current_human_review(tmp_path):
    case = ApplyCase(tmp_path / 'project')
    raw = assessment(InspectionSnapshot(case.root, None), case.original, case.services)
    request = apply_request([*case.original.data['change_plan']['operations'], operation(case.original, raw)])
    before = inventory(case.root)
    with no_write_attempts(), pytest.raises(ModelError) as failed:
        case.apply(authority=request)
    assert failed.value.exit_code == 7 and inventory(case.root) == before
    case.current_decisions = False
    with no_write_attempts(), pytest.raises(ModelError) as failed:
        case.apply(dry_run=True)
    assert failed.value.exit_code == 3 and inventory(case.root) == before
    assert not case.requests


@pytest.mark.parametrize('field', ['plugins', 'plugin', 'execution', 'executor', 'entrypoint', 'hooks'])
def test_project_execution_declarations_fail_before_any_proposal_inspection(tmp_path, field):
    case = ReviewCase(tmp_path / 'project', start=False)
    path = case.root / 'specroad.json'
    config = json.loads(path.read_bytes())
    config[field] = {'module': 'untrusted_module', 'command': ['sh', '-c', 'touch FORBIDDEN']}
    path.write_bytes(jcs(config))
    before = inventory(case.root)
    with no_write_attempts():
        for command in ('validate', 'check'):
            result = dispatch_result(['proposal', command, case.original.data['id']], cwd=case.root)
            assert result.exit_code == 7, result.as_dict()
    assert inventory(case.root) == before
