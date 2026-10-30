"""Public planning and external Work share Restore's supported-source boundary."""
import pytest

from specroad.cli.application import execute, execute_request
from specroad.cli.results import thaw
from support.model import put
from support.read_only import inventory, no_write_attempts
from support.restore import restore_case
from test_restore_invocation import planning
from test_restore_invocation_options import invocation
from test_restore_legacy_history import legacy_registration, unsupported, attach_current_evidence
from test_restore_work_public import start, work
from test_work_resume import recorded


def damaged_format(tmp_path, kind):
    options, _, _ = restore_case(tmp_path)
    if kind == 'legacy':
        put(options['project_root'], 'mappings/legacy-manifest.json', legacy_registration())
    elif kind == 'attachment':
        attach_current_evidence(options, unsupported('9.8.7'))
    else:
        put(options['project_root'], 'spec/evidence/SR-EVD-' + '0' * 26 + '.json', unsupported('0.1.0'))
    return options


@pytest.mark.parametrize('representation', ['argv', 'mapping'])
@pytest.mark.parametrize('kind', ['legacy', 'artifact'])
def test_public_planning_rejects_unsupported_original_without_any_writes(tmp_path, representation, kind):
    options = damaged_format(tmp_path, kind)
    output = tmp_path / 'output'; output.mkdir()
    before = inventory(tmp_path)
    call = execute if representation == 'argv' else execute_request
    with no_write_attempts():
        result = call(invocation(planning(options, output), representation)).result
    assert result.exit_code == 3, thaw(result.details)
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('representation,kind', [('mapping', 'artifact'), ('argv', 'attachment')])
def test_work_partial_capture_never_qualifies_unsupported_originals(recorded, tmp_path, representation, kind):
    options = damaged_format(tmp_path, kind)
    output = tmp_path / 'output'; output.mkdir()
    location = tmp_path / 'work'
    original = {key: inventory(options[key]) for key in ('project_root', 'source_root')}
    result = start({**planning(options, output), '--work-dir': str(location)}, representation)
    assert result.exit_code == 8, thaw(result.details)
    bound = result.continuation.claim.total_units
    for _ in range(bound):
        result = work('resume', location, representation=representation)
        if result.exit_code != 8:
            break
    assert result.exit_code == 3, thaw(result.details)
    assert not (output / 'plans/original.json').exists()
    assert all(inventory(options[key]) == value for key, value in original.items())
    status = work('status', location, representation=representation)
    assert status.exit_code == 0, thaw(status.details)
    assert status.result['data']['state'] != 'completed'
    assert not (location / 'results/restore-plan.json').exists()
