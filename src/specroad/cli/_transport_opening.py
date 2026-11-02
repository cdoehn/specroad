"""Explicit ai-runtime Verify/Extract variants; metadata never loads code."""
from dataclasses import replace

from .contracts import CommandUsageError, EffectScope, WorkContract
from .requests import CommandRequest

FLAGS = frozenset(('--profile', '--patchharbor-pyz', '--patchharbor-pyz-sha256', '--runtime-workspace'))


def opening_options(options):
    if not FLAGS.intersection(options):
        return False
    if not FLAGS <= options.keys() or tuple(options.get('--profile', ())) != ('ai-runtime',):
        raise CommandUsageError('Explicit ai-runtime inputs and a new private workspace are required')
    from ..transport._contract import valid_digest
    from ..transport._files import absolute
    from ..transport.snapshots import TransportFailure
    try:
        for name in ('--patchharbor-pyz', '--runtime-workspace'):
            absolute(options[name])
        if '--output' in options:
            absolute(options['--output'])
    except (TransportFailure, ValueError) as error:
        raise CommandUsageError('Absolute runtime, workspace and target paths are required') from error
    if not valid_digest(options['--patchharbor-pyz-sha256']) or (
            '--expected-sha256' in options and not valid_digest(options['--expected-sha256'])):
        raise CommandUsageError('A full external SHA-256 is required')
    return True


def opening_contract(base):
    extract = base.command_id == 'bundle.extract'
    options = {'--profile': ['ai-runtime'], '--patchharbor-pyz': '/trusted/patchharbor-1.8.0.pyz',
        '--patchharbor-pyz-sha256': '0' * 64, '--runtime-workspace': '/scratch/new-verification'}
    if extract:
        options['--output'] = '/sandbox/new-project'
    protocol = replace(base.protocol,
        result_schema='ai-runtime-' + ('extract' if extract else 'verify') + '-v1',
        example=CommandRequest(base.command_id, options, {'file': '/input/outbound.zip'}),
        handler_exit_codes=(0, 2, 3, 4, 5, 6, 7),
        diagnostic_codes=tuple(dict.fromkeys((*base.protocol.diagnostic_codes, 'CORE_USAGE'))),
        work=WorkContract('native_handoff_opening', ('explicit_handoff', 'standalone_runtime_hash',
            'external_private_workspace', 'complete_native_reference_and_project')))
    return replace(base, protocol=protocol, handler=opening_command,
        effect_scope=base.effect_scope if extract else EffectScope.EXTERNAL_OUTPUT,
        requires_write_paths=(*base.requires_write_paths, 'runtime_workspace'),
        options=tuple(replace(o, required=True) if o.flag in FLAGS else o for o in base.options))


def opening_command(invocation):
    from ..transport.opening import SandboxOpening
    from ..transport.runtime import TransportUnavailable
    from ..transport.snapshots import TransportFailure
    from ..authoring._bootstrap_io import BootstrapError
    from ..bundles.errors import BundleError
    from ..changes.lock_values import ProjectLockError
    from ..model.errors import ModelError
    from ..security import SafetyViolation
    from ..storage.archive import ArchiveError
    from ..diagnostics import Diagnostic
    from .result_schemas import validate_result_document
    from .results import CommandResult, FailureKind
    opening = None
    try:
        options = invocation.options
        opening_options(options)
        opening = SandboxOpening(invocation.arguments['file'],
            patchharbor_pyz=options['--patchharbor-pyz'],
            patchharbor_pyz_sha256=options['--patchharbor-pyz-sha256'],
            runtime_workspace=options['--runtime-workspace'],
            expected_sha256=options.get('--expected-sha256'), output=options.get('--output'))
        value = opening.verify()
        if invocation.command.command_id == 'bundle.extract':
            value = opening.extract()
        validate_result_document(invocation.command.protocol.result_schema, value)
        return CommandResult(invocation.command.command_id, result=value,
            details={'command_class': invocation.command.command_class.value, 'transport': dict(opening.effects)})
    except (TransportUnavailable, TransportFailure, BootstrapError, BundleError, ProjectLockError,
            ModelError, SafetyViolation, ArchiveError, OSError) as error:
        code = (7 if isinstance(error, SafetyViolation) else 5 if isinstance(error, OSError)
                else getattr(error, 'exit_code', 3))
        reason = getattr(error, 'reason', 'opening_io_or_boundary_failure')
        facts = error.as_dict() if isinstance(error, (TransportUnavailable, TransportFailure)) else {
            'reason': reason, 'path': getattr(error, 'path', None),
            'mutation_possible': getattr(error, 'mutation_possible', False)}
        return CommandResult.failed(invocation.command.command_id, FailureKind(code),
            diagnostics=(Diagnostic('CORE_' + FailureKind(code).name, 'error', reason, reason),),
            details={'command_class': invocation.command.command_class.value, 'transport_failure': facts,
                'transport': {} if opening is None else dict(opening.effects)})
