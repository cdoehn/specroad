"""20.f: complete native results and diagnostics across real resource windows."""
from hashlib import sha256
import json

import pytest

from specroad.runtime.consumption import WorkConsumption
from specroad.work.packages import export_work_package, restore_work_package
from support.acceptance_work import CASES, subject_case, business_projection, complete_windows
from support.read_only import inventory
from test_work_resume import recorded


@pytest.mark.parametrize('kind', CASES)
@pytest.mark.parametrize('first_profile', ['constrained', 'standard'])
def test_complete_native_data_and_diagnostics_survive_every_profile_window(recorded, tmp_path, kind, first_profile):
    store, initial, project, roots, registry, advance, finish, oracle = subject_case(tmp_path, kind)
    protected = inventory(project)
    raw = export_work_package(store)
    reference = restore_work_package(raw, expected_sha256=sha256(raw).hexdigest(),
        registry=registry, protected_roots=roots, directory=tmp_path / 'reference')
    ledger = WorkConsumption()
    while reference.read().entries('remaining'):
        call = ledger.begin({'--resource-profile': 'standard'})
        try:
            step = advance(reference, call, max_units=len(initial.entries('tasks')))
            assert step.executed_unit_ids
        finally:
            call.finish()
    expected = finish(reference).outcome_bytes
    store, measurements = complete_windows(store, advance, first_profile=first_profile)
    previous = store.read()
    final = finish(store)
    document = json.loads(final.outcome_bytes)
    assert final.command_exit_code == 0 and document['summary']['complete'] is True
    oracle(document['result'])
    assert final.manifest.as_dict()['state'] == 'completed'
    assert final.manifest.as_dict()['checkpoint_generation'] == previous.as_dict()['checkpoint_generation'] + 1
    assert len(measurements) == len(initial.entries('tasks'))
    assert all(m['invocation']['measured']['wall_ns']['value'] is not None for m in measurements)
    saved = inventory(tmp_path)
    assert finish(store).outcome_bytes == final.outcome_bytes
    assert inventory(tmp_path) == saved and inventory(project) == protected
    assert business_projection(document)[0] == business_projection(json.loads(expected))[0]
    assert final.outcome_bytes == expected
