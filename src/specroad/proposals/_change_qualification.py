"""Fresh complete qualification shared by content preparation and publication."""
from dataclasses import replace
from ..validation import ModelGate
from ..validation.values import HOOK_NAMES
from ._change_control import GATE
from ._review_checks import _initial_inputs
from .context import ProposalContext
from .history import ProposalInputs
from .values import require


def _gates(model, revision, services):
    from ..qualification.project import validate_project
    before, after = revision.before, revision.after
    files = {**model.source_files, after.path: after.source_bytes}
    expected = {d.path: (after.source_bytes if d.path == after.path else d.content)
                for d in model.documents}

    def provider(target, value):
        if value.binding.proposal_id != after.binding.proposal_id:
            return _initial_inputs(target, value, services)
        require(value.source_bytes == after.source_bytes, 'proposal_change_target_changed', exit_code=6)
        # Reobserve host provenance on every check, not only during preparation.
        old = _initial_inputs(model, before, services)
        require(type(old) is ProposalInputs and old.originals[-1].source_bytes == before.source_bytes,
                'proposal_native_inputs_required')
        if not revision.changed:
            return old
        return ProposalInputs((*old.originals, after),
            (*old.contexts, ProposalContext(after, model)), old.reviews, old.controls,
            old.verifier, old.publications)

    selected = replace(services, proposal_inputs=provider)

    def check(context):
        require({d.path: d.content for d in context.documents} == expected,
                'proposal_change_outer_target_changed', exit_code=6)
        validate_project(files, services=selected)
        return context.result()

    def dependencies(context):
        return context.dependency_result({key: list(context.all_ids) for key in context.subjects})

    return tuple(ModelGate(name, 'native-proposal-change-v1', dependencies, check,
        model._sources_sha256) for name in (
            *(name for name in HOOK_NAMES if name not in ('profile_lint', 'language_policy')),
            GATE, 'extension:target-resources'))
