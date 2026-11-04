"""Original-byte admission at the current validator boundary, not a success stub."""
import json
import pytest
from tests.support.migration_transaction import setup
from tests.support.migration_plans import vector_source,planned_files
from tests.support.reference01 import seal,encoded
from specroad.migration.legacy_manifest import validate_legacy_manifest
from specroad.migration.transaction_target import validate_transaction_target
from specroad.validation import ModelDocument,validate_model
from specroad.model.errors import ModelError


def inputs(tmp_path, *, lint_value=None):
    source=vector_source();baseline=seal(source)
    options = {}
    if lint_value is not None:
        from tests.support.migration_transaction import execution_inputs
        from tests.support.profiles import profile_data
        from tests.support.profile_composition import lint
        from specroad.migration.plan_values import b64,unb64
        given=execution_inputs(source);config=json.loads(unb64(given['target_configuration']))
        config['profiles'].append('sample@0.2.0');given['target_configuration']=b64(encoded(config))
        given['target_resources'].append({'path':'profiles/sample.json','bytes_base64':b64(encoded(
            profile_data(lint_rules=[lint(severity='error',value=lint_value)])))})
        given['target_resources'].sort(key=lambda row:row['path']);options['inputs']=given
    _,source,plan,_=setup(tmp_path,files=source,**options)
    target=planned_files(source,plan)
    legacy=validate_legacy_manifest(target,project_id='synthetic-reference-project')
    documents=tuple(ModelDocument(p,b) for p,b in sorted(target.items()) if p.startswith('spec/') and p.endswith('.json'))
    return source,plan,target,legacy,documents,baseline


def test_original_baseline_is_source_qualified_and_never_current_approval(tmp_path):
    source,plan,target,legacy,documents,baseline=inputs(tmp_path,lint_value=True)
    report=validate_transaction_target(plan,source,target)
    assert report.complete and report.passed
    assert report.data['legacy_manifest_sha256']==legacy.sha256
    assert baseline['id'] in report.data['legacy_original_ids']
    assert not report.data['legacy_current_evidence']
    assert not report.data['approval_granted'] and not report.data['write_authorized']
    assert next(s for s in report.data['stages'] if s['stage']=='profile_lint')['status']=='passed'
    from specroad.validation._legacy_inputs import qualified_legacy_records
    from specroad.graph.relations import SourceRelations
    from specroad.srx.graph import LoadedGraph
    from specroad.srx.errors import SrxError
    qualified=qualified_legacy_records(legacy,documents)
    records=tuple(qualified[d.path] if d.path in qualified else SourceRelations(d.content,path=d.path) for d in documents)
    graph=LoadedGraph(records,rule_id='sample:lint',legacy=legacy)
    assert graph.artifact(baseline['id'],rule_id='sample:lint')['schema_version']=='0.1.0'
    with pytest.raises(SrxError):LoadedGraph(records,rule_id='sample:lint')
    with pytest.raises(SrxError):LoadedGraph(records,rule_id='sample:lint',legacy=legacy.data)
    refused=tmp_path/'refused';refused.mkdir()
    old,rejected,new,_,_,_=inputs(refused,lint_value=False)
    with pytest.raises(ModelError) as seen:validate_transaction_target(rejected,old,new)
    assert seen.value.reason=='migration_target_validation_failed'
    for stage in report.data['stages']:
        if stage['stage']=='baseline_integrity':assert baseline['id'] not in stage['checked_ids']


@pytest.mark.parametrize('kind',['edited_original','projection','missing_original'])
def test_legacy_identity_alone_never_admits_modified_or_missing_bytes(tmp_path,kind):
    source,plan,target,legacy,documents,baseline=inputs(tmp_path)
    path='spec/baselines/'+baseline['id']+'.json';original=legacy.artifact(path,target[path])
    replacements={d.path:d.content for d in documents}
    if kind=='edited_original':
        value=json.loads(replacements[path]);value['title']='Changed unreviewed baseline';replacements[path]=encoded(value)
    elif kind=='projection':replacements[path]=encoded(original.navigation)
    else:del replacements[path]
    with pytest.raises(ModelError):
        validate_model(tuple(ModelDocument(p,b) for p,b in replacements.items()),legacy=legacy)


@pytest.mark.parametrize('scope',[{'selected_ids':['SR-DOC-0001']},{'configuration_id':'SR-CFG-0001'},
                                  {'currentness':object()},{'partial':object()}])
def test_qualified_legacy_does_not_widen_selected_or_partial_admission(tmp_path,scope):
    _,_,_,legacy,documents,_=inputs(tmp_path)
    with pytest.raises(ModelError) as seen:validate_model(documents,legacy=legacy,**scope)
    assert seen.value.reason=='validation_legacy_full_scope_required'


def test_saved_manifest_dictionary_cannot_register_source_schema_bypass(tmp_path):
    _,_,_,legacy,documents,_=inputs(tmp_path)
    with pytest.raises(ModelError) as seen:validate_model(documents,legacy=legacy.data)
    assert seen.value.reason=='validation_native_legacy_manifest_required'
