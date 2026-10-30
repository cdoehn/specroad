"""Public argv/structured Restore parity with actual filesystem boundaries."""
import io
import json

import pytest

from specroad.cli import main
from specroad.cli.application import execute, execute_request
from specroad.cli.commands import builtin_registry
from specroad.cli.invocation_context import InvocationContextBuilder
from specroad.cli.result_schemas import validate_result_document
from specroad.cli.results import thaw
from specroad.cli.self_description import describe_command
from support.read_only import inventory, no_write_attempts
from support.restore import restore_case, plan_for
from test_restore_invocation import planning, execution, authority
from test_restore_invocation_options import invocation


def invoke(options, representation, host=None):
    request = invocation(options, representation)
    call = execute if representation == 'argv' else execute_request
    return call(request, context_builder=InvocationContextBuilder(recovery_authority=host)).result


@pytest.mark.parametrize('kind', ['project_bundle', 'baseline'])
@pytest.mark.parametrize('representation', ['argv', 'mapping'])
def test_public_planning_and_execution_preserve_native_target(tmp_path, kind, representation):
    options, _, _ = restore_case(tmp_path, kind)
    plan = plan_for(options)
    out = tmp_path / 'out'; out.mkdir()
    before = inventory(options['project_root'])
    planned = invoke(planning(options, out), representation)
    assert planned.exit_code == 0, planned
    assert thaw(planned.result['restore_plan']) == plan.data
    assert inventory(options['project_root']) == before
    validate_result_document('restore-command-v1', thaw(planned.result))
    events = []
    result = invoke(execution(options, plan, out), representation,
                    authority(lambda request: events.append(request) or True))
    assert result.exit_code == 0, result
    assert result.result['execution']['result'] == 'restored'
    assert result.result['execution']['expected_target_root'] == plan.data['expected_target_root']
    assert events
    validate_result_document('restore-command-v1', thaw(result.result))


@pytest.mark.parametrize('representation', ['argv', 'mapping'])
def test_public_execution_requires_fresh_host_authority_without_writes(tmp_path, representation):
    options, _, _ = restore_case(tmp_path)
    plan = plan_for(options)
    out = tmp_path / 'out'; out.mkdir()
    request = execution(options, plan, out)
    before = inventory(options['project_root'])
    with no_write_attempts():
        response = invoke(request, representation)
    assert response.exit_code == 2
    assert response.details['reason'] == 'restore_authority_required'
    assert inventory(options['project_root']) == before


def test_console_host_context_and_result_schema_are_usable(tmp_path):
    options, _, _ = restore_case(tmp_path)
    plan = plan_for(options)
    out = tmp_path / 'out'; out.mkdir()
    request = execution(options, plan, out)
    request['--format'] = 'json'
    output = io.StringIO()
    code = main(invocation(request, 'argv'), stdout=output,
                context_builder=InvocationContextBuilder(recovery_authority=authority()))
    assert code == 0
    result = json.loads(output.getvalue())
    assert result['result']['execution']['result'] == 'restored'


def test_describing_restore_neither_runs_recovery_nor_grants_authority():
    with no_write_attempts():
        result = describe_command(builtin_registry(), 'recover.restore')
    assert result['lock_kind'] == 'recovery'
    assert result['preflight_profile'] == 'recovery'
    assert result['command_class'] == 'recovery_write'
    assert result['stdout']['result_schema'] == 'restore-command-v1'
    assert {'--plan', '--expected-target-root', '--source-kind'} <= {
        option['flag'] for option in result['options']}
