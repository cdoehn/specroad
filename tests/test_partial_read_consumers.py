"""Partial view/diagram/validation scope and denial at public entry boundaries."""
import json
import shutil
from pathlib import Path

import pytest

from specroad.bundles import prepare_partial_bundle, BundleContainer
from specroad.bundles.extraction import extract_bundle
from specroad.bundles._partial_read import partial_read_snapshot
from specroad.bundles.manifest import MANIFEST_NAME
from specroad.cli.application import dispatch_result, execute_request
from specroad.documents._read_model import PartialDocumentModel
from specroad.documents.project_read import read_document_project, document_read_steps
from specroad.documents.views import resolve_view
from specroad.query import query_project, NormalizedQuery, diff_project, trace_artifact
from specroad.model.canonical import canonical_json_bytes
from support.domain import domain_value
from support.inspection import inspection_project
from support.model import put
from support.records import ref, record_value
from support.read_only import inventory, no_write_attempts
from support.srx import literal, expression_document, binary, field
from support.targets import SCOPE
from test_partial_read_commands import extracted
from test_partial_read_commands_right import checked
from test_partial_bundle import project, scope, save, edge
from test_partial_bundle_right import configured
from test_bundle_verification import rebind
from test_bundle_verification_right import path, context_path


def view_partial(tmp_path, configuration=False, projections=True):
    origin = tmp_path / 'origin'
    values, chain, _ = configured(origin) if configuration else (project(origin), [], None)
    selected = scope(configuration_id=chain[-1]['id'] if chain else None)
    view = record_value('view', scope_descriptor=SCOPE,
        filter=expression_document(binary('eq', field('/artifact_type'), literal('requirement'))),
        columns=[{'source': {'kind': 'artifact_field', 'pointer': '/id'}, 'heading': 'ID',
                  'data_type': 'string', 'format': 'plain', 'missing': 'error'}],
        relation_projections=[], sort=[], grouping=[])
    if projections:
        view['columns'].append({'source': {'kind': 'relation_projection', 'projection_id': 'near'},
            'heading': 'Related', 'data_type': 'array', 'format': 'plain', 'missing': 'error'})
        view['relation_projections'] = [{'id': 'near', 'direction': 'both', 'types': ['duplicates'],
            'max_depth': 20, 'aggregation': 'ids'}]
    block = record_value('content_block', id=ref('BLOCK', '1'), block_kind='table',
        payload={'source': 'view'}, relations=[edge('references', view['id'], 12)])
    values[1]['relations'].append(edge('contains', block['id'], 11))
    for v in (values[1], block, view): save(origin, v)
    bundle = prepare_partial_bundle(origin, selected)
    target = tmp_path / 'partial'; extract_bundle(bundle.source_bytes, target)
    shutil.rmtree(origin)
    return target, bundle, values, [*values[:-2], block, view], chain


@pytest.mark.parametrize('configuration', [False, True])
@pytest.mark.parametrize('route', ['native', 'python', 'cli', 'request'])
def test_view_projection_never_enters_boundary_or_configuration_context(tmp_path, configuration, route):
    root, bundle, values, members, chain = view_partial(tmp_path, configuration)
    with no_write_attempts():
        if route == 'native':
            data = resolve_view(PartialDocumentModel(partial_read_snapshot(root)), ref('VIEW')).data
        else:
            if route == 'python': result = read_document_project(root, 'view.render', ref('VIEW'))
            elif route == 'cli': result = dispatch_result(['view', 'render', ref('VIEW'), '--project', str(root)])
            else: result = execute_request({'command_id': 'view.render', 'arguments': {'id': ref('VIEW')},
                    'options': {'--project': str(root)}}).result
            data = checked(result, bundle, members)['data']
    assert [r['artifact_id'] for r in data['rows']] == [values[-3]['id']]
    assert data['rows'][0]['relation_projections']['near'] == []
    assert data['scope_descriptor'] == data['selection_scope_descriptor'] == bundle.manifest['scope_descriptor']
    assert data['query_binding']['source_count'] == len(members)
    assert not ({v['id'] for v in chain} & {r['artifact_id'] for r in data['rows']})


@pytest.mark.parametrize('configuration', [False, True])
@pytest.mark.parametrize('route', ['python', 'cli', 'request'])
def test_document_table_projection_uses_members_only(tmp_path, configuration, route):
    root, bundle, values, members, chain = view_partial(tmp_path, configuration, projections=False)
    with no_write_attempts():
        if route == 'python': result = read_document_project(root, 'render', values[0]['id'])
        elif route == 'cli': result = dispatch_result(['render', values[0]['id'], '--project', str(root)])
        else: result = execute_request({'command_id': 'render', 'arguments': {'id': values[0]['id']},
            'options': {'--project': str(root)}}).result
    data = checked(result, bundle, members)['data']
    assert set(data['records']) <= {v['id'] for v in members}
    assert data['model_root_sha256'] == bundle.manifest['bundle_model_root_sha256']


@pytest.mark.parametrize('kind', ['document', 'release'])
@pytest.mark.parametrize('depth', [0, 1, 8])
def test_cycles_local_symmetric_views_and_multiple_outside_edges(tmp_path, kind, depth):
    origin = tmp_path / 'origin'; values = project(origin, kind)
    first, outside = values[-3:-1]
    second = domain_value('requirement', id=ref('REQ', '2'), relations=[
        edge('depends_on', first['id'], 21)])
    first['relations'].extend([edge('depends_on', second['id'], 23), edge('duplicates', second['id'], 24),
                              edge('conflicts_with', outside['id'], 22)])
    save(origin, first); save(origin, second)
    bundle = prepare_partial_bundle(origin, scope(kind))
    root = tmp_path / 'partial'; extract_bundle(bundle.source_bytes, root); shutil.rmtree(origin)
    members = [*values[:-2], second]
    with no_write_attempts(): result = trace_artifact(root, first['id'], direction='both', depth=depth)
    assert result.exit_code == 0, json.dumps(result.as_dict(), sort_keys=True)
    data = checked(result, bundle, members)
    nodes = {n['id'] for n in data['nodes']}
    assert outside['id'] not in nodes
    assert second['id'] in nodes if depth else nodes == {first['id']}
    assert {r['source'] for r in data['edges']} <= {v['id'] for v in members}
    assert {r['target'] for r in data['edges']} <= {v['id'] for v in members}
    assert len(bundle.manifest['boundary_references']) == 2


@pytest.mark.parametrize('kind', ['document', 'release'])
@pytest.mark.parametrize('mode', ['empty', 'outside_title', 'sort_page', 'srx_error', 'configuration_conflict'])
def test_filter_projection_and_config_error_contracts(tmp_path, kind, mode):
    root, bundle, values, members, chain = extracted(tmp_path, kind, 'configuration')
    kwargs = {}
    if mode == 'empty': query = NormalizedQuery(filters={'tag': ['never-present']})
    elif mode == 'outside_title': query = NormalizedQuery(srx_filters=[expression_document(binary(
        'eq', field('/statement'), literal(values[-2]['statement'])))])
    elif mode == 'sort_page': query = NormalizedQuery(sort=['id:desc'], offset=1, limit=1)
    elif mode == 'srx_error': query = NormalizedQuery(srx_filters=[expression_document(literal(1))])
    else:
        query = NormalizedQuery(); kwargs['configuration_id'] = chain[0]['id']
    with no_write_attempts(): result = query_project(root, query, **kwargs)
    if mode in ('srx_error', 'configuration_conflict'):
        assert result.exit_code == 3 and result.as_dict()['result'] is None, result.as_dict()
    else:
        data = checked(result, bundle, members)
        if mode == 'sort_page':
            assert data['total'] == len(members)
            assert [r['id'] for r in data['items']] == sorted((v['id'] for v in members), reverse=True)[1:2]
        else: assert data['items'] == [] and data['total'] == 0


@pytest.mark.parametrize('command', ['query', 'trace', 'why', 'impact', 'diff', 'render', 'diagram', 'validate', 'project.inspect'])
def test_forged_native_boundary_is_never_a_command_success(tmp_path, command):
    root, bundle, values, _, _ = extracted(tmp_path)
    bad = BundleContainer(rebind(bundle, bundle.files, boundary_references=[]))
    shutil.rmtree(root)
    for name, raw in {**bad.files, MANIFEST_NAME: bad.manifest_bytes}.items(): put(root, name, raw)
    args = {'query': [], 'trace': [values[-3]['id'], '--direction', 'both', '--depth', '4'],
        'why': [values[-3]['id']], 'impact': [values[-3]['id']],
        'diff': ['--against', str(root), '--against-kind', 'local'], 'render': [values[0]['id']],
        'diagram': ['trace', values[-3]['id'], '--direction', 'both', '--max-depth', '4',
                    '--max-nodes', '100', '--max-edges', '100'], 'validate': ['--partial'], 'project.inspect': []}
    with no_write_attempts(): result = dispatch_result([*command.split('.'), *args[command], '--project', str(root)])
    assert result.exit_code == 3, result.as_dict()


@pytest.mark.parametrize('family', ['lock', 'recover', 'environment'])
def test_operational_diagnoses_remain_available_with_open_journal(tmp_path, family):
    root, _, _, _, _ = extracted(tmp_path)
    (root / '.specroad/transactions/unknown').mkdir(parents=True)
    with no_write_attempts(): result = dispatch_result([family, 'check' if family == 'environment' else 'status',
                                                       '--project', str(root)])
    assert result.exit_code == (5 if family == 'environment' else 0), result.as_dict()
    assert 'partial_scope' not in result.as_dict()['summary']
    if family == 'environment':
        checks = {c['check_id']: c for c in result.as_dict()['result']['checks']}
        assert checks['project.operational']['state'] == 'failed'
        assert checks['project.operational']['reason'] == 'recovery_required'
        assert result.as_dict()['result']['recovery_required'] is True
    else:
        assert result.status.value == 'success'


@pytest.mark.parametrize('command', ['artifact create', 'artifact update', 'relation review', 'baseline create',
    'migrate apply', 'merge apply', 'import apply', 'proposal apply', 'change apply', 'format'])
def test_every_normative_write_lock_is_refused_before_mutation(tmp_path, command):
    from specroad.changes.locking import project_lock
    from specroad.security import SafetyViolation
    root, _, _, _, _ = extracted(tmp_path)
    before = inventory(root); project_id = json.loads((root / 'specroad.json').read_bytes())['project_id']
    with no_write_attempts(), pytest.raises(SafetyViolation):
        with project_lock(root, kind='writer', command=command, project_id=project_id,
                          transaction_id='synthetic-write-attempt'):
            pytest.fail('A partial cannot acquire write authority')
    assert inventory(root) == before


@pytest.mark.parametrize('kind', ['document', 'release'])
def test_selected_diff_uses_configuration_context_without_comparing_it(tmp_path, kind):
    root, bundle, _, members, chain = extracted(tmp_path, kind, 'configuration')
    other = tmp_path / 'other'; shutil.copytree(root, other)
    with no_write_attempts(): result = diff_project(root, str(other), against_kind='local', configuration_id=chain[-1]['id'])
    data = checked(result, bundle, members)
    assert data['configuration_scope']['state'] == 'evaluated'
    assert data['configuration_scope']['retained_ids'] == sorted(v['id'] for v in members)
    assert data['changed'] is False


@pytest.mark.parametrize('kind', ['document', 'release'])
@pytest.mark.parametrize('view', ['traceability', 'roadmap', 'specification', 'verification'])
def test_builtin_views_preserve_membership_and_required_full_project_proofs(tmp_path, kind, view):
    root, bundle, values, members, _ = extracted(tmp_path, kind, 'configuration')
    with no_write_attempts():
        result = dispatch_result(['render', '--view', view, '--project', str(root)])
    if view in ('specification', 'verification'):
        # Neither a global primary-document proof nor a computed verification
        # provider can be inferred from a transported subset.
        assert result.exit_code == 3 and result.as_dict()['result'] is None, result.as_dict()
    else:
        data = checked(result, bundle, members)['data']
        assert data['scope_descriptor'] == bundle.manifest['scope_descriptor']
        assert data['model_root_sha256'] == bundle.manifest['bundle_model_root_sha256']
        if view == 'traceability':
            assert set(data['records']) == {v['id'] for v in members}
            assert all(r['target_id'] != values[-2]['id'] for r in data['relations'].values())
        else:
            assert {r['artifact_id'] for r in data['roadmap']['artifacts']} == {v['id'] for v in members}
            assert data['readiness'] is None and not data['release_readiness_evaluated']


@pytest.mark.parametrize('operation', ['validate', 'project.inspect'])
def test_closed_release_subset_preserves_native_validation_inspection_contract(tmp_path, operation):
    origin = tmp_path / 'origin'; member = domain_value('release')
    inspection_project(origin, artifacts=[member])
    bundle = prepare_partial_bundle(origin, scope('release'))
    root = tmp_path / 'partial'; extract_bundle(bundle.source_bytes, root); shutil.rmtree(origin)
    with no_write_attempts():
        result = dispatch_result([*(['validate', '--partial'] if operation == 'validate' else
            ['project', 'inspect']), '--project', str(root)])
    assert result.exit_code == 0 and result.complete, result.as_dict()
    assert result.status.value == 'success'
    value = result.as_dict()
    assert 'partial_scope' not in value['summary']
    assert value['summary']['read_only'] and not value['summary']['project_complete']
    assert value['summary']['boundary_references'] == []
    if operation == 'validate':
        assert value['result']['checks_complete']
        assert value['result']['source_report']['identified_ids'] == [member['id']]
    else:
        assert value['result']['semantic']['artifact_counts']['release'] == 1


@pytest.mark.parametrize('operation', ['query', 'trace', 'why', 'impact', 'project.inspect'])
def test_marker_safety_precedes_simultaneous_open_transaction(tmp_path, operation):
    from specroad.authoring.project_inspection import inspect_project
    root, _, values, _, _ = extracted(tmp_path)
    (root / MANIFEST_NAME).unlink()
    (root / '.specroad/transactions/pending').mkdir(parents=True)
    with no_write_attempts():
        result = (inspect_project(root) if operation == 'project.inspect' else
            dispatch_result([operation, *([] if operation == 'query' else [values[-3]['id']]),
                *(['--direction', 'both', '--depth', '1'] if operation == 'trace' else []),
                '--project', str(root)]))
    assert result.exit_code == 7, result.as_dict()


@pytest.mark.parametrize('operation', ['render', 'view.render', 'diagram'])
@pytest.mark.parametrize('fault', ['bytes', 'context', 'marker', 'journal'])
def test_document_read_rechecks_before_result_delivery(tmp_path, operation, fault):
    root, _, values, _, chain = view_partial(tmp_path, configuration=True, projections=False)
    kwargs = {'start_id': values[-3]['id'], 'direction': 'both', 'max_depth': 3,
              'max_nodes': 100, 'max_edges': 100} if operation == 'diagram' else {}
    identifier = 'trace' if operation == 'diagram' else ref('VIEW') if operation == 'view.render' else values[0]['id']
    reader = document_read_steps(root, operation, identifier, **kwargs)
    assert next(reader) == 'loaded'
    if fault == 'marker': (root / MANIFEST_NAME).unlink()
    elif fault == 'journal': (root / '.specroad/transactions/pending').mkdir(parents=True)
    else:
        file = root / path(values[-3] if fault == 'bytes' else chain[-1])
        file.write_bytes(file.read_bytes() + b' ')
    with no_write_attempts():
        while True:
            try: next(reader)
            except StopIteration as done:
                result = done.value; break
    assert result.exit_code == {'bytes': 6, 'context': 6, 'marker': 7, 'journal': 5}[fault], result.as_dict()
    assert result.as_dict()['result'] is None


@pytest.mark.parametrize('context', ['review', 'configuration'])
def test_release_diagram_uses_verified_partial_seeds(tmp_path, context):
    root, bundle, values, members, _ = extracted(tmp_path, 'release', context)
    with no_write_attempts():
        result = read_document_project(root, 'diagram', 'release', start_id=values[0]['id'],
            direction='both', max_depth=20, max_nodes=100, max_edges=100)
    data = checked(result, bundle, members)['data']
    assert {n['artifact_id'] for n in data['nodes']} == {values[0]['id'], values[-3]['id']}
    assert data['selection']['scope']['descriptor']['boundary_policy'] == 'partial'


@pytest.mark.parametrize('side', ['before', 'after'])
def test_diff_rechecks_observed_bytes_after_final_yield(tmp_path, side):
    from specroad.query.project_diff import _diff_steps
    root, _, values, _, _ = extracted(tmp_path)
    other = tmp_path / 'other'; shutil.copytree(root, other)
    reader = _diff_steps(root, str(other), against_kind='local')
    assert next(reader) == 'loaded' and next(reader) == 'evaluated'
    selected = other if side == 'before' else root
    (selected / path(values[-3])).write_bytes(b'not JSON')
    with no_write_attempts(), pytest.raises(StopIteration) as stopped:
        next(reader)
    result = stopped.value.value
    assert result.exit_code == 6 and result.as_dict()['result'] is None, result.as_dict()


@pytest.mark.parametrize('mode', ['neither', 'both', 'huge_integer'])
def test_read_command_usage_never_ignores_ambiguous_or_unrepresentable_arguments(tmp_path, mode):
    root, _, values, _, _ = extracted(tmp_path)
    args = (['render'] if mode == 'neither' else ['render', values[0]['id'], '--view', 'traceability']
        if mode == 'both' else ['diagram', 'trace', values[-3]['id'], '--direction', 'both',
            '--max-depth', '9' * 10000, '--max-nodes', '100', '--max-edges', '100'])
    with no_write_attempts(): result = dispatch_result([*args, '--project', str(root)])
    assert result.exit_code == 2 and result.as_dict()['result'] is None, result.as_dict()


@pytest.mark.parametrize('mode', ['project', 'override', 'strict'])
def test_partial_validation_retains_resolved_policy_without_starting_extra_checks(tmp_path, mode):
    origin = tmp_path / 'origin'
    inspection_project(origin, artifacts=[domain_value('release')])
    configuration = json.loads((origin / 'specroad.json').read_bytes())
    configuration['validation_policy'] = {'fail_on': 'warning'}
    put(origin, 'specroad.json', canonical_json_bytes(configuration))
    bundle = prepare_partial_bundle(origin, scope('release'))
    root = tmp_path / 'partial'
    extract_bundle(bundle.source_bytes, root)
    shutil.rmtree(origin)
    before = inventory(root)
    flags = ['--fail-on', 'error'] if mode == 'override' else ['--strict'] if mode == 'strict' else []
    with no_write_attempts():
        result = dispatch_result(['validate', '--partial', '--project', str(root), *flags])
    assert result.exit_code == 0 and result.complete, result.as_dict()
    data = result.as_dict()['result']
    assert data['fail_on'] == ('error' if mode == 'override' else 'warning')
    assert data['strict_requested'] is (mode == 'strict')
    assert data['optional_lint_started'] is False
    assert inventory(root) == before


@pytest.mark.parametrize('family', ['lock', 'recover'])
def test_metadata_adapter_cannot_publish_a_stale_project_identity(tmp_path, monkeypatch, family):
    from specroad.changes import locking, recovery_read
    root, _, _, _, _ = extracted(tmp_path)
    module = locking if family == 'lock' else recovery_read
    name = 'inspect_project_lock' if family == 'lock' else 'inspect_recovery'
    native = getattr(module, name)

    def changing(*args, **kwargs):
        observation = native(*args, **kwargs)
        file = root / 'specroad.json'
        file.write_bytes(file.read_bytes() + b' ')
        return observation

    monkeypatch.setattr(module, name, changing)
    result = dispatch_result([family, 'status', '--project', str(root)])
    assert result.exit_code == 6 and result.as_dict()['result'] is None, result.as_dict()


@pytest.mark.parametrize('command', [
    ['validate'], ['bundle', 'create', '--scope', 'project', '--output', 'new.zip']])
def test_disallowed_partial_command_precedes_an_open_journal(tmp_path, command):
    root, _, _, _, _ = extracted(tmp_path)
    (root / '.specroad/transactions/pending').mkdir(parents=True)
    before = inventory(root)
    with no_write_attempts():
        result = dispatch_result([*command, '--project', str(root)])
    assert result.exit_code == 7 and result.as_dict()['result'] is None, result.as_dict()
    assert inventory(root) == before
