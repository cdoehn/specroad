"""21.a.R: original formats, real distributions and identity collision guards."""
from copy import deepcopy
import json
import os
import subprocess
import sys
from unittest.mock import patch
import pytest
from specroad.model.plan_inventory import PlanProjectionInventory
from specroad.model.plan_projection import PlanProjection
from specroad.model.errors import ModelError
from specroad.model.identities import IdentityInventory, allocate_artifact_identity
from specroad.model.canonical import canonical_json_bytes
from support.plan_models import PLAN, ENTRY, plan, entry, migration
from support.portable import build_distribution
from support.read_only import inventory, no_write_attempts


@pytest.mark.parametrize('fault',['identity','display','relation','claim'])
def test_projected_collisions_are_rejected_by_shared_identity_rules(fault):
    a,b=plan(),entry()
    values=[a,b]
    if fault=='identity': values.append(deepcopy(b))
    elif fault=='display': b['display_id']=a['display_id']
    elif fault=='relation': b['prerequisites']=[{'relation_id':b['parent_relation_id'],'plan_id':PLAN,'entry_id':ENTRY}]
    else:
        claim={'claim_id':'0'*26,'requirement_id':'SR-REQ-0001','requirement_revision':1,
               'requirement_context_sha256':'a'*64,'completeness':'full','contributors':[{'plan_id':PLAN,'entry_id':ENTRY}]}
        a['coverage_claims']=[claim,deepcopy(claim)]
    with pytest.raises(ModelError): PlanProjectionInventory(values,id_prefix='SR')


def test_project_inventory_detaches_values_and_keeps_display_ids_local():
    a,b=plan(),entry();other=plan();other['id']='SR-IPLAN-'+'0'*25+'3';other['children']=[]
    data=[a,b,other];before=deepcopy(data)
    observed=PlanProjectionInventory(data,id_prefix='SR')
    data[0]['title']='changed'
    assert [p.data for p in observed.projections]==before
    changed=entry();changed['requirement_bindings']=[{'relation_id':'REL-'+'0'*25+'4',
        'requirement_id':'XX-REQ-0001','requirement_revision':1,'requirement_context_sha256':'a'*64}]
    with pytest.raises(ModelError): PlanProjection(changed)


def test_plan_entry_allocation_respects_all_historical_reservations():
    token=lambda n:n.to_bytes(16,'big')
    ids=['SR-PENTRY-'+'0'*25+str(n) for n in range(4)]
    original=IdentityInventory('SR',[ids[0]],[ids[1]],[ids[2]])
    with patch('specroad.model.identities.secrets.token_bytes',side_effect=[token(n) for n in range(4)]) as entropy:
        allocation=allocate_artifact_identity('plan_entry',original)
    assert entropy.call_count==4 and allocation.identity.id==ids[3]
    assert original.reserved_ids=={ids[2]} and ids[3] in allocation.inventory.reserved_ids


@pytest.mark.parametrize('result',['passed','failed','incomplete','skipped'])
def test_additive_transition_preserves_nested_baselines_evidence_and_legacy_contract(result):
    from support.legacy_manifest import migrated
    from support.migration_history import evidence_source,BASELINE,EVIDENCE,PROJECT_ID
    from specroad.migration.history import verify_migrated_history
    from specroad.migration.planning import plan_migration
    from specroad.migration.transaction_target import materialized_files
    from specroad.bundles.migration_source import prepare_source_backup,verify_source_backup
    _,source,_=migrated(evidence_source(result=result,nested=True))
    original=dict(source);history=verify_migrated_history(source,project_id=PROJECT_ID).data
    fields,configuration=migration(source)
    with no_write_attempts():
        report=plan_migration(source,**fields)
        target=materialized_files(report.change_plan,source)
        after=verify_migrated_history(target,project_id=PROJECT_ID).data
    backup=prepare_source_backup(source)
    checked_backup=verify_source_backup(backup.source_bytes, expected_sha256=backup.sha256,
        expected_source_files_sha256=backup.manifest['source_files_sha256'])
    assert checked_backup.files==source
    assert source==original and report.ready
    assert target=={**source,'specroad.json':configuration}
    assert target[BASELINE]==source[BASELINE] and target[EVIDENCE]==source[EVIDENCE]
    assert target['mappings/legacy-manifest.json']==source['mappings/legacy-manifest.json']
    assert after['historical']==history['historical']
    assert not after['current_context_verified'] and not after['approval_granted']


def test_no_plan_project_remains_readable_exportable_and_snapshot_bound(tmp_path):
    from specroad.cli.application import dispatch_result
    from specroad.bundles import prepare_project_bundle, verify_bundle
    from specroad.snapshots.sources import SourceSnapshot, SourceRequest
    from support.model import put
    root=tmp_path/'project'
    result=dispatch_result(['init',str(root)]);assert result.exit_code==0,result.as_dict()
    value=json.loads((root/'specroad.json').read_bytes());value['schema_version']='0.3.0'
    put(root,'specroad.json',canonical_json_bytes(value))
    before=inventory(root)
    with no_write_attempts():
        bundle=prepare_project_bundle(root)
        checked=verify_bundle(bundle.source_bytes)
        snapshot=SourceSnapshot(SourceRequest(root,'local'))
        config=dispatch_result(['config','show','--project',str(root),'--format=json'])
    assert config.exit_code==0 and inventory(root)==before
    assert checked['manifest']['schema_version']=='0.3.0'
    assert snapshot.schema_version=='0.3.0' and not any(p.endswith('.md') for p in bundle.files)
    assert all(json.loads(b)['schema_version']=='0.2.0' for p,b in bundle.files.items() if p.startswith('spec/'))


def test_both_distributions_publish_identical_plan_and_configuration_schemas(tmp_path):
    output=tmp_path/'dist';module,archive=build_distribution(output)
    environment=dict(os.environ);environment.pop('PYTHONPATH',None)
    results=[]
    for executable in ([sys.executable,'-m','specroad'],[sys.executable,str(output/'specroad.pyz')]):
        result=subprocess.run([*executable,'schema','list','--format=json'],cwd=module,env=environment,
            capture_output=True,check=True)
        rows=json.loads(result.stdout)['result']['schemas'];results.append(rows)
        ids={r['schema_id'] for r in rows}
        assert 'urn:specroad:schema:0.2.0:project-configuration' in ids
        assert 'urn:specroad:schema:0.3.0:project-configuration' in ids
        for kind in ('implementation_plan','plan_entry'):
            identifier='urn:specroad:schema:0.3.0:artifact-plan:'+kind
            assert identifier in ids
            shown=subprocess.run([*executable,'schema','show',identifier,'--format=json'],cwd=module,env=environment,
                capture_output=True,check=True)
            data=json.loads(shown.stdout)['result']
            assert data['schema']['properties']['schema_version']=={'const':'0.3.0'}
            assert data['metadata']['validation_scope']=='plan_projection_fields_only'
    assert results[0]==results[1]



def test_configuration_selection_is_passive_and_cli_origin_is_preserved(tmp_path):
    from specroad.cli.application import dispatch_result
    from support.model import configuration_file
    configuration_file(tmp_path,profiles=['unknown@1.0.0'])
    before=inventory(tmp_path)
    with no_write_attempts():
        result=dispatch_result(['config','show','--project',str(tmp_path),
            '--profile','selected@2.0.0','--format=json'])
    assert result.exit_code==0,result.as_dict()
    value=result.as_dict()['result']
    assert value['effective_configuration']['profiles']==['core@0.2.0','selected@2.0.0']
    assert [r['source'] for r in value['origins']['/profiles']]==['default','project','cli']
    assert not value['profile_composition_verified'] and inventory(tmp_path)==before
