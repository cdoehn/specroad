"""Saved Baseline plan binding and host-owned native gate preparation.

The Work store and writer remain the common native services. Only fresh
publication resolves current gates; confirmed receipt replay needs no provider.
"""
from ..model.errors import ModelError


def _baseline_work_plan(store):
    from ..work._normative_binding import read_plan
    from ..work.checkpoints import CheckpointStore
    if type(store) is not CheckpointStore:
        raise ModelError('baseline_work_store_required')
    plan = read_plan(store._initial.as_dict(), store._initial.objects)
    value = plan.data
    operations = value['operations']
    if len(operations) != 1 or operations[0]['op'] != 'baseline_create':
        raise ModelError('baseline_work_plan_required')
    return value


def _baseline_work_inputs(store, model, gates):
    from ..authoring.plans import _execution_inputs
    value = _baseline_work_plan(store)
    _, policy, gates = _execution_inputs(model, 'baseline.create', value['operations'],
        value['actor'], value['planned_at'], gates)
    return policy, gates


def _baseline_publication_inputs(store, model, gates):
    from ..authoring.plans import _execution_inputs, _execution_policy
    from ..changes.request_ids import AuthoringError
    value = _baseline_work_plan(store)
    if type(gates) not in (list, tuple):
        raise AuthoringError('explicit_authoring_gates_required')
    gates = tuple(gates)

    def prepare_gates():
        return _execution_inputs(model, 'baseline.create', value['operations'],
            value['actor'], value['planned_at'], gates)[2]

    return _execution_policy('baseline.create'), prepare_gates
