"""Native dirty sources, receipt closure and source-safe export refusals."""
from dataclasses import replace
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
from zipfile import ZipFile

import pytest

from specroad.bundles import prepare_project_bundle
from specroad.transport.runtime import _check_api, TransportUnavailable
from support.transport_outbound import ROOT, FIXTURE, child, register, request, run_request, tree
from test_transport_outbound import distribution
from test_project_bundle import project
from test_bundle_receipts import completed, receipts


def _export_setup(tmp_path, distribution):
    root=tmp_path/'repo'; project(root); register(tmp_path,root)
    return root, request(tmp_path,root,distribution[1])


@pytest.mark.parametrize('history', (False, True))
def test_dirty_native_snapshot_preserves_binary_empty_deleted_and_historical_receipts(tmp_path,distribution,history):
    root=tmp_path/'repo'
    if history: completed(root)
    else: project(root)
    (root/'renamed.bin').write_bytes(b'base');(root/'deleted.bin').write_bytes(b'deleted')
    register(tmp_path,root)
    (root/'renamed.bin').rename(root/'new-name.bin');(root/'deleted.bin').unlink()
    (root/'empty.bin').write_bytes(b'');(root/'binary.bin').write_bytes(b'\0\xff\r\n')
    # Dirty normative representation is taken from effective bytes, not HEAD.
    native=prepare_project_bundle(root)
    name=next(n for n in native.files if n.endswith('.json') and n.startswith('spec/'))
    (root/name).write_text(json.dumps(json.loads(native.files[name]),indent=3)+'\n')
    native=prepare_project_bundle(root)
    value=request(tmp_path,root,distribution[1]);before=tree(root)
    result=run_request(tmp_path,value)
    assert result['code']==0,result
    assert result['outcome']['result']['transport']['dirty'] is True
    assert tree(root)==before
    with ZipFile(tmp_path/'output/handoff.zip') as outer:
        assert outer.read('project/project.zip')==native.source_bytes
        if history:
            with ZipFile(BytesIO(outer.read('project/project.zip'))) as inner:
                assert {n:inner.read(n) for n in receipts(root)}==receipts(root)
    source=Path(result['outcome']['result']['transport']['reference_published'])
    parsed=child(tmp_path, '''
import json
from pathlib import Path
sys.path.insert(0, '''+repr(str(FIXTURE/'patchharbor-1.7.0.pyz'))+''')
from patchharbor import api
p=Path('''+repr(str(source))+''')
s=api.read_result_snapshot(p, expected_sha256='''+repr(sha256(source.read_bytes()).hexdigest())+''')
print(json.dumps({n:f.content.hex() for n,f in s.effective.files.items() if n.endswith('.bin')}))
''')
    assert parsed['new-name.bin']==b'base'.hex() and 'renamed.bin' not in parsed and 'deleted.bin' not in parsed
    assert parsed['binary.bin']=='00ff0d0a' and parsed['empty.bin']==''


@pytest.mark.parametrize('kind', ('ignored_artifact','ignored_receipts','empty_receipts','unverified_receipts','active','partial'))
def test_incomplete_or_unverified_project_is_never_promoted(tmp_path,distribution,kind):
    root=tmp_path/'repo'
    if kind=='ignored_receipts': completed(root)
    else: project(root)
    if kind=='ignored_artifact':(root/'.gitignore').write_text('attachments/\n')
    if kind=='ignored_receipts':(root/'.gitignore').write_text('.specroad/\n')
    if kind=='empty_receipts':
        (root/'.specroad/requests').mkdir(parents=True)
        (root/'.specroad/transactions/receipts').mkdir(parents=True)
    if kind=='unverified_receipts':
        path=root/'.specroad/requests/item.json';path.parent.mkdir(parents=True);path.write_text('{}')
    if kind=='active':
        path=root/'.specroad/transactions/active/journal.json';path.parent.mkdir(parents=True);path.write_text('{}')
    if kind=='partial':
        from specroad.bundles import prepare_partial_bundle
        from support.scopes import descriptor
        from specroad.authoring._inspection_snapshot import InspectionSnapshot
        model=InspectionSnapshot(root,None,include_archive_objects=True).model
        document=next(a for a in model.artifacts if a['artifact_type']=='document')
        from specroad.graph.scope_descriptors import ScopeDescriptor
        partial=prepare_partial_bundle(root,ScopeDescriptor(descriptor('document',{'document_id':document['id']},boundary_policy='partial')))
        (root/'bundle-manifest.json').write_bytes(partial.manifest_bytes)
    register(tmp_path,root);value=request(tmp_path,root,distribution[1]);before=tree(root)
    result=run_request(tmp_path,value)
    if kind=='empty_receipts':
        assert result['code']==0,result
    else:
        assert result['code'] in (3,5,6,7),result
        assert not (tmp_path/'output/handoff.zip').exists()
    assert tree(root)==before


@pytest.mark.parametrize('attribute', ('filter=evil','working-tree-encoding=UTF-16','ident','text eol=crlf'))
@pytest.mark.parametrize('when', ('before','after_prepare'))
def test_git_conversions_never_execute_helpers_or_rebind(tmp_path,distribution,attribute,when):
    root,value=_export_setup(tmp_path,distribution)
    child(tmp_path, '''
import subprocess,json
subprocess.run(['git','-C','''+repr(str(root))+''','config','filter.evil.clean','touch '''+str(tmp_path/'helper-ran')+''''],check=True)
print('{}')
''')
    attrs='* '+attribute+'\n'
    injection=''
    if when=='before':(root/'.gitattributes').write_text(attrs)
    else:
        injection='''
from pathlib import Path
from specroad.transport.outbound import OutboundExport
original=OutboundExport.capture
def changed(self):
    Path('''+repr(str(root/'.gitattributes'))+''').write_text('''+repr(attrs)+''')
    return original(self)
OutboundExport.capture=changed
'''
    result=run_request(tmp_path,value,before=injection)
    assert result['code'] in (6,7), result
    assert not (tmp_path/'helper-ran').exists()
    assert not list((tmp_path/'output').glob('*.zip'))


@pytest.mark.parametrize('change', ('source','output_boundary','capability_bool','old_runtime','occupied','foreign_import','core_hash'))
def test_refusals_keep_source_and_never_publish_handoff(tmp_path,distribution,change):
    root,value=_export_setup(tmp_path,distribution);before=''
    if change=='old_runtime':
        from support.transport_runtime import envelope
        old=tmp_path/'old';old.mkdir();ref,digest=envelope(old)
        value['options'].update({'--runtime-reference':str(ref),'--runtime-reference-sha256':digest})
    elif change=='occupied':(tmp_path/'output/handoff.zip').write_bytes(b'not replaceable')
    elif change=='core_hash':value['options']['--specroad-pyz-sha256']='f'*64
    elif change=='foreign_import':before="import types\nsys.modules['patchharbor']=types.ModuleType('patchharbor')\n"
    else:
        mutation={'source':"(self.project.root/'changed.bin').write_bytes(b'changed')",
            'output_boundary':"self.plan=replace(self.plan,maintenance_enabled=True)",
            'capability_bool':"old=self.api.integration_capabilities; self.api.integration_capabilities=lambda:replace(old(),safe_reference_contract_version=True)"}[change]
        before='''
from dataclasses import replace
from specroad.transport.outbound import OutboundExport
original=OutboundExport.capture
def altered(self):
    '''+mutation+'''
    return original(self)
OutboundExport.capture=altered
'''
    original=tree(root);result=run_request(tmp_path,value,before=before)
    expected={'source':6,'output_boundary':7,'capability_bool':2,'old_runtime':7,
              'occupied':6,'foreign_import':7,'core_hash':6}
    assert result['code']==expected[change],result
    if change!='source':assert tree(root)==original
    path=tmp_path/'output/handoff.zip'
    assert path.read_bytes()==b'not replaceable' if change=='occupied' else not path.exists()


@pytest.mark.parametrize('code,expected', [('configuration',2),('stale',6),('unsupported_conversion',7),
    ('unsafe_path',7),('resource_limit',7),('unsupported_host',5),('repository',5),('io',5),
    ('interrupted',5),('cleanup',5)])
def test_safe_semantic_errors_retain_native_diagnostics(tmp_path,distribution,code,expected):
    root,value=_export_setup(tmp_path,distribution)
    before='''
from pathlib import Path
from specroad.transport.outbound import OutboundExport
original=OutboundExport.capture
def faulty(self):
    def fail(*args,**kwargs):
        raise self.api.SafeExportError(self.api.SafeExportErrorCode('''+repr(code)+'''), 'injected',
            emergency_diagnostics_path=Path('''+repr(str(tmp_path/'output/diagnostic.json'))+'''))
    self.api.bundle=fail
    return original(self)
OutboundExport.capture=faulty
'''
    result=run_request(tmp_path,value,before=before)
    assert result['code']==expected,result
    facts=result['outcome']['summary']['transport_failure']['patchharbor']
    assert facts['code']==code and facts['emergency_diagnostics_path'].endswith('/diagnostic.json')
    assert facts['published_path'] is None and type(facts['emergency_diagnostics_failed']) is bool
    assert not (tmp_path/'output/handoff.zip').exists()


@pytest.mark.parametrize('fault', ('late_cleanup','outer_io'))
def test_late_failure_preserves_actual_reference_without_false_success(tmp_path,distribution,fault):
    root,value=_export_setup(tmp_path,distribution)
    before='''
from specroad.transport.outbound import OutboundExport
original=OutboundExport.capture
def late(self):
    bundle=self.api.bundle
    def fail(*args,**kwargs):
        result=bundle(*args,**kwargs)
        raise self.api.SafeExportError(self.api.SafeExportErrorCode.CLEANUP,'injected',published_path=result.path)
    self.api.bundle=fail
    return original(self)
OutboundExport.capture=late
''' if fault=='late_cleanup' else '''
import specroad.transport.outbound as outbound
def fail(*args,**kwargs):raise OSError('injected')
outbound._publish=fail
'''
    original=tree(root);result=run_request(tmp_path,value,before=before)
    assert result['code']==5,result
    assert tree(root)==original
    references=list((tmp_path/'output').glob('*.zip'))
    assert len(references)==1 and references[0].name!='handoff.zip'
    summary=result['outcome']['summary']
    path=(summary['transport_failure']['patchharbor']['published_path'] if fault=='late_cleanup'
          else summary['transport']['reference_published'])
    assert Path(path)==references[0]


def test_frozen_reference_produces_identical_canonical_handoff(tmp_path,distribution):
    root,value=_export_setup(tmp_path,distribution)
    options=value['options']
    result=child(tmp_path,'''import json
from specroad.work.transport import _export
options='''+repr(options)+'''
a=_export(options);a.prepare();reference=a.capture();one,verify=a.assemble(reference);verify()
b=_export(options);b.prepare(expected=a.expected_source());two,recheck=b.assemble(reference);recheck()
print(json.dumps({'equal':one.source_bytes==two.source_bytes,'hash_equal':one.sha256==two.sha256,
                  'manifest':one.manifest,'references':len(list(a.output.root.glob('*.zip')))}))''')
    assert result['equal'] and result['hash_equal'] and result['references']==1
    assert set(result['manifest'])=={'format_version','direction','runtime_profile','project_id','project_path',
                                    'scope_descriptor','model_root_sha256','reference','runtimes','entries','package_id'}
    assert str(tmp_path) not in json.dumps(result['manifest'])


def test_staged_and_unstaged_layers_are_both_native_effective_inputs(tmp_path,distribution):
    root,value=_export_setup(tmp_path,distribution)
    native=prepare_project_bundle(root)
    name=next(n for n in native.files if n.startswith('spec/') and n.endswith('.json'))
    (root/name).write_text(json.dumps(json.loads(native.files[name]),indent=2)+'\n')
    child(tmp_path,"import subprocess,json\nsubprocess.run(['git','-C',"+repr(str(root))+",'add','--',"+repr(name)+"],check=True)\nprint('{}')")
    (root/name).write_text(json.dumps(json.loads(native.files[name]),indent=5)+'\n')
    expected=prepare_project_bundle(root).source_bytes;before=tree(root)
    result=run_request(tmp_path,value)
    assert result['code']==0,result
    with ZipFile(tmp_path/'output/handoff.zip') as z:assert z.read('project/project.zip')==expected
    assert tree(root)==before


@pytest.mark.parametrize('kind',('symlink','hardlink','inside_project','unregistered','metrics'))
def test_runtime_paths_and_explicit_invocation_boundaries(tmp_path,distribution,kind):
    root=tmp_path/'repo';project(root)
    if kind!='unregistered':register(tmp_path,root)
    value=request(tmp_path,root,distribution[1])
    if kind in ('symlink','hardlink'):
        import os
        candidate=tmp_path/'linked.pyz'
        if kind=='symlink':candidate.symlink_to(distribution[1])
        else:
            real=tmp_path/'core.pyz';real.write_bytes(distribution[1].read_bytes());os.link(real,candidate)
        value['options']['--specroad-pyz']=str(candidate)
    if kind=='inside_project':value['options']['--output-root']=str(root)
    if kind=='metrics':value['options']['--metrics']=True
    before=tree(root)
    result=run_request(tmp_path,value)
    assert result['code']==(0 if kind=='metrics' else 5 if kind=='unregistered' else 7),result
    assert tree(root)==before
    if kind=='unregistered':
        assert not (tmp_path/'config').exists() and not (tmp_path/'state').exists()
