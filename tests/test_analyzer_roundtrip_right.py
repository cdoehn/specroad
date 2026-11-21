"""Real lossy-format imports and stale external reports never rewrite meaning."""
from hashlib import sha256
import json

import pytest

from specroad.analyzers.evaluation import evaluate_reports
from specroad.analyzers.file_adapter import default_inputs
from specroad.analyzers.subjects import request_from_project
from specroad.analyzers.packages import ReportPackage
from specroad.authoring._inspection_snapshot import InspectionSnapshot
from specroad.bundles import prepare_project_bundle
from specroad.documents.requirement_presentation import resolve_requirement_presentation
from specroad.exchange import (prepare_export, prepare_import_plan, select_csv_profile,
    decode_reqifz, decode_reqif_structure)
from specroad.graph.scope_descriptors import ScopeDescriptor
from specroad.mappings import CSVProfile
from specroad.model.canonical import canonical_json_bytes as jcs
from specroad.model.paths import artifact_path
from support.analyzer_work_process import invoke, runtime_factory as runtime_factory
from support.read_only import make_project, inventory, no_write_attempts
from support.reqif_objects import LIMITS
from support.scopes import descriptor
from support.targets import model
from support.analyzer_roundtrip import authored as authored, install_owned_files, CONTENT
from test_requirement_exchange import resources
from test_requirement_exchange_right import candidate, import_arguments

__all__ = ('runtime_factory','authored')


@pytest.mark.parametrize('fmt',['csv','reqif','reqifz'])
def test_real_decoded_projection_reaches_import_plan_then_analyzer_without_source_fallback(tmp_path,authored,runtime_factory,fmt):
    _,values=authored
    original=values[('csv','reqif','reqifz').index(fmt)]
    mapping,files,options=resources(fmt)
    exported=prepare_export(model([original],resource_files=files),ScopeDescriptor(descriptor('project')),**options)
    raw=exported.output_bytes
    if fmt=='csv':
        profile=CSVProfile(files[1].content)
        fields=select_csv_profile([mapping,profile],key=profile.key,expected_sha256=profile.sha256).decode(raw).records[0]['fields']
    else:
        if fmt=='reqifz':
            container=decode_reqifz(raw,expected_sha256=sha256(raw).hexdigest(),document_paths=('exchange.reqif',),
                limits=LIMITS,max_uncompressed_bytes=16*1024*1024)
            raw=dict(container.files)['exchange.reqif']
        document=decode_reqif_structure(raw,limits=LIMITS)
        fields=document.project_object(document.objects[0].identifier)['fields']
    native,record=candidate(mapping,fmt,value=original,fields=fields)
    record['new_artifact'].update(language='en-US',normative_force='may',statement='This unrelated default is not transported content.')
    args=import_arguments(mapping,fmt);args['input_bytes']=exported.output_bytes
    report=prepare_import_plan(native,[record],**args)
    assert report.plan_valid and not report.write_authorized,report.data['diagnostics']
    target=report.plan.data['result_artifacts'][0]['artifact']
    assert {key:target[key] for key in CONTENT}=={key:original[key] for key in CONTENT}
    assert target['external_identities'][0]['last_source_payload_sha256']==sha256(exported.output_bytes).hexdigest()
    losses=exported.manifest['losses']
    assert any(loss['pointer']=='/priority' for loss in losses)
    assert not any(loss['pointer'] in ('/statement','/language','/normative_force') for loss in losses)
    root=tmp_path/'import-candidate';root.mkdir();make_project(root,target)
    request=request_from_project(root,**default_inputs({}),analysis_id='roundtrip-import:'+fmt)
    assert len(request.data['subjects'])==1
    subject=request.data['subjects'][0]
    assert subject['value']==original['statement'] and subject['normative_force']==original['normative_force']
    assert subject['declared_language']==original['language']
    assert subject['value_sha256']==sha256(jcs(original['statement'])).hexdigest()
    path=tmp_path/'request.json';path.write_bytes(request.canonical_bytes)
    before=inventory(root)
    package=ReportPackage(jcs(invoke(runtime_factory(),'single',path,tmp_path/'unused',tmp_path/'trace',tmp_path)['package']),request=request)
    assert package.reports[0].data['run_status']=='complete'
    assert inventory(root)==before


@pytest.fixture(scope='module')
def analyzed(authored,runtime_factory,tmp_path_factory):
    root,values=authored;temp=tmp_path_factory.mktemp('roundtrip-report')
    bundle=prepare_project_bundle(root,exclude_operational_receipts=True)
    request=request_from_project(root,**default_inputs({}),analysis_id='roundtrip-stale')
    path=temp/'request.json';path.write_bytes(request.canonical_bytes)
    package=ReportPackage(jcs(invoke(runtime_factory(),'single',path,temp/'unused',temp/'trace',temp)['package']),request=request)
    return bundle,values,request,package


@pytest.mark.parametrize('change',['tail','language','force'])
def test_external_report_and_presentation_never_change_original_meaning_or_claim_region(tmp_path,analyzed,change):
    bundle,values,request,package=analyzed
    root=tmp_path/'project';install_owned_files(root,bundle.files)
    original_bytes=package.original_bytes
    with no_write_attempts():
        current=evaluate_reports([original_bytes],project=root,current_inputs=default_inputs({}))
    assert current.data['all_reports_current']
    for report in package.reports:
        for subject in report.data['subjects']:
            original=next(s for s in request.data['subjects'] if s['subject_key']==subject['subject_key'])
            assert subject['declared_language']==original['declared_language']
            assert subject['normative_force']==original['normative_force']
            comparison=subject['payload']['specroad.language_detection']['comparison']
            if comparison is not None:
                assert comparison['region_checked'] is comparison['script_checked'] is False
    value=json.loads(jcs(values[0]))
    if change=='tail':value['statement']+=' Only this complete tail is now different.'
    elif change=='language':value['language']='en-IN'
    else:value['normative_force']='may'
    path=root/artifact_path('requirement',value['id'],'SR');path.write_bytes(jcs(value))
    before=inventory(root)
    with no_write_attempts():
        stale=evaluate_reports([original_bytes],project=root,current_inputs=default_inputs({}))
        display=resolve_requirement_presentation(InspectionSnapshot(root,None).model,value['id']).data
    assert not stale.data['all_reports_current']
    assert all(r['currentness']=='stale' for r in stale.data['reports'])
    assert display['statement']==value['statement'] and display['normative_force']==value['normative_force']
    assert display['content_language']['language']==value['language']
    assert not any(display[k] for k in ('text_semantics_evaluated','translation_performed','approval_granted'))
    assert package.original_bytes==original_bytes and inventory(root)==before
