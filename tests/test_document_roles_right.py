"""Full-project role admission, native diagnostics and shared validation binding."""
from copy import deepcopy
import json

import pytest

from specroad.documents import DocumentRoleError, assess_document_roles
from specroad.model.canonical import canonical_json_bytes
from specroad.model.errors import ModelError
from specroad.validation import ModelDocument, validate_model
from support.domain import domain_value
from support.portable import build_distribution
from support.processes import run_core, run_python
from support.read_only import no_write_attempts
from support.records import ref
from support.scopes import descriptor
from support.targets import model, SCOPE
from test_document_roles import document


def full_validation(supplied, **changes):
    options = dict(profile=supplied.profile, document_role_scope='full_project')
    options.update(changes)
    return validate_model(supplied.documents, **options)


def role_stage(report):
    return next(row for row in report.data['stages'] if row['stage'] == 'document_roles')


@pytest.mark.parametrize('role', [None, False, [], {}, '', 'primary'])
@pytest.mark.parametrize('retired', [False, True])
def test_malformed_roles_in_any_document_never_leave_a_successful_selection(role, retired):
    broken = document('1', document_role=role, maturity='retired' if retired else 'draft')
    supplied = model([document(), broken])
    with no_write_attempts(): report = assess_document_roles(supplied)
    assert not report.roles_valid and report.data['active_primary_count'] is None
    assert report.data['primary_document'] is None
    issue, = report.data['diagnostics']
    assert issue['reason'] == 'schema_enum' and issue['pointer'] == '/document_role'
    assert issue['artifact_id'] == broken['id'] and issue['path'].endswith(broken['id'] + '.json')
    with pytest.raises(DocumentRoleError) as error: report.require_primary_document()
    assert error.value.exit_code == 3 and error.value.pointer == issue['pointer']


@pytest.mark.parametrize('field,value,reason', [('purpose', '', 'schema_min_length'),
    ('audience', [], 'schema_any_of'), ('render_policy', 'execute', 'schema_type')])
def test_invalid_local_document_fields_keep_the_native_error_contract(field, value, reason):
    supplied = model([document(), document('1', document_role='supporting', **{field: value})])
    report = assess_document_roles(supplied)
    issue, = report.data['diagnostics']
    assert issue['reason'] == reason and issue['pointer'] == '/' + field
    assert not report.roles_valid and report.data['primary_document'] is None


@pytest.mark.parametrize('scope', [
    descriptor('document', {'document_id': ref('DOC')}),
    descriptor('document', {'document_id': ref('DOC')}, boundary_policy='partial'),
    descriptor('project', boundary_policy='partial'),
    descriptor('project', configuration_id=ref('CFG')),
    descriptor('specification')])
def test_nonfull_or_configured_scope_cannot_be_relabelled_as_a_full_primary_check(scope):
    supplied = model([document()])
    with no_write_attempts(), pytest.raises(DocumentRoleError) as error:
        assess_document_roles(supplied, scope_descriptor=scope)
    assert error.value.reason == 'document_full_project_scope_required'
    assert error.value.pointer == '/scope_descriptor' and error.value.exit_code == 3


def test_explicit_full_scope_preserves_the_original_assessment():
    supplied = model([document()])
    assert assess_document_roles(supplied, scope_descriptor=SCOPE).data == assess_document_roles(supplied).data


def test_caller_scope_and_selection_mutations_cannot_change_an_observation():
    scope = deepcopy(SCOPE); supplied = model([document()])
    report = assess_document_roles(supplied, scope_descriptor=scope); digest = report.sha256
    scope['boundary_policy'] = 'partial'; scope['selector']['document_id'] = ref('DOC', '1')
    report.data['scope_descriptor']['scope_kind'] = 'document'
    assert report.sha256 == digest and report.data['scope_descriptor'] == SCOPE


@pytest.mark.parametrize('value', [None, {}, [], object()], ids=['none', 'mapping', 'sequence', 'object'])
def test_unbound_model_inputs_never_become_a_document_role_observation(value):
    with no_write_attempts(), pytest.raises(ModelError) as error: assess_document_roles(value)
    assert error.value.reason == 'document_target_model_required'


def test_a_new_model_revision_changes_selection_bindings_without_rewriting_the_old_report():
    old = document(); current = document(title='Changed specification', revision=2)
    first = assess_document_roles(model([old])); later = assess_document_roles(model([current]))
    assert first.require_primary_document()['record'] == old
    assert later.require_primary_document()['record'] == current
    for field in ('input_sha256', 'model_root_sha256'):
        assert first.data[field] != later.data[field]
    assert first.require_primary_document()['record_sha256'] != later.require_primary_document()['record_sha256']


def test_invalid_document_data_does_not_invent_a_missing_or_multiple_primary_diagnosis():
    broken = document('1'); broken.pop('purpose')
    report = assess_document_roles(model([document(), broken]))
    assert [d['reason'] for d in report.data['diagnostics']] == ['missing_field']
    assert report.data['active_primary_count'] is None and not report.roles_valid


@pytest.mark.parametrize('records', [[], [domain_value('goal')], [document(document_role='supporting')]])
def test_requested_full_project_validation_rejects_missing_primary_even_without_document_subjects(records):
    supplied = model(records)
    with no_write_attempts(): report = full_validation(supplied)
    observed = role_stage(report)
    assert observed['status'] == 'failed' and not report.passed
    assert [d['reason'] for d in observed['diagnostics']] == ['document_primary_missing']
    assert report.data['document_role_scope'] == 'full_project'
    assert not report.data['project_files_verified'] and not report.data['write_authorized']


def test_global_document_roles_cannot_be_hidden_by_an_unconnected_selected_component():
    goal = domain_value('goal'); supplied = model([goal, document(), document('1')])
    report = full_validation(supplied, selected_ids=[goal['id']]); observed = role_stage(report)
    assert not report.passed and observed['status'] == 'failed'
    assert observed['checked_ids'] == [ref('DOC'), ref('DOC', '1')]
    assert observed['diagnostics'][0]['related_ids'] == [ref('DOC'), ref('DOC', '1')]
    assert observed['diagnostics'][0]['reason'] == 'document_primary_multiple'


def test_a_passing_role_stage_does_not_supply_missing_document_composition_services():
    supplied = model([document(), document('1', maturity='retired')])
    report = full_validation(supplied)
    assert role_stage(report)['status'] == 'passed'
    stage = next(row for row in report.data['stages'] if row['stage'] == 'document_model')
    assert stage['status'] == 'unavailable' and not report.passed and not report.complete
    assert not report.data['approval_granted'] and not report.data['write_authorized']


@pytest.mark.parametrize('scope', [False, True, 'partial', 'legacy', 'project', {}])
def test_shared_validation_does_not_infer_or_alias_the_requested_role_contract(scope):
    with no_write_attempts(), pytest.raises(ModelError) as error:
        validate_model((), document_role_scope=scope)
    assert error.value.reason == 'validation_document_role_scope_invalid'


def test_configuration_selection_cannot_claim_the_full_project_role_contract():
    supplied = model([document()])
    with no_write_attempts(), pytest.raises(ModelError) as error:
        full_validation(supplied, configuration_id=ref('CFG'))
    assert error.value.reason == 'validation_full_project_document_scope_required'


def test_shared_schema_failure_precedes_role_selection_without_hiding_its_original_source():
    supplied = model([document(document_role='other')])
    report = full_validation(supplied)
    assert not report.passed and not any(s['stage'] == 'document_roles' for s in report.data['stages'])
    issue, = report.diagnostics
    assert issue['reason'] == 'schema_enum' and issue['pointer'] == '/document_role'
    assert issue['artifact_id'] == ref('DOC') and issue['path'] == supplied.documents[0].path


def test_duplicate_artifact_identity_is_not_reinterpreted_as_two_primary_documents():
    supplied = model([document()]); source = supplied.documents[0]
    report = validate_model((source, ModelDocument('other.json', source.content)),
        profile=supplied.profile, document_role_scope='full_project')
    assert not report.passed and not any(row['stage'] == 'document_roles' for row in report.data['stages'])
    assert [d['reason'] for d in report.diagnostics] == ['duplicate_artifact_id']


def test_loaded_model_and_requested_full_project_have_distinct_bound_validation_contracts():
    supplied = model([domain_value('goal')])
    loaded = validate_model(supplied.documents, profile=supplied.profile)
    full = full_validation(supplied)
    assert loaded.passed and not full.passed
    assert 'document_role_scope' not in loaded.data
    assert not any(row['stage'] == 'document_roles' for row in loaded.data['stages'])
    assert loaded.data['input_sha256'] != full.data['input_sha256']


@pytest.mark.parametrize('mode', ['core', 'pyz'])
def test_explicit_full_project_role_stage_runs_in_isolated_core_and_pyz(tmp_path, mode):
    supplied = model([document(), document('1')])
    expected = full_validation(supplied).data
    body = '''import json
from specroad.validation import ModelDocument, validate_model
from specroad.profiles import ProfileResource, compose_profiles
'''
    body += 'documents=' + repr([(d.path, d.content) for d in supplied.documents]) + '\n'
    body += 'profile_raw=' + repr(supplied.profile_resources[0].source_bytes) + '\n'
    body += '''profile=ProfileResource(profile_raw)
report=validate_model([ModelDocument(p,b) for p,b in documents],
 profile=compose_profiles([profile],core_key=profile.key),document_role_scope='full_project')
print(json.dumps(report.data,sort_keys=True))
'''
    if mode == 'core': result = run_core(body, tmp_path, capture=True)
    else:
        _, package = build_distribution(tmp_path / 'distribution')
        result = run_python(['-I', '-S', '-B', '-c',
            'import sys;sys.path.insert(0,' + repr(str(package)) + ')\n' + body], tmp_path, capture=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == expected
