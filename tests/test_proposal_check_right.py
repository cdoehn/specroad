"""Fail closed, cleanup, explicit debugging and no project-selected execution."""
from hashlib import sha256
from pathlib import Path
import json
import shutil
import tempfile
import socket
import subprocess
import os

import pytest

from specroad.authoring._inspection_snapshot import InspectionSnapshot
from specroad.cli.application import dispatch_result, execute_request
from specroad.model.canonical import canonical_json_bytes, canonical_json_sha256
from specroad.proposals import check
from specroad.proposals.check import check_proposal_project
from specroad.proposals.content import content_sha256
from specroad.proposals.values import ProposalError
from support.proposal_validation import validation_project, replace_proposal
from support.read_only import inventory


@pytest.mark.parametrize('keep', [False, True])
@pytest.mark.parametrize('bad', ['json', 'content', 'target', 'basis', 'environment'])
def test_failed_checks_report_real_failures_and_cleanup_or_explicit_retention(tmp_path, monkeypatch, keep, bad):
    from specroad.changes import prepare_change_plan
    root, temporary = tmp_path / 'project', tmp_path / 'temp'
    temporary.mkdir(); monkeypatch.setattr(tempfile, 'tempdir', str(temporary))
    _, original = validation_project(root, changed=True)
    value = original.data
    if bad == 'json':
        raw = b'{'
    else:
        if bad in ('target', 'basis'):
            plan = value['change_plan']; plan.pop('change_plan_sha256')
            if bad == 'target':
                plan['expected_result']['model_root_sha256'] = '0' * 64
            else:
                value['base']['model_root_sha256'] = plan['base']['model_root_sha256'] = '0' * 64
            value['change_plan'] = prepare_change_plan(plan).data
            value['content_sha256'] = content_sha256(value)
        elif bad == 'content':
            value['content_sha256'] = '0' * 64
        raw = canonical_json_bytes(value)
    (root / original.path).write_bytes(raw)
    if bad == 'environment':
        def fail(*args, **kwargs): raise OSError('Synthetic private workspace unavailable')
        monkeypatch.setattr(check.CheckWorkspace, 'materialize', fail)
    before = inventory(root)
    result = check_proposal_project(root, original.data['id'], keep_workspace=keep)
    assert result.exit_code == (5 if bad == 'environment' else 6 if bad == 'basis' else 3), result.as_dict()
    report = result.as_dict()['result']
    assert not report['passed'] and not report['full_semantic_validation']
    assert report['eligible_transition'] is None
    assert report['proposal_sha256'] == sha256(raw).hexdigest()
    assert report['audit']['diagnostics']
    assert report['audit']['outcome'] == 'failed'
    assert inventory(root) == before
    remaining = list(temporary.iterdir())
    if keep and bad in ('target', 'basis', 'environment'):
        assert len(remaining) == 1 and report['workspace']['retained']
        assert str(remaining[0]) == report['workspace']['path']
        shutil.rmtree(remaining[0])
    else:
        assert not remaining
    digest = report.pop('result_sha256'); assert digest == canonical_json_sha256(report)


@pytest.mark.parametrize('failed', [False, True])
@pytest.mark.parametrize('change', ['configuration', 'operand', 'inventory'])
def test_source_reread_overrides_success_and_failure_and_preserves_competing_edits(tmp_path, monkeypatch, failed, change):
    root = tmp_path / 'project'
    _, original = validation_project(root, changed=True)
    native = check._isolated
    def race(*args):
        native(*args)
        if change == 'configuration':
            path = root / 'specroad.json'
            path.write_bytes(path.read_bytes() + b'\n')
        elif change == 'operand':
            path = root / original.path
            path.write_bytes(path.read_bytes() + b'\n')
        else:
            from support.model import put
            from support.domain import domain_value
            from support.relations import aid
            from specroad.model.paths import artifact_path
            value = domain_value('goal', id=aid('goal', 2))
            put(root, artifact_path('goal', value['id'], 'SR'), canonical_json_bytes(value))
        if failed:
            raise ProposalError('synthetic_interrupted_check')
    monkeypatch.setattr(check, '_isolated', race)
    result = check_proposal_project(root, original.data['id'])
    assert result.exit_code == 6, result.as_dict()
    assert not result.as_dict()['result']['passed']
    assert result.as_dict()['result']['workspace']['cleanup'] == 'removed'
    if change != 'inventory':
        path = root / ('specroad.json' if change == 'configuration' else original.path)
        assert path.read_bytes().endswith(b'\n')
    else:
        assert len(InspectionSnapshot(root, None).model.artifacts) == 5


@pytest.mark.parametrize('attack', ['shell', 'python', 'url'])
def test_untrusted_passive_content_and_project_programs_cannot_execute(tmp_path, monkeypatch, attack):
    root = tmp_path / 'project'
    _, original = validation_project(root, changed=True)
    text = dict(shell='$(touch SHOULD_NOT_EXIST); false',
                python="__import__('os').system('touch SHOULD_NOT_EXIST')", url='https://example.invalid/execute')[attack]
    value = original.data
    value['rationale'] = text
    value['changes'][0]['rationale'] = text
    value['content_sha256'] = content_sha256(value)
    (root / original.path).write_bytes(canonical_json_bytes(value))
    for filename in ('Makefile', 'conftest.py', 'plugin.py', 'run.sh'):
        (root / filename).write_text(text)
    before = inventory(root)
    def forbidden(*args, **kwargs): raise AssertionError('No execution or network during check')
    for target, attr in ((subprocess, 'Popen'), (os, 'system'), (socket, 'create_connection'),
                         (socket.socket, 'connect'), (socket.socket, 'connect_ex')):
        monkeypatch.setattr(target, attr, forbidden)
    result = check_proposal_project(root, original.data['id'])
    assert result.exit_code == 0, result.as_dict()
    assert inventory(root) == before and not (root / 'SHOULD_NOT_EXIST').exists()


def test_temporary_parent_inside_original_project_is_rejected_before_any_creation(tmp_path, monkeypatch):
    _, original = validation_project(tmp_path)
    monkeypatch.setattr(tempfile, 'tempdir', str(tmp_path))
    before = inventory(tmp_path)
    result = check_proposal_project(tmp_path, original.data['id'])
    assert result.exit_code == 7, result.as_dict()
    assert result.as_dict()['result']['workspace']['cleanup'] == 'not_created'
    assert inventory(tmp_path) == before


def test_cleanup_failure_is_reported_as_failure_with_the_actual_path(tmp_path, monkeypatch):
    _, original = validation_project(tmp_path)
    native = shutil.rmtree
    def fail(*args, **kwargs): raise OSError('Synthetic cleanup denied')
    with monkeypatch.context() as patch:
        patch.setattr(shutil, 'rmtree', fail)
        result = check_proposal_project(tmp_path, original.data['id'])
    assert result.exit_code == 5, result.as_dict()
    value = result.as_dict()['result']
    assert not value['passed'] and value['workspace']['cleanup'] == 'failed'
    path = Path(value['workspace']['path'])
    assert path.is_dir()
    native(path)


def test_debug_option_is_explicit_in_argv_and_structured_requests(tmp_path):
    _, original = validation_project(tmp_path)
    for result in (
        dispatch_result(['proposal', 'check', original.data['id'], '--keep-workspace'], cwd=tmp_path),
        execute_request({'command_id': 'proposal.check', 'arguments': {'proposal': original.data['id']},
                         'options': {'--keep-workspace': True}}, cwd=tmp_path).result):
        assert result.exit_code == 0, result.as_dict()
        workspace = result.as_dict()['result']['workspace']
        assert workspace['retained'] and workspace['cleanup'] == 'retained'
        shutil.rmtree(workspace['path'])


@pytest.mark.parametrize('operand', ['-', '../bad\x00path', 'SR-REQ-' + '0' * 26])
def test_invalid_operands_never_allocate_a_workspace(tmp_path, monkeypatch, operand):
    validation_project(tmp_path)
    def forbidden(*args, **kwargs): raise AssertionError('Invalid operand allocated a workspace')
    monkeypatch.setattr(tempfile, 'mkdtemp', forbidden)
    result = check_proposal_project(tmp_path, operand)
    assert result.exit_code != 0, result.as_dict()
    assert result.as_dict()['result']['workspace']['cleanup'] == 'not_created'


def test_retained_workspace_identity_change_never_removes_replacement(tmp_path, monkeypatch):
    _, original = validation_project(tmp_path)
    native = check._isolated
    saved = []
    def replace_workspace(snapshot, proposal, workspace, report, services):
        native(snapshot, proposal, workspace, report, services)
        owned = workspace.path.with_name(workspace.path.name + '-moved')
        workspace.path.rename(owned)
        workspace.path.mkdir()
        (workspace.path / 'foreign.txt').write_text('preserve')
        saved.extend([owned, workspace.path])
    monkeypatch.setattr(check, '_isolated', replace_workspace)
    try:
        result = check_proposal_project(tmp_path, original.data['id'])
        assert result.exit_code == 7, result.as_dict()
        assert (saved[-1] / 'foreign.txt').read_text() == 'preserve'
        assert result.as_dict()['result']['workspace']['cleanup'] == 'failed'
    finally:
        for path in saved: shutil.rmtree(path)


@pytest.mark.parametrize('status', ['draft', 'validated', 'checked', 'in_review', 'approved', 'rejected', 'stale', 'applied'])
def test_observed_status_is_not_promoted_by_a_successful_check(tmp_path, status):
    from specroad.model.record_contracts import SPECIAL_STATES
    _, original = validation_project(tmp_path)
    value = replace_proposal(tmp_path, original, proposal_status=status,
        maturity=SPECIAL_STATES['proposal'][1][status])
    before = inventory(tmp_path)
    result = check_proposal_project(tmp_path, original.data['id'])
    assert result.exit_code == 0, result.as_dict()
    report = result.as_dict()['result']
    assert report['observed_status'] == status
    assert report['eligible_transition'] == ('checked' if status == 'validated' else None)
    assert not report['approval_granted'] and not report['write_authorized']
    assert inventory(tmp_path) == before
    assert json.loads((tmp_path / original.path).read_bytes()) == value


def test_all_native_view_formats_use_exact_declared_values(tmp_path):
    from specroad.proposals import prepare_proposal_for_model
    from specroad.documents.views import resolve_view
    from support.records import record_value
    from support.domain import domain_value
    from support.model import put
    from support.targets import SCOPE
    from test_proposal_basis import project, fields
    view = record_value('view', scope_descriptor=SCOPE, formats=['json', 'markdown', 'html'])
    model = project(tmp_path, artifacts=[record_value('document'), domain_value('goal'),
        record_value('configuration'), view])
    original = prepare_proposal_for_model(model, **fields(model)).original
    put(tmp_path, original.path, original.source_bytes)
    result = check_proposal_project(tmp_path, original.data['id'])
    assert result.exit_code == 0, result.as_dict()
    checks = result.as_dict()['result']['checks']
    assert checks['queries'] == [dict(artifact_id=view['id'], result=resolve_view(model, view['id']).data)]
    outputs = [r for r in checks['renders'] if r['artifact_id'] == view['id']]
    assert {r['format'] for r in outputs} == {'json', 'markdown', 'html'}
    raw = canonical_json_bytes(resolve_view(model, view['id']).data)
    assert next(r for r in outputs if r['format'] == 'json')['sha256'] == sha256(raw).hexdigest()


@pytest.mark.parametrize('flag,value', [('--execute', None), ('--configuration', 'selected'),
                                      ('--expected-revision', '1'), ('--plugin', 'run.py')])
def test_check_rejects_execution_write_and_unimplemented_variant_options(tmp_path, flag, value):
    _, original = validation_project(tmp_path)
    before = inventory(tmp_path)
    argv = ['proposal', 'check', original.data['id'], flag] + ([] if value is None else [value])
    result = dispatch_result(argv, cwd=tmp_path)
    assert result.exit_code == 2, result.as_dict()
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('supplied', ['missing', 'matching', 'changed'])
def test_existing_trusted_native_source_provider_is_rechecked_for_basis_and_target(tmp_path, supplied):
    from specroad.cli.invocation_context import InvocationContextBuilder
    from specroad.proposals import prepare_proposal_for_model
    from specroad.recovery.services import RestoreServices
    from support.records import record_value
    from support.domain import domain_value
    from support.model import put
    from test_proposal_basis import project, fields
    raw = b'Synthetic immutable source text'
    source = record_value('source', excerpt=raw.decode(), content_sha256=sha256(raw).hexdigest())
    model = project(tmp_path, artifacts=[record_value('document'), domain_value('goal'),
        record_value('configuration'), source])
    original = prepare_proposal_for_model(model, **fields(model)).original
    put(tmp_path, original.path, original.source_bytes)
    calls = []
    def provide(model, record):
        calls.append((model._sources_sha256, record.data['id']))
        return raw if supplied == 'matching' else b'Changed source'
    context = InvocationContextBuilder(restore_services=RestoreServices(
        source_content=None if supplied == 'missing' else provide))
    before = inventory(tmp_path)
    result = dispatch_result(['proposal', 'check', original.data['id']], cwd=tmp_path, context_builder=context)
    assert result.exit_code == {'missing': 3, 'matching': 0, 'changed': 6}[supplied], result.as_dict()
    report = result.as_dict()['result']
    assert report['passed'] is (supplied == 'matching')
    assert len(calls) == {'missing': 0, 'matching': 2, 'changed': 1}[supplied]
    assert report['workspace']['cleanup'] == 'removed'
    assert inventory(tmp_path) == before


def test_uncached_temp_environment_is_checked_before_stdlib_write_probes(tmp_path, monkeypatch):
    _, original = validation_project(tmp_path)
    before = inventory(tmp_path)
    monkeypatch.setattr(tempfile, 'tempdir', None)
    monkeypatch.setenv('TMPDIR', str(tmp_path))
    def forbidden(*args, **kwargs): raise AssertionError('No tempdir probe may write inside the project')
    monkeypatch.setattr(tempfile, '_get_default_tempdir', forbidden)
    monkeypatch.setattr(tempfile, 'mkdtemp', forbidden)
    result = check_proposal_project(tmp_path, original.data['id'])
    assert result.exit_code == 7, result.as_dict()
    assert result.as_dict()['result']['workspace']['cleanup'] == 'not_created'
    assert inventory(tmp_path) == before
