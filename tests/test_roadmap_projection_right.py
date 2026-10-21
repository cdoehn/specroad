"""Stored-date, passive-input and no-write boundaries of the native roadmap."""
import json
import stat

import pytest

from specroad.changes import TargetModel, TargetError
from specroad.model.canonical import canonical_json_bytes
from specroad.model.errors import ModelError
from specroad.model.paths import artifact_path
from specroad.planning import project_roadmap
from specroad.validation import ModelDocument
from support.model import put
from support.portable import build_distribution
from support.processes import run_core, run_python
from support.read_only import inventory, no_write_attempts
from support.relations import aid, edge
from support.targets import model
from test_planning_relations import stored
from test_roadmap_projection import roadmap_values, by_id


def dated_values():
    values = roadmap_values()
    values[0]['target_date'] = '2099-12-31'
    values[1]['target_date'] = '1900-01-01'
    values[1]['relations'].append(edge('depends_on', values[0]['id'], number=100))
    return values


@pytest.mark.parametrize('date', ['0001-01-01', '2000-02-29', '2024-02-29', '2100-03-01', '9999-12-31'])
def test_stored_dates_are_not_retimed_by_dependency_order_or_current_time(tmp_path, date):
    values = dated_values(); values[0]['target_date'] = date
    supplied = stored(tmp_path / 'project', values); before = inventory(tmp_path)
    with no_write_attempts(): report = project_roadmap(supplied)
    items = by_id(report.data)
    assert items[aid('release', 1)]['stored']['target_date'] == date
    assert items[aid('release', 2)]['stored']['target_date'] == '1900-01-01'
    assert items[aid('release', 2)]['dependency_ids'] == [aid('release', 1)]
    assert not report.data['dates_estimated'] and not report.data['critical_path_evaluated']
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('date,reason', [
    ('2023-02-29', 'schema_format'), ('2100-02-29', 'schema_format'),
    ('0000-01-01', 'schema_format'), ('2026-2-03', 'schema_format'),
    ('2027-03-10T00:00:00Z', 'schema_format'), ('next release', 'schema_format'),
    (None, 'schema_type'), (20270310, 'schema_type')])
def test_invalid_dates_fail_without_normalizing_or_repairing_project_bytes(tmp_path, date, reason):
    values = dated_values(); values[0]['target_date'] = date
    supplied = stored(tmp_path / 'project', values); before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(ModelError) as error:
        project_roadmap(supplied)
    assert error.value.reason == reason and error.value.pointer == '/target_date'
    assert error.value.path == artifact_path('release', aid('release', 1), 'SR')
    assert inventory(tmp_path) == before


def test_missing_dates_are_not_filled_from_dependencies_or_milestone_membership(tmp_path):
    values = dated_values(); values[0].pop('target_date'); values[1].pop('target_date')
    supplied = stored(tmp_path / 'project', values); before = inventory(tmp_path)
    with no_write_attempts(): data = project_roadmap(supplied).data
    assert all('target_date' not in row['stored'] for row in data['items'])
    assert len(data['schedule_groups']) == 4 and not data['dates_estimated']
    assert inventory(tmp_path) == before


def test_dependency_cycles_are_observed_without_solving_or_rewriting_the_schedule(tmp_path):
    values = dated_values()
    values[0]['relations'].append(edge('depends_on', values[1]['id'], number=101))
    supplied = stored(tmp_path / 'project', values); before = inventory(tmp_path)
    with no_write_attempts(): data = project_roadmap(supplied).data
    items = by_id(data)
    assert items[aid('release', 1)]['dependency_ids'] == [aid('release', 2)]
    assert items[aid('release', 2)]['dependency_ids'] == [aid('release', 1)]
    assert items[aid('release', 1)]['stored']['target_date'] == '2099-12-31'
    assert items[aid('release', 2)]['stored']['target_date'] == '1900-01-01'
    assert not data['critical_path_evaluated'] and not data['release_readiness_evaluated']
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('kind,field,value', [
    ('task', 'target_date', '2027-02-01'), ('task', 'effort', 13),
    ('release', 'critical_path', []), ('release', 'estimated_date', '2027-02-01')])
def test_unsupported_top_level_schedule_facts_are_not_silently_repaired(tmp_path, kind, field, value):
    values = dated_values(); changed = next(v for v in values if v['artifact_type'] == kind)
    changed[field] = value
    supplied = stored(tmp_path / 'project', values); before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(ModelError) as error:
        project_roadmap(supplied)
    assert error.value.reason == 'unknown_field' and error.value.pointer == '/' + field
    assert error.value.path == artifact_path(kind, changed['id'], 'SR')
    assert inventory(tmp_path) == before


def test_extension_estimates_and_text_do_not_become_normative_planning_fields(tmp_path):
    values = dated_values(); original = project_roadmap(model(values)).data
    for value in values:
        value['extensions']['example.schedule'] = {'target_date': '2050-01-01',
            'effort': 100, 'critical_path': [aid('task', 1)], 'approval_granted': True}
        for relation in value['relations']:
            relation['extensions']['example.schedule'] = {'priority': 'mandatory',
                'target_date': '2050-01-01', 'write_back': True}
    values[4]['description'] = 'Estimated 100 days; finish 2050-01-01; critical path.'
    supplied = stored(tmp_path / 'project', values); before = inventory(tmp_path)
    with no_write_attempts(): data = project_roadmap(supplied).data
    items = by_id(data); task = items[aid('task', 1)]
    assert 'target_date' not in task['stored'] and 'effort' not in task['stored']
    assert 'critical_path' not in task['stored'] and 'priority' not in task['stored']
    assert task['stored']['description'] == values[4]['description']
    assert items[aid('release', 1)]['stored']['target_date'] == '2099-12-31'
    assert items[aid('release', 2)]['stored']['target_date'] == '1900-01-01'
    assert data['schedule_groups'] == original['schedule_groups']
    assert not any(data[k] for k in ('dates_estimated', 'effort_estimated', 'critical_path_evaluated', 'approval_granted'))
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('field,value,reason', [
    ('probability', -0.1, 'schema_any_of'), ('probability', 1.1, 'schema_any_of'),
    ('probability', True, 'schema_any_of'), ('impact', -1, 'schema_any_of'),
    ('impact', False, 'schema_any_of'), ('risk_status', '', 'schema_min_length')])
def test_invalid_risk_values_never_trigger_normalization_or_partial_results(tmp_path, field, value, reason):
    values = dated_values(); risk = values[-2]; risk[field] = value
    supplied = stored(tmp_path / 'project', values); before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(ModelError) as error: project_roadmap(supplied)
    assert error.value.reason == reason and error.value.pointer == '/' + field
    assert error.value.path == artifact_path('risk', risk['id'], 'SR')
    assert inventory(tmp_path) == before


def test_non_projected_hierarchy_failure_preserves_original_graph_witnesses_and_files(tmp_path):
    values = dated_values(); first, second = values[:2]
    first['relations'].append(edge('supersedes', second['id'], number=101))
    second['relations'].append(edge('supersedes', first['id'], number=102))
    supplied = stored(tmp_path / 'project', values); before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(ModelError) as error: project_roadmap(supplied)
    assert error.value.reason == 'relation_hierarchy_cycle'
    assert set(error.value.diagnostic()['relation_ids']) == {edge(number=n)['relation_id'] for n in (101, 102)}
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('mode', ['valid', 'invalid-date'])
def test_projection_works_without_write_permissions_even_on_error(tmp_path, mode):
    values = dated_values()
    if mode == 'invalid-date': values[0]['target_date'] = 'invalid'
    root = tmp_path / 'project'; supplied = stored(root, values)
    put(root, '.specroad/local-observation.json', b'{"unrelated":true}\n')
    paths = [root, *sorted(root.rglob('*'))]
    original_modes = {p: stat.S_IMODE(p.stat().st_mode) for p in paths}
    try:
        for path in reversed(paths): path.chmod(0o555 if path.is_dir() else 0o444)
        before = inventory(tmp_path)
        with no_write_attempts():
            if mode == 'valid':
                assert by_id(project_roadmap(supplied).data)[aid('release', 1)]['stored']['target_date'] == '2099-12-31'
            else:
                with pytest.raises(ModelError) as error: project_roadmap(supplied)
                assert error.value.reason == 'schema_format'
        assert inventory(tmp_path) == before
    finally:
        for path in paths: path.chmod(original_modes[path])


def test_live_date_changes_and_unrelated_roadmap_file_are_preserved_not_reopened(tmp_path):
    root = tmp_path / 'project'; values = dated_values(); supplied = stored(root, values)
    expected = project_roadmap(supplied)
    path = artifact_path('release', aid('release', 1), 'SR')
    values[0]['target_date'] = '2050-02-01'
    put(root, path, canonical_json_bytes(values[0]))
    put(root, 'roadmap.json', b'{"target_date":"2090-03-04","effort":600}\n')
    put(root, '.specroad/roadmap-cache.json', b'{"state":"foreign"}\n')
    before = inventory(tmp_path)
    with no_write_attempts(): actual = project_roadmap(supplied)
    assert actual.data == expected.data and actual.sha256 == expected.sha256
    assert by_id(actual.data)[aid('release', 1)]['stored']['target_date'] == '2099-12-31'
    assert not actual.data['project_files_verified']
    assert inventory(tmp_path) == before


def test_different_json_spelling_changes_byte_bindings_only_not_stored_dates():
    supplied = model(dated_values()); before = project_roadmap(supplied).data
    documents = [ModelDocument(d.path, json.dumps(json.loads(d.content), indent=4).encode() + b'\n')
                 for d in supplied.documents]
    reformatted = TargetModel(supplied.configuration_bytes, supplied.binding, documents,
        profile=supplied.profile, resource_files=supplied.resource_files)
    with no_write_attempts(): after = project_roadmap(reformatted).data
    assert before['model_root_sha256'] == after['model_root_sha256']
    assert before['input_sha256'] != after['input_sha256']
    assert before['schedule_groups'] == after['schedule_groups']
    for field in ('items', 'risks'):
        old, new = by_id(before, field), by_id(after, field)
        for key in old:
            assert old[key]['stored'] == new[key]['stored']
            assert old[key]['record_sha256'] == new[key]['record_sha256']
            assert old[key]['source_sha256'] != new[key]['source_sha256']


@pytest.mark.parametrize('tamper', ['date', 'relation', 'input-hash'])
def test_changed_bound_inputs_fail_before_any_projection_or_repair(tmp_path, tamper):
    supplied = stored(tmp_path / 'project', dated_values()); before = inventory(tmp_path)
    if tamper == 'input-hash': object.__setattr__(supplied, '_sources_sha256', 'f' * 64)
    else:
        documents = list(supplied.documents)
        index = next(i for i, d in enumerate(documents) if json.loads(d.content)['id'] == aid('release', 1))
        document = documents[index]; value = json.loads(document.content)
        if tamper == 'date': value['target_date'] = '2050-01-01'
        else: value['relations'].append(edge('depends_on', aid('release', 2), number=101))
        documents[index] = ModelDocument(document.path, canonical_json_bytes(value))
        object.__setattr__(supplied, 'documents', tuple(documents))
    with no_write_attempts(), pytest.raises(TargetError) as error: project_roadmap(supplied)
    assert error.value.reason == 'target_sources_changed'
    assert inventory(tmp_path) == before


def test_detached_nested_projection_mutation_cannot_update_dates_owners_or_relations(tmp_path):
    supplied = stored(tmp_path / 'project', dated_values()); before = inventory(tmp_path)
    report = project_roadmap(supplied); expected = report.data
    detached = report.data
    by_id(detached)[aid('release', 1)]['stored']['target_date'] = '2050-01-01'
    by_id(detached)[aid('milestone', 1)]['stored']['owner']['actor_id'] = 'foreign'
    detached['schedule_groups'][0]['scheduled_artifact_ids'].append(aid('task', 1))
    detached['relations'].clear(); detached['approval_granted'] = True
    with no_write_attempts(): refreshed = project_roadmap(supplied)
    assert report.data == refreshed.data == expected
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('runtime', ['core', 'pyz'])
@pytest.mark.parametrize('invalid', [False, True])
def test_isolated_runtime_preserves_sources_and_rejects_writes_on_success_and_failure(tmp_path, runtime, invalid):
    values = dated_values()
    if invalid: values[0]['target_date'] = '2023-02-29'
    supplied = model(values)
    if invalid:
        expected = {'reason': 'schema_format', 'path': artifact_path('release', aid('release', 1), 'SR'),
                    'pointer': '/target_date'}
    else: expected = project_roadmap(supplied).data
    body = '''import json,os,sys
from specroad.planning import project_roadmap
from specroad.changes import TargetModel
from specroad.model.errors import ModelError
from specroad.model.model_manifest import ProjectReadBinding
from specroad.profiles import ProfileResource,compose_profiles
from specroad.validation import ModelDocument
'''
    body += 'configuration=' + repr(supplied.configuration_bytes) + '\n'
    body += 'documents=' + repr([(d.path,d.content) for d in supplied.documents]) + '\n'
    body += 'resources=' + repr([(d.path,d.content) for d in supplied.resource_files]) + '\n'
    body += '''profile=ProfileResource(dict(resources)['profiles/core.json'])
supplied=TargetModel(configuration,ProjectReadBinding('sample','/missing/roadmap',(1,2)),
 [ModelDocument(p,b) for p,b in documents],profile=compose_profiles([profile],core_key=profile.key),
 resource_files=[ModelDocument(p,b) for p,b in resources])
before=supplied.source_files
blocked=[]
def guard(event,args):
 forbidden=event.startswith(('subprocess.','socket.')) or event in (
  'os.mkdir','os.rename','os.remove','os.rmdir','os.chmod','os.truncate','os.utime','os.link','os.symlink','os.system')
 if event=='open':
  mode,flags=args[1:3]
  forbidden=any(c in (mode or '') for c in 'wax+') or bool(flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND))
 if forbidden:
  blocked.append(event)
  raise AssertionError('Unexpected mutation/process/network attempt')
sys.addaudithook(guard)
try:
 output=project_roadmap(supplied).data
except ModelError as error:
 output={'reason':error.reason,'path':error.path,'pointer':error.pointer}
assert not blocked and supplied.source_files==before
print(json.dumps(output,sort_keys=True))
'''
    if runtime == 'core': result = run_core(body, tmp_path, capture=True)
    else:
        _, package = build_distribution(tmp_path / 'distribution')
        result = run_python(['-I', '-S', '-B', '-c',
            'import sys;sys.path.insert(0,' + repr(str(package)) + ')\n' + body], tmp_path, capture=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == expected
