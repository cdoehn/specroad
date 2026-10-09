"""Read-only request and declared source/build binding; no handler invocation."""

from ..cli.contracts import CommandClass, CommandUsageError
from ..cli.registry import CommandRegistry
from ..cli.requests import CommandRequest
from ._data_contract import WorkManifestError, _require, _text, _copy, _object, _hash


def _command(registry, request):
    _require(type(registry) is CommandRegistry and type(request) is CommandRequest)
    # The first data codec does not guess which flag denotes a runtime locator,
    # budget or presentation choice. Such normalization belongs to a planner.
    _require(not request.options)
    _text(request.command_id)
    _copy({'arguments': dict(request.arguments)})
    try:
        invocation = registry.bind_request(request)
    except CommandUsageError as error:
        raise WorkManifestError('Invalid registered work request') from error
    _require(invocation.command.command_class is CommandClass.READ_ONLY)
    return {'command_id': request.command_id, 'command_class': 'read_only',
            'normalized_arguments': {'arguments': dict(invocation.arguments), 'options': {}}}


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
