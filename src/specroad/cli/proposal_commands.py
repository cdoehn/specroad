"""Implemented read-only Proposal command and its machine result contract."""
from .contracts import CommandProtocol, PositionalSpec, WorkContract
from .registry import CommandClass, CommandSpec, EffectScope, OptionSpec, PreflightProfile


def _validate(invocation):
    from ..proposals.project_validation import validate_command
    return validate_command(invocation)


def _check(invocation):
    from ..proposals.check import check_command
    return check_command(invocation)


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
            work=WorkContract('native_isolated_proposal_check', ('proposal_original', 'complete_native_basis')))),)



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
