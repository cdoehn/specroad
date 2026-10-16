"""Stored document fields and primary selection, without rendering or write claims."""
from dataclasses import FrozenInstanceError
from hashlib import sha256
from itertools import permutations
import json
import shutil

import pytest

from specroad.documents import DocumentRoleAssessment, DocumentRoleError, assess_document_roles
from specroad.model.canonical import canonical_json_bytes, canonical_json_sha256
from specroad.model.errors import ModelError
from support.domain import domain_value
from support.inspection import inspection_project
from support.portable import build_distribution
from support.processes import run_core, run_python
from support.read_only import inventory, no_write_attempts
from support.records import record_value, ref
from support.targets import model, SCOPE


def document(token='0', **changes):
    return record_value('document', id=ref('DOC', token), **changes)


def test_full_supplied_project_selects_the_exact_primary_and_binds_actual_sources():
    primary = document('2', title='Primary', render_policy={'formats': ['markdown']})
    supporting = document('0', document_role='supporting')
    supplied = model([supporting, domain_value('goal'), primary])
    with no_write_attempts(): report = assess_document_roles(supplied)
    data = report.data; selected = report.require_primary_document()
    assert report.roles_valid and data['document_fields_valid'] and data['active_primary_count'] == 1
    assert selected['record'] == primary and selected['revision'] == primary['revision']
    assert selected['artifact_id'] == primary['id']
    assert selected['record_sha256'] == canonical_json_sha256(primary)
    assert data['model_root_sha256'] == supplied.manifest(supplied.artifacts, SCOPE).sha256
    assert data['scope_descriptor'] == SCOPE and data['project_id'] == 'sample'
    assert [row['artifact_id'] for row in data['documents']] == [supporting['id'], primary['id']]
    for row in data['documents']:
        assert row['source_sha256'] == sha256(supplied.source_files[row['path']]).hexdigest()
    assert data['diagnostics'] == [] and report.sha256 == canonical_json_sha256(data)
    assert not any(data[k] for k in ('full_validation_passed', 'composition_validated',
        'rendering_performed', 'project_files_verified', 'write_authorized', 'approval_granted'))


@pytest.mark.parametrize('order', list(permutations(range(3))))
def test_primary_selection_is_independent_of_input_order(order):
    records = [document('0', document_role='supporting'), document('1'),
               document('2', maturity='retired')]
    expected = assess_document_roles(model(records))
    actual = assess_document_roles(model([records[n] for n in order]))
    assert actual.data == expected.data and actual.sha256 == expected.sha256
    assert actual.require_primary_document()['artifact_id'] == records[1]['id']


@pytest.mark.parametrize('maturity', ['draft', 'proposed', 'in_review', 'approved', 'rejected', 'superseded'])
def test_every_nonretired_primary_is_counted_without_claiming_lifecycle_approval(maturity):
    value = document(maturity=maturity)
    report = assess_document_roles(model([value, document('1', maturity='retired')]))
    assert report.roles_valid and report.require_primary_document()['record'] == value
    assert not report.data['approval_granted']


@pytest.mark.parametrize('records,reason', [([], 'document_primary_missing'),
    ([document(document_role='supporting')], 'document_primary_missing'),
    ([document(maturity='retired')], 'document_primary_missing'),
    ([document(), document('1')], 'document_primary_multiple')])
def test_missing_or_ambiguous_primary_never_selects_a_fallback(records, reason):
    report = assess_document_roles(model([domain_value('goal'), *records]))
    assert not report.roles_valid and report.data['primary_document'] is None
    assert [d['reason'] for d in report.data['diagnostics']] == [reason]
    with pytest.raises(DocumentRoleError) as error: report.require_primary_document()
    assert error.value.reason == reason and error.value.exit_code == 3


@pytest.mark.parametrize('field', ['purpose', 'audience', 'document_role', 'render_policy'])
def test_existing_record_schema_remains_mandatory_for_document_selection(field):
    broken = document('1', document_role='supporting'); broken.pop(field)
    supplied = model([document(), broken])
    report = assess_document_roles(supplied); data = report.data
    assert not report.roles_valid and not data['document_fields_valid']
    assert data['active_primary_count'] is None and data['primary_document'] is None
    issue, = data['diagnostics']
    assert issue['reason'] == 'missing_field' and issue['pointer'] == '/' + field
    assert issue['artifact_id'] == broken['id'] and issue['path'].endswith(broken['id'] + '.json')
    with pytest.raises(DocumentRoleError): report.require_primary_document()


def test_missing_document_language_is_refused_by_the_shared_model_before_role_assessment():
    broken = document(); broken.pop('language')
    with no_write_attempts(), pytest.raises(ModelError) as error:
        model([broken])
    assert error.value.reason == 'missing_field' and error.value.pointer == '/language'


def test_assessment_and_selected_record_are_owned_and_cannot_be_promoted_by_detached_data():
    supplied = model([document()]); report = assess_document_roles(supplied); digest = report.sha256
    detached = report.data; detached['primary_document']['record']['title'] = 'Foreign'
    selected = report.require_primary_document(); selected['record']['render_policy']['execute'] = 'foreign'
    assert report.sha256 == digest and report.require_primary_document()['record'] == document()
    with pytest.raises(FrozenInstanceError): report._encoded = b'{}'
    with pytest.raises(TypeError): bool(report)
    with pytest.raises(TypeError): DocumentRoleAssessment(detached)
    invalid = assess_document_roles(model([])); changed = invalid.data
    changed.update(roles_valid=True, primary_document=selected); changed['diagnostics'].clear()
    with pytest.raises(DocumentRoleError): invalid.require_primary_document()


def test_owned_document_inventory_never_reads_a_later_project_tree(tmp_path):
    root = tmp_path / 'project'; supplied = inspection_project(root, artifacts=[document()])
    before = inventory(tmp_path)
    with no_write_attempts(): expected = assess_document_roles(supplied)
    assert inventory(tmp_path) == before
    shutil.rmtree(root)
    with no_write_attempts(): actual = assess_document_roles(supplied)
    assert actual.data == expected.data and not actual.data['project_files_verified']
    assert not root.exists()


@pytest.mark.parametrize('mode', ['core', 'pyz'])
def test_document_selection_contract_runs_in_isolated_core_and_pyz(tmp_path, mode):
    supplied = model([document('0', document_role='supporting'), document('1')])
    expected = assess_document_roles(supplied).data
    body = '''import json
from specroad.documents import assess_document_roles
from specroad.changes import TargetModel
from specroad.model.model_manifest import ProjectReadBinding
from specroad.profiles import ProfileResource, compose_profiles
from specroad.validation import ModelDocument
'''
    body += 'configuration=' + repr(supplied.configuration_bytes) + '\n'
    body += 'documents=' + repr([(d.path, d.content) for d in supplied.documents]) + '\n'
    body += 'resources=' + repr([(d.path, d.content) for d in supplied.resource_files]) + '\n'
    body += '''profile=ProfileResource(dict(resources)['profiles/core.json'])
supplied=TargetModel(configuration,ProjectReadBinding('sample','/explicit/provider',(1,2)),
 [ModelDocument(p,b) for p,b in documents],profile=compose_profiles([profile],core_key=profile.key),
 resource_files=[ModelDocument(p,b) for p,b in resources])
print(json.dumps(assess_document_roles(supplied).data,sort_keys=True))
'''
    if mode == 'core': result = run_core(body, tmp_path, capture=True)
    else:
        _, package = build_distribution(tmp_path / 'distribution')
        result = run_python(['-I', '-S', '-B', '-c',
            'import sys;sys.path.insert(0,' + repr(str(package)) + ')\n' + body], tmp_path, capture=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == expected
