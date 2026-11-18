"""Explicit return variant; sandbox export never acquires host write authority."""
from dataclasses import replace

from .contracts import CommandClass, CommandUsageError, EffectScope, WorkContract
from .requests import CommandRequest

REQUIRED = frozenset(('--project', '--profile', '--direction', '--reference', '--expected-sha256',
    '--proposal', '--patchharbor-pyz', '--patchharbor-pyz-sha256', '--output-root', '--output'))
FORBIDDEN = frozenset(('--document', '--release', '--configuration', '--exclude-operational-receipts',
    '--specroad-pyz', '--specroad-pyz-sha256', '--work-dir'))


def return_options(options):
    if options.get('--direction') != 'return':
        return False
    if (not REQUIRED <= options.keys() or FORBIDDEN.intersection(options)
            or tuple(options.get('--profile', ())) != ('ai-runtime',)
            or options.get('--scope', 'project') != 'project'
            or options.get('--runtime-profile', 'python-present') != 'python-present'):
        raise CommandUsageError('A complete explicit python-present return request is required')
    from ..transport._contract import valid_digest
    from ..transport._files import absolute
    from ..model.paths import project_path
    from ..model.errors import ModelError
    from ..transport.snapshots import TransportFailure
    try:
        for flag in ('--project', '--reference', '--patchharbor-pyz', '--output-root'):
            absolute(options[flag])
        project_path(options['--output'])
    except (TransportFailure, ModelError, ValueError) as error:
        raise CommandUsageError('Absolute inputs and a safe relative output are required') from error
    if any(not valid_digest(options[flag]) for flag in ('--expected-sha256', '--patchharbor-pyz-sha256')):
        raise CommandUsageError('Full reference and runtime SHA-256 values are required')
    return True


def return_contract(base):
    example = CommandRequest('bundle.create', {'--profile': ['ai-runtime'], '--direction': 'return',
        '--project': '/sandbox/project', '--reference': '/sandbox/reference/outbound.zip',
        '--expected-sha256': '1' * 64, '--proposal': '/sandbox/proposal.json',
        '--patchharbor-pyz': '/trusted/patchharbor-1.8.0.pyz', '--patchharbor-pyz-sha256': '2' * 64,
        '--output-root': '/output', '--output': 'return.zip'})
    return replace(base, command_class=CommandClass.GENERATED_OUTPUT, effect_scope=EffectScope.EXTERNAL_OUTPUT,
        requires_git=False, protocol=replace(base.protocol, example=example,
            result_schema='proposal-return-export-v1',
            work=WorkContract('proposal_return_export', ('original_outbound', 'explicit_proposal',
                'external_runtime_hash', 'external_output'))),
        options=tuple(replace(o, required=True) if o.flag in REQUIRED else o for o in base.options))


def create_return_command(invocation):
    from ..transport.return_export import ReturnExport
    from ..transport.runtime import TransportUnavailable
    from ..transport.snapshots import TransportFailure
    from ..model.errors import ModelError
    from ..security import SafetyViolation
    from ..bundles.errors import BundleError
    from ..storage.archive import ArchiveError
    from .results import CommandResult, FailureKind, OperationFailure
    from ..diagnostics import Diagnostic
    from .result_schemas import validate_result_document
    from ..query.read_work import complete_read_steps

    def steps():
        try:
            o = invocation.options
            return_options(o)
            export = ReturnExport(o['--project'], reference=o['--reference'], reference_sha256=o['--expected-sha256'],
                proposal=o['--proposal'], patchharbor_pyz=o['--patchharbor-pyz'],
                patchharbor_pyz_sha256=o['--patchharbor-pyz-sha256'], output_root=o['--output-root'], output=o['--output'])
            yield 'loaded'
            export.prepare()
            yield 'evaluated'
            result = export.execute()
            validate_result_document('proposal-return-export-v1', result)
            return CommandResult('bundle.create', result=result)
        except (TransportUnavailable, TransportFailure, ModelError, BundleError, ArchiveError, SafetyViolation, OperationFailure, OSError) as error:
            code = (error.kind.value if isinstance(error, OperationFailure) else
                    7 if isinstance(error, SafetyViolation) else 5 if isinstance(error, OSError)
                    else getattr(error, 'exit_code', 3))
            reason = getattr(error, 'reason', 'return_transport_unavailable')
            return CommandResult.failed('bundle.create', FailureKind(code),
                diagnostics=(Diagnostic('CORE_' + FailureKind(code).name, 'error', reason, reason),),
                details={'transport_failure': {'reason': reason}, 'command_class': 'generated_output'})
    return complete_read_steps(steps(), call=invocation.consumption_call)
