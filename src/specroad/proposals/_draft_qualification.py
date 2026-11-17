"""Native outer-draft qualification, separate from authoring plan conversion."""
from dataclasses import replace
from ..qualification.services import native_services
from ..validation import ModelGate
from ..validation.values import HOOK_NAMES
from ._review_checks import _initial_inputs
from ._create_control import GATE
from .values import require


def publication_gates(model, proposal, *, services=None):
    """Requalify the complete actual outer target on every native writer gate."""
    from ..qualification.project import validate_project
    services = native_services(services)
    original = proposal.original
    files = {**model.source_files, original.path: original.source_bytes}
    expected = {d.path: d.content for d in model.documents}
    expected[original.path] = original.source_bytes
    def provider(target, value):
        if value.binding.proposal_id == original.binding.proposal_id:
            require(value.source_bytes == original.source_bytes,
                    'proposal_create_record_changed', exit_code=6)
            return _initial_inputs(target, value, replace(services, proposal_inputs=None))
        return _initial_inputs(target, value, services)
    actual_services = replace(services, proposal_inputs=provider)
    def check(context):
        require({d.path: d.content for d in context.documents} == expected,
                'proposal_create_outer_target_changed', exit_code=6)
        validate_project(files, services=actual_services)
        return context.result()
    def dependencies(context):
        return context.dependency_result({key: list(context.all_ids) for key in context.subjects})
    return tuple(ModelGate(name, 'native-proposal-create-v1', dependencies, check,
        model._sources_sha256) for name in (
            *(name for name in HOOK_NAMES if name not in ('profile_lint', 'language_policy')),
            GATE, 'extension:target-resources'))
