"""Native historical proof reuse and single-model relation observations."""
import json

from specroad.merge import SourceRequest, load_merge_sources
from specroad.merge._recorded_values import RecordedSource
from specroad.merge import _recorded_values as values
from specroad.merge.relation_inputs import _sources
from specroad.model.canonical import canonical_json_bytes as jcs
from specroad.recovery._owned_checks import owned_checks
from specroad.snapshots import inventory as observations
from support.languages import small_restore_registry
from support.read_only import inventory, no_write_attempts
from support.merge_relations import edge
from test_project_bundle import project


def sources_at(tmp_path):
    root = tmp_path / 'source'
    snapshot = project(root, language_registry=small_restore_registry())
    path = next(name for name in snapshot.raw if name.startswith('spec/goals/'))
    goal = json.loads(snapshot.raw[path])
    goal['relations'] = [edge()]
    (root / path).write_bytes(jcs(goal))
    return load_merge_sources(*(SourceRequest(root) for _ in range(3)))


def recorded(source):
    return RecordedSource(jcs(source.binding), tuple(sorted(source.files.items())))


def observe_inventory(monkeypatch):
    native, calls = values.source_resource_rows, []

    def observed(source):
        calls.append((source._binding, source._files))
        return native(source)

    monkeypatch.setattr(values, 'source_resource_rows', observed)
    return calls


def test_recorded_proofs_are_reused_only_inside_one_outer_invocation(tmp_path, monkeypatch):
    source = recorded(sources_at(tmp_path).ours)
    calls = observe_inventory(monkeypatch)

    @owned_checks
    def operation():
        source.verify_owned()
        RecordedSource(source._binding, source._files).verify_owned()
        source.files.clear()
        source.binding.clear()
        source.verify_owned()

    operation()
    assert len(calls) == 1
    operation()
    assert len(calls) == 2
    source.verify_owned()
    source.verify_owned()
    assert len(calls) == 4


def test_relations_use_one_qualified_inventory_model_per_role(tmp_path, monkeypatch):
    sources = sources_at(tmp_path)
    before = inventory(tmp_path)
    native, calls = observations.owned_payload_model, []

    def observed(*args, **kwargs):
        model = native(*args, **kwargs)
        calls.append(model)
        return model

    monkeypatch.setattr(observations, 'owned_payload_model', observed)
    with no_write_attempts():
        rows, relations, owners = _sources(sources)
    assert len(calls) == 3
    assert rows['base'] == rows['ours'] == rows['theirs']
    assert relations['base'] == relations['ours'] == relations['theirs']
    assert len(relations['base']) == 1
    assert owners['base'] == owners['ours'] == owners['theirs']
    assert inventory(tmp_path) == before
