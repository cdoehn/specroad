"""Analyzer option, class and handler contracts owned by the command registry."""
from .registry import CommandClass, CommandSpec, EffectScope, OptionSpec, PreflightProfile
from .contracts import CommandProtocol, PositionalSpec, WorkContract
from .options import global_options

def _analyzer_handler(invocation):
    from .analyzer_cli import analyzer_command
    return analyzer_command(invocation)

def analyzer_commands():
    selection = tuple(OptionSpec('--'+name, takes_value=True, repeatable=True)
                      for name in ('analyzer','subject','field')) + (OptionSpec('--analysis-id', takes_value=True),)
    inputs = OptionSpec('--inputs', takes_value=True)
    output = (OptionSpec('--output', takes_value=True), OptionSpec('--output-root', takes_value=True))
    request = OptionSpec('--request', takes_value=True)
    common = (*global_options('--fail-on', '--strict', '--no-color', '--quiet'),
              OptionSpec('--format', takes_value=True, choices=('pretty','json')))
    rows = (
        ('list', (), (inputs,), {}, 'analyzer-directory-v1'),
        ('describe', (PositionalSpec('id'),), (inputs,), {'arguments':{'id':'specroad.py3langid'}}, 'analyzer-directory-v1'),
        ('request', (), (*selection, inputs, *output), {'options':{'--analyzer':['specroad.py3langid']}}, 'analyzer-request-v1'),
        ('run', (), (*selection, inputs, *output, OptionSpec('--request', takes_value=True,
            excludes=('--analyzer','--subject','--field','--analysis-id','--inputs','--configuration'))),
            {'options':{'--request':'request.json'}}, 'analyzer-package-v1'),
        ('import', (PositionalSpec('file'),), (request, inputs, *output), {'arguments':{'file':'report.json'}}, 'analyzer-inspection-v1'),
        ('show', (PositionalSpec('file'),), (request, inputs), {'arguments':{'file':'report.json'}}, 'analyzer-inspection-v1'),
        ('evaluate', (PositionalSpec('files', repeatable=True),), (request, inputs),
            {'arguments':{'files':['report.json']}}, 'analyzer-inspection-v1'),
    )
    generated = {'request', 'run', 'import'}
    commands = []
    for name, args, specific, example, result_schema in rows:
        static = name in ('list','describe')
        options = (*common, *specific)
        if not static:
            options += global_options('--project','--configuration')
        commands.append(CommandSpec(command_id='analyzer.'+name, words=('analyzer',name),
            command_class=CommandClass.GENERATED_OUTPUT if name in generated else CommandClass.READ_ONLY,
            effect_scope=EffectScope.EXTERNAL_OUTPUT if name in generated else EffectScope.NONE,
            preflight_profile=PreflightProfile.PROJECT_READ if name == 'request' else PreflightProfile.INPUT_READ,
            requires_project=name == 'request', configuration_schema_required=name == 'request', handler=_analyzer_handler, options=options, positionals=args,
            protocol=CommandProtocol(result_schema, {'command_id':'analyzer.'+name, **example},
                handler_exit_codes=(0,1,2,3,4,5,6,7), diagnostic_codes=('CORE_MODEL','CORE_SECURITY','CORE_ENVIRONMENT','CORE_CONFLICT'),
                work=WorkContract('analyzer_files_and_snapshot', ('explicit_inputs',)))))
    return tuple(commands)
