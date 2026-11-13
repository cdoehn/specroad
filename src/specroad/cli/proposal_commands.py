"""Implemented Proposal routes and machine result contracts."""
from .contracts import CommandProtocol, PositionalSpec, WorkContract
from .registry import CommandClass, CommandSpec, EffectScope, OptionSpec, PreflightProfile


def _validate(invocation):
    from ..proposals.project_validation import validate_command
    return validate_command(invocation)


def _check(invocation):
    from ..proposals.check import check_command
    return check_command(invocation)


def _review_start(invocation):
    from ..proposals.review_start import review_start_command
    return review_start_command(invocation)


def _review(invocation):
    from ..proposals.review_decision import review_command
    return review_command(invocation)


def proposal_commands():
    return (CommandSpec('proposal.validate', ('proposal', 'validate'), CommandClass.READ_ONLY,
        PreflightProfile.PROJECT_READ, EffectScope.NONE, requires_project=True,
        configuration_schema_required=True, handler=_validate,
        positionals=(PositionalSpec('proposal'),), options=(
            OptionSpec('--project', takes_value=True),
            OptionSpec('--format', takes_value=True, choices=('pretty', 'json')),
            OptionSpec('--quiet'), OptionSpec('--no-color')),
        protocol=CommandProtocol('proposal-validation-v1', {'command_id': 'proposal.validate',
            'arguments': {'proposal': 'SR-PROP-' + '0' * 26}},
            handler_exit_codes=(0, 2, 3, 4, 5, 6, 7), diagnostic_codes=(
                'SRV001', 'SRV002', 'CORE_USAGE', 'CORE_MODEL', 'CORE_ENVIRONMENT', 'CORE_CONFLICT', 'CORE_SECURITY', 'SRV140'),
            work=WorkContract('native_proposal_structure_read', ('proposal_original', 'complete_native_basis')))),
        CommandSpec('proposal.check', ('proposal', 'check'), CommandClass.READ_ONLY,
        PreflightProfile.PROJECT_READ, EffectScope.EXTERNAL_OUTPUT, requires_project=True,
        configuration_schema_required=True, handler=_check,
        positionals=(PositionalSpec('proposal'),), options=(
            OptionSpec('--project', takes_value=True), OptionSpec('--keep-workspace'),
            OptionSpec('--format', takes_value=True, choices=('pretty', 'json')),
            OptionSpec('--quiet'), OptionSpec('--no-color')),
        protocol=CommandProtocol('proposal-check-v1', {'command_id': 'proposal.check',
            'arguments': {'proposal': 'SR-PROP-' + '0' * 26}},
            handler_exit_codes=(0, 1, 2, 3, 4, 5, 6, 7), diagnostic_codes=(
                'SRV001', 'SRV002', 'CORE_USAGE', 'CORE_MODEL', 'CORE_ENVIRONMENT', 'CORE_CONFLICT', 'CORE_SECURITY', 'SRV140'),
            work=WorkContract('native_isolated_proposal_check', ('proposal_original', 'complete_native_basis')))),
        CommandSpec('proposal.review.start', ('proposal', 'review', 'start'), CommandClass.NORMATIVE_WRITE,
            PreflightProfile.PROJECT_WRITE, EffectScope.NORMATIVE_TRANSACTION, requires_project=True,
            configuration_schema_required=True, handler=_review_start,
            positionals=(PositionalSpec('proposal'),), options=(
                OptionSpec('--expected-revision', takes_value=True, required=True),
                OptionSpec('--actor-type', takes_value=True, required=True, choices=('human', 'ai', 'ci')),
                OptionSpec('--actor-id', takes_value=True, required=True),
                OptionSpec('--request-id', takes_value=True), OptionSpec('--dry-run'),
                OptionSpec('--project', takes_value=True),
                OptionSpec('--format', takes_value=True, choices=('pretty', 'json')),
                OptionSpec('--quiet'), OptionSpec('--no-color')),
            protocol=CommandProtocol('proposal-review-start-v1', {'command_id': 'proposal.review.start',
                'arguments': {'proposal': 'SR-PROP-' + '0' * 26}, 'options': {
                    '--expected-revision': '1', '--actor-type': 'human', '--actor-id': 'author'}},
                handler_exit_codes=(0, 2, 3, 4, 5, 6, 7),
                diagnostic_codes=('CORE_USAGE', 'CORE_MODEL', 'CORE_ENVIRONMENT', 'CORE_CONFLICT', 'CORE_SECURITY'),
                lock_kind='writer', work=WorkContract('native_proposal_review_start',
                    ('proposal_original', 'complete_native_basis', 'fresh_check', 'host_authority')))), _review_spec(), _apply_spec())


def review_start_schema():
    from .result_schemas import _object, _nullable
    sha = {'type': 'string', 'pattern': r'^[0-9a-f]{64}(?![\s\S])'}
    return _object({'format_version': {'const': 'proposal-review-start-v1'},
        'proposal_id': {'type': 'string', 'minLength': 1},
        'revision': {'type': 'integer', 'minimum': 2},
        'content_revision': {'type': 'integer', 'minimum': 1},
        'content_sha256': sha, 'base_model_root_sha256': sha, 'change_plan_sha256': sha,
        'proposal_status': {'const': 'in_review'}, 'maturity': {'const': 'in_review'},
        'changed_change_ids': {'const': []},
        'review_validity': _object({'current_approval': {'const': False},
                                    'human_decision_required': {'const': True}}),
        **{key: {'type': 'boolean'} for key in ('dry_run', 'replayed', 'project_writes_performed')},
        'approval_granted': {'const': False}, 'write_authorized': {'const': False},
        'completion': _nullable({'type': 'object'})})



def validation_schema():
    from .result_schemas import _object, _nullable
    text = {'type': 'string', 'minLength': 1}
    sha = {'type': 'string', 'pattern': r'^[0-9a-f]{64}(?![\s\S])'}
    count = {'type': 'integer', 'minimum': 1}
    return _object({'format_version': {'const': 'proposal-validation-v1'},
        'validation_scope': {'const': 'proposal_structure_and_applicability'},
        'passed': {'type': 'boolean'},
        'observed_status': _nullable({'enum': ['draft', 'validated', 'checked', 'in_review',
            'approved', 'rejected', 'stale', 'applied']}),
        'eligible_transition': {'enum': [None, 'validated']}, 'revision': _nullable(count),
        'binding': _nullable(_object({'proposal_id': text, 'content_revision': count,
            'content_sha256': sha, 'base_model_root_sha256': sha, 'change_plan_sha256': sha})),
        'proposal_sha256': _nullable(sha), 'context_sha256': _nullable(sha),
        'failure_reason': _nullable(text), 'result_sha256': sha,
        **{key: {'const': False} for key in ('full_semantic_validation', 'approval_granted', 'write_authorized')}})


def _review_spec():
    return CommandSpec('proposal.review', ('proposal', 'review'), CommandClass.NORMATIVE_WRITE,
        PreflightProfile.PROJECT_WRITE, EffectScope.NORMATIVE_TRANSACTION, requires_project=True,
        configuration_schema_required=True, handler=_review,
        positionals=(PositionalSpec('proposal'),), options=(
            OptionSpec('--expected-revision', takes_value=True, required=True),
            OptionSpec('--decision', takes_value=True, required=True, choices=('approved', 'rejected', 'withdrawn')),
            OptionSpec('--comment', takes_value=True),
            OptionSpec('--actor-type', takes_value=True, required=True, choices=('human', 'ai', 'ci')),
            OptionSpec('--actor-id', takes_value=True, required=True),
            OptionSpec('--request-id', takes_value=True), OptionSpec('--dry-run'),
            OptionSpec('--project', takes_value=True),
            OptionSpec('--format', takes_value=True, choices=('pretty', 'json')),
            OptionSpec('--quiet'), OptionSpec('--no-color')),
        protocol=CommandProtocol('proposal-review-v1', {'command_id': 'proposal.review',
            'arguments': {'proposal': 'SR-PROP-' + '0' * 26}, 'options': {
                '--expected-revision': '2', '--decision': 'approved', '--actor-type': 'human',
                '--actor-id': 'reviewer'}}, handler_exit_codes=(0, 2, 3, 4, 5, 6, 7),
            diagnostic_codes=('CORE_USAGE', 'CORE_MODEL', 'CORE_ENVIRONMENT', 'CORE_CONFLICT', 'CORE_SECURITY'),
            lock_kind='writer', work=WorkContract('native_proposal_human_review',
                ('proposal_original', 'complete_native_basis', 'human_decision', 'host_authority'))))


def review_schema():
    from .result_schemas import _object, _nullable
    schema = review_start_schema()
    fields = schema['properties']
    fields['format_version'] = {'const': 'proposal-review-v1'}
    fields['proposal_status'] = fields['maturity'] = {'enum': ['in_review', 'approved', 'rejected']}
    fields['approval_granted'] = {'type': 'boolean'}
    fields['decision'] = {'enum': ['approved', 'rejected', 'withdrawn']}
    fields['comment'] = _nullable({'type': 'string'})
    fields['review_validity'] = _object({'current_approval': {'type': 'boolean'},
        'effective_human_approvals': {'type': 'integer', 'minimum': 0},
        'minimum_human_approvals': {'type': 'integer', 'minimum': 1}})
    schema['required'] = list(fields)
    return schema


def _apply(invocation):
    from ..proposals.apply import apply_command
    return apply_command(invocation)


def _apply_spec():
    return CommandSpec('proposal.apply', ('proposal', 'apply'), CommandClass.NORMATIVE_WRITE,
        PreflightProfile.PROJECT_WRITE, EffectScope.NORMATIVE_TRANSACTION, requires_project=True,
        configuration_schema_required=True, handler=_apply,
        positionals=(PositionalSpec('proposal'),), options=(
            OptionSpec('--expected-revision', takes_value=True, required=True),
            OptionSpec('--actor-type', takes_value=True, required=True, choices=('human', 'ai', 'ci')),
            OptionSpec('--actor-id', takes_value=True, required=True),
            OptionSpec('--request-id', takes_value=True), OptionSpec('--dry-run'),
            OptionSpec('--project', takes_value=True),
            OptionSpec('--format', takes_value=True, choices=('pretty', 'json')),
            OptionSpec('--quiet'), OptionSpec('--no-color')),
        protocol=CommandProtocol('proposal-apply-v1', {'command_id': 'proposal.apply',
            'arguments': {'proposal': 'SR-PROP-' + '0' * 26}, 'options': {
                '--expected-revision': '3', '--actor-type': 'human', '--actor-id': 'publisher'}},
            handler_exit_codes=(0, 2, 3, 4, 5, 6, 7),
            diagnostic_codes=('CORE_USAGE', 'CORE_MODEL', 'CORE_ENVIRONMENT', 'CORE_CONFLICT', 'CORE_SECURITY'),
            lock_kind='writer', work=WorkContract('native_approved_proposal_apply',
                ('proposal_original', 'complete_native_basis', 'current_human_reviews', 'host_authority'))))
