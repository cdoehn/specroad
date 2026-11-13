"""Fresh approval and native target qualification, not a fabricated receipt."""
from ..validation import ModelGate
from ..validation.values import HOOK_NAMES
from ._apply_control import GATE, assessment, operation_proof, read_apply_observation
from .context import ProposalContext
from .values import require


def gates(snapshot, original, target, after, operation, services):
    from ..recovery._validation import validate_project
    raw, _ = operation_proof(operation)
    # Prove exact physical/control reduction without pretending a transaction
    # has already happened. Persisted applied readers still need real receipts.
    read_apply_observation(after, ProposalContext(original, snapshot.model))
    expected = {d.path: d.content for d in target.documents}
    remainder = {p: b for p, b in target.source_files.items() if p != after.path}

    def dependencies(context):
        return context.dependency_result({identity: list(context.all_ids) for identity in context.subjects})

    def check(context):
        require({d.path: d.content for d in context.documents} == expected,
                'proposal_apply_target_changed', exit_code=6)
        require(assessment(snapshot, original, services) == raw,
                'proposal_apply_authority_changed', exit_code=6)
        # The old approved model proves all original controls. The complete
        # computed target proves all remaining artifacts and control histories.
        # No host callback can attest away a changed inner plan or target byte.
        validate_project(snapshot.raw, services=services)
        validate_project(remainder, services=services)
        return context.result()

    names = (*(name for name in HOOK_NAMES if name not in ('profile_lint', 'language_policy')),
             GATE, 'extension:target-resources', 'extension:evidence-record', 'extension:evidence-import')
    return tuple(ModelGate(name, 'proposal-apply-native-v1', dependencies, check,
                           snapshot.model._sources_sha256) for name in names)
