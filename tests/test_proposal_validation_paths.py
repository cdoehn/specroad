"""Proposal operands use invocation cwd independently of the selected project."""
from pathlib import Path

import pytest

from specroad.cli.application import dispatch_result, execute_request
from support.proposal_validation import validation_project
from support.read_only import inventory, no_write_attempts


def invoke(root, operand, cwd, structured):
    if structured:
        return execute_request({'command_id': 'proposal.validate',
            'arguments': {'proposal': operand}, 'options': {'--project': str(root)}}, cwd=cwd).result
    return dispatch_result(['proposal', 'validate', operand, '--project', str(root)], cwd=cwd)


@pytest.mark.parametrize('structured', [False, True])
@pytest.mark.parametrize('origin', ['explicit', 'process_default'])
def test_external_relative_file_is_resolved_at_invocation_cwd_not_project_root(tmp_path, monkeypatch, structured, origin):
    root = tmp_path / 'project'
    _, original = validation_project(root)
    outside = tmp_path / 'review'; outside.mkdir()
    (outside / 'candidate.json').write_bytes(original.source_bytes)
    # A mistaken project-relative read must not accidentally pass this case.
    (root / 'candidate.json').write_bytes(b'{')
    if origin == 'process_default':
        monkeypatch.chdir(outside)
    cwd = outside if origin == 'explicit' else None
    before = inventory(tmp_path)
    process_cwd = Path.cwd()
    with no_write_attempts():
        result = invoke(root, 'candidate.json', cwd, structured)
    assert result.exit_code == 0, result.as_dict()
    assert result.as_dict()['result']['proposal_sha256'] == original.sha256
    assert result.as_dict()['result']['observed_status'] == 'draft'
    assert inventory(tmp_path) == before
    assert Path.cwd() == process_cwd


@pytest.mark.parametrize('structured', [False, True])
def test_managed_relative_path_uses_nested_invocation_directory(tmp_path, structured):
    root = tmp_path / 'project'
    _, original = validation_project(root, changed=True)
    cwd = root / 'spec'
    operand = (root / original.path).relative_to(cwd).as_posix()
    before = inventory(tmp_path)
    process_cwd = Path.cwd()
    with no_write_attempts():
        result = invoke(root, operand, cwd, structured)
    assert result.exit_code == 0, result.as_dict()
    assert result.as_dict()['result']['binding'] == original.binding.data
    assert inventory(tmp_path) == before
    assert Path.cwd() == process_cwd
