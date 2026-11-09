"""Native fixed-basis construction and authoring, using small synthetic projects."""
from dataclasses import FrozenInstanceError

import pytest

from specroad.changes._target_materialization import materialize_target
from specroad.changes.core import prepare_change_plan
from specroad.model.canonical import canonical_json_bytes as jcs
from specroad.model.identity_values import ArtifactIdentity
from specroad.model.paths import artifact_path
from specroad.proposals import (ProposalBasis, ProposalError, build_proposal_basis,
                               prepare_proposal_for_model)
from specroad.proposals.context import specification_manifest
from specroad.proposals.values import SPECIFICATION_SCOPE
from specroad.validation import ModelDocument
from support.change_plans import document
from support.domain import domain_value
from support.inspection import inspection_project
from support.languages import small_restore_registry
from support.read_only import no_write_attempts
from support.records import record_value, ref


def project(root, *, bundled=False, artifacts=None):
    return inspection_project(root, artifacts=artifacts if artifacts is not None else
        [record_value('document'), domain_value('goal'), record_value('configuration')],
        language_registry=None if bundled else small_restore_registry())


def fields(model):
    value = document([], [])
    value['base'] = build_proposal_basis(model).data
    value['expected_result']['model_root_sha256'] = value['base']['model_root_sha256']
    return dict(identity=ArtifactIdentity(ref('PROP'), 'random128-v1', 'proposal', 'SR'),
                title='Synthetic fixed basis', rationale='Exercise native construction',
                change_plan=prepare_change_plan(value), changes=[])


def put_model(model, *values):
    return materialize_target(model, tuple(ModelDocument(
        artifact_path(v['artifact_type'], v['id'], 'SR'), jcs(v)) for v in values))


def planned_change(model):
    from specroad.changes.lifecycle import prepare_change_lifecycle
    from support.change_plans import result
    from support.folds import edit
    supplied = fields(model)
    goal = next(a for a in model.artifacts if a['artifact_type'] == 'goal')
    plan = document([edit(goal, 'Native proposed change')], [])
    plan['base'] = build_proposal_basis(model).data
    folded = prepare_change_lifecycle(model.artifacts, plan['operations'],
        metadata_policy_version=plan['metadata_policy_version'], actor=plan['actor'],
        planned_at=plan['planned_at'], source_files=model.source_files, **model.reservations)
    final = next(a for a in folded.artifacts if a['id'] == goal['id'])
    target = put_model(model, final)
    plan['result_artifacts'] = [result(final)]
    plan['expected_result']['model_root_sha256'] = build_proposal_basis(target).data['model_root_sha256']
    supplied['change_plan'] = prepare_change_plan(plan)
    supplied['changes'] = [{'change_id': 'CHG-' + '0' * 26, 'targets': [goal['id']],
        'rationale': 'Native synthetic edit', 'requirement_or_issue_ids': [],
        'sources': [], 'assumptions': [], 'confidence': None}]
    return supplied


@pytest.mark.parametrize('bundled', [False, True])
def test_basis_uses_exact_existing_native_closure_and_manifest(tmp_path, bundled):
    model = project(tmp_path / 'project', bundled=bundled)
    original = model.source_files
    with no_write_attempts():
        basis = build_proposal_basis(model)
        expected = specification_manifest(model)
    assert type(basis) is ProposalBasis
    assert basis.data == {'scope_descriptor': SPECIFICATION_SCOPE,
                          'model_root_sha256': expected.sha256}
    assert basis.manifest.canonical_bytes == expected.canonical_bytes
    assert {row['id'] for row in basis.manifest.data['artifacts']} == {a['id'] for a in model.artifacts}
    assert basis.manifest.data['boundary_references'] == []
    assert basis.write_authorized is False
    assert model.source_files == original


def test_basis_is_owned_and_has_no_mutable_manifest_or_descriptor_alias(tmp_path):
    basis = build_proposal_basis(project(tmp_path / 'project'))
    expected = basis.data
    basis.data['scope_descriptor']['scope_kind'] = 'project'
    basis.manifest.data['artifacts'].clear()
    assert basis.data == expected
    with pytest.raises(FrozenInstanceError):
        basis._manifest_bytes = b'{}'


def test_empty_supplied_artifact_set_still_binds_configuration_and_profile(tmp_path):
    model = project(tmp_path / 'project', artifacts=[])
    basis = build_proposal_basis(model)
    assert basis.manifest.data['artifacts'] == []
    assert basis.manifest.data['resources']
    assert basis.data['model_root_sha256'] == specification_manifest(model).sha256


def test_creation_and_control_updates_do_not_change_the_specification_basis(tmp_path):
    model = project(tmp_path / 'project')
    supplied = fields(model)
    with no_write_attempts():
        proposal = prepare_proposal_for_model(model, **supplied)
        with_proposal = put_model(model, proposal.data)
        current = proposal.data
        current.update(revision=2, updated_at='2026-01-02T00:00:00Z')
        controlled = put_model(with_proposal, current)
        basis = build_proposal_basis(controlled)
    assert basis.data == proposal.data['base'] == build_proposal_basis(model).data
    assert all(row['artifact_type'] != 'proposal' for row in basis.manifest.data['artifacts'])
    assert controlled.manifest(controlled.artifacts, document()['base']['scope_descriptor']).sha256 != \
        with_proposal.manifest(with_proposal.artifacts, document()['base']['scope_descriptor']).sha256
    assert proposal.write_authorized is False


def test_real_sealed_baseline_and_its_archive_do_not_enter_proposal_basis(tmp_path):
    from specroad.changes.baselines import prepare_baseline_operation, object_documents
    model = project(tmp_path / 'project')
    before = build_proposal_basis(model)
    with no_write_attempts():
        operation = prepare_baseline_operation(model, baseline_id=ref('BASE'), name='Synthetic baseline',
            actor={'actor_type': 'human', 'actor_id': 'synthetic-author'}, planned_at='2026-01-01T00:00:00Z')
        target = materialize_target(model, (*object_documents(operation), ModelDocument(
            artifact_path('baseline', ref('BASE'), 'SR'), jcs(operation['record']))))
        after = build_proposal_basis(target)
    assert before.manifest.canonical_bytes == after.manifest.canonical_bytes
    assert not after.manifest.data.get('archive_objects', [])
    assert all(row['artifact_type'] != 'baseline' for row in after.manifest.data['artifacts'])


def test_real_semantic_edit_changes_basis_and_old_plan_is_stale(tmp_path):
    model = project(tmp_path / 'project'); supplied = fields(model)
    goal = next(a for a in model.artifacts if a['artifact_type'] == 'goal')
    goal['statement'] = 'New actual statement'
    changed = put_model(model, goal)
    with no_write_attempts(), pytest.raises(ProposalError) as error:
        prepare_proposal_for_model(changed, **supplied)
    assert error.value.exit_code == 6
    assert build_proposal_basis(changed).data != build_proposal_basis(model).data


@pytest.mark.parametrize('value', [None, {}, b'{}', 'asserted root'])
def test_caller_labels_cannot_replace_native_source_model(value):
    with no_write_attempts(), pytest.raises(ProposalError):
        build_proposal_basis(value)


def test_native_target_reconstruction_rejects_false_declared_result(tmp_path):
    model = project(tmp_path / 'project'); supplied = planned_change(model)
    value = supplied['change_plan'].data; value.pop('change_plan_sha256')
    value['expected_result']['model_root_sha256'] = '0' * 64
    supplied['change_plan'] = prepare_change_plan(value)
    with no_write_attempts(), pytest.raises(ProposalError) as error:
        prepare_proposal_for_model(model, **supplied)
    assert error.value.reason == 'proposal_original_target_mismatch'


def test_nonempty_native_plan_binds_both_real_basis_and_target(tmp_path):
    model = project(tmp_path / 'project'); supplied = planned_change(model)
    with no_write_attempts():
        proposal = prepare_proposal_for_model(model, **supplied)
    assert proposal.data['base'] == build_proposal_basis(model).data
    assert proposal.data['change_plan'] == supplied['change_plan'].data
    assert proposal.data['change_plan']['expected_result']['model_root_sha256'] != \
        proposal.data['base']['model_root_sha256']


def test_absolute_location_and_original_json_format_are_not_basis_inputs(tmp_path):
    first = project(tmp_path / 'one'); second = project(tmp_path / 'two')
    import json
    from specroad.changes.target_model import TargetModel
    second = TargetModel(second.configuration_bytes, second.binding,
        tuple(ModelDocument(d.path, json.dumps(json.loads(d.content), indent=3).encode()) for d in second.documents),
        profile=second.profile, resource_files=second.resource_files)
    with no_write_attempts():
        one = build_proposal_basis(first); two = build_proposal_basis(second)
    assert one.manifest.canonical_bytes == two.manifest.canonical_bytes
