"""Live changing runtime/input observations and exact semantic determinism."""
from contextlib import ExitStack
import shutil
from unittest.mock import patch

import pytest

from specroad.authoring import project_inspection as inspection
from specroad.authoring._inspection_snapshot import InspectionSnapshot
from specroad.authoring.project_inspection import inspect_project
from specroad.changes import project_lock
from specroad.model.canonical import canonical_json_bytes
from specroad.validation import ModelGate
from support.domain import domain_value
from support.inspection import inspection_project
from support.model import put
from support.model_validation import no_dependencies
from support.project_locks import options, orphan
from support.read_only import inventory, no_write_attempts


def semantic_bytes(outcome):
    result = outcome.as_dict()['result']
    return canonical_json_bytes({k: result[k] for k in ('format_version', 'semantic')})


def finding_gate(model, severity):
    # An explicit host predicate over actual model data; no approval or
    # substitute document/lifecycle/evidence service is supplied by this fixture.
    path = model.documents[0].path
    def check(context):
        return context.result([{'reason': 'forbidden_title', 'severity': severity,
            'artifact_id': identity, 'path': path, 'pointer': '/title'}
            for identity in context.subjects if context.artifact(identity)['title'] == 'forbidden'])
    return ModelGate('extension:inspection-titles', '1', no_dependencies, check)


@pytest.mark.parametrize('severity', ['error', 'warning', 'info'])
def test_semantic_findings_are_counted_without_runtime_or_approval(tmp_path, severity):
    root = tmp_path / 'source'; model = inspection_project(root, artifacts=[domain_value('goal', title='forbidden')])
    relocated = tmp_path / 'relocated'; shutil.copytree(root, relocated)
    put(relocated, '.specroad/cache/untrusted.json', b'not a model resource')
    put(relocated, '.specroad/transactions/receipts/retained.json', b'not a current transaction')
    put(relocated, 'generated/unrelated.json', b'not a model resource')
    gate = finding_gate(model, severity)
    before = inventory(root), inventory(relocated)
    with no_write_attempts():
        first = inspect_project(root, gates=(gate,))
        second = inspect_project(relocated, gates=(gate,))
    assert first.exit_code == second.exit_code == 0 and first.complete and second.complete
    result = first.as_dict()['result']
    assert result['semantic']['diagnostic_summary'] == {s: int(s == severity) for s in ('error', 'warning', 'info')}
    assert len(first.diagnostics) == 1 and first.diagnostics[0].path == model.documents[0].path
    assert semantic_bytes(first) == semantic_bytes(second)
    assert str(root).encode() not in semantic_bytes(first) and str(relocated).encode() not in semantic_bytes(second)
    assert result['runtime']['project_root'] != second.as_dict()['result']['runtime']['project_root']
    assert result['runtime']['open_transaction'] is None and second.as_dict()['result']['runtime']['open_transaction'] is None
    assert not first.as_dict()['summary']['approval_granted'] and not first.as_dict()['summary']['write_authorized']
    assert (inventory(root), inventory(relocated)) == before


def test_new_writer_during_inspection_remains_visible_and_invalidates_semantics(tmp_path):
    root = tmp_path / 'project'; inspection_project(root)
    native = InspectionSnapshot.verify_current; states = []
    with ExitStack() as stack:
        def enter_writer(snapshot):
            native(snapshot)
            held = stack.enter_context(project_lock(root, **options()))
            states.append((held, inventory(root)))
        with patch.object(InspectionSnapshot, 'verify_current', enter_writer):
            result = inspect_project(root)
        assert result.exit_code == 6 and not result.complete and len(states) == 1
        payload = result.as_dict()['result']
        assert set(payload['semantic'].values()) == {None}
        assert payload['runtime']['consistency_state'] == 'writer_active'
        assert payload['runtime']['writer_lock']['record'] == states[0][0].record.data
        assert result.project['model_root_sha256'] is None and states[0][0].check()
        assert inventory(root) == states[0][1]


@pytest.mark.parametrize('path,state', [('.specroad/transactions/new/journal.json', 'recovery_required'),
                                      ('.specroad/unclassified.json', 'unknown')])
def test_new_stable_operational_blocker_is_reported_after_model_read(tmp_path, path, state):
    root = tmp_path / 'project'; inspection_project(root); states = []
    native = InspectionSnapshot.verify_current
    def add_blocker(snapshot):
        native(snapshot); put(root, path, b'preserve this evidence'); states.append(inventory(root))
    with patch.object(InspectionSnapshot, 'verify_current', add_blocker):
        result = inspect_project(root)
    assert result.exit_code == 5 and not result.complete and len(states) == 1
    payload = result.as_dict()['result']
    assert set(payload['semantic'].values()) == {None}
    assert payload['runtime']['consistency_state'] == state and inventory(root) == states[0]
    if state == 'recovery_required':
        assert payload['runtime']['open_transaction']['unresolved_paths'] == ['.specroad/transactions/new']
        assert not payload['runtime']['open_transaction']['journal_contents_loaded']


def test_incoherent_runtime_observations_cannot_be_combined_into_a_healthy_snapshot(tmp_path):
    root = tmp_path / 'project'; inspection_project(root); native = inspection.observe_operational_preflight; calls = []
    def changing(boundary, **kwargs):
        result = native(boundary, **kwargs); calls.append(result)
        if len(calls) == 1:
            put(root, '.specroad/transactions/new.json', b'unresolved')
        return result
    with patch.object(inspection, 'observe_operational_preflight', changing), \
            patch.object(inspection, 'InspectionSnapshot', side_effect=AssertionError('no model read')):
        result = inspect_project(root)
    assert len(calls) == 2 and result.exit_code == 6 and not result.complete
    assert set(result.as_dict()['result']['semantic'].values()) == {None}
    runtime = result.as_dict()['result']['runtime']
    assert runtime['consistency_state'] == 'unknown'
    assert runtime['writer_lock'] == runtime['open_transaction'] == {'observation_status': 'unknown'}
    assert (root / '.specroad/transactions/new.json').read_bytes() == b'unresolved'


@pytest.mark.parametrize('source', ['configuration', 'artifact', 'profile', 'registry'])
def test_normative_change_during_final_runtime_read_cannot_escape_the_last_input_check(tmp_path, source):
    root = tmp_path / 'project'; model = inspection_project(root)
    path = {'configuration': 'specroad.json', 'artifact': model.documents[0].path,
            'profile': 'profiles/core.json', 'registry': model.configuration.data['language_registry']['path']}[source]
    native = inspection._runtime; calls = []
    def changing(boundary, project_id=None):
        result = native(boundary, project_id); calls.append(result)
        if len(calls) == 2:
            (root / path).write_bytes((root / path).read_bytes() + b' ')
        return result
    with patch.object(inspection, '_runtime', changing):
        result = inspect_project(root)
    assert len(calls) == 2 and result.exit_code == 6 and not result.complete
    assert set(result.as_dict()['result']['semantic'].values()) == {None}
    assert result.as_dict()['result']['runtime']['consistency_state'] == 'unknown'


def test_disappearing_configuration_after_the_final_runtime_read_is_a_conflict(tmp_path):
    root = tmp_path / 'project'; inspection_project(root); native = inspection._runtime; calls = []
    def disappearing(boundary, project_id=None):
        result = native(boundary, project_id); calls.append(result)
        if len(calls) == 2:
            (root / 'specroad.json').unlink()
        return result
    with patch.object(inspection, '_runtime', disappearing):
        result = inspect_project(root)
    assert result.exit_code == 6 and not result.complete
    assert set(result.as_dict()['result']['semantic'].values()) == {None}
    assert not (root / 'specroad.json').exists()


def test_previously_successful_description_does_not_hide_a_later_open_transaction(tmp_path):
    root = tmp_path / 'project'; inspection_project(root); first = inspect_project(root)
    assert first.exit_code == 0
    put(root, '.specroad/transactions/pending.json', b'not a completed receipt')
    before = inventory(root)
    with no_write_attempts(), patch.object(inspection, 'InspectionSnapshot', side_effect=AssertionError('no stale model')):
        second = inspect_project(root)
    assert second.exit_code == 5 and not second.complete
    payload = second.as_dict()['result']
    assert set(payload['semantic'].values()) == {None}
    assert payload['runtime']['consistency_state'] == 'recovery_required'
    assert payload['runtime']['open_transaction']['unresolved_paths'] == ['.specroad/transactions/pending.json']
    assert inventory(root) == before and first.as_dict()['result']['semantic']['model_root_sha256'] is not None


def test_native_orphan_writer_is_observed_without_lock_recovery(tmp_path):
    root = tmp_path / 'project'; inspection_project(root); record = orphan(root); before = inventory(root)
    with no_write_attempts(), patch.object(inspection, 'InspectionSnapshot', side_effect=AssertionError('no model read')):
        result = inspect_project(root)
    assert result.exit_code == 5 and not result.complete
    runtime = result.as_dict()['result']['runtime']
    assert runtime['consistency_state'] == 'recovery_required'
    assert runtime['writer_lock']['record'] == record and runtime['writer_lock']['owner_state'] == 'dead'
    assert runtime['open_transaction'] is None and inventory(root) == before
    assert set(result.as_dict()['result']['semantic'].values()) == {None}


def test_complete_operational_inventory_does_not_hide_later_unresolved_entries(tmp_path):
    root = tmp_path / 'project'; inspection_project(root)
    paths = ['.specroad/transactions/entry-' + str(i).zfill(2) + '.json' for i in range(25)]
    for path in reversed(paths): put(root, path, b'unresolved')
    before = inventory(root)
    with no_write_attempts(), patch.object(inspection, 'InspectionSnapshot', side_effect=AssertionError('no model read')):
        result = inspect_project(root)
    assert result.exit_code == 5
    observation = result.as_dict()['result']['runtime']['open_transaction']
    assert observation['inspection_complete'] and observation['unresolved_paths'] == paths
    assert not observation['journal_contents_loaded'] and inventory(root) == before


def test_host_cannot_remove_a_required_explicit_gate_during_source_loading(tmp_path):
    root = tmp_path / 'project'; model = inspection_project(root, artifacts=[domain_value('goal', title='forbidden')])
    gates = [finding_gate(model, 'error')]; native = inspection.InspectionSnapshot
    def mutate(canonical_root, profiles):
        gates.clear()
        return native(canonical_root, profiles)
    with patch.object(inspection, 'InspectionSnapshot', mutate):
        result = inspect_project(root, gates=gates)
    assert not gates and result.exit_code == 0 and result.complete
    assert result.as_dict()['result']['semantic']['diagnostic_summary'] == {'error': 1, 'warning': 0, 'info': 0}
    assert result.diagnostics[0].rationale == 'forbidden_title'
