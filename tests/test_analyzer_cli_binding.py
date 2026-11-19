"""Public command binding, actual project preflights and independent input roots."""
import json

import pytest

from specroad.cli.application import dispatch_result, execute_request
from specroad.cli.commands import builtin_registry
from specroad.cli.contracts import PreflightProfile
from specroad.cli.requests import CommandRequest
from specroad.cli.results import thaw
from specroad.cli.self_description import describe_command
from specroad.model._schema import validate_builtin
from specroad.model.errors import ModelError
from support.read_only import inventory, no_write_attempts
from test_analyzer_cli import BUILTIN, observation_files
from test_analyzer_subjects import project


@pytest.mark.parametrize('route', ['argv', 'structured'])
def test_selected_run_is_owned_by_registry_and_executes_through_public_api(tmp_path, route):
    values = project(tmp_path)
    registry = builtin_registry()
    options = {'--analyzer': [BUILTIN], '--analysis-id': 'bound-run'}
    invocation = (registry.parse(['analyzer', 'run', '--analyzer', BUILTIN, '--analysis-id', 'bound-run'])
                  if route == 'argv' else registry.bind_request(CommandRequest('analyzer.run', options)))
    assert invocation.command is registry.bind_request(CommandRequest('analyzer.run', options)).command
    assert invocation.command.preflight_profile is PreflightProfile.PROJECT_READ
    before = inventory(tmp_path)
    with no_write_attempts():
        result = registry.execute_result(invocation, cwd=tmp_path)
    assert result.exit_code == 5 and result.command == 'analyzer.run'
    assert result.result['request']['request_id'] == 'bound-run'
    assert [s['value'] for s in result.result['request']['subjects']] == [v['statement'] for v in values]
    assert result.result['reports'][0]['run_status'] == 'unavailable'
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('command,arguments,options', [
    ('request', {}, {'--analyzer': [BUILTIN]}),
    ('run', {}, {'--request': 'request.json'}),
    ('import', {'file': 'report.json'}, {}),
    ('show', {'file': 'report.json'}, {}),
    ('evaluate', {'files': ['report.json']}, {}),
])
def test_every_explicit_project_mode_validates_configuration_before_handler(tmp_path, command, arguments, options):
    observation_files(tmp_path)
    path = tmp_path / 'specroad.json'
    configuration = json.loads(path.read_bytes())
    configuration['schema_version'] = 'unsupported'
    path.write_text(json.dumps(configuration))
    request = {'command_id': 'analyzer.' + command, 'arguments': arguments,
               'options': {**options, '--project': str(tmp_path)}}
    before = inventory(tmp_path)
    with no_write_attempts():
        result = execute_request(request, cwd=tmp_path).result
    assert result.exit_code == 3 and result.result is None
    assert inventory(tmp_path) == before


def test_project_read_mode_keeps_relative_input_files_bound_to_caller_directory(tmp_path):
    root = tmp_path / 'selected'
    observation_files(root)
    caller = tmp_path / 'caller'; caller.mkdir()
    for name in ('report.json', 'inputs.json'):
        (caller / name).write_bytes((root / name).read_bytes())
        (root / name).write_bytes(b'{')
    before = inventory(tmp_path)
    with no_write_attempts():
        result = dispatch_result(['analyzer', 'evaluate', 'report.json', '--project', str(root),
                                  '--inputs', 'inputs.json'], cwd=caller)
    assert result.exit_code == 0 and result.result['gate_passed']
    assert len(result.result['evaluation']['reports']) == 2
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('args,code', [
    (['list'], 0), (['describe', BUILTIN], 0),
    (['run', '--request', 'request.json'], 5),
    (['import', 'report.json'], 0), (['show', 'report.json'], 0),
    (['evaluate', 'report.json'], 5),
])
def test_file_only_commands_do_not_select_an_incidental_invalid_project(tmp_path, args, code):
    source = tmp_path / 'source'; observation_files(source)
    caller = tmp_path / 'caller'; caller.mkdir()
    for name in ('request.json', 'report.json'):
        (caller / name).write_bytes((source / name).read_bytes())
    (caller / 'specroad.json').write_bytes(b'{')
    before = inventory(tmp_path)
    with no_write_attempts():
        result = dispatch_result(['analyzer', *args], cwd=caller)
    assert result.exit_code == code and result.project is None
    if args[0] in ('show', 'import', 'evaluate'):
        assert not result.result['gate_passed']
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('name', ['run', 'import', 'show', 'evaluate'])
def test_project_variant_description_binds_actual_registered_contract_without_transport_claims(name):
    registry = builtin_registry()
    description = describe_command(registry, 'analyzer.' + name)
    variant = description['variants'][0]
    request = CommandRequest.from_mapping(variant['example'])
    bound = registry.bind_request(request).command
    assert bound is registry.variants(registry.resolve(request.command_id))[0]
    assert bound.requires_project and bound.configuration_schema_required
    assert bound.preflight_profile.value == variant['preflight_profile'] == 'project_read'
    assert variant['operating_effects'] == []
    assert variant['work']['continuation_supported'] is (name == 'run')
    validate_builtin(thaw(request.options), variant['when'])
    if name == 'run':
        validate_builtin({'--analyzer': [BUILTIN]}, variant['when'])
        with pytest.raises(ModelError):
            validate_builtin({'--request': 'request.json'}, variant['when'])
    else:
        with pytest.raises(ModelError):
            validate_builtin({}, variant['when'])
