"""Removed product repair requests fail closed; ordinary Work remains separate."""
import pytest

from specroad.cli.application import execute, execute_request
from specroad.cli.commands import builtin_registry
from specroad.cli.contracts import CommandClass, PreflightProfile, EffectScope
from specroad.cli.requests import CommandRequest
from specroad.work.manifest import read_work_manifest, WorkManifestError
from support.read_only import inventory, no_write_attempts
from test_work_manifest import create, sealed, BUILD


@pytest.mark.parametrize('command', ['recover.status', 'recover.restore', 'recover.run',
                                      'recover.discard', 'recover.cleanup', 'lock.recover'])
@pytest.mark.parametrize('route', ['argv', 'request'])
def test_removed_public_repair_never_starts_or_writes(tmp_path, command, route):
    before = inventory(tmp_path)
    with no_write_attempts():
        response = (execute(command.split('.'), cwd=tmp_path) if route == 'argv'
                    else execute_request(CommandRequest(command), cwd=tmp_path))
    assert response.result.exit_code == 2
    assert inventory(tmp_path) == before


def test_public_command_contract_has_no_repair_writer_or_repair_profile():
    registry = builtin_registry()
    assert not any(c.command_id.startswith('recover.') for c in registry.commands)
    for enum, old in ((CommandClass, 'recovery_write'), (PreflightProfile, 'recovery'),
                      (EffectScope, 'recovery_transaction')):
        with pytest.raises(ValueError):
            enum(old)
    assert {'work.export', 'work.restore', 'work.resume', 'migrate.plan', 'merge.plan'} <= {
        c.command_id for c in registry.commands}


@pytest.mark.parametrize('identity', ['command', 'class', 'both'])
def test_retained_restore_identity_is_not_a_native_work_request(tmp_path, identity):
    original = create()
    value = original.as_dict()
    if identity in ('command', 'both'):
        value['command_id'] = 'recover.restore'
    if identity in ('class', 'both'):
        value['command_class'] = 'recovery_write'
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(WorkManifestError):
        read_work_manifest(sealed(value), original.objects,
                           registry=builtin_registry(), expected_tool_build=BUILD)
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('option', ['--force', '--expected-lock-sha256', '--reason',
    '--accept-remote-risk', '--expected-work-lock-sha256', '--work-recovery-reason'])
def test_work_resume_cannot_accept_old_owner_takeover_options(tmp_path, option):
    before = inventory(tmp_path)
    request = {'command_id': 'work.resume', 'arguments': {'work_dir': str(tmp_path/'absent')},
               'options': {option: True if option in ('--force', '--accept-remote-risk') else 'old-authority'}}
    with no_write_attempts():
        result = execute_request(request, cwd=tmp_path).result
    # X.12.3 now accepts explicit Force, but supplies neither a missing Work
    # nor owner-takeover authority. The removed recovery options stay invalid.
    assert result.exit_code == (3 if option == '--force' else 2)
    assert result.force['requested'] is (option == '--force')
    assert not result.force['used'] and not result.force['overrides']
    assert inventory(tmp_path) == before
