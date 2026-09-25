"""Formal approval contracts and explicitly verified human observations, not UI."""
import copy
from dataclasses import FrozenInstanceError, replace
import pytest
from specroad.model.errors import ModelError
from specroad.validation import (ApprovalContext, HumanRequirementReview, ApprovalPrerequisite,
                                assess_requirement_approval)
from specroad.validation.approval_values import HUMAN_CRITERIA, PREREQUISITES
from support.approval import (values, context, assess, prerequisites, review_data, verifier,
                              quality_records, QUALITY_FIELDS, reasons)
from support.domain import domain_value
from support.model_validation import doc


def test_complete_data_only_enables_human_transition_without_writing():
    ctx=context(); before=tuple(d.content for d in ctx.documents)
    result=assess(ctx)
    assert result.eligible_for_human_approval and result.data['requirements_satisfied']
    for flag in ('approval_granted','write_authorized','atomic_snapshot','project_complete','semantic_detection_performed'):
        assert result.data[flag] is False
    assert tuple(d.content for d in ctx.documents)==before
    assert ctx.requirement()['maturity']=='in_review'
    assert ctx.requirement()['revision']==1


def test_draft_cannot_jump_to_approved():
    result=assess(context(values(maturity='draft')))
    assert not result.eligible_for_human_approval
    assert 'approval_source_maturity_invalid' in reasons(result)


def test_proposed_cannot_skip_in_review():
    assert not assess(context(values(maturity='proposed'))).eligible_for_human_approval


def test_stored_approved_is_observed_not_approved_again():
    result=assess(context(values(maturity='approved'),mode='stored'))
    assert result.data['requirements_satisfied'] and not result.eligible_for_human_approval
    assert not result.data['approval_granted']


def test_transition_rejects_an_already_approved_requirement():
    assert not assess(context(values(maturity='approved'))).eligible_for_human_approval


def test_rationale_is_required_in_hypothetical_approved_schema():
    rows=values();del rows[0]['rationale']
    assert not assess(context(rows)).data['formal_data_valid']


def test_empty_rationale_is_not_a_filled_field():
    assert not assess(context(values(rationale=''))).data['formal_data_valid']


def test_origin_metadata_does_not_replace_outgoing_origin_relation():
    rows=values();rows[0]['relations']=rows[0]['relations'][1:]
    result=assess(context(rows))
    assert 'core:requirement-origin' in reasons(result)
    assert any(f['diagnostic']['code']=='SRV031' for f in result.data['findings'])


def test_missing_verified_by_blocks_even_if_service_receipt_claims_passed():
    rows=values();rows[0]['relations']=rows[0]['relations'][:1]
    result=assess(context(rows))
    assert 'core:requirement-verification' in reasons(result)
    assert not result.eligible_for_human_approval


def test_missing_relation_target_is_a_model_error():
    rows=values();rows.pop()
    assert not assess(context(rows)).data['formal_data_valid']


def test_should_requires_deviation_metadata():
    assert not assess(context(values(normative_force='should'))).data['formal_data_valid']


def test_explicit_force_not_inferred_from_statement_or_priority():
    for force in ('must','must_not','may'):
        result=assess(context(values(normative_force=force, statement='The visible state is READY.')))
        assert result.eligible_for_human_approval


def test_quality_requires_all_four_measurement_fields():
    rows=quality_records();ctx=context(rows,quality_fields=QUALITY_FIELDS)
    assert assess(ctx).eligible_for_human_approval
    for key in ('property','method','comparison','target'):
        bad=copy.deepcopy(rows);del bad[0]['thresholds'][0][key]
        assert not assess(context(bad,quality_fields=QUALITY_FIELDS)).eligible_for_human_approval


def test_quality_projection_is_not_guessed_from_field_names():
    assert not assess(context(quality_records())).eligible_for_human_approval


def test_quality_zero_target_is_present_and_valid():
    rows=quality_records();rows[0]['thresholds'][0]['target']=0
    assert assess(context(rows,quality_fields=QUALITY_FIELDS)).eligible_for_human_approval


def test_quality_null_target_is_not_a_boundary():
    rows=quality_records();rows[0]['thresholds'][0]['target']=None
    assert 'approval_quality_target_invalid' in reasons(assess(context(rows,quality_fields=QUALITY_FIELDS)))


def test_interface_requires_explicit_system_boundary():
    assert not assess(context(values('interface'))).eligible_for_human_approval


def test_interface_accepts_existing_component_boundary():
    rows=values('interface');component=domain_value('component')
    rows[0]['scope']={'boundary':component['id']};rows.append(component)
    assert assess(context(rows,interface_fields=('/scope/boundary',))).eligible_for_human_approval


def test_interface_source_and_target_must_exist_in_model():
    rows=values('interface');a=domain_value('component');b=domain_value('component',id='SR-COMP-'+'1'*26)
    rows[0]['scope']={'source':a['id'],'target':b['id']};rows.extend([a,b])
    fields=('/scope/source','/scope/target')
    assert assess(context(rows,interface_fields=fields)).eligible_for_human_approval
    rows.pop(); assert not assess(context(rows,interface_fields=fields)).eligible_for_human_approval


def test_human_review_is_required_even_with_all_services_passed():
    result=assess(review=None)
    assert 'approval_human_review_missing' in reasons(result)
    assert not result.eligible_for_human_approval


def test_human_actor_label_is_not_authentication():
    result=assess(verifier=None)
    assert not result.eligible_for_human_approval
    assert not result.data['authenticated_by_supplied_verifier']


def test_ai_review_never_replaces_human_judgment():
    ctx=context();review=HumanRequirementReview(review_data(ctx,reviewer={'actor_type':'ai','actor_id':'detector'}))
    result=assess(ctx,review=review)
    assert result.data['human_review_status']=='nonhuman'
    assert not result.eligible_for_human_approval


def test_human_confirmation_of_compound_is_error():
    ctx=context();review=HumanRequirementReview(review_data(ctx,compound=True))
    result=assess(ctx,review=review)
    assert result.data['human_review_status']=='compound'
    assert any(f['diagnostic']['code']=='SRV162' for f in result.data['findings'])
    assert not result.eligible_for_human_approval


def test_core_does_not_detect_compound_from_and_word():
    assert assess(context(values(statement='Measure the input and output latency.'))).eligible_for_human_approval


def test_each_human_criterion_must_be_confirmed():
    ctx=context()
    for criterion in HUMAN_CRITERIA:
        data=review_data(ctx);del data['criteria'][criterion]
        assert not assess(ctx,review=HumanRequirementReview(data)).eligible_for_human_approval


def test_rejected_review_remains_blocking():
    ctx=context()
    assert not assess(ctx,review=HumanRequirementReview(review_data(ctx,decision='rejected'))).eligible_for_human_approval


def test_every_service_is_required_not_inferred_from_structural_success():
    ctx=context();receipts=prerequisites(ctx)
    for name in PREREQUISITES:
        result=assess(ctx,prerequisites=tuple(p for p in receipts if p.gate_id!=name))
        assert not result.eligible_for_human_approval
        assert next(p for p in result.data['prerequisites'] if p['gate_id']==name)['status']=='unavailable'


def test_failed_or_unavailable_service_never_passes():
    ctx=context();receipts=prerequisites(ctx)
    for state in ('failed','unavailable'):
        result=assess(ctx,prerequisites=(replace(receipts[0],status=state),*receipts[1:]))
        assert not result.eligible_for_human_approval


def test_review_from_another_exact_candidate_is_stale():
    original=context();changed=context(values(statement='A different statement.'))
    result=assess(changed,review=HumanRequirementReview(review_data(original)))
    assert result.data['human_review_status']=='stale'
    assert not result.eligible_for_human_approval


def test_old_service_results_are_not_rebound_automatically():
    original=context();changed=context(values(rationale='Different rationale.'))
    result=assess(changed,prerequisites=prerequisites(original))
    assert {p['status'] for p in result.data['prerequisites']}=={'stale'}


def test_inputs_and_report_are_detached():
    rows=values();ctx=context(rows);review_source=review_data(ctx);review=HumanRequirementReview(review_source)
    rows[0]['statement']='Modified';review_source['criteria'].clear()
    result=assess(ctx,review=review);view=result.data;view['findings'].append({'forged':True})
    assert result.eligible_for_human_approval and not result.data['findings']
    assert ctx.requirement()['statement']!='Modified'
    with pytest.raises(FrozenInstanceError):ctx.input_sha256='f'*64
    with pytest.raises(TypeError):bool(result)


def test_duplicate_service_result_is_rejected():
    ctx=context();receipts=prerequisites(ctx)
    with pytest.raises(ModelError):assess(ctx,prerequisites=receipts+(receipts[0],))


def test_absent_effective_profile_is_not_implicit_core_success():
    assert not assess(context(profile=None)).eligible_for_human_approval


def test_reordered_input_sources_have_same_binding_and_result():
    rows=values();ctx=context(rows)
    other=ApprovalContext(rows[0]['id'],tuple(reversed(ctx.documents)),profile=ctx.profile)
    assert other.input_sha256==ctx.input_sha256
    assert assess(other).data==assess(ctx).data
