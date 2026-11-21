"""One actual authoring/transport/bundle/analyzer path; no display snapshots."""
from hashlib import sha256
import json


from specroad.authoring._inspection_snapshot import InspectionSnapshot
from specroad.analyzers.file_adapter import default_inputs
from specroad.analyzers.subjects import request_from_project
from specroad.analyzers.packages import ReportPackage
from specroad.bundles import BundleContainer, prepare_project_bundle, verify_bundle
from specroad.cli.application import dispatch_result
from specroad.cli.results import thaw
from specroad.documents.requirement_presentation import resolve_requirement_presentation
from specroad.exchange import prepare_export, decode_ndjson
from specroad.graph.scope_descriptors import ScopeDescriptor
from specroad.model.canonical import canonical_json_bytes as jcs
from specroad.model.paths import artifact_path
from support.analyzer_work_process import invoke, runtime_factory as runtime_factory
from support.read_only import inventory
from support.scopes import descriptor
from support.targets import model
from test_requirement_exchange import resources

from support.analyzer_roundtrip import authored as authored, meaning_hashes, install_owned_files

__all__ = ('runtime_factory','authored')


def test_complete_multilingual_roundtrip_uses_the_same_native_values(tmp_path,authored,runtime_factory):
    root,values=authored;before=inventory(root);expected=meaning_hashes(values)
    native=InspectionSnapshot(root,None).model
    for value in values:
        presentation=resolve_requirement_presentation(native,value['id']).data
        assert presentation['statement']==value['statement']
        assert presentation['normative_force']==value['normative_force']
        assert presentation['content_language']['language']==value['language']
        assert presentation['requirement']['record_sha256']==expected[value['id']]['record']
        assert not presentation['translation_performed'] and not presentation['approval_granted']
    mapping,files,options=resources('ndjson')
    exported=prepare_export(model(values,resource_files=files),ScopeDescriptor(descriptor('project')),**options)
    decoded=[v['object'] for v in decode_ndjson(exported.output_bytes).objects]
    assert meaning_hashes(decoded)==expected and {v['id'] for v in decoded}=={v['id'] for v in values}
    original=prepare_project_bundle(root,exclude_operational_receipts=True)
    transferred=dict(original.files)
    for value in decoded:
        transferred[artifact_path('requirement',value['id'],'SR')]=jcs(value)
    recipient=tmp_path/'recipient';install_owned_files(recipient,transferred)
    bundle=prepare_project_bundle(recipient,exclude_operational_receipts=True)
    verified=verify_bundle(bundle.source_bytes,expected_sha256=bundle.sha256)
    assert verified['model_root_verified'] and not verified['approval_granted']
    assert bundle.manifest['bundle_model_root_sha256']==original.manifest['bundle_model_root_sha256']
    container=BundleContainer(bundle.source_bytes)
    clone=tmp_path/'clone';install_owned_files(clone,container.files)
    clone_before=inventory(clone)
    request=request_from_project(clone,**default_inputs({}),analysis_id='roundtrip:original')
    assert len(request.data['subjects'])==len(values)
    by_id={v['id']:v for v in values}
    for subject in request.data['subjects']:
        value=by_id[subject['artifact_id']]
        assert subject['value']==value['statement'] and subject['declared_language']==value['language']
        assert subject['normative_force']==value['normative_force']
        assert subject['artifact_sha256']==expected[value['id']]['record']
        assert subject['value_sha256']==expected[value['id']]['statement']
    request_file=tmp_path/'request.json';request_file.write_bytes(request.canonical_bytes)
    runtime=runtime_factory()
    value=invoke(runtime,'single',request_file,tmp_path/'unused',tmp_path/'trace',tmp_path)['package']
    package=ReportPackage(jcs(value),request=request)
    assert all(r.data['run_status']=='complete' for r in package.reports)
    reports=tmp_path/'reports';reports.mkdir()
    raw=json.dumps(value,ensure_ascii=False,indent=3).encode('utf-8')+b'\n'
    source=reports/'original.json';source.write_bytes(raw)
    imported=dispatch_result(['analyzer','import',str(source),'--project',str(clone),
        '--output','received.json','--output-root',str(reports)],cwd=tmp_path)
    assert imported.exit_code==0,imported.as_dict()
    assert (reports/'received.json').read_bytes()==raw
    assert thaw(imported.result)['sources'][0]['sha256']==sha256(raw).hexdigest()
    shown=dispatch_result(['analyzer','show',str(reports/'received.json')],cwd=tmp_path)
    assert shown.exit_code==0,shown.as_dict()
    assert inventory(root)==before and inventory(clone)==clone_before
    assert meaning_hashes([json.loads((clone/artifact_path('requirement',v['id'],'SR')).read_bytes()) for v in values])==expected
