"""Original raw command inputs with valid independent project files."""
from hashlib import sha256
from specroad.model.canonical import canonical_json_bytes as jcs, canonical_json_sha256 as digest
from specroad.model.paths import artifact_path
from support.model import put
from support.records import record_value, ref
from support.native_plan_authoring import setup, values, ACTOR
from test_authoring_inputs import fields
from test_document_structure import contains, section


def store(root, value):
    put(root,artifact_path(value['artifact_type'],value['id'],'SR'),jcs(value))


def specialist_example(root, name):
    if name in ('evidence.record','evidence.import'):
        from test_evidence_recording import project, measurement
        from test_evidence_import_transaction import import_project, SOURCE
        model = project(root) if name=='evidence.record' else import_project(root)
        store(root,record_value('document'))
        if name=='evidence.record':
            return {'verification_id':ref('VER'),'record':measurement(model,actor=ACTOR).data}
        # Raw import files have an explicit existing attachment descriptor; no
        # unreferenced arbitrary file becomes a normative input by pathname.
        # The fixture starts with a real native Evidence record; goals
        # do not admit attachments. This independent synthetic run is
        # not one of the two observations that the import must publish.
        original=measurement(model,actor=ACTOR,token='3').data
        original['run_context']['run_id']='synthetic-meter:source-binding'
        store(root,original)
        return {'source_path':SOURCE,'source_sha256':sha256((root/SOURCE).read_bytes()).hexdigest(),
                'policy':'abort_import','title':'Synthetic imported observations'}
    setup(root,with_plan=False)
    if name=='view.create':
        from support.targets import SCOPE
        return {'fields':{**fields('view'), 'scope_descriptor': dict(SCOPE)}}
    if name=='baseline.create':return {'name':'Explicit working snapshot'}
    doc=next(v for v in values(root).values() if v['artifact_type']=='document')
    if name=='document.create':return {'fields':{**fields('document'),'document_role':'supporting'}}
    if name=='section.add':return {'fields':fields('section'),'parent_id':doc['id'],'position':0}
    sec=section();doc['relations']=[contains(sec['id'],'5',0)];store(root,doc);store(root,sec)
    if name=='block.add':return {'fields':fields('content_block'),'parent_id':sec['id'],'position':0}
    if name=='section.move':return {'target':sec['id'],'parent_id':doc['id'],'position':9,
        'expected_relation_sha256':digest(doc['relations'][0]),'reason':'Explicit reorder'}
    if name=='section.remove':return {'target':sec['id'],'expected_revision':sec['revision'],'reason':'Explicit retirement'}
    if name=='relation.review':return {'source':doc['id'],'relation_id':doc['relations'][0]['relation_id'],
        'decision':'confirmed','reason':'Synthetic review input','expected_revision':doc['revision']}
    block=record_value('content_block');sec['relations']=[contains(block['id'],'6',0)];store(root,sec);store(root,block)
    if name=='block.update':return {'target':block['id'],'expected_revision':block['revision'],
        'patch':[{'op':'replace','path':'/title','value':'New explicit block title'}]}
    if name=='block.remove':return {'target':block['id'],'expected_revision':block['revision'],'reason':'Explicit retirement'}
    raise AssertionError(name)
