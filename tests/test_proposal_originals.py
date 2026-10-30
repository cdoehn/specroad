"""Read-only native Proposal originals; all actors and sources are synthetic."""
from copy import deepcopy

import pytest

from specroad.changes.core import prepare_change_plan
from specroad.model.canonical import canonical_json_bytes
from specroad.model.paths import artifact_path
from specroad.proposals.context import (ProposalContext, specification_manifest,
                                       reconstruct_proposal_target)
from specroad.proposals.values import ProposalOriginal, ProposalError, content_sha256, SPECIFICATION_SCOPE
from support.change_plans import document
from support.domain import domain_value
from support.inspection import inspection_project
from support.read_only import no_write_attempts
from support.records import record_value


def draft(tmp_path):
    model = inspection_project(tmp_path / 'origin', artifacts=[record_value('document'), domain_value('goal')])
    root = specification_manifest(model).sha256
    plan = document([], [])
    plan['base'] = {'scope_descriptor': deepcopy(SPECIFICATION_SCOPE), 'model_root_sha256': root}
    plan['expected_result']['model_root_sha256'] = root
    plan = prepare_change_plan(plan)
    value = record_value('proposal', base=plan.data['base'], change_plan=plan.data)
    value['content_sha256'] = content_sha256(value)
    return model, value


def original(value):
    return ProposalOriginal(canonical_json_bytes(value),
        path=artifact_path('proposal', value['id'], 'SR'))


def test_original_reconstructs_actual_native_basis_and_target_without_writes(tmp_path):
    model, value = draft(tmp_path)
    with no_write_attempts():
        record = original(value)
        context = ProposalContext(record, model)
        target = reconstruct_proposal_target(context)
    assert specification_manifest(target).sha256 == value['base']['model_root_sha256']
    assert record.binding.data['proposal_id'] == value['id']
    assert record.source_bytes == canonical_json_bytes(value)


@pytest.mark.parametrize('field', ['revision', 'created_at', 'created_by', 'updated_at', 'updated_by',
    'content_revision', 'content_sha256', 'maturity', 'proposal_status', 'reviews', 'control_history'])
def test_content_hash_excludes_only_top_level_management_fields(tmp_path, field):
    _, value = draft(tmp_path)
    digest = content_sha256(value)
    changed = deepcopy(value)
    changed[field] = {'synthetic': field}
    assert content_sha256(changed) == digest
    changed = deepcopy(value)
    changed.setdefault('extensions', {})['test:binding'] = {field: 'inner value'}
    assert content_sha256(changed) != digest


@pytest.mark.parametrize('mutation', ['content', 'scope', 'base', 'plan'])
def test_original_rejects_false_content_basis_or_plan_bindings(tmp_path, mutation):
    model, value = draft(tmp_path)
    if mutation == 'content':
        value['rationale'] = 'changed without a new hash'
    elif mutation == 'scope':
        value['base']['scope_descriptor']['scope_kind'] = 'project'
        value['content_sha256'] = content_sha256(value)
    elif mutation == 'base':
        value['base']['model_root_sha256'] = '0' * 64
        value['content_sha256'] = content_sha256(value)
    else:
        value['change_plan']['change_plan_sha256'] = '0' * 64
        value['content_sha256'] = content_sha256(value)
    from specroad.model.errors import ModelError
    with no_write_attempts(), pytest.raises(ModelError):
        reconstruct_proposal_target(ProposalContext(original(value), model))


def test_current_files_cannot_replace_original_proposal_basis(tmp_path):
    model, value = draft(tmp_path)
    from specroad.changes._target_materialization import materialize_target
    from specroad.validation import ModelDocument
    goal = next(a for a in model.artifacts if a['artifact_type'] == 'goal')
    goal['statement'] = 'Different current statement'
    changed = materialize_target(model, (ModelDocument(artifact_path('goal', goal['id'], 'SR'),
                                                      canonical_json_bytes(goal)),))
    with no_write_attempts(), pytest.raises(ProposalError, match='original_basis_mismatch'):
        reconstruct_proposal_target(ProposalContext(original(value), changed))


@pytest.mark.parametrize('fault', [None, 'guard', 'metadata', 'result', 'target'])
def test_actual_operations_are_folded_with_native_guards_metadata_and_results(tmp_path, fault):
    from specroad.changes.lifecycle import prepare_change_lifecycle
    from specroad.changes._target_materialization import materialize_target
    from specroad.validation import ModelDocument
    from specroad.model.canonical import canonical_json_sha256
    from specroad.model.errors import ModelError
    from support.folds import edit
    from support.change_plans import result
    model, value = draft(tmp_path)
    source = next(a for a in model.artifacts if a['artifact_type'] == 'goal')
    operations = [edit(source, 'First actual change'), edit(source, 'Final actual change')]
    plan = document(operations, [])
    fold = prepare_change_lifecycle(model.artifacts, operations,
        metadata_policy_version=plan['metadata_policy_version'], actor=plan['actor'],
        planned_at=plan['planned_at'], source_files=model.source_files, **model.reservations)
    final = next(a for a in fold.artifacts if a['id'] == source['id'])
    target = materialize_target(model, (ModelDocument(artifact_path('goal', source['id'], 'SR'),
                                                     canonical_json_bytes(final)),))
    plan['base'] = value['base']
    plan['result_artifacts'] = [result(final)]
    plan['expected_result']['model_root_sha256'] = specification_manifest(target).sha256
    if fault == 'guard':
        plan['operations'][0]['expected_revision'] += 1
    elif fault == 'metadata':
        plan['result_artifacts'][0]['artifact']['revision'] += 1
    elif fault == 'result':
        plan['result_artifacts'][0]['artifact']['statement'] = 'Invented result'
    elif fault == 'target':
        plan['expected_result']['model_root_sha256'] = '0' * 64
    for entry in plan['result_artifacts']:
        entry['sha256'] = canonical_json_sha256(entry['artifact'])
    value['change_plan'] = prepare_change_plan(plan).data
    value['content_sha256'] = content_sha256(value)
    if fault is None:
        with no_write_attempts():
            actual = reconstruct_proposal_target(ProposalContext(original(value), model))
        assert actual.artifacts == target.artifacts
        assert final['revision'] == source['revision'] + 1
        assert final['statement'] == 'Final actual change'
    else:
        with no_write_attempts(), pytest.raises(ModelError):
            reconstruct_proposal_target(ProposalContext(original(value), model))
