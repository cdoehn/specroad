"""Every retained unit survives relocation; current bytes beat cache hints."""
from hashlib import sha256
import json
import shutil

import pytest

from specroad.cli.application import execute_request
from specroad.work.packages import export_work_package, restore_work_package
from support.read_only import inventory
from test_acceptance_work_matrix import CASES, subject_case, complete_windows, business_projection
from test_acceptance_work_processes import distribution, run_reader
from test_query_read_integration import project_pair, request
from test_work_resume import recorded


@pytest.mark.parametrize('kind', CASES)
@pytest.mark.parametrize('first_profile', ['constrained', 'standard'])
def test_each_confirmed_prefix_restores_exactly_and_cannot_be_repeated_as_progress(
        recorded, tmp_path, kind, first_profile):
    store, initial, project, roots, registry, advance, finish, oracle = subject_case(tmp_path, kind)
    protected = inventory(project)
    generations = []
    def relocate(current, completed):
        saved = current.read()
        raw = export_work_package(current)
        old = current._location.path
        restored = restore_work_package(raw, expected_sha256=sha256(raw).hexdigest(),
            registry=registry, protected_roots=roots, directory=tmp_path / ('restored-' + str(completed)))
        assert restored.read().raw == saved.raw
        assert dict(restored.read().objects) == dict(saved.objects)
        assert export_work_package(restored) == raw
        shutil.rmtree(old)
        generations.append(saved.as_dict()['checkpoint_generation'])
        return restored
    store, measures = complete_windows(store, advance, first_profile=first_profile, after_step=relocate)
    final = finish(store); outcome = json.loads(final.outcome_bytes)
    assert final.command_exit_code == 0 and outcome['summary']['complete']
    oracle(outcome['result'])
    assert generations == list(range(1, len(initial.entries('tasks')) + 1))
    assert len(measures) == len(generations)
    before = inventory(tmp_path)
    assert finish(store).outcome_bytes == final.outcome_bytes
    assert inventory(tmp_path) == before and inventory(project) == protected


@pytest.mark.parametrize('kind', ['module', 'specroad.pyz'])
@pytest.mark.parametrize('fault', ['source', 'poison', 'deleted'])
@pytest.mark.parametrize('command', ['query', 'diff', 'why'])
def test_changed_original_bytes_and_poisoned_cache_never_substitute_for_current_reading(
        tmp_path, distribution, kind, fault, command):
    root, before, _ = project_pair(tmp_path)
    original = execute_request(request(command, root, before)).result.as_dict()
    actual = run_reader(distribution / kind, root, before, command, 'constrained', 'read', tmp_path, fault=fault)
    expected = execute_request(request(command, root, before)).result
    assert actual == business_projection(expected.as_dict())[0]
    if fault == 'source' and command in ('query', 'diff'):
        assert actual['result'] != original['result']
