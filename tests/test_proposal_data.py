"""Complete synthetic Proposal data, native parsing and no execution authority."""
from copy import deepcopy

import pytest

from specroad.changes import ChangePlan
from specroad.changes.core import prepare_change_plan
from specroad.model.canonical import canonical_json_bytes, canonical_json_sha256
from specroad.model.errors import ModelError
from specroad.model.identity_values import ArtifactIdentity
from specroad.proposals import Proposal, ProposalOriginal, prepare_proposal
from specroad.proposals.values import SPECIFICATION_SCOPE, content_sha256
from specroad.storage.record_artifact import RecordArtifact
from support.change_plans import document, operation
from support.read_only import no_write_attempts
from support.records import ref

IDENTITY = ArtifactIdentity(ref('PROP'), 'random128-v1', 'proposal', 'SR')
MODEL = {'provider': 'synthetic-provider', 'model_name': 'synthetic-model',
         'model_version_or_build': 'build-1', 'prompt_template_version': 'template-1',
         'runner_version': 'runner-1', 'unknown_reasons': {}}


def inputs(*, actor_type='human', empty=False, representation=False):
    value = document([] if empty else None, [] if empty else None)
    value['base']['scope_descriptor'] = deepcopy(SPECIFICATION_SCOPE)
    value['actor']['actor_type'] = actor_type
    if empty:
        value['expected_result']['model_root_sha256'] = value['base']['model_root_sha256']
    if representation:
        value['operations'] = [operation('representation_normalize')]
        value['result_artifacts'] = []
    plan = prepare_change_plan(value)
    changes = [{'change_id': 'CHG-' + '0' * 26,
                'targets': ([entry.data['path']] if representation else list(entry.result_ids)),
                'rationale': 'Explain the synthetic operation.',
                'requirement_or_issue_ids': [ref('REQ'), ref('ISSUE')],
                'sources': [{'locator': 'synthetic:source', 'captured_at': value['planned_at'],
                             'excerpt': 'Synthetic source text.'}],
                'assumptions': ['Synthetic assumption requiring review.'],
                'confidence': 0.75 if actor_type == 'ai' else None}
               for entry in plan.operations]
    return dict(identity=IDENTITY, title='Synthetic proposal', rationale='Explain the whole change.',
                change_plan=plan, changes=changes,
                model_provenance=deepcopy(MODEL) if actor_type == 'ai' else None)


@pytest.mark.parametrize('actor_type', ['human', 'ai', 'ci', 'tool'])
def test_complete_owned_proposal_roundtrips_explicit_plan_actor_and_explanations(actor_type):
    supplied = inputs(actor_type=actor_type)
    with no_write_attempts():
        result = prepare_proposal(**supplied)
        read = Proposal(result.source_bytes, path=IDENTITY.path)
        passive = RecordArtifact(result.source_bytes, expected_type='proposal')
    data = result.data
    assert data == read.data == passive.data
    assert data['change_plan'] == supplied['change_plan'].data
    assert data['changes'] == supplied['changes']
    assert data['created_by'] == data['updated_by'] == data['change_plan']['actor']
    assert data['created_at'] == data['updated_at'] == data['change_plan']['planned_at']
    assert data['revision'] == data['content_revision'] == 1
    assert data['proposal_status'] == data['maturity'] == 'draft'
    assert data['reviews'] == data['control_history'] == []
    assert data['content_sha256'] == content_sha256(data)
    assert result.binding.change_plan_sha256 == supplied['change_plan'].sha256
    assert result.write_authorized is False
    assert ChangePlan(canonical_json_bytes(data['change_plan'])).execution_ready is False
    original = result.source_bytes
    supplied['changes'][0]['rationale'] = 'Caller mutation'
    data['changes'].clear()
    assert result.source_bytes == original
    assert result.data['changes'][0]['rationale'] == 'Explain the synthetic operation.'


@pytest.mark.parametrize('empty,representation', [(True, False), (False, True)])
def test_empty_and_representation_plans_keep_exact_explanation_correspondence(empty, representation):
    supplied = inputs(empty=empty, representation=representation)
    with no_write_attempts():
        result = prepare_proposal(**supplied)
    assert result.data['changes'] == supplied['changes']
    assert result.data['change_plan']['operations'] == supplied['change_plan'].data['operations']


@pytest.mark.parametrize('fault', ['missing', 'extra', 'target', 'duplicate_requirement',
    'change_id', 'rationale', 'reference', 'source', 'assumption', 'confidence_low',
    'confidence_high', 'confidence_bool', 'extra_key'])
def test_invalid_explanations_are_rejected_before_any_write(fault):
    supplied = inputs(actor_type='ai')
    changes = supplied['changes']; row = changes[0]
    if fault == 'missing':
        changes.clear()
    elif fault == 'extra':
        changes.append(deepcopy(row))
    elif fault == 'target':
        row['targets'] = [ref('GOAL', '1')]
    elif fault == 'duplicate_requirement':
        row['requirement_or_issue_ids'] *= 2
    elif fault == 'change_id':
        row['change_id'] = 'CHG-not-an-identity'
    elif fault == 'rationale':
        row['rationale'] = '  '
    elif fault == 'reference':
        row['requirement_or_issue_ids'] = [ref('GOAL')]
    elif fault == 'source':
        row['sources'][0].pop('excerpt')
    elif fault == 'assumption':
        row['assumptions'] = ['']
    elif fault.startswith('confidence_'):
        row['confidence'] = {'confidence_low': -0.1, 'confidence_high': 1.1,
                             'confidence_bool': True}[fault]
    else:
        row['approved'] = True
    with no_write_attempts(), pytest.raises(ModelError):
        prepare_proposal(**supplied)


def test_distinct_changes_require_distinct_ids_and_targets_in_plan_order():
    supplied = inputs()
    value = supplied['change_plan'].data
    value.pop('change_plan_sha256')
    second = deepcopy(value['operations'][0])
    second['artifact']['id'] = second['result_id'] = ref('GOAL', '1')
    value['operations'].append(second)
    value['result_artifacts'].append({'artifact': second['artifact'],
                                     'sha256': canonical_json_sha256(second['artifact'])})
    supplied['change_plan'] = prepare_change_plan(value)
    row = deepcopy(supplied['changes'][0]); row['targets'] = [second['result_id']]
    supplied['changes'].append(row)
    with pytest.raises(ModelError, match='duplicate_proposal_change_id'):
        prepare_proposal(**supplied)
    row['change_id'] = 'CHG-' + '1' * 26
    with no_write_attempts():
        accepted = prepare_proposal(**supplied)
    assert accepted.data['changes'] == supplied['changes']
    supplied['changes'].reverse()
    with pytest.raises(ModelError, match='proposal_explanation_targets'):
        prepare_proposal(**supplied)


@pytest.mark.parametrize('field', ['rationale', 'assumptions', 'sources', 'confidence'])
def test_each_explanation_is_content_bound_and_mutations_need_a_new_hash(field):
    result = prepare_proposal(**inputs(actor_type='ai'))
    data = result.data
    data['changes'][0][field] = {'rationale': 'Different rationale', 'assumptions': [],
        'sources': [], 'confidence': 0.5}[field]
    assert content_sha256(data) != result.binding.content_sha256
    with pytest.raises(ModelError):
        Proposal(canonical_json_bytes(data), path=IDENTITY.path)
    data['content_sha256'] = content_sha256(data)
    assert Proposal(canonical_json_bytes(data), path=IDENTITY.path).data == data


def test_content_and_control_are_disjoint_owned_projections_without_hash_loss():
    result = prepare_proposal(**inputs(actor_type='ai'))
    content, control = result.content_data, result.control_data
    assert not content.keys() & control.keys()
    assert content | control == result.data
    assert canonical_json_sha256(content) == result.binding.content_sha256
    content['changes'].clear(); control['created_by']['actor_id'] = 'forged'
    assert result.content_data['changes'] and result.control_data['created_by']['actor_id'] != 'forged'
    assert result.data['provider'] == MODEL['provider']


@pytest.mark.parametrize('fault', ['missing', 'unknown_without_reason'])
def test_ai_origin_never_passes_as_complete_when_required_information_is_missing(fault):
    supplied = inputs(actor_type='ai')
    if fault == 'missing':
        supplied['model_provenance'] = None
    else:
        supplied['model_provenance']['provider'] = 'unknown'
    with no_write_attempts(), pytest.raises(ModelError):
        prepare_proposal(**supplied)


@pytest.mark.parametrize('fault', ['identity_kind', 'identity_legacy', 'plan_dictionary', 'scope', 'title'])
def test_native_identity_plan_and_core_contracts_remain_required(fault):
    supplied = inputs()
    if fault == 'identity_kind':
        supplied['identity'] = ArtifactIdentity(ref('GOAL'), 'random128-v1', 'goal', 'SR')
    elif fault == 'identity_legacy':
        supplied['identity'] = ArtifactIdentity('SR-PROP-0001', 'legacy-sequential-v1', 'proposal', 'SR')
    elif fault == 'plan_dictionary':
        supplied['change_plan'] = supplied['change_plan'].data
    elif fault == 'scope':
        plan = supplied['change_plan'].data; plan.pop('change_plan_sha256')
        plan['base']['scope_descriptor']['scope_kind'] = 'project'
        supplied['change_plan'] = prepare_change_plan(plan)
    else:
        supplied['title'] = ''
    with no_write_attempts(), pytest.raises(ModelError):
        prepare_proposal(**supplied)


def test_read_only_restore_core_accepts_prepared_data_against_native_basis(tmp_path):
    from test_proposal_originals import draft
    from specroad.proposals.context import ProposalContext, reconstruct_proposal_target, specification_manifest
    from support.languages import small_restore_registry
    model, old = draft(tmp_path, language_registry=small_restore_registry())
    plan = ChangePlan(canonical_json_bytes(old['change_plan']))
    with no_write_attempts():
        result = prepare_proposal(identity=IDENTITY, title='Native basis', rationale='No mutation',
                                  change_plan=plan, changes=[])
        target = reconstruct_proposal_target(ProposalContext(result.original, model))
    assert specification_manifest(target).sha256 == plan.data['base']['model_root_sha256']
    assert target.artifacts == model.artifacts
    historical = ProposalOriginal(canonical_json_bytes(old), path=IDENTITY.path)
    assert historical.data == old
    with pytest.raises(ModelError, match='proposal_explanations_required'):
        Proposal(historical.source_bytes, path=IDENTITY.path)


def test_prepared_explained_operation_reconstructs_the_real_native_target(tmp_path):
    from specroad.changes.lifecycle import prepare_change_lifecycle
    from specroad.changes._target_materialization import materialize_target
    from specroad.proposals.context import ProposalContext, reconstruct_proposal_target, specification_manifest
    from specroad.validation import ModelDocument
    from specroad.model.paths import artifact_path
    from support.folds import edit
    from support.change_plans import result as result_row
    from support.languages import small_restore_registry
    from test_proposal_originals import draft
    model, old = draft(tmp_path, language_registry=small_restore_registry())
    source = next(a for a in model.artifacts if a['artifact_type'] == 'goal')
    op = edit(source, 'A real proposed target')
    plan = document([op], [])
    fold = prepare_change_lifecycle(model.artifacts, [op],
        metadata_policy_version=plan['metadata_policy_version'], actor=plan['actor'],
        planned_at=plan['planned_at'], source_files=model.source_files, **model.reservations)
    final = next(a for a in fold.artifacts if a['id'] == source['id'])
    target = materialize_target(model, (ModelDocument(artifact_path('goal', final['id'], 'SR'),
                                                    canonical_json_bytes(final)),))
    plan['base'] = old['base']; plan['result_artifacts'] = [result_row(final)]
    plan['expected_result']['model_root_sha256'] = specification_manifest(target).sha256
    supplied = inputs(); supplied['change_plan'] = prepare_change_plan(plan)
    supplied['changes'][0]['targets'] = [source['id']]
    with no_write_attempts():
        proposal = prepare_proposal(**supplied)
        actual = reconstruct_proposal_target(ProposalContext(proposal.original, model))
    assert actual.artifacts == target.artifacts
    assert next(a for a in model.artifacts if a['id'] == source['id']) == source
    assert final['statement'] == 'A real proposed target'
    assert final['revision'] == source['revision'] + 1
