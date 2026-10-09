"""Restore bound normative work data, without current target authorization."""

from .manifest import read_work_manifest
from .resume import _require, _compatible_read


def check_initial_normative(store, registry, build):
    """Check the caller's independent initial binding against current contracts."""
    _require(store._initial.as_dict()['tool_build'] == build, 'incompatible_runtime_build')
    initial = _compatible_read(read_work_manifest, store._initial.raw, store._initial.objects,
                               registry=registry, expected_tool_build=build)
    _require(initial.as_dict()['command_class'] == 'normative_write'
             and initial.as_dict()['checkpoint_generation'] == 0
             and not initial.entries('completed'), 'initial_normative_work_required')


def restore_normative_checkpoint(store, held, registry, build):
    """Read the complete saved chain under the caller-retained work mutex."""
    pointer = store._pointer(held)
    _require(pointer is not None, 'published_work_required')
    current = _compatible_read(store._read_chain, held, pointer[0])
    current = _compatible_read(read_work_manifest, current.raw, current.objects,
                               registry=registry, expected_tool_build=build)
    return pointer, current
