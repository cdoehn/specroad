"""Fresh native checks and explicitly bound historical observations.

No write protocol or human decision is performed by this module. Repeated
writer gates reobserve native specialists; a prior successful result is not cached.
"""
from dataclasses import replace
from hashlib import sha256
from ..cli.result_schemas import validate_result_document
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.audit_values import UtcTimestamp
from ..validation import ModelGate
from ..validation.values import HOOK_NAMES
from ._check_report import _initial, _now
from ._check_workspace import CheckWorkspace
from ._review_control import GATE, reports, read_review_start_observations
from .check import _isolated
from .context import ProposalContext
from .history import ProposalInputs
from .observations import ProposalVerifier, ProposalVerification
from .validation import validate_proposal
from .values import require


def _fresh_reports(snapshot, original, services):
    context = ProposalContext(original, snapshot.model)
    validation = validate_proposal(context).canonical_bytes
    report = _initial()
    report.update(observed_status=original.data['proposal_status'],
        binding=original.binding.data, proposal_sha256=original.sha256, context_sha256=context.sha256)
    report['audit'].update(proposal_id=original.data['id'], base=original.data['base'])
    workspace = CheckWorkspace(snapshot.source.boundary.root, False)
    try:
        workspace.create()
        _isolated(snapshot, original, workspace, report, services)
    finally:
        try:
            workspace.close()
        finally:
            report['workspace'] = dict(workspace.state)
    snapshot.verify_current()
    report.update(passed=True, full_semantic_validation=True, eligible_transition=None)
    report['audit']['diagnostics'] += [d for value in report['checks'].get('validation', {}).values()
        for stage in value['stages'] for d in stage['diagnostics']]
    report['audit']['diagnostics'] += report['checks'].get('lint', {}).get('diagnostics', [])
    report['audit'].update(ended_at=_now(), outcome='passed')
    report['result_sha256'] = canonical_json_sha256(report)
    validate_result_document('proposal-check-v1', report)
    return validation, canonical_json_bytes(report)


def _initial_inputs(model, original, services):
    if services.proposal_inputs is not None:
        return services.proposal_inputs(model.snapshot(), original)
    require(original.data['revision'] == 1 and original.data['proposal_status'] == 'draft'
        and not original.data.get('reviews', []) and not original.data['control_history'],
        'proposal_original_contexts_required')

    def no_observations(inputs):
        require(False, 'proposal_unexpected_historical_observation')

    return ProposalInputs((original,), (ProposalContext(original, model),), (), (),
        ProposalVerifier('native-initial-draft', '1', no_observations))


def _extended_services(snapshot, original, after, operation, actor, planned_at, services):
    old = _initial_inputs(snapshot.model, original, services)
    require(type(old) is ProposalInputs, 'proposal_native_inputs_required')
    context = ProposalContext(original, snapshot.model)
    result_bytes = [pair[0] for pair in reports(operation)]
    offset = len(original.data['control_history'])
    added = read_review_start_observations(after, offset, context)
    require(all(item.actor.as_fields() == actor and item.occurred_at.value == planned_at
        and item.result_bytes == result_bytes[0 if index == 0 else 1]
        for index, item in enumerate(added)), 'proposal_live_control_binding_changed', exit_code=6)

    def verify(inputs):
        item = inputs.observation
        if item in added:
            # These exact rows were just produced from actual native checks in
            # this call. This never authenticates existing/foreign observations.
            require(item.original.source_bytes == after.source_bytes
                and item.context == context and item.actor.as_fields() == actor,
                'proposal_live_control_binding_changed', exit_code=6)
            return ProposalVerification(inputs.sha256, sha256(item.row_bytes).hexdigest(),
                True, True, False)
        return old.verifier.check(inputs)

    extended = ProposalInputs((*old.originals, after),
        (*old.contexts, ProposalContext(after, snapshot.model)), old.reviews,
        (*old.controls, *added), ProposalVerifier('native-live-review-start', '1', verify), old.publications)

    def provider(model, value):
        if value.binding.proposal_id == after.binding.proposal_id:
            require(value.source_bytes == after.source_bytes, 'proposal_target_changed', exit_code=6)
            return extended
        return _initial_inputs(model, value, services)

    return replace(services, proposal_inputs=provider)


def _gates(snapshot, original, after, operation, actor, planned_at, services):
    from ..recovery._validation import validate_project
    qualified_services = _extended_services(snapshot, original, after, operation,
                                            actor, planned_at, services)
    files = {**snapshot.raw, after.path: after.source_bytes}
    expected_documents = {d.path: (after.source_bytes if d.path == after.path else d.content)
                          for d in snapshot.model.documents}

    def dependencies(context):
        return context.dependency_result({identity: list(context.all_ids) for identity in context.subjects})

    def check(context):
        require({d.path: d.content for d in context.documents} == expected_documents,
                'proposal_review_target_changed', exit_code=6)
        # No positive-result cache: source/review providers can change between
        # native writer gates, including the post-publication target check.
        validate_project(files, services=qualified_services)
        return context.result()

    return tuple(ModelGate(name, 'proposal-review-start-native-v1', dependencies, check,
        snapshot.model._sources_sha256) for name in (
            *(name for name in HOOK_NAMES if name not in ('profile_lint', 'language_policy')),
            GATE, 'extension:target-resources'))
