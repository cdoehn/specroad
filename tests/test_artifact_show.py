"""Real artifact/graph results and read-only effects, never presentation."""
import importlib
import json
import shutil
from unittest.mock import patch

import pytest

from specroad.changes import project_lock
from specroad.cli.application import dispatch_result, execute_request
from specroad.cli.commands import builtin_registry
from specroad.model.canonical import canonical_json_bytes
from specroad.model.errors import ModelError
from specroad.model.paths import artifact_path
from specroad.model.schema_catalog import SchemaCatalog
from specroad.query import show_artifact
from support.domain import domain_value
from support.model import put
from support.processes import run_cli, run_python
from support.project_locks import options
from support.read_only import inventory, make_project, no_write_attempts
from support.relations import aid, edge, rid
from support.portable import build_distribution

show_module = importlib.import_module('specroad.query.show')


def project(root, *artifacts):
    root.mkdir()
    make_project(root, *artifacts)
    return root


def requirement(number, **changes):
    return domain_value('requirement', id=aid(number=number), **changes)


def test_target_with_only_incoming_edges_includes_complete_source_relation(tmp_path):
    target = requirement(2, statement='Vollständige Aussage: e\u0301 und é.',
                         extensions={'test.example': {'nested': [None, True, {'value': 3}]}})
    relation = edge('refines', target['id'], extensions={'test.example': {'note': 'kept'}})
    source = requirement(1, relations=[relation])
    root = project(tmp_path / 'project', target, source)
    result = show_artifact(root, target['id']); data = result.as_dict()['result']
    assert result.exit_code == 0 and result.complete
    assert data['artifact'] == target and data['outgoing'] == []
    assert data['incoming'] == [{'relation_id': rid(), 'type': 'refines',
        'source': target['id'], 'target': source['id'], 'inverse': True,
        'stored_source': source['id'], 'stored_relation': relation}]
    assert data['coverage']['source_count'] == 2 and data['coverage']['relation_count'] == 1
    assert data['coverage']['scope'] == 'current_project_artifacts'
    assert data['coverage']['validation_scope'] == 'relation_references_and_canonical_storage_only'
    assert not data['coverage']['atomic_snapshot']
    assert not result.as_dict()['summary']['full_semantic_validation']
    assert not result.as_dict()['summary']['approval_granted']


def test_canonical_alias_python_structured_and_isolated_cli_return_same_data(tmp_path):
    a = requirement(1, relations=[edge(target=aid(number=2))]); b = requirement(2)
    root = project(tmp_path / 'project', a, b); before = inventory(root)
    direct = show_artifact(root, b['id'])
    canonical = dispatch_result(['artifact', 'show', b['id'], '--project', str(root)])
    alias = dispatch_result(['show', b['id'], '--project', str(root), '--format=json'])
    structured = execute_request({'command_id': 'artifact.show', 'arguments': {'id': b['id']},
                                  'options': {'--project': str(root)}}).result
    process = run_cli(['show', b['id'], '--format=json'], root, capture=True)
    for result in (direct, canonical, alias, structured):
        assert result.exit_code == 0 and result.command == 'artifact.show'
        assert result.as_dict()['result'] == direct.as_dict()['result']
        assert result.project['project_id'] == 'sample' and result.project['project_root'] == str(root)
    assert process.returncode == 0 and json.loads(process.stdout)['result'] == direct.as_dict()['result']
    assert inventory(root) == before and not (root / '.git').exists()


def test_incoming_and_outgoing_are_independent_complete_directions(tmp_path):
    center = requirement(2, relations=[edge('depends_on', aid(number=3), number=2)])
    left = requirement(1, relations=[edge('refines', center['id'])]); right = requirement(3)
    root = project(tmp_path / 'project', right, center, left)
    result = show_artifact(root, center['id']); data = result.as_dict()['result']
    assert result.exit_code == 0 and data['artifact'] == center
    assert [(v['target'], v['type'], v['inverse']) for v in data['incoming']] == [(left['id'], 'refines', True)]
    assert [(v['target'], v['type'], v['inverse']) for v in data['outgoing']] == [(right['id'], 'depends_on', False)]
    assert data['outgoing'][0]['stored_relation'] == center['relations'][0]
    assert data['coverage']['source_count'] == 3 and data['coverage']['relation_count'] == 2


def test_superseded_by_keeps_the_one_stored_supersedes_identity(tmp_path):
    older = requirement(1); newer = requirement(2, relations=[edge('supersedes', older['id'])])
    root = project(tmp_path / 'project', newer, older); before = inventory(root)
    result = show_artifact(root, older['id']); row = result.as_dict()['result']['incoming'][0]
    assert result.exit_code == 0 and row['type'] == 'superseded_by'
    assert row['stored_relation'] == newer['relations'][0] and row['stored_relation']['type'] == 'supersedes'
    assert row['relation_id'] == rid() and row['stored_source'] == newer['id']
    assert result.as_dict()['result']['artifact']['relations'] == [] and inventory(root) == before


def test_symmetric_relationship_is_visible_from_either_endpoint_without_storage_copy(tmp_path):
    a = requirement(1, relations=[edge('conflicts_with', aid(number=2))]); b = requirement(2)
    root = project(tmp_path / 'project', b, a); before = inventory(root)
    left = show_artifact(root, a['id']); right = show_artifact(root, b['id'])
    assert left.exit_code == right.exit_code == 0
    outgoing = left.as_dict()['result']['outgoing'][0]; incoming = right.as_dict()['result']['incoming'][0]
    assert outgoing['relation_id'] == incoming['relation_id'] == rid()
    assert outgoing['stored_relation'] == incoming['stored_relation'] == a['relations'][0]
    assert outgoing['inverse'] is False and incoming['inverse'] is True and inventory(root) == before


def test_isolated_artifact_has_known_empty_directions_and_full_content(tmp_path):
    value = domain_value('goal'); root = project(tmp_path / 'project', value)
    result = show_artifact(root, value['id']); data = result.as_dict()['result']
    assert result.exit_code == 0 and data['artifact'] == value
    assert data['incoming'] == data['outgoing'] == []
    assert data['coverage']['source_count'] == 1 and data['coverage']['relation_count'] == 0


def test_actual_initialized_primary_document_is_read_without_specialist_approval(tmp_path):
    root = tmp_path / 'project'; created = dispatch_result(['init', str(root)])
    assert created.exit_code == 0
    identifier = created.as_dict()['result']['primary_document_id']; before = inventory(root)
    result = dispatch_result(['show', identifier, '--project', str(root)])
    assert result.exit_code == 0 and result.complete
    data = result.as_dict()['result']; path = artifact_path('document', identifier,
                                                          identifier.split('-')[0])
    assert data['artifact'] == json.loads((root / path).read_bytes())
    assert data['artifact']['document_role'] == 'primary_specification'
    assert data['incoming'] == data['outgoing'] == []
    assert not result.as_dict()['summary']['full_semantic_validation'] and inventory(root) == before


def test_query_never_attempts_writes_processes_stdin_entropy_or_lock_acquisition(tmp_path):
    value = requirement(1); root = project(tmp_path / 'project', value); before = inventory(root)
    with no_write_attempts(), patch('builtins.input', side_effect=AssertionError('stdin')), \
            patch('secrets.token_bytes', side_effect=AssertionError('entropy')), \
            patch('specroad.changes.locking.LockFiles.acquire', side_effect=AssertionError('lock')):
        direct = show_artifact(root, value['id'])
        cli = dispatch_result(['show', value['id'], '--project', str(root)])
    assert direct.exit_code == cli.exit_code == 0 and inventory(root) == before
    assert not (root / '.specroad').exists()


def test_returned_artifact_and_relations_cannot_mutate_sources_or_future_results(tmp_path):
    a = requirement(1, relations=[edge(target=aid(number=2))]); b = requirement(2)
    root = project(tmp_path / 'project', a, b); first = show_artifact(root, b['id'])
    expected = first.as_dict()['result']; value = first.as_dict()['result']
    value['artifact']['title'] = 'changed'; value['incoming'][0]['stored_relation']['target'] = a['id']
    value['incoming'].clear(); value['coverage']['source_count'] = 0
    assert first.as_dict()['result'] == show_artifact(root, b['id']).as_dict()['result'] == expected


def test_relation_order_matches_scan_and_is_independent_of_source_creation_order(tmp_path):
    target = requirement(3)
    a = requirement(1, relations=[edge('refines', target['id'], number=7)])
    b = requirement(2, relations=[edge('depends_on', target['id'], number=9)])
    root = project(tmp_path / 'project', target, b, a)
    indexed = show_artifact(root, target['id']); scanned = show_artifact(root, target['id'], strategy='scan')
    assert indexed.exit_code == scanned.exit_code == 0
    data = indexed.as_dict()['result']; assert data == scanned.as_dict()['result']
    assert [(v['type'], v['target'], v['relation_id']) for v in data['incoming']] == [
        ('depends_on', b['id'], rid(9)), ('refines', a['id'], rid(7))]
    moved = tmp_path / 'moved'; shutil.copytree(root, moved)
    other = show_artifact(moved, target['id']).as_dict()['result']
    assert {k: data[k] for k in ('artifact', 'incoming', 'outgoing')} == {
        k: other[k] for k in ('artifact', 'incoming', 'outgoing')}
    assert data['coverage']['observation_sha256'] != other['coverage']['observation_sha256']


def test_unknown_identity_fails_without_an_empty_success_answer(tmp_path):
    root = project(tmp_path / 'project', requirement(1)); before = inventory(root)
    for result in (show_artifact(root, aid(number=9)),
                   dispatch_result(['show', aid(number=9), '--project', str(root)])):
        assert result.exit_code == 3 and not result.complete and result.result is None
        assert any(d.rationale == 'unknown_relation_view_artifact' for d in result.diagnostics)
    assert inventory(root) == before


def test_broken_unselected_source_prevents_claim_of_complete_incoming_relations(tmp_path):
    target = requirement(2); root = project(tmp_path / 'project', target)
    put(root, artifact_path('requirement', aid(number=1), 'SR'), b'{broken')
    before = inventory(root); result = show_artifact(root, target['id'])
    assert result.exit_code == 3 and not result.complete and result.result is None
    assert inventory(root) == before


def test_actual_writer_blocks_public_api_and_cli_before_relation_loading(tmp_path):
    value = requirement(1); root = project(tmp_path / 'project', value)
    (root / '.specroad/locks').mkdir(parents=True)
    with project_lock(root, **options()):
        before = inventory(root)
        with patch.object(show_module, 'read_project_relation_views', side_effect=AssertionError('model read')), no_write_attempts():
            direct = show_artifact(root, value['id'])
            cli = dispatch_result(['show', value['id'], '--project', str(root)])
        assert direct.exit_code == cli.exit_code == 5
        assert direct.result is cli.result is None and not direct.complete and not cli.complete
        assert inventory(root) == before


def test_unresolved_journal_blocks_without_loading_or_repair(tmp_path):
    value = requirement(1); root = project(tmp_path / 'project', value)
    put(root, '.specroad/transactions/pending.json', b'not a readable journal'); before = inventory(root)
    with patch.object(show_module, 'read_project_relation_views', side_effect=AssertionError('model read')), no_write_attempts():
        result = show_artifact(root, value['id'])
    assert result.exit_code == 5 and not result.complete and result.result is None
    assert inventory(root) == before


def test_passive_generated_archive_and_cache_entries_do_not_become_graph_sources(tmp_path):
    value = requirement(1); root = project(tmp_path / 'project', value)
    expected = show_artifact(root, value['id']).as_dict()['result']
    for path in ('generated/forged.json', '.specroad/cache/relations.json', 'archive/forged.json', 'attachments/forged.json'):
        put(root, path, b'{broken')
    before = inventory(root); result = show_artifact(root, value['id'])
    assert result.exit_code == 0 and result.as_dict()['result'] == expected and inventory(root) == before


def test_schema_and_command_contract_are_retrievable_and_bound_to_actual_output(tmp_path):
    value = requirement(1); root = project(tmp_path / 'project', value)
    result = show_artifact(root, value['id']); data = result.as_dict()['result']
    catalog = SchemaCatalog(); catalog.validate('artifact-show-v1', data)
    command = builtin_registry().resolve('artifact.show')
    assert command.words == ('artifact', 'show') and command.aliases == (('show',),)
    assert command.preflight_profile.value == 'project_read' and command.effect_scope.value == 'none'
    assert command.requires_project and not command.requires_git
    assert command.protocol.result_schema == 'artifact-show-v1'
    data['format_version'] = '9.0.0'
    with pytest.raises(ModelError): catalog.validate('artifact-show-v1', data)
    data = result.as_dict()['result']; del data['incoming']
    with pytest.raises(ModelError): catalog.validate('artifact-show-v1', data)
    assert dispatch_result(['show', '--project', str(root)]).exit_code == 2


def test_moved_module_and_zipapp_execute_the_real_show_alias(tmp_path):
    a = requirement(1, relations=[edge(target=aid(number=2))]); b = requirement(2)
    root = project(tmp_path / 'project', a, b)
    build_distribution(tmp_path / 'build'); (tmp_path / 'build').rename(tmp_path / 'moved')
    expected = show_artifact(root, b['id']).as_dict()['result']; before = inventory(root)
    for distribution in (tmp_path / 'moved/module', tmp_path / 'moved/specroad.pyz'):
        body = 'import sys;sys.path.insert(0,sys.argv[1]);from specroad.cli import main;sys.exit(main(sys.argv[2:]))'
        completed = run_python(['-I', '-S', '-B', '-c', body, str(distribution),
                               'show', b['id'], '--format=json'], root, capture=True)
        assert completed.returncode == 0, completed.stderr
        assert json.loads(completed.stdout)['result'] == expected
    assert inventory(root) == before
