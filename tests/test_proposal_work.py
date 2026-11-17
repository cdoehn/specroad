"""18.o.W: real portable check results and independent current human Apply gates."""
import shutil

import pytest

from specroad.authoring._inspection_snapshot import InspectionSnapshot
from specroad.cli.self_description import describe_command
from specroad.cli.commands import builtin_registry
from specroad.proposals.check import check_proposal_project
from specroad.proposals.context import ProposalContext, reconstruct_proposal_target
from specroad.proposals.review_start import review_start_project
from specroad.proposals.apply import apply_project
from specroad.work.proposal import resume_proposal_work, proposal_work_result
from support.proposal_decisions import ReviewCase
from support.proposal_validation import validation_project
from support.proposal_work import recorded as recorded
from support.proposal_work import store_for, finish, invoke, work, complete_public
from support.read_only import inventory

__all__ = ['recorded']  # Explicit fixture re-export for pytest collection.


@pytest.mark.parametrize('window', [1, 3, 100000])
def test_split_native_check_has_same_complete_result_without_project_writes(recorded, tmp_path, window):
    root = tmp_path/'project'
    _, original = validation_project(root, changed=True)
    expected = check_proposal_project(root, original.data['id']).as_dict()['result']
    before = inventory(root)
    store = store_for(tmp_path/'work', root, original)
    report, code = finish(store, window=window)
    assert code == 0 and report['passed'] and report['full_semantic_validation']
    for key in ('binding', 'proposal_sha256', 'context_sha256', 'target_model_root_sha256',
                'target_sources_sha256', 'checks', 'observed_status', 'eligible_transition', 'workspace'):
        assert report[key] == expected[key], key
    assert not report['approval_granted'] and not report['write_authorized']
    assert inventory(root) == before
    saved = inventory(tmp_path/'work')
    assert proposal_work_result(store) == (report, code)
    assert resume_proposal_work(store).as_dict()['state'] == 'completed'
    assert inventory(tmp_path/'work') == saved


@pytest.mark.parametrize('form', ['argv', 'mapping'])
def test_public_check_work_portable_after_source_disappears(recorded, tmp_path, form):
    root = tmp_path/'project'
    _, original = validation_project(root, changed=True)
    expected = check_proposal_project(root, original.data['id']).as_dict()['result']
    path = tmp_path/'work'
    result = invoke('proposal.check', arguments={'proposal': original.data['id']}, form=form,
        options={'--project': str(root), '--work-dir': str(path)})
    assert result.exit_code == 8 and not result.complete, result.as_dict()
    status = work('status', path)
    assert status.exit_code == 0 and status.result['data']['progress']['completed_units'] == 1
    assert not status.result['data']['project_writes_performed']
    prompt = work('prompt', path)
    assert prompt.exit_code == 0 and not prompt.result['data']['control']['authorization_granted']
    package = tmp_path/'transport'/'work.zip'; package.parent.mkdir()
    assert work('export', path, {'--output': str(package)}).exit_code == 0
    shutil.rmtree(root); shutil.rmtree(path)
    restored = tmp_path/'restored'
    assert invoke('work.restore', arguments={'file': str(package)}, options={'--output': str(restored)}).exit_code == 0
    result = complete_public(restored, form=form)
    assert result.exit_code == 0, result.as_dict()
    report = result.as_dict()['result']['data']
    for key in ('binding', 'context_sha256', 'target_model_root_sha256', 'checks'):
        assert report[key] == expected[key]
    before = inventory(restored)
    assert work('resume', restored).as_dict()['result']['data'] == report
    assert inventory(restored) == before and not root.exists()


def test_work_completion_does_not_replace_real_reviews_before_apply(recorded, tmp_path):
    case = ReviewCase(tmp_path/'project', minimum=1, start=False)
    store = store_for(tmp_path/'work', case.root, case.original)
    report, code = finish(store)
    assert code == 0 and report['observed_status'] == 'draft'
    options = dict(actor={'actor_type': 'human', 'actor_id': 'synthetic-publisher'},
        planned_at='2026-11-17T01:00:00Z', change_plan_id='work-apply-plan',
        transaction_id='work-apply', request_id='synthetic:work-apply', authority=case.authority,
        services=case.services, checked_work=tmp_path/'work')
    before = inventory(case.root)
    with pytest.raises(Exception) as error:
        apply_project(case.root, case.original.data['id'], expected_revision=1, **options)
    assert error.value.exit_code == 3 and error.value.reason == 'proposal_apply_requires_approved'
    assert inventory(case.root) == before
    review_start_project(case.root, case.original.data['id'], expected_revision=1,
        actor={'actor_type': 'human', 'actor_id': 'synthetic-author'}, planned_at='2026-11-11T01:00:00Z',
        change_plan_id='work-start-plan', transaction_id='work-start', authority=case.authority)
    case.capture(start=True); case.decide()
    assert case.original.binding.data == report['binding']
    model = InspectionSnapshot(case.root, None).model
    target = reconstruct_proposal_target(ProposalContext(case.original, model))
    result = apply_project(case.root, case.original.data['id'],
        expected_revision=case.original.data['revision'], **options)
    assert result['proposal_status'] == 'applied' and result['completion']['current_target_verified']
    for path, raw in target.source_files.items():
        if path != case.original.path:
            assert (case.root/path).read_bytes() == raw
    assert not proposal_work_result(store)[0]['approval_granted']


def test_actual_public_contract_separates_passive_work_and_reviewed_writer():
    registry = builtin_registry()
    check = describe_command(registry, 'proposal.check')
    apply = describe_command(registry, 'proposal.apply')
    assert check['work']['continuation_supported'] and 8 in check['exit_codes']
    assert check['command_class'] == 'read_only' and check['lock_kind'] == 'none'
    assert '--work-dir' in {o['flag'] for o in check['options']}
    assert '--checked-work' in {o['flag'] for o in apply['options']}
    assert apply['authorization']['current_human_reviews_required']
    assert apply['authorization']['host_authority_required'] and not apply['work']['continuation_supported']
