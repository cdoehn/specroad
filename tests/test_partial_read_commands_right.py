"""15.f.R: exact member population, boundary observations and read-only consumers."""
import json
import shutil

import pytest

from specroad.bundles import prepare_partial_bundle
from specroad.bundles.extraction import extract_bundle
from specroad.bundles._partial_read import partial_read_snapshot
from specroad.cli.application import dispatch_result, execute_request
from specroad.cli.result_schemas import validate_result_document
from specroad.query import (NormalizedQuery, query_project, trace_artifact, why_artifact,
                           impact_artifact, diff_project)
from specroad.query.read_work import ReadCommandWork
from specroad.documents.project_read import read_document_project
from specroad.model.canonical import canonical_json_bytes
from specroad.srx import LoadedGraph, EvaluationContext, SrxProgram, evaluate
from support.read_only import no_write_attempts, inventory
from support.srx import roots, expression_document, binary, field, literal
from support.srx_graph import count, incoming, has, reach
from test_partial_read_commands import extracted


def checked(result, bundle, members):
    value = result.as_dict()
    assert result.exit_code == 0 and result.complete, value
    assert result.status.value == 'partial'
    summary = value['summary']
    assert summary['partial_scope'] == 'partial_bundle_artifacts'
    assert summary['scope_descriptor'] == bundle.manifest['scope_descriptor']
    assert summary['boundary_references'] == bundle.manifest['boundary_references']
    assert summary['read_only'] and not summary['project_complete'] and not summary['origin_root_verified']
    assert summary['bundle_model_root_sha256'] == bundle.manifest['bundle_model_root_sha256']
    assert summary['origin_model_root_sha256'] == bundle.manifest['origin_model_root_sha256']
    payload = value['result']
    if 'coverage' in payload:
        assert payload['coverage']['source_count'] == len(members)
        assert payload['coverage']['relation_count'] == sum(len(m['relations']) for m in members)
    return payload


@pytest.mark.parametrize('kind', ['document', 'release'])
@pytest.mark.parametrize('context', ['review', 'configuration'])
@pytest.mark.parametrize('route', ['python', 'cli', 'request'])
def test_query_population_is_exactly_members(tmp_path, kind, context, route):
    root, bundle, _, members, hidden = extracted(tmp_path, kind, context)
    before = inventory(root)
    with no_write_attempts():
        if route == 'python': result = query_project(root)
        elif route == 'cli': result = dispatch_result(['query', '--project', str(root)])
        else: result = execute_request({'command_id': 'query', 'options': {'--project': str(root)}}).result
    data = checked(result, bundle, members)
    assert set(data) == {'items', 'total', 'offset', 'limit', 'returned', 'truncated'}
    assert {v['id'] for v in data['items']} == {v['id'] for v in members}
    assert data['total'] == data['returned'] == len(members)
    assert not ({v['id'] for v in hidden} & {v['id'] for v in data['items']})
    assert inventory(root) == before


@pytest.mark.parametrize('kind', ['document', 'release'])
@pytest.mark.parametrize('context', ['review', 'configuration'])
@pytest.mark.parametrize('limit', [0, 1, 100])
def test_query_pages_and_direct_boundary_filters(tmp_path, kind, context, limit):
    root, bundle, values, members, _ = extracted(tmp_path, kind, context)
    source = values[-3]
    query = NormalizedQuery(filters={'has_relation': ['duplicates']}, limit=limit)
    with no_write_attempts(): result = query_project(root, query)
    data = checked(result, bundle, members)
    assert data['total'] == 1 and data['returned'] == min(limit, 1)
    assert data['items'] == [] if limit == 0 else data['items'][0]['id'] == source['id']


@pytest.mark.parametrize('kind', ['document', 'release'])
@pytest.mark.parametrize('context', ['review', 'configuration'])
def test_srx_direct_boundary_is_not_a_reachable_artifact(tmp_path, kind, context):
    root, _, values, _, hidden = extracted(tmp_path, kind, context)
    snapshot = partial_read_snapshot(root)
    source, outside = values[-3:-1]
    graph = LoadedGraph(snapshot.records, rule_id='partial-test', partial=snapshot)
    def run(node, record=source):
        return evaluate(SrxProgram(expression_document(node), rule_id='partial-test'),
            EvaluationContext(roots(record), graph=graph, rule_id='partial-test'))
    with no_write_attempts():
        assert run(has(target_id=outside['id'], target_type='requirement')) is True
        assert run(count(['duplicates'])) == 1
        assert run(incoming(['duplicates'])) == 0
        assert run(reach(outside['id'], depth=20)) is False
        assert run(reach(source['id'], depth=0)) is True
        assert run(reach(outside['id'], depth=0)) is False
        # Original outside fields exist as proof, but they are never candidates.
        for value in hidden:
            assert value['id'] not in graph.artifact_ids


@pytest.mark.parametrize('kind', ['document', 'release'])
@pytest.mark.parametrize('context', ['review', 'configuration'])
@pytest.mark.parametrize('operation', ['trace', 'why', 'impact'])
def test_graph_readers_keep_original_population_and_reviews(tmp_path, kind, context, operation):
    root, bundle, values, members, _ = extracted(tmp_path, kind, context)
    source, outside = values[-3:-1]
    with no_write_attempts():
        if operation == 'trace': result = trace_artifact(root, source['id'], direction='both', depth=20)
        elif operation == 'why': result = why_artifact(root, source['id'])
        else: result = impact_artifact(root, source['id'])
    data = checked(result, bundle, members)
    validate_result_document('artifact-' + operation + '-v1', data)
    if operation == 'trace':
        assert outside['id'] not in {v['id'] for v in data['nodes']}
    elif operation == 'why':
        assert outside['id'] not in json.dumps(data['paths'])
    else:
        row = next(g for g in data['groups'] if g['relation_type'] == 'duplicates')['connections'][0]
        assert row['related_id'] == outside['id'] and row['related_present'] is False
        assert row['review_status'] == ('current' if context == 'review' else 'unreviewed')
        target = next(v for v in data['artifact_observations'] if v['artifact_id'] == outside['id'])
        assert target['present'] is False and all(v['state'] == 'unavailable' for v in target['fields'].values())


@pytest.mark.parametrize('operation', ['trace', 'why', 'impact'])
def test_explicit_outside_start_is_not_loaded_from_proof(tmp_path, operation):
    root, _, values, _, _ = extracted(tmp_path)
    with no_write_attempts():
        result = dispatch_result([operation, values[-2]['id'], '--project', str(root),
            *(['--direction', 'both', '--depth', '20'] if operation == 'trace' else [])])
    assert result.exit_code == 3 and result.as_dict()['result'] is None, result.as_dict()


@pytest.mark.parametrize('operation', ['query', 'trace', 'why', 'impact', 'diff'])
@pytest.mark.parametrize('fault', ['bytes', 'context', 'marker', 'journal'])
def test_read_freshness_and_safety_precedence(tmp_path, operation, fault):
    from test_bundle_verification_right import path, context_path
    from specroad.bundles.manifest import MANIFEST_NAME
    root, _, values, _, _ = extracted(tmp_path)
    kwargs = ({'artifact_id': values[-3]['id'], 'direction': 'both', 'depth': 2} if operation == 'trace' else
        {'artifact_id': values[-3]['id']} if operation in ('why', 'impact') else
        {'against': str(root), 'against_kind': 'local'} if operation == 'diff' else {})
    with ReadCommandWork(operation, root, **kwargs) as work:
        work.advance()
        if fault == 'marker': (root / MANIFEST_NAME).unlink()
        elif fault == 'journal': (root / '.specroad/transactions/pending').mkdir(parents=True)
        else:
            name = path(values[-3]) if fault == 'bytes' else context_path(values[-2])
            p = root / name; p.write_bytes(p.read_bytes() + b' ')
        with no_write_attempts():
            while not work.advance(): pass
        result = work.result
    assert result.exit_code == {'bytes': 6, 'context': 6, 'marker': 7, 'journal': 5}[fault], result.as_dict()
    assert result.as_dict()['result'] is None


@pytest.mark.parametrize('kind', ['document', 'release'])
@pytest.mark.parametrize('context', ['review', 'configuration'])
def test_diff_binds_member_sets_and_excludes_context(tmp_path, kind, context):
    root, bundle, _, members, hidden = extracted(tmp_path, kind, context)
    copy = tmp_path / 'other'; shutil.copytree(root, copy)
    with no_write_attempts(): result = diff_project(root, str(copy), against_kind='local')
    data = checked(result, bundle, members)
    assert data['changed'] is False
    assert data['inventory_delta'] == {'scope': 'supplied_artifact_sets', 'added_ids': [], 'removed_ids': []}
    before = result.as_dict()['summary']['before_source']
    assert before['comparison_scope'] == 'partial_bundle_artifacts'
    assert not any(v['id'] in json.dumps(data) for v in hidden)


@pytest.mark.parametrize('operation', ['render', 'diagram'])
def test_document_and_diagram_use_native_members(tmp_path, operation):
    root, bundle, values, members, _ = extracted(tmp_path)
    with no_write_attempts():
        if operation == 'render': result = read_document_project(root, 'render', values[0]['id'])
        else: result = read_document_project(root, 'diagram', 'trace', start_id=values[-3]['id'],
                direction='both', max_depth=20, max_nodes=100, max_edges=100)
    data = checked(result, bundle, members)['data']
    assert data['model_root_sha256'] == bundle.manifest['bundle_model_root_sha256']
    if operation == 'diagram':
        assert values[-2]['id'] not in {n['artifact_id'] for n in data['nodes']}


@pytest.mark.parametrize('kind', ['document', 'release'])
@pytest.mark.parametrize('operation', ['validate', 'project.inspect'])
def test_validation_and_inspection_do_not_claim_missing_gates(tmp_path, kind, operation):
    root, _, _, members, hidden = extracted(tmp_path, kind)
    with no_write_attempts(): result = dispatch_result([
        *(['validate', '--partial'] if operation == 'validate' else ['project', 'inspect']),
        '--project', str(root)])
    assert result.exit_code == 5, result.as_dict()
    data = result.as_dict()['result']
    if operation == 'validate':
        assert data['source_report']['source_count'] == len(members)
        assert set(data['source_report']['identified_ids']) == {v['id'] for v in members}
        assert data['checks_complete'] is False
    else:
        assert sum(data['semantic']['artifact_counts'].values()) == len(members)
        assert data['semantic']['diagnostic_summary'] is None
    assert result.as_dict()['summary']['project_complete'] is False


@pytest.mark.parametrize('command', [
    ['validate'], ['configuration', 'evaluate', 'SR-CFG-' + '0' * 26],
    ['roadmap', 'explain', 'SR-GOAL-' + '0' * 26], ['bundle', 'create', '--scope', 'project', '--output', 'new.zip']])
def test_other_project_commands_are_denied_on_partial(tmp_path, command):
    root, _, _, _, _ = extracted(tmp_path)
    before = inventory(root)
    with no_write_attempts(): result = dispatch_result([*command, '--project', str(root)])
    assert result.exit_code == 7, result.as_dict()
    assert inventory(root) == before
