"""18.o.R: no stale consent, forged completion, implicit actor or source authority."""
from hashlib import sha256
import json
import shutil
import tempfile

import pytest

from specroad import _build
from specroad.cli.commands import builtin_registry
from specroad.model.audit_values import Actor, Revision, UtcTimestamp
from specroad.model.canonical import canonical_json_bytes as jcs
from specroad.proposals import ProposalRevision, prepare_proposal_for_model
from specroad.proposals.check import check_proposal_project
from specroad.qualification.services import QualificationServices
from specroad.work.manifest import partition_work_manifest
from specroad.work.proposal import prepare_proposal_work, resume_proposal_work
from support.proposal_apply import ApplyCase
from support.proposal_policy import no_foreign_execution
from support.proposal_validation import validation_project
from support.proposal_work import recorded as recorded
from support.proposal_work import store_for, finish, work, invoke, complete_public
from support.read_only import inventory, no_write_attempts
from support.domain import domain_value
from support.records import record_value
from support.model import put
from test_proposal_basis import project, fields

__all__ = ['recorded']


@pytest.mark.parametrize('fault', ['content', 'revision', 'basis', 'build', 'incomplete', 'cancelled'])
def test_live_apply_refuses_changed_or_unfinished_work_before_any_write(recorded, tmp_path, monkeypatch, fault):
    case = ApplyCase(tmp_path/'project')
    store = store_for(tmp_path/'work', case.root, case.original)
    if fault not in ('incomplete', 'cancelled'):
        finish(store, services=case.services)
    if fault == 'content':
        value = case.original.data; value['rationale'] = 'A new rationale requires a new review'
        changed = ProposalRevision(case.original, value, expected_revision=Revision(value['revision']),
            actor=Actor('human', 'synthetic-editor'), planned_at=UtcTimestamp('2026-11-17T01:00:00Z'))
        put(case.root, case.original.path, changed.after.source_bytes)
    elif fault == 'revision':
        from specroad.proposals.values import content_sha256
        value = case.original.data; value['content_revision'] += 1
        value['content_sha256'] = content_sha256(value)
        put(case.root, case.original.path, jcs(value))
    elif fault == 'basis':
        path = next(d.path for d in case.before.documents if json.loads(d.content)['artifact_type'] == 'goal')
        value = json.loads((case.root/path).read_bytes()); value['statement'] = 'Changed independent basis'
        put(case.root, path, jcs(value))
    elif fault == 'build':
        monkeypatch.setattr(_build, 'BUILD_METADATA', {'format_version': 1,
            'hash_algorithm': 'specroad-dev-payload-v1', 'build_sha256': '5'*64})
    elif fault == 'cancelled':
        result = work('cancel', tmp_path/'work', {'--reason': 'Explicitly abandon this check'})
        assert result.exit_code == 0 and result.result['data']['state'] == 'cancelled'
    before, retained = inventory(case.root), inventory(tmp_path/'work')
    if fault == 'build':
        for operation in ('status', 'resume'):
            result = work(operation, tmp_path/'work')
            assert result.exit_code == 6, result.as_dict()
            assert inventory(case.root) == before and inventory(tmp_path/'work') == retained
    with pytest.raises(Exception) as error:
        case.apply(checked_work=tmp_path/'work',
            expected_revision=json.loads((case.root/case.original.path).read_bytes())['revision'])
    assert error.value.exit_code == 6, (type(error.value), str(error.value))
    if fault in ('content', 'revision', 'basis'):
        assert error.value.reason == 'proposal_work_live_binding_changed'
    elif fault == 'build':
        assert error.value.reason == 'incompatible_runtime_build'
    assert inventory(case.root) == before and not case.requests
    assert inventory(tmp_path/'work') == retained


@pytest.mark.parametrize('fault', ['missing-host-originals', 'withdrawn-current-authority', 'no-publication-host'])
def test_completed_work_is_not_a_reviewer_or_a_publication_capability(recorded, tmp_path, fault):
    case = ApplyCase(tmp_path/'project')
    store = store_for(tmp_path/'work', case.root, case.original)
    finish(store, services=case.services)
    options = {'checked_work': tmp_path/'work'}
    if fault == 'missing-host-originals': options['services'] = QualificationServices()
    elif fault == 'withdrawn-current-authority': case.current_decisions = False
    else: options['authority'] = None
    before = inventory(case.root)
    with pytest.raises(Exception) as error:
        case.apply(**options)
    assert error.value.exit_code in (3, 6, 7), error.value
    assert inventory(case.root) == before and not case.requests


@pytest.mark.parametrize('phase', ['check', 'finalize'])
def test_rehashed_claim_cannot_replace_actual_native_check(recorded, tmp_path, phase):
    root = tmp_path/'project'; _, original = validation_project(root, changed=True)
    store = store_for(tmp_path/'work', root, original)
    tasks = store.read().entries('tasks')
    offset = next(i for i, task in enumerate(tasks) if task['phase'] == phase)
    resume_proposal_work(store, max_units=offset)
    current = store.read(); task = current.entries('remaining')[0]
    genuine = check_proposal_project(root, original.data['id']).as_dict()['result']
    genuine['target_model_root_sha256'] = '0'*64
    genuine['result_sha256'] = sha256(jcs({k: v for k, v in genuine.items() if k != 'result_sha256'})).hexdigest()
    store.publish(partition_work_manifest(current, {task['unit_id']: jcs({
        'adapter': 'proposal-check-work-v1', 'phase': phase, 'result': {'report': genuine, 'exit_code': 0}})}))
    before, retained = inventory(root), inventory(tmp_path/'work')
    result = work('resume', tmp_path/'work')
    assert result.exit_code == 6, result.as_dict()
    assert store.read().as_dict()['state'] == 'running'
    assert inventory(root) == before and inventory(tmp_path/'work') == retained


@pytest.mark.parametrize('phase', ['check', 'finalize', 'completed'])
def test_every_global_boundary_restores_from_complete_owned_bytes(recorded, tmp_path, phase):
    root = tmp_path/'project'; _, original = validation_project(root, changed=True)
    store = store_for(tmp_path/'work', root, original)
    tasks = store.read().entries('tasks')
    if phase == 'completed': finish(store)
    else:
        offset = next(i for i, task in enumerate(tasks) if task['phase'] == phase)
        resume_proposal_work(store, max_units=offset)
    package = tmp_path/'transport'/'check.zip'; package.parent.mkdir()
    result = work('export', tmp_path/'work', {'--output': str(package)})
    assert result.exit_code == 0, result.as_dict()
    shutil.rmtree(root); shutil.rmtree(tmp_path/'work')
    dest = tmp_path/'new-work'
    result = invoke('work.restore', arguments={'file': str(package)}, options={'--output': str(dest)})
    assert result.exit_code == 0, result.as_dict()
    completed = complete_public(dest)
    assert completed.exit_code == 0 and completed.result['data']['binding'] == original.binding.data
    assert not root.exists() and not (tmp_path/'work').exists()


def test_failed_full_validation_remains_a_failed_completed_result(recorded, tmp_path):
    root = tmp_path/'project'
    model = project(root, artifacts=[domain_value('goal'), record_value('configuration')])
    original = prepare_proposal_for_model(model, **fields(model)).original
    put(root, original.path, original.source_bytes)
    store = store_for(tmp_path/'work', root, original)
    before = inventory(root)
    report, code = finish(store)
    assert code == 3 and not report['passed'] and report['audit']['outcome'] == 'failed'
    assert store.read().as_dict()['state'] == 'completed' and report['audit']['diagnostics']
    result = work('resume', tmp_path/'work')
    assert result.exit_code == 3 and result.complete and result.as_dict()['result']['data'] == report
    assert inventory(root) == before


def test_new_sandbox_requires_current_native_human_provenance(recorded, tmp_path):
    from support.proposal_apply import restore_apply_host
    case = ApplyCase(tmp_path/'old-project')
    store = store_for(tmp_path/'work', case.root, case.original); finish(store, services=case.services)
    retained = [(o.path, o.source_bytes, dict(c.basis.source_files), c.sha256)
                for o, c in zip(case.originals, case.contexts)]
    fresh = tmp_path/'new-project'; shutil.copytree(case.root, fresh); shutil.rmtree(case.root)
    moved = restore_apply_host(fresh, retained)
    before = inventory(fresh)
    # An actual native Work reader reacquires identity; no vanished source path is reused.
    options = {'--project': str(fresh), '--expected-revision': str(moved.original.data['revision']),
        '--actor-type': 'human', '--actor-id': 'synthetic-new-host', '--request-id': 'new-host:apply',
        '--checked-work': str(tmp_path/'work')}
    denied = invoke('proposal.apply', arguments={'proposal': moved.original.data['id']}, options=options,
                    authority=moved.authority)
    assert denied.exit_code == 7 and inventory(fresh) == before
    allowed = invoke('proposal.apply', arguments={'proposal': moved.original.data['id']}, options=options,
                     authority=moved.authority, services=moved.services)
    assert allowed.exit_code == 0, allowed.as_dict()
    assert allowed.result['completion']['current_target_verified']
    assert not case.root.exists()


def test_project_data_is_not_executed_by_work(recorded, tmp_path):
    root = tmp_path/'project'; model = project(root)
    supplied = fields(model); supplied['rationale'] = '$(touch SHOULD_NOT_EXIST); import os; os.system("false")'
    original = prepare_proposal_for_model(model, **supplied).original
    put(root, original.path, original.source_bytes)
    with no_foreign_execution():
        store = store_for(tmp_path/'work', root, original)
        report, code = finish(store)
    assert code == 0 and report['binding'] == original.binding.data
    assert not (root/'SHOULD_NOT_EXIST').exists()


def test_temp_parent_in_a_project_is_rejected_before_writing(recorded, tmp_path, monkeypatch):
    root = tmp_path/'project'; _, original = validation_project(root, changed=True)
    store = store_for(tmp_path/'work', root, original)
    tasks = store.read().entries('tasks')
    resume_proposal_work(store, max_units=next(i for i, t in enumerate(tasks) if t['phase'] == 'check'))
    monkeypatch.setattr(tempfile, 'tempdir', str(root))
    before = inventory(tmp_path)
    result = work('resume', tmp_path/'work')
    assert result.exit_code == 7, result.as_dict()
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('kind', ['inside', 'symlink', 'debug'])
def test_invalid_work_destination_has_no_project_effects(recorded, tmp_path, kind):
    root = tmp_path/'project'; _, original = validation_project(root)
    path = root/'work' if kind == 'inside' else tmp_path/'work'
    if kind == 'symlink': path.symlink_to(root, target_is_directory=True)
    options = {'--project': str(root), '--work-dir': str(path)}
    if kind == 'debug': options['--keep-workspace'] = True
    before = inventory(tmp_path)
    result = invoke('proposal.check', arguments={'proposal': original.data['id']}, options=options)
    assert result.exit_code in (2, 7), result.as_dict()
    assert inventory(tmp_path) == before


def test_work_capture_rechecks_original_bytes_before_returning(recorded, tmp_path, monkeypatch):
    import specroad.work.proposal as adapter
    root = tmp_path/'project'; _, original = validation_project(root)
    native = adapter._create_manifest
    def change_after_capture(*args, **kwargs):
        result = native(*args, **kwargs)
        (root/original.path).write_bytes(original.source_bytes+b'\n')
        return result
    monkeypatch.setattr(adapter, '_create_manifest', change_after_capture)
    with pytest.raises(Exception) as error:
        prepare_proposal_work(builtin_registry(), root, original.data['id'])
    assert error.value.exit_code == 6
    assert not (tmp_path/'work').exists()


def test_confirmed_apply_retry_preserves_receipts_without_reopening_work(recorded, tmp_path):
    case = ApplyCase(tmp_path/'project')
    store = store_for(tmp_path/'work', case.root, case.original); finish(store, services=case.services)
    result = case.apply(checked_work=tmp_path/'work'); shutil.rmtree(tmp_path/'work')
    before = inventory(case.root)
    with no_write_attempts():
        retry = case.apply(checked_work=tmp_path/'work', transaction_id='retry-work-apply')
    assert retry['replayed'] and not retry['completion']['current_target_verified']
    assert retry['completion']['receipts'] == result['completion']['receipts']
    assert inventory(case.root) == before


@pytest.mark.parametrize('fault', ['outcome', 'time', 'identity'])
def test_rehashed_audit_cannot_disagree_with_its_check(recorded, tmp_path, fault):
    root = tmp_path/'project'; _, original = validation_project(root)
    store = store_for(tmp_path/'work', root, original)
    tasks = store.read().entries('tasks')
    offset = next(i for i, t in enumerate(tasks) if t['phase'] == 'check')
    resume_proposal_work(store, max_units=offset)
    current = store.read(); task = current.entries('remaining')[0]
    report = check_proposal_project(root, original.data['id']).as_dict()['result']
    if fault == 'outcome': report['audit']['outcome'] = 'failed'
    elif fault == 'time': report['audit']['ended_at'] = '2020-01-01T00:00:00Z'
    else: report['audit']['proposal_id'] = 'SR-PROP-'+'1'*26
    report['result_sha256'] = sha256(jcs({k: v for k, v in report.items() if k != 'result_sha256'})).hexdigest()
    store.publish(partition_work_manifest(current, {task['unit_id']: jcs({
        'adapter': 'proposal-check-work-v1', 'phase': 'check', 'result': {'report': report, 'exit_code': 0}})}))
    before = inventory(tmp_path)
    result = work('resume', tmp_path/'work')
    assert result.exit_code == 6, result.as_dict()
    assert inventory(tmp_path) == before


def test_delivery_rechecks_the_actual_checkpoint_after_fresh_check(recorded, tmp_path, monkeypatch):
    from specroad.work.proposal import proposal_work_result
    root = tmp_path/'project'; _, original = validation_project(root)
    first = store_for(tmp_path/'first', root, original); finish(first)
    second = store_for(tmp_path/'second', root, original); finish(second)
    native = first.read; other = second.read(); calls = []
    def changed_read():
        calls.append(True)
        return native() if len(calls) == 1 else other
    monkeypatch.setattr(first, 'read', changed_read)
    before = inventory(tmp_path)
    with pytest.raises(Exception) as error:
        proposal_work_result(first)
    assert error.value.reason == 'proposal_work_delivery_changed' and error.value.exit_code == 6
    assert inventory(tmp_path) == before


def test_human_validity_is_checked_again_inside_real_writer_lock(recorded, tmp_path, monkeypatch):
    from contextlib import contextmanager
    import specroad.proposals.apply as publication
    case = ApplyCase(tmp_path/'project')
    store = store_for(tmp_path/'work', case.root, case.original); finish(store, services=case.services)
    native = publication.project_lock; acquired = []
    @contextmanager
    def revoke_under_lock(*args, **kwargs):
        with native(*args, **kwargs) as held:
            acquired.append(True)
            case.current_decisions = False
            yield held
    monkeypatch.setattr(publication, 'project_lock', revoke_under_lock)
    before = inventory(case.root)
    with pytest.raises(Exception) as error:
        case.apply(checked_work=tmp_path/'work')
    assert error.value.exit_code in (3, 6, 7), error.value
    assert acquired == [True] and not case.requests and inventory(case.root) == before
