"""Explicit in-memory transformations and independent-vector checks; no publication."""
import json

from .contracts import MigrationError, ResolvedStep, _encoded
from .registry import MigrationRegistry


def execute_step(resolved, value):
    """Invoke one trusted implementation on detached JSON values; never publish."""
    if type(resolved) is not ResolvedStep:
        raise MigrationError('invalid_step')
    program = resolved.transformation
    before = _encoded(value)
    phase = 'precondition'
    try:
        if program.precondition(json.loads(before)) is not True:
            raise MigrationError('precondition_failed', step_id=resolved.step.step_id)
        phase = 'transformation'
        after = _encoded(program.transform(json.loads(before)))
        phase = 'postcondition'
        if program.postcondition(json.loads(before), json.loads(after)) is not True:
            raise MigrationError('postcondition_failed', step_id=resolved.step.step_id)
    except MigrationError:
        raise
    except Exception as error:
        raise MigrationError(phase + '_failed', step_id=resolved.step.step_id) from error
    return json.loads(after)


def verify_vectors(registry):
    """Explicit behavior verification, used by Apply tests; never during admission."""
    if type(registry) is not MigrationRegistry:
        raise MigrationError('invalid_registry')
    for step in registry.steps:
        for reverse in (False, True) if step.backward is not None else (False,):
            edge = ResolvedStep(step, reverse)
            for vector in edge.transformation.vectors:
                actual = execute_step(edge, vector.before)
                if _encoded(actual) != vector._after:
                    raise MigrationError('vector_mismatch', step_id=step.step_id)
                if step.backward is not None:
                    restored = execute_step(ResolvedStep(step, not reverse), actual)
                    if _encoded(restored) != vector._before:
                        raise MigrationError('reverse_not_lossless', step_id=step.step_id)
    return None
