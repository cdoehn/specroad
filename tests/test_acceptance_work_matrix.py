"""20.f: complete native results, durable progress and separate measurements.

Small complete inputs complement the mandatory large/portable/native-transport
regressions; they never substitute for the full Work/Annex-W.7 corpus.
"""
from functools import partial
from hashlib import sha256
import json
from pathlib import Path

import pytest

from specroad.documents.work import advance_document_work, finalize_document_work
from specroad.exchange import prepare_import_plan
from specroad.exchange.import_work import advance_import_work, finalize_import_work
from specroad.model.canonical import canonical_json_bytes
from specroad.runtime.consumption import WorkConsumption
from specroad.security import ProjectBoundary
from specroad.work.evaluation import advance_evaluation_work, finalize_evaluation_work
from specroad.work.packages import export_work_package, restore_work_package
from support import document_work, import_work, work_evaluation
from support.read_only import inventory
from test_document_work import assert_native
from test_work_resume import recorded

CASES = ('evaluation', 'document', 'csv', 'ndjson', 'reqif', 'reqifz')


def subject_case(root, kind):
    """Retain actual host services; no saved code or fabricated validation."""
    if kind == 'evaluation':
        inputs, jobs, _, project, boundaries, initial, _, store = work_evaluation.setup(root)
        registry = work_evaluation.registry()
        expected = work_evaluation.direct(inputs, jobs)
        def oracle(result):
            assert result['results'] == expected
            assert result['source_scope'] == 'explicit_saved_model'
        advance = partial(advance_evaluation_work, registry=registry)
        finish = partial(finalize_evaluation_work, registry=registry)
        protected = tuple(boundaries.values())
    elif kind == 'document':
        model, project, initial, store = document_work.setup(root)
        registry = document_work.registry()
        oracle = partial(assert_native, supplied=model)
        advance = partial(advance_document_work, registry=registry)
        finish = partial(finalize_document_work, registry=registry)
        protected = (ProjectBoundary(project),)
    else:
        model, candidates, options, initial, store = import_work.setup(root, kind)
        expected = prepare_import_plan(model, candidates, **options)
        assert expected.plan_valid, expected.data['diagnostics']
        project = Path(model.binding.source_root)
        registry = import_work.registry()
        def oracle(result):
            assert canonical_json_bytes(result['import_plan']) == expected.canonical_bytes
            assert result['import_completed'] is False and result['write_authorized'] is False
        advance = partial(advance_import_work, registry=registry,
                          policy=options['policy'], gates=options['gates'])
        finish = partial(finalize_import_work, registry=registry)
        protected = (ProjectBoundary(project),)
    return store, initial, project, protected, registry, advance, finish, oracle


def business_projection(document):
    """Remove only explicitly operational runtime measurements, never findings."""
    value = json.loads(canonical_json_bytes(document))
    runtime = value['summary'].pop('runtime', None)
    return value, runtime


def complete_windows(store, advance, *, first_profile, after_step=None):
    ledger = WorkConsumption()
    tasks = [row['unit_id'] for row in store.read().entries('tasks')]
    executed, measurements = [], []
    while store.read().entries('remaining'):
        previous = store.read()
        profile = first_profile if len(executed) % 2 == 0 else (
            'standard' if first_profile == 'constrained' else 'constrained')
        call = ledger.begin({'--resource-profile': profile, '--step-cpu-ms': 1,
                             '--step-wall-ms': 1})
        try:
            step = advance(store, call, max_units=1)
        finally:
            measurement = call.finish()
        assert list(step.reused_unit_ids) == executed
        assert len(step.executed_unit_ids) == 1
        assert step.executed_unit_ids[0] not in executed
        executed.extend(step.executed_unit_ids)
        assert step.manifest.as_dict()['checkpoint_generation'] == previous.as_dict()['checkpoint_generation'] + 1
        assert len(step.manifest.entries('remaining')) == len(tasks) - len(executed)
        assert measurement['invocations_recorded'] == len(executed)
        assert measurement['invocation']['controls']['phases']['work_unit'] == {'start': 1, 'end': 1}
        measurements.append(measurement)
        if after_step is not None:
            store = after_step(store, len(executed))
    assert len(executed) == len(set(executed)) == len(tasks)
    assert set(executed) == set(tasks)
    return store, measurements


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
