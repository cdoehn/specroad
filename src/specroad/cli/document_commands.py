"""Registered readers backed by the native document and validation kernels."""
from .registry import CommandClass, CommandSpec, EffectScope, OptionSpec, PreflightProfile
from .contracts import CommandProtocol, PositionalSpec, WorkContract
from .options import global_options


def _document_read(invocation):
    from ..documents.project_read import document_read_command
    return document_read_command(invocation)


def _validate(invocation):
    from ..bundles.partial_validation import validate_command
    return validate_command(invocation)


def read_commands():
    common = (OptionSpec('--project', takes_value=True),
        OptionSpec('--format', takes_value=True, choices=('pretty', 'json')),
        OptionSpec('--no-color'), OptionSpec('--quiet'))
    rows = (
        ('render', ('render',), (('document', 'render'),), (PositionalSpec('id', required=False),),
         (OptionSpec('--view', takes_value=True, choices=('specification', 'traceability', 'roadmap', 'verification')),
          OptionSpec('--output-format', takes_value=True, choices=('markdown', 'html'))),
         {'arguments': {'id': 'SR-DOC-' + '0' * 26}}),
        ('view.render', ('view', 'render'), (), (PositionalSpec('id'),),
         (OptionSpec('--configuration', takes_value=True),
          OptionSpec('--output-format', takes_value=True, choices=('markdown', 'html'))),
         {'arguments': {'id': 'SR-VIEW-' + '0' * 26}}),
        ('diagram', ('diagram',), (), (PositionalSpec('kind', choices=('trace', 'architecture', 'release')), PositionalSpec('id')),
         (OptionSpec('--direction', takes_value=True, required=True, choices=('incoming', 'outgoing', 'both')),
          *(OptionSpec('--' + name, takes_value=True, required=True) for name in ('max-depth', 'max-nodes', 'max-edges')),
          OptionSpec('--output-format', takes_value=True, choices=('mermaid', 'dot'))),
         {'arguments': {'kind': 'trace', 'id': 'SR-REQ-' + '0' * 26}, 'options': {
             '--direction': 'both', '--max-depth': '3', '--max-nodes': '100', '--max-edges': '200'}}),
        ('validate', ('validate',), (), (PositionalSpec('id', required=False),),
         (OptionSpec('--partial'), *global_options('--fail-on', '--strict')),
         {'options': {'--partial': True}}),
    )
    return tuple(CommandSpec(command_id=name, words=words, aliases=aliases,
        command_class=CommandClass.READ_ONLY, preflight_profile=PreflightProfile.PROJECT_READ,
        effect_scope=EffectScope.NONE, requires_project=True, configuration_schema_required=True,
        handler=_validate if name == 'validate' else _document_read,
        positionals=args, options=(*options, *common), protocol=CommandProtocol(
            'model-validation-v1' if name == 'validate' else 'document-read-v1',
            {'command_id': name, **example}, handler_exit_codes=(0, 1, 2, 3, 4, 5, 6, 7),
            diagnostic_codes=('CORE_MODEL', 'CORE_ENVIRONMENT', 'CORE_SECURITY', 'CORE_CONFLICT',
                'MODEL_VALIDATION', 'VALIDATION_UNAVAILABLE', 'SRV001', 'SRV002'),
            work=WorkContract('native_model_read', ('project_configuration', 'verified_model_inputs'))))
        for name, words, aliases, args, options, example in rows)
