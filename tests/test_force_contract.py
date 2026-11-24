"""R-86/R-87: explicit request binding, negative findings and result identity."""
import json
import pytest
from specroad.force import ForceRequest, ForceDecisions, GATE_CLASSES, operations_hash
from specroad.cli.results import CommandResult, ResultStatus, FailureKind, serialize_result, ResultContractError
from specroad.cli.application import execute, execute_request
from specroad.model.canonical import canonical_json_sha256 as digest


@pytest.mark.parametrize('gate', GATE_CLASSES)
@pytest.mark.parametrize('allowed', [False, None])
def test_every_declared_gate_class_keeps_its_negative_finding(gate, allowed):
    binding = {'old': 'actual', 'new': 'requested'}
    inputs = dict(gate_id=gate + ':case', diagnostic_code='CORE_MODEL', subject='project', operation='change.apply',
        observed_binding={'sha256': 'a' * 64}, requested_binding=binding, effect='write_exact_requested_bytes')
    ordinary = ForceDecisions()
    assert ordinary.decide(allowed, **inputs) is False
    assert ordinary.summary == {'requested': False, 'used': False, 'reason': None, 'overrides': []}
    forced = ForceDecisions(ForceRequest(True, 'Explicit audit reason'))
    assert forced.decide(allowed, **inputs) is True
    binding['new'] = 'mutated after decision'
    row = forced.summary['overrides'][0]
    assert set(row) == {'gate_id', 'diagnostic_code', 'subject', 'original_decision', 'operation',
        'observed_binding', 'requested_binding', 'effect'}
    assert row['requested_binding']['new'] == 'requested'
    assert row['original_decision'] == ('denied' if allowed is False else 'unknown')
    assert forced.validation_status == ('invalid' if allowed is False else 'unknown')
    result = CommandResult('change.apply', status=ResultStatus.FORCED,
        force=forced.summary, validation_status=forced.validation_status)
    document = json.loads(serialize_result(result))
    assert document['format_version'] == '2.1.0' and result.exit_code == 0
    assert document['summary']['force']['used'] is True and document['summary']['complete'] is True
    assert document['summary']['validation_status'] != 'valid'


def test_normal_and_requested_without_blocker_are_distinct_but_not_forced():
    normal = execute_request({'command_id': 'help'}).result
    requested = execute_request({'command_id': 'help', 'force': True}).result
    raw = execute(['--help', '--force', '--format', 'json']).result
    assert normal.exit_code == requested.exit_code == raw.exit_code == 0
    assert normal.as_dict()['summary']['force'] == {'requested': False, 'used': False, 'reason': None, 'overrides': []}
    assert requested.as_dict()['summary']['force'] == raw.as_dict()['summary']['force'] == {
        'requested': True, 'used': False, 'reason': None, 'overrides': []}
    assert requested.status is ResultStatus.SUCCESS


@pytest.mark.parametrize('supplied', [
    {'force': 1}, {'force': 'true'}, {'force_reason': 'orphan'},
    {'force': True, 'options': {'--force': True}},
])
def test_force_is_a_single_explicit_typed_request(supplied):
    result = execute_request({'command_id': 'help', **supplied}).result
    assert result.exit_code == 2 and result.status is ResultStatus.FAILED


def test_incomplete_force_or_success_with_overrides_cannot_be_reported():
    decisions = ForceDecisions(ForceRequest(True))
    decisions.decide(False, gate_id='schema:case', diagnostic_code='CORE_MODEL', subject='project',
        operation='change.apply', observed_binding='invalid', requested_binding='explicit', effect='write')
    with pytest.raises(ResultContractError):
        CommandResult('change.apply', status='forced', force=decisions.summary, complete=False)
    with pytest.raises(ResultContractError):
        CommandResult('change.apply', force=decisions.summary)
    failure = CommandResult.failed('change.apply', FailureKind.ENVIRONMENT, force=decisions.summary)
    assert failure.exit_code == 5 and failure.status is ResultStatus.FAILED


def test_unknown_command_never_becomes_force_success():
    result = execute(['not-a-command', '--force', '--format', 'json']).result
    assert result.exit_code == 2 and result.status is ResultStatus.FAILED


@pytest.mark.parametrize('first', ['specroad.authoring', 'specroad.verification', 'specroad.planning.relations'])
def test_public_force_api_is_importable_after_independent_specialists(first, tmp_path):
    from support.portable import build_distribution
    from support.processes import SOURCE, run_python
    module, archive = build_distribution(tmp_path / 'distribution')
    for provider in (SOURCE, module, archive):
        program = 'import sys;sys.path.insert(0,' + repr(str(provider)) + ');\n'
        program += ('import importlib\nimportlib.import_module(' + repr(first) + ')\n'
            'from specroad.changes import bind_force_plan, apply_force_plan, ForcePublicationRequest, '
            'read_force_completion, prepare_resource_plan\n'
            'assert all(callable(value) for value in (bind_force_plan, apply_force_plan, '
            'ForcePublicationRequest, read_force_completion, prepare_resource_plan))\n')
        process = run_python(['-I', '-S', '-B', '-c', program], tmp_path, capture=True)
        assert process.returncode == 0, (first, str(provider), process.stderr.decode())
