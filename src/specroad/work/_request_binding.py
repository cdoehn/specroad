"""Registered request and declared source/build binding; no handler invocation."""

from ..cli.contracts import CommandClass, CommandUsageError, PreflightProfile, EffectScope
from ..cli.registry import CommandRegistry
from ..cli.requests import CommandRequest
from ._data_contract import WorkManifestError, _require, _text, _copy, _object, _hash


def _command(registry, request, *, normative=False, recovery=False):
    _require(type(registry) is CommandRegistry and type(request) is CommandRequest)
    # Read-only requests still accept no guessed option projection. Restore
    # uses its own closed parser and explicit transport projection separately.
    _require(type(normative) is bool and type(recovery) is bool and not (normative and recovery)
             and (normative or recovery or not request.options))
    _text(request.command_id)
    _copy({'arguments': dict(request.arguments), 'options': dict(request.options)})
    try:
        invocation = registry.bind_request(request)
    except CommandUsageError as error:
        raise WorkManifestError('Invalid registered work request') from error
    expected = (CommandClass.RECOVERY_WRITE if recovery else
                CommandClass.NORMATIVE_WRITE if normative else CommandClass.READ_ONLY)
    _require(invocation.command.command_class is expected)
    if recovery:
        from ..cli._restore_options import restore_request
        _require(invocation.command.command_id == 'recover.restore'
                 and invocation.command.words == ('recover', 'restore')
                 and invocation.command.preflight_profile is PreflightProfile.RECOVERY
                 and invocation.command.effect_scope is EffectScope.RECOVERY_TRANSACTION)
        restore_request(CommandRequest(request.command_id, invocation.options, invocation.arguments))
    return {'command_id': request.command_id, 'command_class': expected.value,
            'normalized_arguments': {'arguments': dict(invocation.arguments),
                                    'options': dict(invocation.options) if normative or recovery else {}}}


def _tool(value):
    _object(value, ('version', 'build_sha256', 'hash_algorithm'))
    _text(value['version']); _hash(value['build_sha256'])
    _text(value['hash_algorithm'])
    _require(value['hash_algorithm'] == 'specroad-dev-payload-v1')


def _sources(value):
    _object(value, ('project_id', 'scope', 'model_root_sha256'))
    if value['project_id'] is not None:
        _text(value['project_id'])
    _require(type(value['scope']) is list)
    for scope in value['scope']:
        _text(scope)
    _require(len(value['scope']) == len(set(value['scope'])))
    if value['model_root_sha256'] is not None:
        _hash(value['model_root_sha256'])
