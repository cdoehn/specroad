"""Trusted synchronous drivers; native metrics never enter pure result values."""
from io import FileIO

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
    """Hash a guarded payload with one reusable, at most 64 KiB buffer."""
    return _fingerprint_file(boundary, path, call, block_size=block_size)


def _fingerprint_file(boundary, path, call, *, block_size, attempt=None):
    from ..model.paths import project_path
    from ..security.resource_access import opened_resource
    from ..storage.byte_binding import (allocate_transfer_buffer,
                                       fingerprint_into_steps, validate_block_size)
    _invocation(call)
    validate_block_size(block_size)
    if attempt is not None:
        attempt['stage'] = 'guarded_open'
    with opened_resource(boundary, project_path(path)) as (descriptor, initial):
        if attempt is None:
            buffer = allocate_transfer_buffer(block_size)
        else:
            attempt['stage'] = 'buffer_allocation'
            buffer = allocate_transfer_buffer(block_size, attempts=attempt['buffer_attempts'])
        capacity = len(buffer)
        call.account_bytes('memory', capacity)
        try:
            if attempt is not None:
                attempt['stage'] = 'bounded_hash_step'
                attempt['buffer_bytes'] = capacity
            # The guard retains ownership and rechecks this very descriptor.
            with FileIO(descriptor, 'rb', closefd=False) as source:
                result = _drive(fingerprint_into_steps(source.readinto, initial.st_size, buffer), call)
        finally:
            del buffer
            call.account_bytes('memory', capacity, release=True)
        if attempt is not None:
            attempt['stage'] = 'source_revalidation'
    return result


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
