"""Native 0.1 planning, original preservation and shared machine contracts."""
import base64
import copy
from dataclasses import FrozenInstanceError
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch
import pytest

from specroad.changes import ChangePlan, ChangeOperation, ChangePlanError, prepare_change_plan
from specroad.changes.authoring import bind_plan_authoring, AuthoringError
from specroad.migration.planning import plan_migration, migration_inputs
from specroad.migration.plan_values import MigrationPlanError
from specroad.migration.registry import builtin_registry
from support.migration_plans import (ACTOR, STAMP, FIELDS, target_inputs, mapped_inputs,
    planned_files, vector_source, unsigned, empty_proposal_plan)
from support.reference01 import (CONTRACT, minimal, full_project, release_project,
    finish_proposal, encoded, digest, put, seal)


def test_literal_independent_requirement_and_relation_vector_matches_exactly():
    files = vector_source(); result = plan_migration(files, inputs=target_inputs(files), **FIELDS)
    assert result.ready
    target = planned_files(files, result.change_plan)
    actual = json.loads(target['spec/requirements/SR-REQ-0001.json'])
    assert actual == json.loads((CONTRACT/'vectors/requirement-after.json').read_bytes())
    assert next(r['sha256'] for r in result.change_plan.data['result_artifacts']
                if r['artifact']['id']=='SR-REQ-0001') == '520e42f0647bae17a37b8bf8c1c9717fa274a890f0164e97f7ecebeb817ffcb3'
    assert actual['relations'][0]['relation_id'] == 'REL-62Z6E501RHRRJZ06XBGZX8KRB9'
    assert actual['extensions'] == {'example.note': {'value': 'e\u0301'}}


def test_full_native_source_family_materializes_all_types_and_protects_legacy():
    files = full_project(); before = dict(files)
    plan = plan_migration(files, inputs=mapped_inputs(files), **FIELDS).change_plan
    target = planned_files(files, plan); types = set()
    for name, raw in files.items():
        if not name.startswith('spec/'): continue
        old, new = json.loads(raw), json.loads(target[name]); types.add(old['artifact_type'])
        immutable = old['artifact_type'] in ('evidence', 'baseline', 'relation_review')
        if immutable:
            assert target[name] == raw and new['schema_version'] == '0.1.0'
        else:
            assert new['schema_version'] == '0.2.0' and new['id'] == old['id']
            assert new['revision'] == old['revision'] + 1
            assert new['created_at'] == old['created_at'] and new['created_by'] == old['created_by']
            assert new['updated_at'] == STAMP and new['updated_by'] == ACTOR
    assert len(types) == 28 and files == before
    assert plan.data['operations'][0]['losses'] == []


def test_all_originals_and_transitive_archives_remain_verifiable_bytes():
    files = full_project(); seal(files, 3); result = plan_migration(files, inputs=mapped_inputs(files), **FIELDS)
    target = planned_files(files, result.change_plan)
    manifest = json.loads(target['mappings/legacy-manifest.json'])
    for entry in manifest['entries']:
        raw = target[entry['path']]
        assert len(raw) == entry['original_size'] and sha256(raw).hexdigest() == entry['original_byte_sha256']
        if entry['original_canonical_sha256'] is not None:
            assert digest(json.loads(raw)) == entry['original_canonical_sha256']
        for row in entry['referenced_payloads']:
            address = 'archive/objects/' + row['sha256'][:2] + '/' + row['sha256']
            raw = target[address]
            assert len(raw) == row['size'] and sha256(raw).hexdigest() == row['sha256']
    assert all(target[p] == raw for p, raw in files.items() if p.startswith('archive/'))
    old_profile = files['profiles/core-reference01.json']; h = sha256(old_profile).hexdigest()
    assert target['archive/objects/' + h[:2] + '/' + h] == old_profile
    assert 'profiles/core-reference01.json' not in target


def test_legacy_hashes_use_original_bytes_and_bind_manifest_in_shared_root():
    files = full_project(); result = plan_migration(files, inputs=mapped_inputs(files), **FIELDS)
    plan = result.change_plan; target = planned_files(files, plan)
    manifest = json.loads(target['mappings/legacy-manifest.json']); root = plan.data['operations'][0]['target_manifest']
    rows = {r['id']: r for r in root['artifacts']}
    old = files['spec/evidence/SR-EVD-0001.json']; evidence = json.loads(old)
    assert rows[evidence['id']] == {'kind': 'artifact', 'id': evidence['id'], 'artifact_type': 'evidence',
        'revision': evidence['revision'], 'sha256': sha256(old).hexdigest(),
        'hash_domain': 'legacy-original-bytes-v1', 'legacy_manifest_sha256': digest(manifest)}
    assert rows['SR-REQ-0001']['sha256'] == digest(json.loads(target['spec/requirements/SR-REQ-0001.json']))
    assert 'hash_domain' not in rows['SR-REQ-0001']
    assert root['scope_sha256'] == digest({k: v for k, v in root.items() if k not in ('scope_sha256','model_manifest_version')})
    assert result.data['expected_target_model_root_sha256'] == digest(root)
    assert plan.data['expected_result']['model_root_sha256'] == digest(root)


def test_deterministic_plan_ignores_dictionary_order_and_has_explicit_bound_metadata():
    files = vector_source(); inputs = target_inputs(files)
    left = plan_migration(files, inputs=inputs, **FIELDS)
    right = plan_migration(dict(reversed(list(files.items()))), inputs=copy.deepcopy(inputs), **FIELDS)
    assert left.canonical_bytes == right.canonical_bytes
    assert left.change_plan.data['actor'] == ACTOR and left.change_plan.data['planned_at'] == STAMP


def test_same_source_and_mappings_keep_original_representations_out_of_semantic_roots_only():
    files = vector_source(); a = plan_migration(files, inputs=target_inputs(files), **FIELDS)
    files['notes.txt'] = b'opaque additional data\r\n'
    b = plan_migration(files, inputs=target_inputs(files), **FIELDS)
    assert a.data['expected_target_model_root_sha256'] == b.data['expected_target_model_root_sha256']
    assert a.change_plan.sha256 != b.change_plan.sha256
    assert planned_files(files,b.change_plan)['notes.txt'] == b'opaque additional data\r\n'


def test_shared_change_plan_roundtrip_and_specialist_route_never_authorize_regular_apply():
    files = vector_source(); result = plan_migration(files, inputs=target_inputs(files), **FIELDS)
    plan = result.change_plan
    assert ChangePlan(plan.canonical_bytes).data == plan.data
    op = ChangeOperation(plan.data['operations'][0])
    assert op.required_workflow == 'schema_migrate' and op.executable is False
    assert plan.execution_ready is False and plan.write_authorized is False
    with pytest.raises(AuthoringError) as caught: bind_plan_authoring(plan)
    assert caught.value.exit_code == 7
    assert result.write_authorized is False and result.data['public_apply_supported'] is True
    assert result.data['backup_verified'] is False and result.data['current_readiness_verified'] is False
    with pytest.raises(TypeError): bool(result)


def test_regular_policy_label_cannot_launder_a_migration_operation():
    files=vector_source(); plan=plan_migration(files, inputs=target_inputs(files), **FIELDS).change_plan
    data=unsigned(plan); data['metadata_policy_version']='change-metadata-v1'
    with pytest.raises(ChangePlanError): prepare_change_plan(data)


def test_migration_policy_cannot_be_mixed_with_generic_operations():
    files=vector_source(); plan=plan_migration(files, inputs=target_inputs(files), **FIELDS).change_plan
    data=unsigned(plan); data['operations'].append({'op':'update','target':'SR-REQ-0001',
        'expected_revision':1,'patch':[{'op':'replace','path':'/statement','value':'Injected'}]})
    with pytest.raises(ChangePlanError): prepare_change_plan(data)


def test_missing_inputs_report_every_missing_mapping_without_dummy_roots_or_writes():
    files=full_project(); before=dict(files)
    result=plan_migration(files, inputs=migration_inputs(), **FIELDS)
    assert {b['reason'] for b in result.data['blockers']} == {
        'target_configuration_required','requirement_mapping_required','proposal_mapping_required'}
    assert not result.ready and result.change_plan is None
    assert result.data['expected_target_model_root_sha256'] is None and files==before


def test_missing_target_core_is_visible_and_a_fabricated_core_is_not_accepted():
    files=minimal(); inputs=target_inputs(files); inputs['target_resources']=[]
    result=plan_migration(files, inputs=inputs, **FIELDS)
    assert result.data['blockers']==[{'reason':'target_core_profile_required','path':'profiles/'}]
    inputs=target_inputs(files); raw=json.loads(base64.b64decode(inputs['target_resources'][0]['bytes_base64']))
    raw['required_fields']=[]; inputs['target_resources'][0]['bytes_base64']=base64.b64encode(encoded(raw)).decode()
    with pytest.raises(MigrationPlanError,match='migration_target_core_not_builtin'):
        plan_migration(files,inputs=inputs,**FIELDS)


def test_source_hash_mismatch_is_a_conflict_instead_of_a_missing_mapping():
    files=vector_source(); inputs=target_inputs(files); inputs['requirement_mappings'][0]['source_sha256']='0'*64
    with pytest.raises(MigrationPlanError) as caught: plan_migration(files,inputs=inputs,**FIELDS)
    assert caught.value.reason=='migration_mapping_source_changed' and caught.value.exit_code==6


def test_open_proposal_requires_an_explicit_current_basis_and_preserves_prior_content():
    files=full_project(); source=json.loads(files['spec/proposals/SR-PROP-0001.json'])
    blocked=plan_migration(files,inputs=target_inputs(files),**FIELDS)
    assert not blocked.ready and blocked.data['expected_proposal_basis_sha256'] is not None
    assert blocked.data['expected_target_model_root_sha256'] is None
    inputs=mapped_inputs(files); result=plan_migration(files,inputs=inputs,**FIELDS)
    target=planned_files(files,result.change_plan); value=json.loads(target['spec/proposals/SR-PROP-0001.json'])
    assert value['base']['model_root_sha256']==blocked.data['expected_proposal_basis_sha256']
    assert value['content_revision']==source['content_revision']+1
    assert value['proposal_status']==value['maturity']=='draft'
    assert value.get('reviews',[])==source.get('reviews',[]) and value['control_history']==source['control_history']
    original=files['spec/proposals/SR-PROP-0001.json']; h=sha256(original).hexdigest()
    assert target['archive/objects/'+h[:2]+'/'+h]==original
    inputs['proposal_mappings'][0]['change_plan']=empty_proposal_plan('0'*64)
    with pytest.raises(MigrationPlanError,match='migration_proposal_target_basis_mismatch'):
        plan_migration(files,inputs=inputs,**FIELDS)


@pytest.mark.parametrize('state',['applied','rejected','stale'])
def test_finished_proposals_stay_original_immutable_records(state):
    files=finish_proposal(full_project(),state); original=files['spec/proposals/SR-PROP-0001.json']
    result=plan_migration(files,inputs=target_inputs(files),**FIELDS)
    assert result.ready and planned_files(files,result.change_plan)['spec/proposals/SR-PROP-0001.json']==original
    assert 'SR-PROP-0001' not in result.change_plan.data['operations'][0]['result_ids']


def test_release_baseline_and_explicit_original_release_selection_are_unchanged():
    files=release_project(); result=plan_migration(files,inputs=mapped_inputs(files),**FIELDS)
    target=planned_files(files,result.change_plan)
    for name, raw in files.items():
        if name.startswith('spec/baselines/'):
            assert target[name]==raw
    assert result.data['approval_granted'] is False


def test_values_are_detached_and_input_objects_are_never_rewritten():
    files=vector_source(); inputs=target_inputs(files); before=copy.deepcopy(inputs)
    result=plan_migration(files,inputs=inputs,**FIELDS); original=result.canonical_bytes
    data=result.data; data['change_plan']['operations'].clear(); inputs['requirement_mappings'].clear()
    assert result.canonical_bytes==original
    assert before['requirement_mappings'] and result.data['change_plan']['operations']
    with pytest.raises(FrozenInstanceError): result._encoded=b'{}'


def test_native_planning_does_not_create_project_files_or_run_source_code(tmp_path):
    files=full_project(); inputs=mapped_inputs(files)
    for name,raw in files.items():
        p=tmp_path/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
    before={p.relative_to(tmp_path).as_posix():p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    with patch.object(Path,'write_bytes',side_effect=AssertionError('unexpected write')), \
         patch.object(Path,'write_text',side_effect=AssertionError('unexpected write')), \
         patch.object(subprocess,'run',side_effect=AssertionError('unexpected child')):
        assert plan_migration(files,inputs=inputs,**FIELDS).ready
    after={p.relative_to(tmp_path).as_posix():p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    assert after==before and not (tmp_path/'.specroad').exists()


def test_common_plan_schema_is_retrievable_and_validates_the_real_specialist_plan():
    from specroad.model.schema_catalog import SchemaCatalog
    files=vector_source(); plan=plan_migration(files,inputs=target_inputs(files),**FIELDS).change_plan
    SchemaCatalog().validate('urn:specroad:schema:1.2.0:change-plan',plan.data)
    assert len(plan.operations)==1


def test_source_plan_uses_only_the_explicit_builtin_reference_path():
    files=vector_source(); result=plan_migration(files,inputs=target_inputs(files),**FIELDS)
    assert result.ready
    graph = builtin_registry()
    assert len(graph.steps) == 1 and graph.steps[0].step_id == 'reference01-to-current.v1'
    assert graph.steps[0].source.contract_sha256 == result.data['source_contract']['contract_sha256']


def test_core_and_pyz_materialize_identical_plans_without_optional_packages(tmp_path):
    from support.portable import build_distribution
    module, pyz = build_distribution(tmp_path/'distribution')
    files=full_project(); inputs=mapped_inputs(files)
    payload={'files':{p:base64.b64encode(raw).decode() for p,raw in files.items()},
             'inputs':inputs,'fields':FIELDS}
    source=tmp_path/'inputs.json';source.write_bytes(encoded(payload))
    program=('import sys,json,base64;sys.path.insert(0,sys.argv[1]);'
        'from specroad.migration.planning import plan_migration;'
        'v=json.load(open(sys.argv[2]));'
        'r=plan_migration({p:base64.b64decode(b) for p,b in v["files"].items()},inputs=v["inputs"],**v["fields"]);'
        'sys.stdout.buffer.write(r.canonical_bytes)')
    expected=plan_migration(files,inputs=inputs,**FIELDS).canonical_bytes
    for runtime in (module,pyz):
        child=subprocess.run([sys.executable,'-I','-S','-B','-c',program,str(runtime),str(source)],
                             capture_output=True,check=True)
        assert child.stdout==expected
