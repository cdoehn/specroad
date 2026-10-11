"""Actual read-only CLI/model/runtime behavior, never terminal presentation."""
import json
import shutil
from unittest.mock import patch

import pytest

from specroad.authoring import project_inspection as inspection
from specroad.authoring._inspection_snapshot import InspectionSnapshot
from specroad.authoring.project_inspection import inspect_project
from specroad.changes import project_lock
from specroad.changes.target_model import _default_scope
from specroad.cli.application import dispatch_result, execute_request
from specroad.cli.commands import builtin_registry
from specroad.model.canonical import canonical_json_bytes
from specroad.model.errors import ModelError
from specroad.model.schema_catalog import SchemaCatalog
from specroad.profiles import ProfileResource
from support.domain import domain_value
from support.inspection import inspection_project
from support.model import put
from support.processes import run_cli
from support.profiles import profile_data
from support.project_locks import options
from support.read_only import inventory, no_write_attempts
from support.records import record_value


def projection(result):
    value = result.as_dict()['result']
    return canonical_json_bytes({k: value[k] for k in ('format_version', 'semantic')})


def test_real_cli_python_and_structured_request_describe_the_actual_project(tmp_path):
    root = tmp_path / 'project'; model = inspection_project(root)
    before = inventory(root)
    direct = inspect_project(root)
    cli = dispatch_result(['project', 'inspect', '--format=json', '--project', str(root)])
    structured = execute_request({'command_id': 'project.inspect',
                                 'options': {'--project': str(root), '--format': 'json'}}).result
    process = run_cli(['project', 'inspect', '--format=json'], root, capture=True)
    assert direct.exit_code == cli.exit_code == structured.exit_code == process.returncode == 0, direct.as_dict()
    assert cli.project['project_id'] == direct.project['project_id'] == 'sample'
    for value in (cli, structured):
        assert value.as_dict()['result'] == direct.as_dict()['result']
    assert json.loads(process.stdout)['result'] == direct.as_dict()['result']
    result = direct.as_dict()['result']; semantic = result['semantic']
    assert set(result) == {'format_version', 'semantic', 'runtime'}
    assert result['format_version'] == '1.0.0' and len(semantic) == 8
    assert semantic == {'project_id': 'sample', 'schema_version': '0.2.0',
        'model_root_sha256': model.manifest(model.artifacts, _default_scope()).sha256,
        'active_profiles': [{'profile_id': 'core', 'version': '0.2.0'}],
        'artifact_counts': {'goal': 1}, 'migration_needed': False,
        'diagnostic_summary': {'error': 0, 'warning': 0, 'info': 0}, 'primary_documents': []}
    assert result['runtime'] == {'project_root': str(root), 'open_transaction': None,
                                'writer_lock': None, 'consistency_state': 'consistent'}
    assert direct.as_dict()['summary']['complete'] and not direct.as_dict()['summary']['atomic_snapshot']
    assert not direct.as_dict()['summary']['approval_granted'] and inventory(root) == before


def test_identical_relocated_models_have_equal_canonical_semantics(tmp_path):
    first = tmp_path / 'first'; second = tmp_path / 'second'
    inspection_project(first); shutil.copytree(first, second)
    left, right = inspect_project(first), inspect_project(second)
    assert left.exit_code == right.exit_code == 0
    assert projection(left) == projection(right)
    assert left.as_dict()['result']['runtime']['project_root'] != right.as_dict()['result']['runtime']['project_root']


def test_inspection_has_no_write_process_stdin_entropy_or_lock_acquisition(tmp_path):
    root = tmp_path / 'project'; inspection_project(root); before = inventory(root)
    with no_write_attempts(), patch('builtins.input', side_effect=AssertionError('stdin')), \
            patch('secrets.token_bytes', side_effect=AssertionError('entropy')), \
            patch('specroad.changes.locking.LockFiles.acquire', side_effect=AssertionError('lock')):
        result = inspect_project(root)
    assert result.exit_code == 0 and inventory(root) == before


def test_primary_documents_and_counts_remain_known_when_a_required_service_is_missing(tmp_path):
    primary = record_value('document', document_role='primary_specification')
    supporting = record_value('document', id='SR-DOC-' + '1' * 26, document_role='supporting')
    root = tmp_path / 'project'; model = inspection_project(root, artifacts=[supporting, primary, domain_value('goal')])
    result = inspect_project(root); semantic = result.as_dict()['result']['semantic']
    assert result.exit_code == 5 and not result.complete
    assert semantic['primary_documents'] == [{'id': primary['id'], 'title': primary['title']}]
    assert list(semantic['artifact_counts']) == ['document', 'goal']
    assert semantic['artifact_counts'] == {'document': 2, 'goal': 1}
    assert semantic['model_root_sha256'] == model.manifest(model.artifacts, _default_scope()).sha256
    assert semantic['diagnostic_summary'] is None
    assert any(d.code == 'VALIDATION_UNAVAILABLE' for d in result.diagnostics)
    assert result.as_dict()['result']['runtime']['consistency_state'] == 'consistent'


def test_actual_initialized_project_binds_distributed_profiles_and_language_packages(tmp_path):
    result = dispatch_result(['init', str(tmp_path / 'project')])
    assert result.exit_code == 0
    root = tmp_path / 'project'; before = inventory(root)
    observed = inspect_project(root); semantic = observed.as_dict()['result']['semantic']
    assert observed.exit_code == 5 and not observed.complete, observed.as_dict()
    assert semantic['active_profiles'] == [{'profile_id': 'core', 'version': '0.2.0'},
                                          {'profile_id': 'software-de', 'version': '0.2.0'}]
    assert semantic['project_id'] == result.as_dict()['result']['project_id']
    assert semantic['primary_documents'][0]['id'] == result.as_dict()['result']['primary_document_id']
    assert semantic['artifact_counts'] == {'document': 1} and semantic['diagnostic_summary'] is None
    assert semantic['migration_needed'] is False and len(semantic['model_root_sha256']) == 64
    assert inventory(root) == before


def test_effective_profile_order_and_explicit_cli_selection_are_observed(tmp_path):
    root = tmp_path / 'project'
    profiles = [ProfileResource(canonical_json_bytes(profile_data(profile_id=name))) for name in ('zeta', 'alpha')]
    inspection_project(root, extra_profiles=profiles)
    default = inspect_project(root)
    chosen = dispatch_result(['project', 'inspect', '--project', str(root), '--profile', profiles[1].key])
    assert default.exit_code == chosen.exit_code == 0
    assert [p['profile_id'] for p in default.as_dict()['result']['semantic']['active_profiles']] == ['core', 'zeta', 'alpha']
    assert [p['profile_id'] for p in chosen.as_dict()['result']['semantic']['active_profiles']] == ['core', 'alpha']
    assert projection(default) != projection(chosen)


@pytest.mark.parametrize('route', ['python', 'cli'])
def test_actual_active_writer_blocks_before_model_loading(tmp_path, route):
    root = tmp_path / 'project'; inspection_project(root)
    with project_lock(root, **options()) as held:
        before = inventory(root)
        with patch.object(inspection, 'InspectionSnapshot', side_effect=AssertionError('model read')), no_write_attempts():
            result = inspect_project(root) if route == 'python' else dispatch_result(
                ['project', 'inspect', '--project', str(root)])
        assert result.exit_code == 6 and not result.complete
        payload = result.as_dict()['result']
        assert set(payload['semantic'].values()) == {None}
        assert payload['runtime']['consistency_state'] == 'writer_active'
        assert payload['runtime']['writer_lock']['record'] == held.record.data
        assert inventory(root) == before


@pytest.mark.parametrize('path,state', [('.specroad/transactions/unresolved.json', 'recovery_required'),
                                      ('.specroad/unclassified.json', 'unknown')])
def test_unresolved_operational_entries_block_without_repair_or_model_read(tmp_path, path, state):
    root = tmp_path / 'project'; inspection_project(root); put(root, path, b'not a readable journal')
    before = inventory(root)
    with patch.object(inspection, 'InspectionSnapshot', side_effect=AssertionError('model read')), no_write_attempts():
        result = inspect_project(root)
    assert result.exit_code == 5 and not result.complete
    payload = result.as_dict()['result']
    assert payload['runtime']['consistency_state'] == state and set(payload['semantic'].values()) == {None}
    if state == 'recovery_required':
        assert path in payload['runtime']['open_transaction']['unresolved_paths']
    assert inventory(root) == before


@pytest.mark.parametrize('change', ['schema', 'profile', 'artifact', 'registry'])
def test_unreadable_or_unbound_model_has_no_invented_success_facts(tmp_path, change):
    root = tmp_path / 'project'; model = inspection_project(root)
    if change == 'schema':
        value = json.loads((root / 'specroad.json').read_bytes()); value['schema_version'] = '0.1.0'
        put(root, 'specroad.json', canonical_json_bytes(value))
    elif change == 'profile':
        (root / 'profiles/core.json').unlink()
    elif change == 'artifact':
        put(root, model.documents[0].path, b'{broken')
    else:
        put(root, model.configuration.data['language_registry']['path'], b'{}')
    before = inventory(root); result = inspect_project(root)
    assert result.exit_code in (3, 5) and not result.complete
    assert set(result.as_dict()['result']['semantic'].values()) == {None}
    assert inventory(root) == before


@pytest.mark.parametrize('change', ['bytes', 'inventory'])
def test_final_read_detects_input_changes_and_discards_stale_semantics(tmp_path, change):
    root = tmp_path / 'project'; model = inspection_project(root)
    original = InspectionSnapshot.verify_current
    def changed(snapshot):
        if change == 'bytes':
            value = model.artifacts[0]; value['statement'] = 'Changed while being inspected.'
            put(root, model.documents[0].path, canonical_json_bytes(value))
        else:
            put(root, 'profiles/new.json', canonical_json_bytes(profile_data(profile_id='new')))
        return original(snapshot)
    with patch.object(InspectionSnapshot, 'verify_current', changed):
        result = inspect_project(root)
    assert result.exit_code == 6 and not result.complete
    assert set(result.as_dict()['result']['semantic'].values()) == {None}
    assert result.as_dict()['result']['runtime']['consistency_state'] == 'unknown'


def test_failed_lock_observation_is_unknown_never_an_absent_lock(tmp_path):
    root = tmp_path / 'project'; inspection_project(root)
    with patch.object(inspection, 'inspect_project_lock', side_effect=OSError('private host detail')):
        result = inspect_project(root)
    assert result.exit_code == 5
    assert result.as_dict()['result']['runtime']['writer_lock'] == {'observation_status': 'unknown'}
    assert 'private host detail' not in json.dumps(result.as_dict())


def test_returned_values_are_detached_and_unknown_result_versions_fail(tmp_path):
    root = tmp_path / 'project'; inspection_project(root)
    first = inspect_project(root); original = projection(first)
    data = first.as_dict()['result']; data['semantic']['artifact_counts']['goal'] = 999
    assert projection(first) == projection(inspect_project(root)) == original
    catalog = SchemaCatalog(); catalog.validate('project-inspect-v1', first.as_dict()['result'])
    data['format_version'] = '9.0.0'
    with pytest.raises(ModelError): catalog.validate('project-inspect-v1', data)
    command = builtin_registry().resolve('project.inspect')
    assert command.requires_project and command.effect_scope.value == 'none'
