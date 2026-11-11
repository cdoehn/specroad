"""Historical reuse never lends success to changed bytes or live sources."""
from dataclasses import replace

import pytest

from specroad.merge._recorded import verify_observation
from specroad.merge._recorded_values import RecordedSource
from specroad.merge.relation_inputs import _sources
from specroad.model.canonical import canonical_json_bytes as jcs
from specroad.model.errors import ModelError
from specroad.recovery._owned_checks import owned_checks
from specroad.snapshots import SourceSnapshot
from test_merge_reuse import sources_at, recorded, observe_inventory


@pytest.mark.parametrize('change', ['binding', 'file'])
def test_changed_historical_inputs_are_rejected_each_time_without_poisoning_valid_proof(tmp_path, monkeypatch, change):
    source = recorded(sources_at(tmp_path).ours)
    if change == 'binding':
        binding = source.binding
        binding['model_root_sha256'] = '0' * 64
        damaged = replace(source, _binding=jcs(binding))
    else:
        files = source.files
        files['attachments/owned.bin'] += b'changed'
        damaged = replace(source, _files=tuple(sorted(files.items())))
    calls = observe_inventory(monkeypatch)

    @owned_checks
    def operation():
        source.verify_owned()
        for _ in range(2):
            with pytest.raises(ModelError):
                damaged.verify_owned()
        source.verify_owned()

    operation()
    assert len(calls) == 3


def test_nonimmutable_internal_file_container_is_never_cached(tmp_path, monkeypatch):
    source = recorded(sources_at(tmp_path).ours)
    mutable = RecordedSource(source._binding, list(source._files))
    calls = observe_inventory(monkeypatch)

    @owned_checks
    def operation():
        mutable.verify_owned()
        mutable.verify_owned()

    operation()
    assert len(calls) == 2


def test_live_sources_keep_current_verification_inside_historical_reuse_scope(tmp_path, monkeypatch):
    sources = sources_at(tmp_path)
    native, calls = SourceSnapshot.verify_current, []

    def observed(source):
        calls.append(source)
        return native(source)

    monkeypatch.setattr(SourceSnapshot, 'verify_current', observed)

    @owned_checks
    def operation():
        verify_observation(sources.ours)
        verify_observation(sources.ours)
        _sources(sources)

    operation()
    assert calls == [sources.ours, sources.ours, sources.base, sources.ours, sources.theirs]


def test_a_new_relation_observation_rejects_changes_to_a_previously_read_source(tmp_path):
    sources = sources_at(tmp_path)

    @owned_checks
    def operation():
        _sources(sources)
        attachment = tmp_path / 'source/attachments/owned.bin'
        attachment.write_bytes(attachment.read_bytes() + b'changed')
        with pytest.raises(ModelError):
            _sources(sources)

    operation()
