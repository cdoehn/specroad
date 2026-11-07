"""Complete virtual targets, real native gates and independently verified observations.

Review fixtures are synthetic test data; they record no actual human acceptance.
"""
from base64 import b64decode
from hashlib import sha256
import json
from pathlib import Path

import pytest

from specroad.merge import verify_merge_target, SourceSnapshot, SourceRequest, load_merge_sources
from specroad.model.canonical import canonical_json_bytes as jcs
from specroad.model.errors import ModelError
from specroad.recovery import RestoreServices
from specroad.recovery._validation import validate_project
from specroad.security import ProjectBoundary, SafetyViolation
from support.domain import domain_value
from support.records import record_value, ref
from support.model import put
from support.merge_target import small_seed as seed, replace, inputs, target
from support.profile_composition import profile, lint
from support.read_only import inventory
from support.relations import aid, edge
from test_merge_sources import read_only_sources


def reread(values, result, *, raw=None, services=None):
    sources, history, plan, metadata = values
    raw = result.canonical_bytes if raw is None else raw
    return verify_merge_target(raw, metadata.canonical_bytes, plan.canonical_bytes, sources,
        history=history, expected_target_sha256=sha256(raw).hexdigest(),
        expected_metadata_sha256=metadata.sha256, expected_plan_sha256=plan.sha256, services=services)


def test_separately_valid_branches_form_a_forbidden_combined_hierarchy_cycle(tmp_path):
    a, b = aid('need', 1), aid('need', 2)
    files = seed(tmp_path/'seed', values=[record_value('document'),
        domain_value('need', id=a), domain_value('need', id=b)])
    ours = replace(files, 'need', identifier=a, relations=[edge(kind='refines',target=b,number=1)])
    theirs = replace(files, 'need', identifier=b, relations=[edge(kind='refines',target=a,number=2)])
    validate_project(ours); validate_project(theirs)
    values = inputs(tmp_path/'inputs', [files, ours, theirs])
    assert values[-1].data['metadata_complete']
    before = inventory(tmp_path)
    with read_only_sources(): result = target(values)
    assert not result.target_validated
    assert any(c['reason'] == 'relation_hierarchy_cycle' for c in result.data['conflicts'])
    assert result.data['expected_target_model_root_sha256'] == values[-1].data['expected_target_model_root_sha256']
    assert inventory(tmp_path) == before
    with pytest.raises(ModelError): result.files


def test_independent_field_changes_can_violate_a_combined_native_profile_policy(tmp_path):
    rule = lint('target:combined', severity='error'); rule['artifact_types'] = ['goal']
    rule['program']['expression'] = {'op':'or', 'args':[
        {'op':'eq','args':[{'op':'field','context':'artifact','pointer':'/title'}, {'op':'literal','value':'old title'}]},
        {'op':'eq','args':[{'op':'field','context':'artifact','pointer':'/owner'}, {'op':'literal','value':'old owner'}]}]}
    files = seed(tmp_path/'seed', profiles=(profile('target-combined',lint_rules=[rule]),))
    files = replace(files,'goal',title='old title',owner='old owner')
    ours = replace(files,'goal',title='new title',revision=3)
    theirs = replace(files,'goal',owner='new owner',revision=7)
    validate_project(ours); validate_project(theirs)
    values = inputs(tmp_path/'inputs',[files,ours,theirs])
    assert values[-1].data['metadata_complete']
    with read_only_sources(): result = target(values)
    assert not result.target_validated
    assert any(c['reason'] == 'profile_lint_predicate_false' for c in result.data['conflicts'])
    assert result.data['validation']['source_report']['source_count'] == 2
    with pytest.raises(ModelError): result.files


@pytest.mark.parametrize('fault',[None,'no-provider','missing','changed'])
def test_code_reference_requires_actual_current_host_bytes_without_code_execution(tmp_path,fault):
    raw = b'raise RuntimeError("must never execute")\n'
    reference = record_value('code_ref',reference_kind='file',path='source.py',file_sha256=sha256(raw).hexdigest())
    files = seed(tmp_path/'seed',values=[record_value('document'),reference])
    values = inputs(tmp_path/'inputs',[files]*3)
    code = tmp_path/'external'; code.mkdir()
    if fault != 'missing': put(code,'source.py',b'changed' if fault == 'changed' else raw)
    native = None if fault == 'no-provider' else RestoreServices(code_source=lambda model,record:ProjectBoundary(code))
    before = inventory(tmp_path)
    with read_only_sources(): result = target(values,services=native)
    assert result.target_validated is (fault is None)
    if fault is not None:
        assert result.data['conflicts']
        with pytest.raises(ModelError): result.files
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('fault',[None,'no-provider','rejected','nonhuman','foreign','criteria',
                                 'unauthenticated','stale','prerequisite'])
def test_approved_requirement_uses_native_review_inputs_for_actual_target(tmp_path,fault):
    from test_restore_qualification import approved_project, services
    options = approved_project(tmp_path)
    files = SourceSnapshot(SourceRequest(options['project_root'])).files
    values = inputs(tmp_path/'inputs',[files]*3)
    calls = []
    native = None if fault == 'no-provider' else services(fault=fault,calls=calls)
    before = inventory(tmp_path)
    with read_only_sources(): result = target(values,services=native)
    assert result.target_validated is (fault is None)
    assert not result.approval_granted
    if fault is None:
        assert calls
        count = len(calls)
        with read_only_sources(): reread(values,result,services=native)
        assert len(calls) > count
    else:
        assert result.data['conflicts']
        with pytest.raises(ModelError): result.files
    assert inventory(tmp_path) == before


def test_saved_positive_report_does_not_preserve_a_now_stale_review(tmp_path):
    from test_restore_qualification import approved_project, services
    options = approved_project(tmp_path)
    values = inputs(tmp_path/'inputs',[SourceSnapshot(SourceRequest(options['project_root'])).files]*3)
    result = target(values,services=services())
    assert result.target_validated
    with read_only_sources(), pytest.raises(ModelError,match='merge_target_binding_mismatch'):
        reread(values,result,services=services(fault='stale'))


@pytest.mark.parametrize('field,value',[
    ('target_format_version','future'),('ready',True),('write_authorized',True),('approval_granted',True),
    ('target_validated',False),('checks_complete',False),('validation',{}),('conflicts',[{'reason':'invented'}]),
    ('pending_gates',[]),('expected_target_model_root_sha256','0'*64),('target_files_sha256','0'*64),
    ('source_bindings_sha256','0'*64),('metadata_candidate_sha256','0'*64),('input_plan_sha256','0'*64),
    ('unexpected',None)])
def test_saved_observation_is_fully_recomputed_despite_rehashed_outer_bytes(tmp_path,field,value):
    files = seed(tmp_path/'seed'); values = inputs(tmp_path/'inputs',[files]*3)
    result = target(values); data = result.data; data[field] = value
    with read_only_sources(), pytest.raises(ModelError,match='merge_target_binding_mismatch'):
        reread(values,result,raw=jcs(data))


def test_negative_observation_cannot_be_relabelled_as_valid_and_genuine_negative_roundtrips(tmp_path):
    rule = lint('target:negative',value=False,severity='error'); rule['artifact_types'] = ['goal']
    files = seed(tmp_path/'seed',profiles=(profile('target-negative',lint_rules=[rule]),))
    values = inputs(tmp_path/'inputs',[files]*3); result = target(values)
    assert not result.target_validated
    with read_only_sources(): assert reread(values,result).canonical_bytes == result.canonical_bytes
    data = result.data; data.update(target_validated=True,checks_complete=True,conflicts=[])
    with read_only_sources(), pytest.raises(ModelError,match='merge_target_binding_mismatch'):
        reread(values,result,raw=jcs(data))


@pytest.mark.parametrize('kind',['mapping','boolean','callable'])
def test_stored_success_shapes_cannot_substitute_native_services(tmp_path,kind):
    files = seed(tmp_path/'seed'); values = inputs(tmp_path/'inputs',[files]*3)
    service = {'mapping':{'passed':True},'boolean':True,'callable':lambda:True}[kind]
    result = target(values,services=service)
    assert not result.target_validated
    assert result.data['conflicts'][0]['reason'] == 'restore_native_services_required'


@pytest.mark.parametrize('role',['base','ours','theirs'])
@pytest.mark.parametrize('outcome',['valid','negative','io-error'])
def test_real_source_change_during_native_checks_invalidates_every_outcome(tmp_path,role,outcome):
    raw = b'actual external source'
    files = seed(tmp_path/'seed',values=[record_value('document'),
        record_value('source',content_sha256=sha256(raw).hexdigest())])
    values = inputs(tmp_path/'inputs',[files]*3)
    source = getattr(values[0],role)
    path = Path(source.source_root)/next(p for p in files if p.startswith('spec/sources/'))
    def observe(model,record):
        # A genuine adversarial source mutation, not a replaced verification gate.
        path.write_bytes(path.read_bytes()+b'\n')
        if outcome == 'io-error': raise OSError('synthetic provider I/O failure')
        return b'changed' if outcome == 'negative' else raw
    with pytest.raises((ModelError,SafetyViolation)):
        target(values,services=RestoreServices(source_content=observe))


def test_external_io_failure_is_not_a_success_report(tmp_path):
    raw = b'original'
    files = seed(tmp_path/'seed',values=[record_value('document'),
        record_value('source',content_sha256=sha256(raw).hexdigest())])
    values = inputs(tmp_path/'inputs',[files]*3)
    def unavailable(model,record): raise OSError('synthetic provider unavailable')
    before = inventory(tmp_path)
    with read_only_sources(), pytest.raises(OSError):
        target(values,services=RestoreServices(source_content=unavailable))
    assert inventory(tmp_path) == before


def test_genuine_native_baseline_originals_remain_exact_and_are_rechecked(tmp_path):
    from specroad.bundles._payload_model import owned_payload_model
    from specroad.changes.baselines import prepare_baseline_operation
    from specroad.model.paths import artifact_path
    from support.merge_resolution import ACTOR, WHEN
    files = seed(tmp_path/'seed')
    operation = prepare_baseline_operation(owned_payload_model(files,source_label='synthetic-target-history'),
        baseline_id=ref('BASE'),name='Synthetic target history',actor=ACTOR,planned_at=WHEN)
    files[artifact_path('baseline',operation['record']['id'],'SR')] = jcs(operation['record'])
    for item in operation['objects']: files[item['path']] = b64decode(item['bytes_base64'])
    values = inputs(tmp_path/'inputs',[files]*3)
    before = inventory(tmp_path)
    with read_only_sources():
        result = target(values)
        again = reread(values,result)
    assert result.target_validated and again.files == files
    assert result.files == files and inventory(tmp_path) == before
    corrupted = dict(files)
    path = next(p for p in files if p.startswith('archive/'))
    corrupted[path] += b'\n'
    with pytest.raises((ModelError,SafetyViolation)):
        inputs(tmp_path/'corrupted',[corrupted]*3)


@pytest.mark.parametrize('kind',['local','bundle','baseline','git'])
def test_full_validation_accepts_complete_native_source_kinds_without_materializing_project(tmp_path,kind):
    from support.restore import restore_case
    from support.git_objects import GitFixture
    from support.merge_relations import history_for
    from support.merge_resolution import PLAN_ID
    from specroad.merge import build_merge_conflicts, prepare_merge_metadata
    options, files, source_raw = restore_case(tmp_path,'baseline' if kind == 'baseline' else 'project_bundle')
    if kind == 'baseline':
        raw = json.loads(source_raw)
        request = SourceRequest(options['source_root'],'baseline',raw['id'])
        semantic_row = next(row for row in raw['manifest'] if row['role'] == 'semantic_configuration')
        archived_semantic = (options['source_root']/semantic_row['object_path']).read_bytes()
        assert sha256(archived_semantic).hexdigest() == raw['configuration_hash']
    elif kind == 'bundle':
        request = SourceRequest(options['source_root']/options['source_path'],'bundle')
    elif kind == 'git':
        git = GitFixture(tmp_path/'git'); commit = git.commit(files)
        request = SourceRequest(git.root,'git',commit)
    else: request = SourceRequest(options['project_root'])
    before = inventory(tmp_path)
    with read_only_sources():
        sources = load_merge_sources(request,request,request); history = history_for(sources)
        plan = build_merge_conflicts(sources,plan_id=PLAN_ID,history=history)
        metadata = prepare_merge_metadata(plan.canonical_bytes,sources,history=history,expected_plan_sha256=plan.sha256)
        result = target((sources,history,plan,metadata))
    assert result.target_validated and result.files == sources.ours.files
    if kind == 'baseline':
        from specroad.model.configuration import ProjectConfiguration
        from specroad.model.semantic_configuration import semantic_configuration
        # Baselines preserve semantic configuration, not the working tree's
        # operational defaults. Check original archive bytes and every other
        # file independently; do not invent a byte-identical specroad.json.
        assert set(result.files) == set(files)
        assert {p:b for p,b in result.files.items() if p != 'specroad.json'} == {
            p:b for p,b in files.items() if p != 'specroad.json'}
        configuration = ProjectConfiguration(json.loads(result.files['specroad.json']))
        assert jcs(semantic_configuration(configuration)) == archived_semantic
        assert result.data['expected_target_model_root_sha256'] == raw['model_root_sha256']
    else:
        assert result.files == files
    assert result.data['expected_target_model_root_sha256'] == sources.ours.binding['model_root_sha256']
    assert inventory(tmp_path) == before


def test_distinct_valid_document_role_changes_cannot_leave_two_primaries(tmp_path):
    a, b, c = [aid('document',n) for n in (1,2,3)]
    files = seed(tmp_path/'seed',values=[record_value('document',id=a),
        record_value('document',id=b,document_role='supporting'),
        record_value('document',id=c,document_role='supporting')])
    common = replace(files,'document',identifier=a,document_role='supporting')
    ours = replace(common,'document',identifier=b,document_role='primary_specification')
    theirs = replace(common,'document',identifier=c,document_role='primary_specification')
    validate_project(ours); validate_project(theirs)
    values = inputs(tmp_path/'inputs',[files,ours,theirs])
    assert values[-1].data['metadata_complete']
    before = inventory(tmp_path)
    with read_only_sources(): result = target(values)
    assert not result.target_validated
    assert any(c['reason'] == 'document_primary_multiple' for c in result.data['conflicts'])
    assert inventory(tmp_path) == before


def test_combined_reference_must_stay_inside_each_configured_dependency_scope(tmp_path):
    from test_configuration_evaluation import configuration, condition
    a,b = aid('requirement',1),aid('requirement',2)
    files = seed(tmp_path/'seed',values=[record_value('document'),configuration(),
        domain_value('requirement',id=a),domain_value('requirement',id=b)])
    ours = replace(files,'requirement',identifier=a,relations=[edge('depends_on',b)])
    theirs = replace(files,'requirement',identifier=b,applicability=condition('windows'))
    validate_project(ours); validate_project(theirs)
    values = inputs(tmp_path/'inputs',[files,ours,theirs])
    assert values[-1].data['metadata_complete']
    with read_only_sources(): result = target(values)
    assert not result.target_validated
    assert any(c['reason'] == 'configuration_dependency_excluded' for c in result.data['conflicts'])
    with pytest.raises(ModelError): result.files
