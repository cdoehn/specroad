"""AI provenance remains explicit and content-bound through native readers."""
from copy import deepcopy

import pytest

from specroad.changes.core import prepare_change_plan
from specroad.model.canonical import canonical_json_bytes
from specroad.model.errors import ModelError
from specroad.model.proposal_fields import MODEL_FIELDS
from specroad.proposals import Proposal, ProposalOriginal, prepare_proposal
from specroad.proposals.values import content_sha256
from specroad.storage.record_artifact import RecordArtifact
from support.read_only import no_write_attempts
from test_proposal_data import IDENTITY, MODEL, inputs


@pytest.mark.parametrize('field', MODEL_FIELDS)
def test_each_unknown_model_value_keeps_its_explicit_individual_reason(field):
    supplied = inputs(actor_type='ai')
    supplied['model_provenance'][field] = 'unknown'
    reason = 'Synthetic provider did not expose ' + field
    supplied['model_provenance']['unknown_reasons'][field] = reason
    with no_write_attempts():
        proposal = prepare_proposal(**supplied)
        restored = ProposalOriginal(proposal.source_bytes, path=IDENTITY.path)
    assert restored.data[field] == 'unknown'
    assert restored.data['unknown_reasons'] == {field: reason}
    assert all(restored.data[key] == supplied['model_provenance'][key] for key in MODEL_FIELDS)
    changed = proposal.data
    changed['unknown_reasons'][field] += ' changed'
    assert content_sha256(changed) != proposal.binding.content_sha256


@pytest.mark.parametrize('field', (*MODEL_FIELDS, 'unknown_reasons'))
@pytest.mark.parametrize('reader', ['factory', 'record', 'original', 'proposal'])
def test_missing_ai_provenance_is_not_fabricated_by_any_reader(field, reader):
    supplied = inputs(actor_type='ai')
    if reader == 'factory':
        supplied['model_provenance'].pop(field)
        with no_write_attempts(), pytest.raises(ModelError):
            prepare_proposal(**supplied)
        return
    value = prepare_proposal(**supplied).data
    value.pop(field)
    value['content_sha256'] = content_sha256(value)
    raw = canonical_json_bytes(value)
    with no_write_attempts(), pytest.raises(ModelError, match='proposal_model_fields_required'):
        {'record': lambda: RecordArtifact(raw, expected_type='proposal'),
         'original': lambda: ProposalOriginal(raw, path=IDENTITY.path),
         'proposal': lambda: Proposal(raw, path=IDENTITY.path)}[reader]()


@pytest.mark.parametrize('fault', ['all_missing', 'no_reason', 'empty_reason', 'unknown_key',
    'known_reason', 'empty_value', 'null_value', 'extra_model_field', 'non_object'])
def test_incomplete_or_ambiguous_model_declarations_fail_closed(fault):
    supplied = inputs(actor_type='ai')
    model = supplied['model_provenance']
    if fault == 'all_missing':
        supplied['model_provenance'] = None
    elif fault == 'no_reason':
        model['provider'] = 'unknown'
    elif fault == 'empty_reason':
        model['provider'] = 'unknown'; model['unknown_reasons'] = {'provider': '  '}
    elif fault == 'unknown_key':
        model['unknown_reasons'] = {'unlisted': 'Not a model field'}
    elif fault == 'known_reason':
        model['unknown_reasons'] = {'provider': 'A known value needs no unknown reason'}
    elif fault == 'empty_value':
        model['provider'] = ''
    elif fault == 'null_value':
        model['provider'] = None
    elif fault == 'extra_model_field':
        model['reviews'] = [{'decision': 'approved'}]
    else:
        supplied['model_provenance'] = 'not an object'
    with no_write_attempts(), pytest.raises(ModelError):
        prepare_proposal(**supplied)


@pytest.mark.parametrize('value', [0, 1, 0.125])
def test_ai_confidence_boundaries_and_explicit_empty_origin_lists(value):
    supplied = inputs(actor_type='ai')
    row = supplied['changes'][0]
    row.update(confidence=value, sources=[], assumptions=[], requirement_or_issue_ids=[])
    with no_write_attempts():
        proposal = prepare_proposal(**supplied)
    assert proposal.data['changes'][0] == row


@pytest.mark.parametrize('value', [None, True, False, '0.5', float('nan'), float('inf'), -float('inf')])
def test_ai_confidence_rejects_absence_coercion_and_nonfinite_values(value):
    supplied = inputs(actor_type='ai'); supplied['changes'][0]['confidence'] = value
    with no_write_attempts(), pytest.raises(ModelError):
        prepare_proposal(**supplied)


def test_all_unknown_fields_require_five_reasons_even_for_an_empty_ai_proposal():
    supplied = inputs(actor_type='ai', empty=True)
    supplied['model_provenance'] = {name: 'unknown' for name in MODEL_FIELDS}
    supplied['model_provenance']['unknown_reasons'] = {name: 'Synthetic missing ' + name for name in MODEL_FIELDS}
    with no_write_attempts():
        result = prepare_proposal(**supplied)
    assert result.data['changes'] == []
    assert result.data['unknown_reasons'] == supplied['model_provenance']['unknown_reasons']
    supplied['model_provenance']['unknown_reasons'].clear()
    assert len(result.data['unknown_reasons']) == 5


@pytest.mark.parametrize('actor_type', ['human', 'ci', 'tool'])
def test_optional_model_provenance_is_complete_when_non_ai_authors_supply_it(actor_type):
    supplied = inputs(actor_type=actor_type); supplied['model_provenance'] = deepcopy(MODEL)
    result = prepare_proposal(**supplied)
    assert result.data['provider'] == MODEL['provider']
    data = result.data; data.pop('runner_version'); data['content_sha256'] = content_sha256(data)
    with pytest.raises(ModelError):
        ProposalOriginal(canonical_json_bytes(data), path=IDENTITY.path)


def test_provenance_cannot_inject_control_and_raw_noncanonical_original_bytes_survive():
    import json
    result = prepare_proposal(**inputs(actor_type='ai'))
    raw = json.dumps(result.data, indent=3, ensure_ascii=False).encode() + b'\n'
    with no_write_attempts():
        reread = Proposal(raw, path=IDENTITY.path)
    assert reread.source_bytes == raw and reread.binding == result.binding
    assert reread.content_data | reread.control_data == result.data
    assert reread.data['reviews'] == [] and reread.write_authorized is False
    tampered = result.data; tampered['runner_version'] = 'different'
    with pytest.raises(ModelError, match='proposal_content_hash_mismatch'):
        ProposalOriginal(canonical_json_bytes(tampered), path=IDENTITY.path)


@pytest.mark.parametrize('actor_type', ['ai', 'ci'])
def test_passive_proposal_preserves_absent_request_without_claiming_write_authority(actor_type):
    supplied = inputs(actor_type=actor_type)
    plan = supplied['change_plan'].data; plan.pop('change_plan_sha256')
    plan['request_id'] = None
    supplied['change_plan'] = prepare_change_plan(plan)
    with no_write_attempts():
        result = prepare_proposal(**supplied)
    assert result.data['change_plan']['request_id'] is None
    assert result.write_authorized is False
