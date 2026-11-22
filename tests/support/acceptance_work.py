"""20.f: complete native results, durable progress and separate measurements.

Small complete inputs complement the mandatory large/portable/native-transport
regressions; they never substitute for the full Work/Annex-W.7 corpus.
"""
from functools import partial
from hashlib import sha256
import json
from pathlib import Path

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
