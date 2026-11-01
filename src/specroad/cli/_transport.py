"""Closed outbound variant, shared by argv, structured binding and metadata."""
from dataclasses import replace

from .contracts import CommandClass, CommandUsageError, EffectScope, WorkContract
from .requests import CommandRequest


RUNTIME_FLAGS = ('--patchharbor-pyz', '--patchharbor-pyz-sha256',
                 '--specroad-pyz', '--specroad-pyz-sha256')
VARIANT_FLAGS = frozenset(('--profile', '--direction', '--runtime-profile', *RUNTIME_FLAGS))
REQUIRED = frozenset(('--project', '--profile', '--direction', '--output', '--output-root', *RUNTIME_FLAGS))
FORBIDDEN = frozenset(('--document', '--release', '--configuration', '--exclude-operational-receipts',
                       '--reference', '--proposal'))


def outbound_options(options):
    if not VARIANT_FLAGS.intersection(options):
        if {'--reference', '--proposal', '--work-dir'}.intersection(options):
            raise CommandUsageError('Return transport is not implemented')
        return False
    if (not REQUIRED <= options.keys() or FORBIDDEN.intersection(options)
            or tuple(options.get('--profile', ())) != ('ai-runtime',)
            or options.get('--direction') != 'outbound'
            or options.get('--runtime-profile', 'python-present') != 'python-present'
            or options.get('--scope', 'project') != 'project'):
        raise CommandUsageError('A complete closed python-present outbound request is required')
    from ..transport._contract import valid_digest
    from ..transport._files import absolute
    from ..model.paths import project_path
    from ..model.errors import ModelError
    from ..transport.snapshots import TransportFailure
    try:
        for name in ('--project', '--patchharbor-pyz', '--specroad-pyz', '--output-root'):
            absolute(options[name])
        project_path(options['--output'])
    except (TransportFailure, ModelError, ValueError) as error:
        raise CommandUsageError('Explicit absolute inputs and a safe relative output are required') from error
    if any(not valid_digest(options[name]) for name in ('--patchharbor-pyz-sha256', '--specroad-pyz-sha256')):
        raise CommandUsageError('Both external full runtime hashes are required')
    return True


def outbound_contract(base):
    example = CommandRequest('bundle.create', {'--profile': ['ai-runtime'], '--direction': 'outbound',
        '--project': '/project', '--patchharbor-pyz': '/trusted/patchharbor-1.8.0.pyz',
        '--patchharbor-pyz-sha256': '1' * 64, '--specroad-pyz': '/trusted/specroad.pyz',
        '--specroad-pyz-sha256': '2' * 64, '--output-root': '/output', '--output': 'outbound.zip'})
    protocol = replace(base.protocol, example=example, handler_exit_codes=(*base.protocol.handler_exit_codes, 8),
        diagnostic_codes=tuple(dict.fromkeys((*base.protocol.diagnostic_codes, 'CORE_USAGE'))), work=WorkContract('source_safe_outbound_pyz_export',
        ('explicit_runtime_hashes', 'registered_repository', 'complete_project_and_receipts',
         'external_output', 'safe_reference_contract_1'), continuation_supported=True,
        external_side_effects=('external_work_directory',), checkpoint_algorithms=('work-manifest-segments-v1',)))
    return replace(base, command_class=CommandClass.TRANSPORT_OPERATIONAL,
        effect_scope=EffectScope.TRANSPORT_OUTPUT, requires_git=True,
        budget_policy_version='runtime-budget-v2', protocol=protocol,
        options=tuple(replace(o, required=True) if o.flag in REQUIRED else o for o in base.options))


def create_outbound_command(invocation):
    from ..transport.outbound import OutboundExport
    from ..transport.runtime import TransportUnavailable
    from ..transport.snapshots import TransportFailure
    from ..bundles.errors import BundleError
    from ..model.errors import ModelError
    from ..security import SafetyViolation
    from ..storage.archive import ArchiveError
    from ..recovery.values import RestoreError
    from ..query.read_work import complete_read_steps
    from .results import CommandResult, FailureKind
    from ..diagnostics import Diagnostic
    from .result_schemas import validate_result_document

    def steps():
        export = None
        try:
            options = invocation.options
            outbound_options(options)
            if ('--work-dir' in options or any(k in options for k in ('--step-cpu-ms', '--step-wall-ms',
                    '--cpu-budget-ms', '--wall-budget-ms')) or options.get('--resource-profile') == 'constrained'):
                from ..work.transport import start
                return start(invocation)
            export = OutboundExport(options['--project'], output_root=options['--output-root'],
                output=options['--output'], patchharbor_pyz=options['--patchharbor-pyz'],
                patchharbor_pyz_sha256=options['--patchharbor-pyz-sha256'],
                specroad_pyz=options['--specroad-pyz'], specroad_pyz_sha256=options['--specroad-pyz-sha256'])
            yield 'loaded'
            export.prepare()
            yield 'evaluated'
            result = export.execute()
            validate_result_document('bundle-create-v1', result)
            return CommandResult('bundle.create', result=result,
                details={'command_class': 'transport_operational', 'transport': dict(export.effects)})
        except (TransportUnavailable, TransportFailure, BundleError, ModelError, ArchiveError,
                SafetyViolation, OSError, RestoreError) as error:
            code = (7 if isinstance(error, SafetyViolation) else 5 if isinstance(error, OSError)
                    else getattr(error, 'exit_code', 3))
            reason = getattr(error, 'reason', 'transport_io_or_boundary_failure')
            facts = error.as_dict() if isinstance(error, (TransportUnavailable, TransportFailure)) else {'reason': reason}
            return CommandResult.failed('bundle.create', FailureKind(code),
                diagnostics=(Diagnostic('CORE_' + FailureKind(code).name, 'error', reason, reason),),
                details={'command_class': 'transport_operational', 'transport_failure': facts,
                         'transport': {} if export is None else dict(export.effects)})
    return complete_read_steps(steps(), call=invocation.consumption_call)
