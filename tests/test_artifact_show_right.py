"""Complete current Show results under stale hints, failures and real changes."""
from contextlib import ExitStack
import importlib
import json
import os
from unittest.mock import patch

import pytest

from specroad.changes import project_lock
from specroad.cli.application import dispatch_result
from specroad.graph.indices import RelationIndex
from specroad.graph.references import RelationReferences
from specroad.graph.relations import SourceRelations
from specroad.model.canonical import canonical_json_bytes
from specroad.model.paths import artifact_path
from specroad.query import show_artifact
from specroad.storage.project import ProjectSource
from specroad.storage.relation_index import build_project_relation_index
from support.domain import domain_value
from support.model import configuration_file, put
from support.project_locks import options
from support.read_only import inventory, make_project, no_write_attempts
from support.relations import aid, edge, rid

show_module = importlib.import_module('specroad.query.show')


def value(number, **changes):
    return domain_value('requirement', id=aid(number=number), **changes)


def save(root, artifact):
    return put(root, artifact_path(artifact['artifact_type'], artifact['id'], 'SR'),
               canonical_json_bytes(artifact))


def pair(root):
    a = value(1, relations=[edge(target=aid(number=2))]); b = value(2)
    make_project(root, a, b)
    return a, b


def hint(*artifacts):
    return RelationIndex(RelationReferences(tuple(SourceRelations(canonical_json_bytes(a)) for a in artifacts)))


@pytest.mark.parametrize('missing', ['source', 'edge'])
def test_partial_index_cannot_hide_real_incoming_source(tmp_path, missing):
    a, b = pair(tmp_path)
    partial = hint(b) if missing == 'source' else hint(dict(a, relations=[]), b)
    assert partial.for_artifact(b['id']) == ()
    before = inventory(tmp_path)
    with no_write_attempts(): result = show_artifact(tmp_path, b['id'], index=partial)
    assert result.exit_code == 0
    data = result.as_dict()['result']
    assert data['artifact'] == b and [r['stored_source'] for r in data['incoming']] == [a['id']]
    assert [r['relation_id'] for r in data['incoming']] == [rid()]
    assert data['coverage']['source_count'] == 2 and data['coverage']['relation_count'] == 1
    assert inventory(tmp_path) == before


def test_stale_project_index_includes_new_source_and_excludes_removed_source(tmp_path):
    a, b = pair(tmp_path); stale = build_project_relation_index(ProjectSource(tmp_path))
    save(tmp_path, value(3, relations=[edge(target=b['id'], number=3)]))
    (tmp_path / artifact_path('requirement', a['id'], 'SR')).unlink()
    before = inventory(tmp_path)
    with no_write_attempts(): result = show_artifact(tmp_path, b['id'], index=stale)
    assert result.exit_code == 0
    data = result.as_dict()['result']; assert [r['stored_source'] for r in data['incoming']] == [aid(number=3)]
    assert [r['relation_id'] for r in data['incoming']] == [rid(3)]
    assert data['coverage']['source_count'] == 2 and data['coverage']['relation_count'] == 1
    assert data['coverage']['observation_sha256'] != stale.binding.sha256 and inventory(tmp_path) == before


def test_retargeted_edge_is_not_returned_at_its_previous_endpoint(tmp_path):
    a, b = pair(tmp_path); stale = build_project_relation_index(ProjectSource(tmp_path))
    c = value(3); save(tmp_path, c); save(tmp_path, dict(a, relations=[edge(target=c['id'])]))
    before = inventory(tmp_path)
    old = show_artifact(tmp_path, b['id'], index=stale); current = show_artifact(tmp_path, c['id'], index=stale)
    assert old.exit_code == current.exit_code == 0
    assert old.as_dict()['result']['incoming'] == []
    assert [r['stored_source'] for r in current.as_dict()['result']['incoming']] == [a['id']]
    assert current.as_dict()['result']['incoming'][0]['stored_relation']['target'] == c['id']
    assert inventory(tmp_path) == before


def test_foreign_project_index_never_becomes_local_coverage(tmp_path):
    root = tmp_path / 'local'; other = tmp_path / 'other'; root.mkdir(); other.mkdir()
    a, b = pair(root); pair(other); foreign = build_project_relation_index(ProjectSource(other))
    save(root, value(3, relations=[edge(target=b['id'], number=3)]))
    before = inventory(tmp_path)
    with no_write_attempts(): result = show_artifact(root, b['id'], index=foreign)
    data = result.as_dict()['result']; assert result.exit_code == 0
    assert {r['stored_source'] for r in data['incoming']} == {a['id'], aid(number=3)}
    assert data['coverage']['source_count'] == 3
    assert data['coverage']['observation_sha256'] != foreign.binding.sha256
    assert result.project['project_root'] == str(root) and inventory(tmp_path) == before


def test_missing_selected_artifact_does_not_fall_back_to_previous_index(tmp_path):
    a, b = pair(tmp_path); stale = build_project_relation_index(ProjectSource(tmp_path))
    (tmp_path / artifact_path('requirement', b['id'], 'SR')).unlink(); before = inventory(tmp_path)
    with no_write_attempts(): result = show_artifact(tmp_path, b['id'], index=stale)
    assert result.exit_code == 3 and not result.complete and result.result is None
    assert inventory(tmp_path) == before


def test_invalid_unselected_current_source_never_uses_cached_success(tmp_path):
    a, b = pair(tmp_path); stale = build_project_relation_index(ProjectSource(tmp_path))
    put(tmp_path, artifact_path('requirement', a['id'], 'SR'), b'{invalid'); before = inventory(tmp_path)
    with no_write_attempts(): result = show_artifact(tmp_path, b['id'], index=stale)
    assert result.exit_code == 3 and not result.complete and result.result is None
    assert inventory(tmp_path) == before


def test_claimed_complete_untyped_index_is_rejected_without_side_effects(tmp_path):
    a, b = pair(tmp_path); before = inventory(tmp_path)
    with no_write_attempts(): result = show_artifact(tmp_path, b['id'], index={'complete': True, 'entries': []})
    assert result.exit_code == 3 and not result.complete and result.result is None
    assert any(d.rationale == 'invalid_relation_index_hint' for d in result.diagnostics)
    assert inventory(tmp_path) == before


def test_many_retired_incoming_sources_are_complete_despite_query_page_defaults(tmp_path):
    target = value(1); sources = [value(n, maturity='retired', relations=[edge(target=target['id'], number=n)])
                                 for n in range(2, 132)]
    make_project(tmp_path, target, *sources, resource_limits={'query_default_limit': 1, 'query_result_count': 1})
    before = inventory(tmp_path)
    with no_write_attempts(): result = show_artifact(tmp_path, target['id'])
    data = result.as_dict()['result']; assert result.exit_code == 0
    assert len(data['incoming']) == 130 and data['outgoing'] == []
    assert {r['stored_source'] for r in data['incoming']} == {a['id'] for a in sources}
    assert {r['relation_id'] for r in data['incoming']} == {rid(n) for n in range(2, 132)}
    assert data['coverage']['source_count'] == 131 and data['coverage']['relation_count'] == 130
    assert inventory(tmp_path) == before


def test_display_labels_do_not_replace_stable_identity_lookup(tmp_path):
    artifact = value(1, display_id='Readable label'); make_project(tmp_path, artifact)
    result = dispatch_result(['show', 'Readable label', '--project', str(tmp_path)])
    assert result.exit_code == 3 and not result.complete and result.result is None
    exact = show_artifact(tmp_path, artifact['id'])
    assert exact.exit_code == 0 and exact.as_dict()['result']['artifact'] == artifact


def test_legacy_artifact_ids_keep_full_inverse_relations(tmp_path):
    a = domain_value('requirement', id='SR-REQ-0001', id_scheme='legacy-sequential-v1',
                     relations=[edge(target='SR-REQ-0002')])
    b = domain_value('requirement', id='SR-REQ-0002', id_scheme='legacy-sequential-v1')
    make_project(tmp_path, a, b); before = inventory(tmp_path)
    result = dispatch_result(['show', b['id'], '--project', str(tmp_path)])
    assert result.exit_code == 0
    data = result.as_dict()['result']; assert data['artifact'] == b
    assert data['incoming'][0]['stored_source'] == a['id'] and data['incoming'][0]['relation_id'] == rid()
    assert inventory(tmp_path) == before


def test_same_size_and_timestamp_changes_are_read_from_current_bytes(tmp_path):
    a, b = pair(tmp_path); stale = build_project_relation_index(ProjectSource(tmp_path))
    path = tmp_path / artifact_path('requirement', b['id'], 'SR'); info = path.stat()
    old = path.read_bytes(); changed = old.replace(b'Sample', b'Latest'); assert len(changed) == len(old)
    path.write_bytes(changed); os.utime(path, ns=(info.st_atime_ns, info.st_mtime_ns)); before = inventory(tmp_path)
    with no_write_attempts(): result = show_artifact(tmp_path, b['id'], index=stale)
    assert result.exit_code == 0 and result.as_dict()['result']['artifact']['title'] == 'Latest'
    assert result.as_dict()['result']['coverage']['observation_sha256'] != stale.binding.sha256
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('change', ['artifact', 'new_source', 'removed_source', 'configuration', 'missing_configuration'])
def test_change_during_final_preflight_invalidates_all_project_results(tmp_path, change):
    a, b = pair(tmp_path); original = show_module._preflight; calls = 0; after_change = []
    def changing(source):
        nonlocal calls
        original(source); calls += 1
        if calls == 2:
            if change == 'artifact': save(tmp_path, dict(b, title='Latest'))
            elif change == 'new_source': save(tmp_path, value(3, relations=[edge(target=b['id'], number=3)]))
            elif change == 'removed_source': (tmp_path / artifact_path('requirement', a['id'], 'SR')).unlink()
            elif change == 'configuration': configuration_file(tmp_path, project_name='Changed')
            else: (tmp_path / 'specroad.json').unlink()
            after_change.append(inventory(tmp_path))
    with patch.object(show_module, '_preflight', changing): result = show_artifact(tmp_path, b['id'])
    assert calls == 2 and result.exit_code == 6 and not result.complete and result.result is None
    assert inventory(tmp_path) == after_change[0]
    if change == 'missing_configuration':
        assert any(d.rationale == 'show_source_disappeared' for d in result.diagnostics)


def test_source_disappearing_during_final_bound_read_is_a_conflict(tmp_path):
    a, b = pair(tmp_path); original_gate = show_module._preflight; original_read = ProjectSource.read_normative
    state = {'calls': 0, 'removed': False}; path = artifact_path('requirement', a['id'], 'SR'); after_change = []
    def gate(source):
        original_gate(source); state['calls'] += 1
    def reading(source, name, **kwargs):
        if state['calls'] == 2 and name == path and not state['removed']:
            (tmp_path / path).unlink(); state['removed'] = True; after_change.append(inventory(tmp_path))
        return original_read(source, name, **kwargs)
    with patch.object(show_module, '_preflight', gate), patch.object(ProjectSource, 'read_normative', reading):
        result = show_artifact(tmp_path, b['id'])
    assert state['removed'] and result.exit_code == 6 and not result.complete and result.result is None
    assert any(d.rationale == 'show_source_disappeared' for d in result.diagnostics)
    assert inventory(tmp_path) == after_change[0]


@pytest.mark.parametrize('blocker', ['writer', 'journal'])
def test_late_real_operational_blocker_prevents_payload_delivery(tmp_path, blocker):
    a, b = pair(tmp_path); (tmp_path / '.specroad/locks').mkdir(parents=True)
    original = show_module.read_project_relation_views; injected = []
    with ExitStack() as stack:
        def reading(*args, **kwargs):
            observed = original(*args, **kwargs)
            if blocker == 'writer': stack.enter_context(project_lock(tmp_path, **options()))
            else: put(tmp_path, '.specroad/transactions/late/journal.json', b'not read')
            injected.append(inventory(tmp_path)); return observed
        with patch.object(show_module, 'read_project_relation_views', reading):
            result = show_artifact(tmp_path, b['id'])
        assert len(injected) == 1 and result.exit_code == 5 and not result.complete and result.result is None
        assert inventory(tmp_path) == injected[0]


def test_read_permission_failure_stays_io_failure_without_private_host_details(tmp_path):
    a, b = pair(tmp_path); stale = build_project_relation_index(ProjectSource(tmp_path))
    original = ProjectSource.read_normative; path = artifact_path('requirement', a['id'], 'SR')
    def reading(source, name, **kwargs):
        if name == path: raise PermissionError('private-host-token-should-not-escape')
        return original(source, name, **kwargs)
    before = inventory(tmp_path)
    with patch.object(ProjectSource, 'read_normative', reading), no_write_attempts():
        result = show_artifact(tmp_path, b['id'], index=stale)
    assert result.exit_code == 5 and not result.complete and result.result is None
    assert 'private-host-token-should-not-escape' not in json.dumps(result.as_dict())
    assert inventory(tmp_path) == before


def test_symlink_source_is_rejected_without_following_or_repair(tmp_path):
    root = tmp_path / 'project'; root.mkdir(); a, b = pair(root)
    outside = put(tmp_path, 'outside.json', canonical_json_bytes(a))
    source = root / artifact_path('requirement', a['id'], 'SR'); source.unlink(); source.symlink_to(outside)
    before = inventory(tmp_path)
    with no_write_attempts(): result = show_artifact(root, b['id'])
    assert result.exit_code == 7 and not result.complete and result.result is None
    assert inventory(tmp_path) == before


def test_nested_project_is_not_combined_into_complete_show(tmp_path):
    a, b = pair(tmp_path); put(tmp_path, 'spec/requirements/specroad.json', b'{}'); before = inventory(tmp_path)
    with no_write_attempts(): result = show_artifact(tmp_path, b['id'])
    assert result.exit_code == 7 and not result.complete and result.result is None
    assert inventory(tmp_path) == before


def test_missing_unselected_endpoint_prevents_complete_answer_even_with_partial_hint(tmp_path):
    a, b = pair(tmp_path); save(tmp_path, dict(a, relations=[edge(target=aid(number=9))]))
    before = inventory(tmp_path)
    with no_write_attempts(): result = show_artifact(tmp_path, b['id'], index=hint(b))
    assert result.exit_code == 3 and not result.complete and result.result is None
    assert any(d.rationale == 'missing_relation_target' for d in result.diagnostics)
    assert inventory(tmp_path) == before


def test_noncanonical_symmetric_relation_is_not_silently_repaired(tmp_path):
    a, b = pair(tmp_path); save(tmp_path, dict(a, relations=[]))
    save(tmp_path, dict(b, relations=[edge('conflicts_with', a['id'])])); before = inventory(tmp_path)
    with no_write_attempts(): result = show_artifact(tmp_path, a['id'])
    assert result.exit_code == 3 and not result.complete and result.result is None
    assert any(d.rationale == 'noncanonical_symmetric_relation' for d in result.diagnostics)
    assert inventory(tmp_path) == before
