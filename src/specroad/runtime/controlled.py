"""Trusted synchronous drivers; native metrics never enter pure result values."""
import os

from .consumption import InvocationConsumption, ConsumptionError
from .control_points import PhaseBoundary


def _invocation(call):
    if type(call) is not InvocationConsumption or call._work._active is not call:
        raise ConsumptionError('An active owned invocation is required')


def _drive(steps, call):
    _invocation(call)
    try:
        while True:
            try:
                point = next(steps)
            except StopIteration as completed:
                return completed.value
            call.control(point)
    finally:
        steps.close()


def evaluate_srx(program, context, call):
    """Measure pure SRX control yields and return its unchanged observation."""
    from ..srx.evaluation import evaluation_steps
    _invocation(call)
    return _drive(evaluation_steps(program, context), call)


def fingerprint_file(boundary, path, call, *, block_size=65536):
    """Read a guarded payload in at most 64 KiB units, preserving all guards."""
    from ..model.paths import project_path
    from ..security.resource_access import opened_resource
    from ..storage.byte_binding import fingerprint_steps, validate_block_size
    _invocation(call)
    validate_block_size(block_size)
    with opened_resource(boundary, project_path(path)) as (descriptor, initial):
        return _drive(fingerprint_steps(lambda size: os.read(descriptor, size),
            initial.st_size, block_size=block_size), call)


def load_srx_graph(sources, call, *, rule_id):
    """Bracket actual graph construction; its source scope remains caller-bound."""
    from ..srx.graph import LoadedGraph
    _invocation(call)
    call.control(PhaseBoundary('graph_load', 'start'))
    result = LoadedGraph(sources, rule_id=rule_id)
    call.control(PhaseBoundary('graph_load', 'end'))
    return result


def publish_prepared(preflight, journal, call, *, held_lock, authority, gates=()):
    """Measure the existing native publication with its unchanged authorities.

    Soft events never request a pause inside publication. A successful return is
    still PublishedFiles in committing, requiring the existing receipt/finalizer.
    No retry, recovery or cleanup is inferred from an observation failure.
    """
    from ..changes.committing import publish_prepared_journal
    _invocation(call)
    call.control(PhaseBoundary('publication', 'start'))
    result = publish_prepared_journal(preflight, journal, held_lock=held_lock,
                                     authority=authority, gates=gates)
    call.control(PhaseBoundary('publication', 'end'))
    return result
