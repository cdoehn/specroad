"""Native common qualification: original bytes and host inputs never grant writes."""
from dataclasses import replace
from hashlib import sha256

import pytest

from specroad.model.errors import ModelError
from specroad.qualification import QualificationError, QualificationServices
from specroad.qualification.owned import owned_checks
from specroad.qualification.project import project_validation_report, validate_project
from specroad.qualification.services import native_services
from support.domain import domain_value
from support.read_only import inventory, no_write_attempts
from support.records import record_value
from test_proposal_basis import project


@pytest.mark.parametrize('primary', [True, False])
def test_complete_native_project_reports_validity_without_authority_or_writes(tmp_path, primary):
    artifacts = [domain_value('goal'), record_value('configuration')]
    if primary:
        artifacts.append(record_value('document'))
    original = project(tmp_path, artifacts=artifacts)
    files = original.source_files
    retained = dict(files)
    before = inventory(tmp_path)
    with no_write_attempts():
        model, root, report = project_validation_report(files)
        assert report.data['model_valid'] is primary
        if primary:
            checked, checked_root = validate_project(files)
            assert checked.source_files == files == model.source_files
            assert checked_root == root
            assert report.data['checks_complete']
        else:
            with pytest.raises(QualificationError):
                validate_project(files)
    assert files == retained and inventory(tmp_path) == before


@pytest.mark.parametrize('invalid', [object(), {}, True])
def test_project_data_cannot_supply_a_native_service_or_success_gate(invalid):
    with no_write_attempts(), pytest.raises(ModelError) as error:
        native_services(invalid)
    assert error.value.reason == 'restore_native_services_required'


def test_live_source_is_reobserved_even_when_original_model_bytes_are_reused(tmp_path):
    raw = b'Original externally supplied source bytes'
    source = record_value('source', content_sha256=sha256(raw).hexdigest())
    model = project(tmp_path, artifacts=[record_value('document'), source])
    before = inventory(tmp_path)
    responses, calls = [raw, b'changed externally', raw], []

    def provider(snapshot, record):
        calls.append((snapshot._sources_sha256, record.data['id']))
        return responses.pop(0)

    services = QualificationServices(source_content=provider)

    @owned_checks
    def qualify():
        validate_project(model.source_files, services=services)
        with pytest.raises(QualificationError) as error:
            validate_project(model.source_files, services=services)
        assert error.value.reason == 'restore_source_content_changed'
        assert error.value.exit_code == 6 and error.value.path == source['id']
        validate_project(model.source_files, services=services)

    with no_write_attempts():
        with pytest.raises(QualificationError) as error:
            validate_project(model.source_files)
        assert error.value.reason == 'restore_source_content_provider_required'
        qualify()
    assert len(calls) == 3 and not responses and inventory(tmp_path) == before


@pytest.mark.parametrize('receipts', [True, False])
def test_applied_proposal_needs_original_publication_proof_for_read_qualification(tmp_path, receipts):
    from support.proposal_apply import ApplyCase
    case = ApplyCase(tmp_path / 'project')
    case.apply()
    inputs, model = case.completion_inputs()
    if not receipts:
        inputs = replace(inputs, publications=())
    services = QualificationServices(proposal_inputs=lambda snapshot, original: inputs)
    before = inventory(tmp_path)
    with no_write_attempts():
        if receipts:
            checked, root = validate_project(model.source_files, services=services)
            assert checked.source_files == model.source_files and root
        else:
            with pytest.raises(ModelError):
                validate_project(model.source_files, services=services)
    assert inventory(tmp_path) == before
