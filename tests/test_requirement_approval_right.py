"""Failure, freshness and isolation tests for the actual approval boundary."""
import copy
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import json
from pathlib import Path
import shutil
from unittest.mock import Mock, patch
import builtins
import pytest
from specroad.validation import (ApprovalContext,ApprovalPrerequisite,HumanRequirementReview,
    ReviewVerifier,ReviewVerification,ModelDocument,assess_requirement_approval)
from specroad.model.errors import ModelError
from specroad.model.canonical import canonical_json_bytes
from support.approval import (values,context,assess,review_data,prerequisites,verifier,reasons,
                             quality_records,QUALITY_FIELDS)
from support.domain import domain_value
from support.model_validation import doc,edge,profile
from support.artifacts import artifact_bytes
from support.profiles import profile_data,selector
from support.io_guards import block_imports_and_open
from support.portable import build_distribution
from support.processes import run_python


def test_core_placeholders_block_even_with_claimed_passed_services():
    for text in ('TBD','TODO','FIXME'):
        result=assess(context(values(statement='State: '+text)))
        assert 'approval_open_placeholder' in reasons(result)
        assert not result.eligible_for_human_approval
        d=next(f['diagnostic'] for f in result.data['findings'] if f['reason']=='approval_open_placeholder')
        assert d['code']=='SRV033' and d['location']['pointer']=='/statement'


def test_placeholder_in_nested_normative_data_has_exact_pointer():
    result=assess(context(values(scope={'a/b~':['Ready','TODO']})))
    d=next(f['diagnostic'] for f in result.data['findings'] if f['reason']=='approval_open_placeholder')
    assert d['location']['pointer']=='/scope/a~1b~0/1'
    assert d['location']['character_offset']==0


def test_placeholder_in_passive_extension_is_not_inferred_semantics():
    assert assess(context(values(extensions={'org.example':{'note':'TODO'}}))).eligible_for_human_approval


def test_unicode_placeholder_offset_uses_characters():
    r=assess(context(values(statement='😀 e\u0301 TODO')))
    d=next(f['diagnostic'] for f in r.data['findings'] if f['reason']=='approval_open_placeholder')
    assert d['location']['character_offset']==5
    assert 'byte_offset' not in d['location']


def test_verification_subject_must_include_this_requirement():
    rows=values();rows[2]['subjects']=['SR-REQ-'+'1'*26]
    assert 'approval_verification_subject_mismatch' in reasons(assess(context(rows)))


def test_many_measurement_rows_are_checked_without_display_limit():
    rows=quality_records();rows[0]['thresholds']*=151
    fields=tuple(tuple('/thresholds/'+str(i)+'/'+key for key in ('property','method','comparison','target')) for i in range(151))
    assert assess(context(rows,quality_fields=fields)).eligible_for_human_approval
    rows[0]['thresholds']=[dict(v) for v in rows[0]['thresholds']]
    rows[0]['thresholds'][150]['method']=''
    assert not assess(context(rows,quality_fields=fields)).eligible_for_human_approval


def test_invalid_quality_array_address_is_structured_failure():
    fields=(tuple(p.replace('/0/','/01/') for p in QUALITY_FIELDS[0]),)
    result=assess(context(quality_records(),quality_fields=fields))
    assert not result.eligible_for_human_approval
    assert 'approval_pointer_invalid' in reasons(result)


def test_interface_artifact_requires_resolved_component_endpoints():
    rows=values('interface');iface=domain_value('interface')
    rows[0]['scope']={'boundary':iface['id']};rows.append(iface)
    result=assess(context(rows,interface_fields=('/scope/boundary',)))
    assert 'approval_interface_endpoint_missing' in reasons(result)
    rows += [domain_value('component'),domain_value('component',id='SR-COMP-'+'1'*26)]
    assert assess(context(rows,interface_fields=('/scope/boundary',))).eligible_for_human_approval


def test_interface_does_not_match_display_ids():
    rows=values('interface');comp=domain_value('component',display_id='CPU')
    rows[0]['scope']={'boundary':'CPU'};rows.append(comp)
    assert not assess(context(rows,interface_fields=('/scope/boundary',))).eligible_for_human_approval


def test_review_is_stale_after_language_force_or_statement_change():
    old=context();review=HumanRequirementReview(review_data(old))
    for changes in ({'language':'en-US'},{'normative_force':'may'},{'statement':'Different proposition.'}):
        result=assess(context(values(**changes)),review=review)
        assert result.data['human_review_status']=='stale'


def test_same_semantics_different_source_bytes_invalidates_observation():
    old=context();docs=list(old.documents)
    docs[0]=ModelDocument(docs[0].path,docs[0].content+b'\n')
    new=ApprovalContext(old.requirement_id,docs,profile=old.profile)
    assert old.input_sha256!=new.input_sha256
    assert not assess(new,review=HumanRequirementReview(review_data(old))).eligible_for_human_approval


def test_changed_dependency_invalidates_bound_review():
    rows=values();old=context(rows);rows[1]['locator']='attachments/different.txt'
    assert assess(context(rows),review=HumanRequirementReview(review_data(old))).data['human_review_status']=='stale'


def test_configuration_changes_invalidate_service_and_human_observations():
    old=context(configuration={'variant':'one'});new=context(configuration={'variant':'two'})
    result=assess(new,review=HumanRequirementReview(review_data(old)),prerequisites=prerequisites(old))
    assert not result.eligible_for_human_approval
    assert all(v['status']=='stale' for v in result.data['prerequisites'])


def test_profile_changes_invalidate_old_human_review():
    old=context();new=context(profile=profile(required_fields=[selector(fields=['/rationale'])]))
    assert old.input_sha256!=new.input_sha256
    assert not assess(new,review=HumanRequirementReview(review_data(old))).eligible_for_human_approval


def test_hypothetical_approved_profile_fields_are_enforced():
    p=profile(required_fields=[selector(fields=['/timing'],maturities=['approved'])])
    result=assess(context(profile=p))
    assert not result.data['formal_data_valid']
    assert any(d['diagnostic']['location']['pointer']=='/timing' for d in result.data['findings'])


def test_false_human_criteria_are_not_truthy_labels():
    ctx=context();data=review_data(ctx);data['criteria']['single_testable_fact']=False
    assert not assess(ctx,review=HumanRequirementReview(data)).eligible_for_human_approval
    data['criteria']['single_testable_fact']=1
    with pytest.raises(ModelError):HumanRequirementReview(data)


def test_detector_scores_or_unknown_review_fields_are_rejected():
    ctx=context();data=review_data(ctx);data['detector_confidence']=1.0
    with pytest.raises(ModelError):HumanRequirementReview(data)


def test_unauthenticated_compound_is_not_claimed_as_human_confirmation():
    ctx=context();review=HumanRequirementReview(review_data(ctx,compound=True))
    result=assess(ctx,review=review,verifier=verifier(authenticated=False))
    assert not result.eligible_for_human_approval
    assert not any(f['diagnostic']['code']=='SRV162' for f in result.data['findings'])


def test_stale_human_verification_blocks_even_with_matching_review_hashes():
    assert not assess(verifier=verifier(current=False)).eligible_for_human_approval


def test_verifier_result_must_be_typed_not_boolean():
    result=assess(verifier=ReviewVerifier('bad','1',lambda c,r:True))
    assert result.data['human_review_status']=='verification_failed'


def test_verifier_must_bind_exact_context_and_review():
    for wrong in ('context','review'):
        v=ReviewVerifier('bad','1',lambda c,r:ReviewVerification(
            'f'*64 if wrong=='context' else c.input_sha256,
            'f'*64 if wrong=='review' else r.sha256,True,True))
        assert not assess(verifier=v).eligible_for_human_approval


def test_verifier_exception_produces_unavailable_without_exposing_details():
    def broken(c,r):raise RuntimeError('SECRET_TOKEN_123')
    result=assess(verifier=ReviewVerifier('broken','1',broken))
    assert result.data['human_review_status']=='verification_failed'
    assert 'SECRET_TOKEN_123' not in json.dumps(result.data)


def test_stale_review_does_not_call_verifier():
    c=context();check=Mock(side_effect=AssertionError('should not run'))
    old=HumanRequirementReview(review_data(c));changed=context(values(statement='New.'))
    assess(changed,review=old,verifier=ReviewVerifier('test','1',check));check.assert_not_called()


def test_nonhuman_review_does_not_call_verifier():
    c=context();check=Mock(side_effect=AssertionError('should not run'))
    data=review_data(c,reviewer={'actor_type':'ci','actor_id':'job'})
    assess(c,review=HumanRequirementReview(data),verifier=ReviewVerifier('test','1',check));check.assert_not_called()


def test_multiple_bad_sources_are_preserved_as_failures():
    good=context();docs=(*good.documents,ModelDocument('bad1',b'{'),ModelDocument('bad2',b'null'))
    ctx=ApprovalContext(good.requirement_id,docs,profile=good.profile)
    result=assess_requirement_approval(ctx)
    assert {'bad1','bad2'} <= {f['diagnostic']['path'] for f in result.data['findings']}
    assert not result.eligible_for_human_approval


def test_duplicate_artifact_in_distinct_file_is_not_accepted():
    c=context();docs=(*c.documents,ModelDocument('duplicate',c.documents[0].content))
    result=assess_requirement_approval(ApprovalContext(c.requirement_id,docs,profile=c.profile))
    assert not result.data['formal_data_valid']


def test_selected_id_is_not_an_existing_display_name():
    c=context();ctx=ApprovalContext('Sample',c.documents,profile=c.profile)
    assert not assess_requirement_approval(ctx).eligible_for_human_approval


def test_deep_immutable_values_survive_copy_and_parallel_calls():
    c=context();review=HumanRequirementReview(review_data(c));copied=copy.deepcopy(review)
    assert copied.sha256==review.sha256
    with ThreadPoolExecutor(max_workers=3) as pool:
        reports=list(pool.map(lambda _:assess(c,review=review).data,range(12)))
    assert all(r==reports[0] for r in reports)


def test_repeated_failure_does_not_poison_later_success():
    c=context();bad=assess(c,review=None)
    assert not bad.eligible_for_human_approval
    assert assess(c).eligible_for_human_approval


def test_declared_verifier_and_core_do_not_open_or_import_data():
    c=context();review=HumanRequirementReview(review_data(c));v=verifier();ps=prerequisites(c)
    original_import=builtins.__import__
    def trusted_relative_only(name,globals=None,locals=None,fromlist=(),level=0):
        # Existing validators lazily import their own package modules. Do not
        # confuse that trusted implementation detail with imports from data.
        if level and type(globals) is dict and globals.get('__package__','').startswith('specroad.'):
            return original_import(name,globals,locals,fromlist,level)
        raise AssertionError('Unexpected external import')
    with patch.object(builtins,'open',side_effect=AssertionError('Unexpected open')), \
            patch.object(builtins,'__import__',side_effect=trusted_relative_only):
        result=assess_requirement_approval(c,review=review,verifier=v,prerequisites=ps)
    assert result.eligible_for_human_approval


def test_code_like_statement_is_never_executed(tmp_path):
    target=tmp_path/'must-not-exist'
    statement='__import__("pathlib").Path('+repr(str(target))+').write_text("bad")'
    assert assess(context(values(statement=statement))).eligible_for_human_approval
    assert not target.exists()


def test_bad_projection_and_duplicate_field_rows_rejected():
    for fields in ((('/title','/scope/a','/scope/b','/scope/c'),),QUALITY_FIELDS*2):
        with pytest.raises(ModelError):context(quality_records(),quality_fields=fields)


def test_bad_evidence_digest_cannot_claim_passing_prerequisite():
    c=context()
    for digest in (None,'123','G'*64):
        with pytest.raises(ModelError):ApprovalPrerequisite('model_validation',c.input_sha256,'passed',digest)


def test_verifier_flags_are_true_booleans():
    for value in ('true',1,None):
        with pytest.raises(ModelError):ReviewVerification('a'*64,'b'*64,value,True)


def test_both_portable_distribution_forms_expose_approval_contract(tmp_path):
    c=context();source_values=[(d.path,d.content) for d in c.documents]
    module,archive=build_distribution(tmp_path/'built')
    moved=tmp_path/'moved';app=tmp_path/'relocated.pyz'
    shutil.move(str(module),moved);shutil.move(str(archive),app)
    pbytes=artifact_bytes(profile_data(profile_id='core'))
    review=review_data(c)
    for entry in (moved,app):
        code=('import sys;sys.path.insert(0,'+repr(str(entry))+');\n'
              'from specroad.validation import *\n'
              'from specroad.validation.approval_values import PREREQUISITES\n'
              'from specroad.profiles.values import ProfileResource\n'
              'from specroad.profiles.composition import compose_profiles\n'
              'p=compose_profiles([ProfileResource('+repr(pbytes)+')],core_key="core@0.2.0")\n'
              'c=ApprovalContext('+repr(c.requirement_id)+',[ModelDocument(*v) for v in '+repr(source_values)+'],profile=p)\n'
              'r=HumanRequirementReview('+repr(review)+')\n'
              'v=ReviewVerifier("synthetic","1",lambda c,r:ReviewVerification(c.input_sha256,r.sha256,True,True))\n'
              'ps=[ApprovalPrerequisite(n,c.input_sha256,"passed","a"*64) for n in PREREQUISITES]\n'
              'out=assess_requirement_approval(c,review=r,verifier=v,prerequisites=ps)\n'
              'assert out.eligible_for_human_approval and not out.data["approval_granted"]\n')
        child=run_python(['-I','-S','-B','-c',code],tmp_path,capture=True)
        assert child.returncode==0,child.stderr.decode()
