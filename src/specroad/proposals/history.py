"""Deterministic review/control history over complete original revisions."""
from dataclasses import dataclass

from ..model.canonical import canonical_json_bytes
from .context import ProposalContext, reconstruct_proposal_target, specification_manifest
from .observations import (ProposalReviewObservation, ProposalControlObservation,
    ProposalVerifier, ProposalVerificationInput, verify_observation)
from .values import ProposalOriginal, require


@dataclass(frozen=True)
class ProposalInputs:
    originals: tuple
    contexts: tuple
    reviews: tuple
    controls: tuple
    verifier: ProposalVerifier
    publications: tuple = ()

    def __post_init__(self):
        from .publication import ProposalPublication
        for values, kind in ((self.originals, ProposalOriginal),
                (self.contexts, ProposalContext), (self.reviews, ProposalReviewObservation),
                (self.controls, ProposalControlObservation)):
            require(type(values) is tuple and all(type(v) is kind for v in values),
                    'proposal_native_inputs_required')
        require(bool(self.originals) and bool(self.contexts)
                and type(self.verifier) is ProposalVerifier
                and type(self.publications) is tuple
                and all(type(p) is ProposalPublication for p in self.publications),
                'proposal_native_inputs_required')


def native_check(context, *, services=None):
    """Recompute the full plan and actual native model gates on original bytes.

    Proposal/Baseline control artifacts cannot enter the specification closure.
    Their histories are independently checked by the enclosing project reader.
    This does not run an analyzer, transaction, command or project code.
    """
    from ..recovery._validation import validate_project
    from ..storage.json_syntax import parse_json_object
    target = reconstruct_proposal_target(context)
    for model in (context.basis, target):
        # First enforce the permanent exclusion through the native closure:
        # simply dropping a required control dependency would be unsound.
        specification_manifest(model)
        excluded = {d.path for d in model.documents if parse_json_object(d.content)[
            'artifact_type'] in ('proposal', 'baseline')}
        validate_project({p: raw for p, raw in model.source_files.items() if p not in excluded},
                         services=services)
    return canonical_json_bytes({'context_sha256': context.sha256,
        'binding': context.original.binding.data,
        'base_manifest': specification_manifest(context.basis).data,
        'target_manifest': specification_manifest(target).data,
        'target_sources_sha256': target._sources_sha256,
        'qualification': 'complete_native_model_and_plan_checks',
        'write_authorized': False})


def _chain(originals):
    identity = originals[-1].binding.proposal_id
    previous = None
    for revision, original in enumerate(originals, 1):
        value = original.data
        require(value['id'] == identity and value['revision'] == revision,
                'proposal_original_revision_chain_incomplete', path=original.path)
        if previous is None:
            require(value['content_revision'] == 1 and value['proposal_status'] == 'draft'
                    and not value.get('reviews', []) and not value['control_history'],
                    'proposal_initial_revision_invalid', path=original.path)
        else:
            require(previous['proposal_status'] not in ('rejected', 'stale', 'applied'),
                    'proposal_terminal_revision_changed', path=original.path)
            require(value['created_at'] == previous['created_at']
                    and value['created_by'] == previous['created_by'],
                    'proposal_creation_metadata_changed', path=original.path)
            from ..model.audit_fields import _valid_utc
            from datetime import datetime
            require(_valid_utc(value['updated_at']) and datetime.fromisoformat(
                value['updated_at'].replace('Z', '+00:00')) > datetime.fromisoformat(
                previous['updated_at'].replace('Z', '+00:00')),
                'proposal_revision_time_invalid', path=original.path)
            changed = value['content_sha256'] != previous['content_sha256']
            require(value['content_revision'] == previous['content_revision'] + int(changed),
                    'proposal_content_revision_mismatch', path=original.path)
            if changed:
                require(previous['proposal_status'] in ('draft', 'in_review', 'approved')
                        and value['proposal_status'] == 'draft',
                        'proposal_authoring_status_invalid', path=original.path)
            for field in ('reviews', 'control_history'):
                old, new = previous.get(field, []), value.get(field, [])
                require(new[:len(old)] == old, 'proposal_history_rewritten', path=original.path)
        require(value['proposal_status'] not in ('validated', 'checked'),
                'proposal_review_start_incomplete', path=original.path)
        previous = value


def assess_proposal(original, inputs, current_model, *, services=None):
    """Historical validity and current approval are separate, neither is a grant."""
    require(type(original) is ProposalOriginal and type(inputs) is ProposalInputs,
            'proposal_native_inputs_required')
    require(inputs.originals[-1].source_bytes == original.source_bytes
            and inputs.originals[-1].path == original.path,
            'proposal_original_binding_changed', exit_code=6)
    _chain(inputs.originals)
    by_revision = {item.data['revision']: item for item in inputs.originals}
    contexts = {item.original.data['revision']: item for item in inputs.contexts}
    require(len(contexts) == len(inputs.contexts) and set(contexts) == set(by_revision),
            'proposal_original_contexts_incomplete')
    for revision, context in contexts.items():
        require(context.original == by_revision[revision]
                and context.basis.configuration.project_id == current_model.configuration.project_id,
                'proposal_context_binding_changed', exit_code=6)
    current = ProposalContext(original, current_model)
    value = original.data
    require([item.index for item in inputs.reviews] == list(range(len(value.get('reviews', []))))
            and [item.index for item in inputs.controls] == list(range(len(value['control_history']))),
            'proposal_observations_incomplete')
    observations = {}
    # Each observation must run the required qualification afresh, including
    # its host services. native_check includes dynamic source/review checks,
    # so even identical context bytes do not make its result cacheable.
    qualified = set()
    for item in (*inputs.reviews, *inputs.controls):
        field = 'reviews' if type(item) is ProposalReviewObservation else 'control_history'
        revision = item.original.data['revision']
        require(item.original == by_revision.get(revision)
                and item.context == contexts.get(item.context.original.data['revision'])
                and item.original.data[field][item.index] == value[field][item.index],
                'proposal_observation_binding_changed', exit_code=6)
        first_revision = next(number for number, source in by_revision.items()
                              if len(source.data.get(field, [])) > item.index)
        require(revision == first_revision
                and item.context.original.data['revision'] < revision,
                'proposal_observation_original_revision_mismatch')
        key = item.context.original.data['revision']
        native_result = native_check(item.context, services=services)
        qualified.add(key)
        publication = None
        if type(item) is ProposalControlObservation and item.after == 'applied':
            require(len(inputs.publications) == 1, 'proposal_original_completion_required')
            publication = inputs.publications[0]
        observation = verify_observation(inputs.verifier,
            ProposalVerificationInput(item, native_result, current, publication))
        observations[field, item.index] = observation
    # Drafts also need an actual basis/plan, even without historical decisions.
    if value['revision'] not in qualified:
        native_check(contexts[value['revision']], services=services)

    review_findings = []
    eligible = set()
    for revision, frame in by_revision.items():
        row = frame.data
        approvals = {}
        for item in inputs.reviews[:len(row.get('reviews', []))]:
            origin = item.context.original
            require(item.observed_revision == origin.data['revision']
                    and item.observed_revision <= revision,
                    'proposal_review_observed_revision_mismatch')
            if item.binding != frame.binding:
                continue
            require(item.decision != 'approved' or origin.data['proposal_status'] == 'in_review',
                    'proposal_review_state_invalid')
            key = item.reviewer.actor_id
            verified = observations['reviews', item.index]
            if item.decision in ('rejected', 'withdrawn'):
                approvals.pop(key, None)
            elif item.reviewer.actor_type == 'human':
                approvals[key] = verified.decision_current
        minimum = contexts[revision].minimum_approvals
        if row['proposal_status'] in ('approved', 'applied'):
            require(len(approvals) >= minimum, 'proposal_historical_quorum_not_met')
        if revision == value['revision']:
            eligible = {actor for actor, effective in approvals.items() if effective}
            review_findings = [{'review_index': item.index, 'actor_id': item.reviewer.actor_id,
                'decision': item.decision, 'binding_current': item.binding == frame.binding,
                'decision_current': observations['reviews', item.index].decision_current,
                'human': item.reviewer.actor_type == 'human'} for item in inputs.reviews]

    previous = None
    for frame in inputs.originals:
        row = frame.data
        start = 0 if previous is None else len(previous['control_history'])
        events = inputs.controls[start:len(row['control_history'])]
        state = 'draft' if previous is None or previous['content_sha256'] != row['content_sha256'] else previous['proposal_status']
        for event in events:
            require(event.original.data['revision'] == row['revision']
                    and event.binding == frame.binding and event.before == state,
                    'proposal_control_chain_mismatch')
            from ..changes.metadata_time import next_update_time
            require(previous is not None and event.actor.as_fields() == row['updated_by']
                    and row['updated_at'] == next_update_time(event.occurred_at.value, previous['updated_at'])
                    and all(other.actor == event.actor and other.occurred_at == event.occurred_at
                            for other in events), 'proposal_control_metadata_mismatch')
            state = event.after
        require(state == row['proposal_status'], 'proposal_control_status_mismatch')
        if any(event.after in ('validated', 'checked', 'in_review') for event in events):
            require([(event.before, event.after) for event in events] ==
                [('draft', 'validated'), ('validated', 'checked'), ('checked', 'in_review')],
                'proposal_review_start_not_atomic')
        previous = row

    status = value['proposal_status']
    current_basis = specification_manifest(current_model).sha256
    basis_matches = current_basis == original.binding.base_model_root_sha256
    minimum = current_model.configuration.data['validation_policy'].get(
        'minimum_human_proposal_approvals', 1)
    approved = status == 'approved' and basis_matches and len(eligible) >= minimum
    if status == 'approved':
        require(basis_matches, 'proposal_current_basis_stale', exit_code=6)
        require(approved, 'proposal_current_quorum_not_met')
    if status == 'applied':
        from .publication import verify_proposal_publication
        require(len(inputs.publications) == 1, 'proposal_original_completion_required')
        verify_proposal_publication(inputs.publications[0], inputs.originals[-2], original,
                                    contexts[value['revision']])
    else:
        require(not inputs.publications, 'proposal_unexpected_completion')
    return {'proposal_id': value['id'], 'original_sha256': original.sha256,
        'observed_status': status, 'historical_valid': True,
        'current_basis_matches': basis_matches, 'current_approval': approved,
        'effective_human_approvals': len(eligible), 'minimum_human_approvals': minimum,
        'reviews': review_findings, 'write_authorized': False, 'apply_performed': False}
