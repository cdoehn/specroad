"""Review start through the real checks, native writer and durable receipts."""
from base64 import b64decode
from hashlib import sha256
import json

import pytest

from specroad.changes import PublicationAuthority, read_transaction_completion
from specroad.cli.application import dispatch_result, execute_request
from specroad.cli.result_schemas import validate_result_document
from specroad.model.canonical import canonical_json_bytes, canonical_json_sha256
from specroad.proposals.review_start import review_start_project
from specroad.storage.project import ProjectSource
from support.proposal_validation import validation_project
from support.read_only import inventory


def options(**changes):
    return dict(expected_revision=1, actor={'actor_type': 'human', 'actor_id': 'synthetic-author'},
        planned_at='2026-11-10T08:00:00Z', change_plan_id='synthetic-review-start-plan',
        transaction_id='synthetic-review-start', authority=PublicationAuthority(
            'synthetic-test-host', '1', lambda request: True), **changes)


@pytest.mark.parametrize('changed,bundled', [(False, False), (True, True)])
def test_native_review_start_writes_only_one_physical_revision_and_complete_evidence(tmp_path, monkeypatch, changed, bundled):
    from specroad import changes
    prepared = []
    native_stage = changes.stage_building_journal
    def observe_preflight(preflight, *args, **kwargs):
        journal = native_stage(preflight, *args, **kwargs)
        prepared.append(preflight)
        return journal
    monkeypatch.setattr(changes, 'stage_building_journal', observe_preflight)
    root = tmp_path / 'project'
    _, original = validation_project(root, changed=changed, bundled=bundled)
    before = inventory(root)
    result = review_start_project(root, original.data['id'], **options(request_id='review-start'))
    after = json.loads((root / original.path).read_bytes())
    assert (after['revision'], after['content_revision'], after['proposal_status'], after['maturity']) == (2, 1, 'in_review', 'in_review')
    assert after['content_sha256'] == original.binding.content_sha256
    assert after['change_plan'] == original.data['change_plan']
    assert after.get('reviews', []) == original.data.get('reviews', [])
    assert [(r['from'], r['to']) for r in after['control_history']] == [
        ('draft', 'validated'), ('validated', 'checked'), ('checked', 'in_review')]
    for index, row in enumerate(after['control_history']):
        assert row['binding'] == original.binding.data
        assert row['actor'] == options()['actor']
        assert row['occurred_at'] == options()['planned_at'] and row['observed_revision'] == 1
        raw = b64decode(row['result_bytes_base64'], validate=True)
        assert row['result_sha256'] == sha256(raw).hexdigest()
        report = json.loads(raw)
        assert raw == canonical_json_bytes(report)
        assert report['result_sha256'] == canonical_json_sha256({k: v for k, v in report.items() if k != 'result_sha256'})
        assert report['passed'] and report['observed_status'] == 'draft'
        assert not report['approval_granted'] and not report['write_authorized']
        assert report['binding'] == original.binding.data and report['proposal_sha256'] == original.sha256
        if index:
            assert report['full_semantic_validation'] and report['workspace']['cleanup'] == 'removed'
            assert set(report['checks']) == {'validation', 'lint', 'diff', 'impact', 'queries', 'renders'}
    assert after['control_history'][1]['result_bytes_base64'] == after['control_history'][2]['result_bytes_base64']
    now = {row[0]: row for row in inventory(root)}
    for row in before:
        if row[0] != original.path:
            assert now[row[0]] == row
    assert len(prepared) == 1
    historical = read_transaction_completion(ProjectSource(root), options()['transaction_id'])
    assert historical.data['current_target_verified'] is False
    completion = read_transaction_completion(ProjectSource(root), options()['transaction_id'],
                                           preflight=prepared[0])
    assert completion.data['current_target_verified'] is True
    assert completion.data == {**historical.data, 'current_target_verified': True}
    assert result['completion'] == completion.data
    assert result['changed_change_ids'] == [] and result['project_writes_performed']
    assert result['review_validity'] == dict(current_approval=False, human_decision_required=True)
    validate_result_document('proposal-review-start-v1', result)


def test_dry_run_qualifies_the_real_target_without_normative_or_receipt_writes(tmp_path):
    root = tmp_path / 'project'
    _, original = validation_project(root, changed=True)
    before = inventory(root)
    supplied = options(dry_run=True)
    supplied['authority'] = None
    result = review_start_project(root, original.data['id'], **supplied)
    assert inventory(root) == before
    assert result['dry_run'] and not result['project_writes_performed'] and result['completion'] is None
    assert result['revision'] == 2 and result['content_revision'] == 1


@pytest.mark.parametrize('change,reason', [
    ({'expected_revision': 2}, 'proposal_revision_conflict'),
    ({'expected_revision': True}, 'proposal_expected_revision_required'),
    ({'authority': None}, 'proposal_host_publication_authority_required'),
    ({'actor': {'actor_type': 'ai', 'actor_id': 'synthetic-ai'}}, 'normative_request_id_required')])
def test_preconditions_do_not_change_the_original(tmp_path, change, reason):
    root = tmp_path / 'project'
    _, original = validation_project(root)
    before = inventory(root)
    supplied = options(); supplied.update(change)
    with pytest.raises(Exception) as error:
        review_start_project(root, original.data['id'], **supplied)
    assert getattr(error.value, 'reason', None) == reason
    assert inventory(root) == before


def test_external_proposal_file_cannot_select_a_control_write_even_in_dry_run(tmp_path):
    root = tmp_path / 'project'
    _, original = validation_project(root)
    external = tmp_path / 'external.json'; external.write_bytes(original.source_bytes)
    before = inventory(tmp_path)
    with pytest.raises(Exception) as error:
        review_start_project(root, str(external), **options(dry_run=True))
    assert error.value.reason == 'proposal_review_start_requires_managed_original'
    assert inventory(tmp_path) == before


def test_failed_full_check_never_publishes_validated_or_checked(tmp_path, monkeypatch):
    from specroad.proposals import check
    from specroad.model.errors import ModelError
    root = tmp_path / 'project'
    _, original = validation_project(root)
    before = (root / original.path).read_bytes()
    def fail(*args, **kwargs):
        raise ModelError('synthetic_full_check_failure')
    monkeypatch.setattr(check, '_services', fail)
    with pytest.raises(ModelError, match='synthetic_full_check_failure'):
        review_start_project(root, original.data['id'], **options())
    assert (root / original.path).read_bytes() == before
    assert not list((root / '.specroad').glob('transactions/*/journal.json'))


def test_cli_and_structured_request_resolve_managed_relative_path_for_dry_run(tmp_path):
    root = tmp_path / 'project'
    _, original = validation_project(root)
    arguments = ['proposal', 'review', 'start', original.path, '--expected-revision', '1',
        '--actor-type', 'human', '--actor-id', 'synthetic-author', '--dry-run']
    result = dispatch_result(arguments, cwd=root)
    assert result.exit_code == 0, result.as_dict()
    request = execute_request({'command_id': 'proposal.review.start',
        'arguments': {'proposal': original.path}, 'options': {'--expected-revision': '1',
        '--actor-type': 'human', '--actor-id': 'synthetic-author', '--dry-run': True}}, cwd=root).result
    assert request.exit_code == 0, request.as_dict()
    assert request.result == result.result
    assert json.loads((root / original.path).read_bytes())['revision'] == 1
