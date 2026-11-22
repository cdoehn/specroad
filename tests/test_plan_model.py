"""21.a.W: typed projections, explicit carrier ownership and native migration."""
import json
import pytest
from specroad.model.plan_projection import PlanProjection
from specroad.model.plan_schemas import plan_schema
from specroad.model.paths import artifact_path, classify_path, PathClass
from specroad.model.configuration import ProjectConfiguration
from specroad.model.errors import ModelError
from specroad.model.schema_catalog import SchemaCatalog
from support.plan_models import PLAN, ENTRY, plan, entry, migration
from support.model import configuration_value, put
from support.read_only import inventory, no_write_attempts


@pytest.mark.parametrize('kind', ['implementation_plan', 'plan_entry'])
def test_plan_projections_use_current_native_catalog_and_one_carrier(kind):
    value = plan() if kind == 'implementation_plan' else entry()
    original = json.loads(json.dumps(value))
    projection = PlanProjection(value)
    assert projection.data == original and value == original
    assert projection.path == 'spec/implementation-plans/' + PLAN + '.md'
    schema = plan_schema(value['artifact_type'])
    SchemaCatalog().validate(schema['$id'], value)
    assert SchemaCatalog().get(schema['$id']).schema == schema
    assert projection.validation_scope == 'plan_projection_fields_only'
    projection.data['title'] = 'attempt to mutate'
    assert projection.data == original


@pytest.mark.parametrize('field,value', [('schema_version','0.2.0'), ('language',None),
    ('revision',0), ('implemented','yes'), ('entry_kind','group'), ('work_kind','review'),
    ('display_id','broken\nlabel'), ('display_id','[x]'), ('display_id','e\u0301'),
    ('parent_id','XX-IPLAN-'+'0'*26), ('id','SR-PENTRY-0001'), ('extra',True)])
def test_entry_field_errors_are_rejected_without_inventing_metadata(field,value):
    data = entry(); data[field] = value
    with pytest.raises(ModelError): PlanProjection(data)


def test_no_optional_proof_or_id_is_synthesized():
    value=entry(); projection=PlanProjection(value)
    assert 'required' not in projection.data and 'commit_refs' not in projection.data
    for key in ('id','plan_id','parent_id','parent_relation_id','created_by','language'):
        changed=dict(value);del changed[key]
        with pytest.raises(ModelError): PlanProjection(changed)
    with pytest.raises(ModelError, match='plan_carrier_required'):
        artifact_path('plan_entry',ENTRY,'SR')
    assert artifact_path('plan_entry',ENTRY,'SR',plan_id=PLAN).endswith(PLAN+'.md')


def test_projects_require_explicit_capability_and_reject_shadow_files(tmp_path):
    path='spec/implementation-plans/'+PLAN+'.md'
    old=ProjectConfiguration(configuration_value())
    current=ProjectConfiguration(configuration_value(schema_version='0.3.0'))
    with pytest.raises(ModelError,match='plan_project_migration_required'): classify_path(path,old)
    assert classify_path(path,current) is PathClass.PLAN
    for name in (path+'.json','spec/plan-entries/'+ENTRY+'.json'):
        with pytest.raises(ModelError): classify_path(name,current)
    from specroad.storage.project import ProjectSource
    from specroad.storage.resource_discovery import current_json_paths
    put(tmp_path,'specroad.json',json.dumps(current.data).encode())
    put(tmp_path,path,b'# Plan -- explicit future Markdown parser input\n')
    before=inventory(tmp_path)
    with no_write_attempts(), pytest.raises(ModelError,match='plan_markdown_reader_required'):
        current_json_paths(ProjectSource(tmp_path))
    assert inventory(tmp_path)==before


def test_additive_migration_runs_native_public_writer_backup_and_verification(tmp_path):
    from specroad.cli.application import dispatch_result
    from specroad.cli.results import thaw
    from specroad.migration._backup_source import _observe
    from support.migration_cli import invoke, success, verified
    from specroad.model.canonical import canonical_json_bytes
    from specroad.bundles.migration_source import verify_source_backup
    root=tmp_path/'project'
    initial=dispatch_result(['init',str(root)])
    assert initial.exit_code==0,initial.as_dict()
    source,_,check=_observe(root);check()
    original_journal='.specroad/recovery/init-bootstrap/journal.json'
    assert original_journal in source
    assert not (root/'spec/implementation-plans').exists()
    fields,target=migration(source)
    inputs=tmp_path/'inputs';inputs.mkdir();outputs=tmp_path/'outputs';outputs.mkdir();backups=tmp_path/'backups';backups.mkdir()
    (inputs/'mapping.json').write_bytes(canonical_json_bytes(fields['inputs']))
    options={'--project':str(root),'--to':'0.3.0','--inputs-root':str(inputs),'--inputs':'mapping.json',
        '--actor-type':'tool','--actor-id':'synthetic-plan-migration','--planned-at':fields['planned_at'],
        '--plan-id':fields['change_plan_id'],'--request-id':fields['request_id'],
        '--output-root':str(outputs),'--output':'migration.json'}
    before=inventory(root)
    result=success(invoke('migrate.plan',options));report=result['planning']
    assert report['ready'] and not report['approval_granted'] and inventory(root)==before
    op=report['change_plan']['operations'][0]
    assert [c['path'] for c in op['changes']]==['specroad.json']
    assert op['protected_paths']==sorted(set(source)-{'specroad.json'})
    apply={'--project':str(root),'--to':'0.3.0','--plan-root':str(outputs),'--plan':'migration.json',
        '--expected-plan-sha256':report['change_plan']['change_plan_sha256'],
        '--expected-inputs-sha256':report['inputs_sha256'],'--expected-report-sha256':result['plan_file']['sha256'],
        '--backup-root':str(backups),'--backup':'source.zip','--transaction-id':'synthetic-plan-capability'}
    result=success(invoke('migrate.apply',apply))
    assert result['execution']['write_state']=='committed'
    assert (root/'specroad.json').read_bytes()==target
    assert all((root/p).read_bytes()==raw for p,raw in source.items() if p!='specroad.json')
    verified_backup=verify_source_backup((backups/'source.zip').read_bytes(),
        expected_sha256=result['backup']['file']['sha256'],
        expected_source_files_sha256=result['backup']['source_files_sha256'])
    assert verified_backup.files==source
    assert verified_backup.files[original_journal]==source[original_journal]
    before=inventory(root)
    with no_write_attempts(): checked=verified(apply,result)
    assert checked['verification']['verified'] and inventory(root)==before
    assert not checked['verification']['current_readiness_verified']
    assert not checked['verification']['approval_granted']
    assert not list((root/'spec/implementation-plans').glob('*.json'))


def test_additive_migration_does_not_accept_other_edits_or_implicit_target(tmp_path):
    from support.inspection import inspection_project
    from specroad.migration.planning import plan_migration
    from specroad.migration.plan_inputs import migration_inputs
    from specroad.migration.plan_values import b64
    source=dict(inspection_project(tmp_path).source_files)
    fields,raw=migration(source)
    partial=plan_migration(source,**{**fields,'inputs':migration_inputs()})
    assert not partial.ready and partial.data['blockers']==[{'reason':'target_configuration_required','path':'specroad.json'}]
    altered=json.loads(raw);altered['project_name']='changed by migration'
    fields['inputs']['target_configuration']=b64(json.dumps(altered).encode())
    with pytest.raises(ModelError,match='additive_migration_configuration_changed'):
        plan_migration(source,**fields)


@pytest.mark.parametrize('target', ['children', 'contributors'])
def test_plan_catalog_rejects_duplicate_structural_references(target):
    value=plan()
    if target=='children':
        value['children']=[ENTRY,ENTRY]
    else:
        ref={'plan_id':PLAN,'entry_id':ENTRY}
        value['coverage_claims']=[{'claim_id':'0'*26,'requirement_id':'SR-REQ-0001',
            'requirement_revision':1,'requirement_context_sha256':'a'*64,
            'completeness':'full','contributors':[ref,dict(ref)]}]
    with pytest.raises(ModelError,match='schema_unique_items'):
        SchemaCatalog().validate(plan_schema('implementation_plan')['$id'],value)


def test_native_unique_items_preserves_json_boolean_number_and_object_equality():
    from specroad.model._schema import validate_builtin
    schema={'type':'array','uniqueItems':True}
    validate_builtin([True,1,{'a':1,'b':2},[1,True]],schema)
    for values in ([1,1.0],[{'a':1,'b':2},{'b':2,'a':1}],[[1,True],[1.0,True]]):
        with pytest.raises(ModelError,match='schema_unique_items'): validate_builtin(values,schema)
    validate_builtin([1,1],{'type':'array','uniqueItems':False})
    with pytest.raises(ValueError): validate_builtin([],{'type':'array','uniqueItems':1})
