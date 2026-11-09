"""Actual isolated full checks; original inventories and independent native results."""
from datetime import datetime
from hashlib import sha256
from pathlib import Path
import json
import shutil
import tempfile

import pytest

from specroad.cli.application import dispatch_result, execute_request
from specroad.cli.result_schemas import validate_result_document
from specroad.documents.rendering import render_document
from specroad.model.canonical import canonical_json_sha256
from specroad.proposals.check import check_proposal_project
from specroad.proposals.context import ProposalContext, reconstruct_proposal_target
from specroad.proposals.scope import specification_manifest
from support.proposal_validation import validation_project
from support.read_only import inventory


@pytest.mark.parametrize('changed,bundled', [(False, False), (True, False), (False, True)])
def test_check_uses_actual_target_and_full_native_gates_without_original_writes(tmp_path, changed, bundled):
    root = tmp_path / 'project'
    basis, original = validation_project(root, changed=changed, bundled=bundled)
    before = inventory(root)
    outcome = check_proposal_project(root, original.data['id'])
    assert outcome.exit_code == 0, outcome.as_dict()
    report = outcome.as_dict()['result']
    target = reconstruct_proposal_target(ProposalContext(original, basis))
    assert report['passed'] and report['full_semantic_validation']
    assert report['target_model_root_sha256'] == specification_manifest(target).sha256
    from specroad.authoring._inspection_snapshot import InspectionSnapshot
    live = InspectionSnapshot(root, None).model
    assert report['target_sources_sha256'] == reconstruct_proposal_target(ProposalContext(original, live))._sources_sha256
    assert report['binding'] == original.binding.data
    assert report['proposal_sha256'] == sha256(original.source_bytes).hexdigest()
    assert set(report['checks']) == {'validation', 'lint', 'diff', 'impact', 'queries', 'renders'}
    assert all(v['checks_complete'] and v['model_valid'] for v in report['checks']['validation'].values())
    assert report['checks']['diff']['changed'] is changed
    assert bool(report['checks']['impact']) is changed
    assert report['checks']['lint']['core_checks_passed']
    assert report['observed_status'] == 'draft' and report['eligible_transition'] is None
    assert report['workspace'] == dict(retained=False, path=None, cleanup='removed')
    assert report['audit']['proposal_id'] == original.data['id']
    assert report['audit']['base'] == original.data['base']
    assert report['audit']['outcome'] == 'passed'
    assert datetime.fromisoformat(report['audit']['ended_at'].replace('Z', '+00:00')) >= datetime.fromisoformat(report['audit']['started_at'].replace('Z', '+00:00'))
    doc = next(a for a in target.artifacts if a['artifact_type'] == 'document')
    raw = render_document(target, doc['id'])
    assert report['checks']['renders'] == [dict(artifact_id=doc['id'], format='markdown', size=len(raw), sha256=sha256(raw).hexdigest())]
    assert not report['approval_granted'] and not report['write_authorized']
    validate_result_document('proposal-check-v1', report)
    digest = report.pop('result_sha256')
    assert digest == canonical_json_sha256(report)
    assert inventory(root) == before


@pytest.mark.parametrize('form', ['id', 'relative', 'absolute', 'external'])
def test_check_public_argv_and_request_use_the_same_read_operand_contract(tmp_path, form):
    root = tmp_path / 'project'
    _, original = validation_project(root, changed=True)
    external = tmp_path / 'proposal.json'; external.write_bytes(original.source_bytes)
    operand = dict(id=original.data['id'], relative=original.path,
                   absolute=str(root / original.path), external=str(external))[form]
    before = inventory(tmp_path)
    result = dispatch_result(['proposal', 'check', operand], cwd=root)
    request = execute_request({'command_id': 'proposal.check', 'arguments': {'proposal': operand}}, cwd=root).result
    assert result.exit_code == request.exit_code == 0, (result.as_dict(), request.as_dict())
    left, right = result.as_dict()['result'], request.as_dict()['result']
    for key in ('passed', 'binding', 'context_sha256', 'target_model_root_sha256', 'checks'):
        assert left[key] == right[key]
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('keep', [False, True])
def test_real_workspace_contains_basis_and_separate_changed_target_only_when_retained(tmp_path, monkeypatch, keep):
    from specroad.proposals import check
    root, temporary = tmp_path / 'project', tmp_path / 'temp'
    temporary.mkdir()
    monkeypatch.setattr(tempfile, 'tempdir', str(temporary))
    basis, original = validation_project(root, changed=True)
    before = inventory(root)
    result = check_proposal_project(root, original.data['id'], keep_workspace=keep)
    assert result.exit_code == 0, result.as_dict()
    report = result.as_dict()['result']
    assert inventory(root) == before
    if keep:
        workspace = Path(report['workspace']['path'])
        try:
            goal = next(d for d in basis.documents if json.loads(d.content)['artifact_type'] == 'goal')
            assert (workspace / 'basis' / goal.path).read_bytes() == goal.content
            assert b'Native proposed change' in (workspace / 'target' / goal.path).read_bytes()
            assert workspace.stat().st_mode & 0o777 == 0o700
            assert (workspace / 'target' / goal.path).stat().st_mode & 0o111 == 0
        finally:
            shutil.rmtree(workspace)
    else:
        assert not list(temporary.iterdir())


def test_full_check_rejects_a_model_which_passes_structure_only(tmp_path):
    from specroad.proposals import prepare_proposal_for_model
    from specroad.proposals.project_validation import validate_proposal_project
    from support.domain import domain_value
    from support.records import record_value
    from support.model import put
    from test_proposal_basis import project, fields
    # A complete inventory without the required primary specification document.
    model = project(tmp_path, artifacts=[domain_value('goal'), record_value('configuration')])
    original = prepare_proposal_for_model(model, **fields(model)).original
    put(tmp_path, original.path, original.source_bytes)
    assert validate_proposal_project(tmp_path, original.data['id']).exit_code == 0
    before = inventory(tmp_path)
    result = check_proposal_project(tmp_path, original.data['id'])
    assert result.exit_code == 3, result.as_dict()
    data = result.as_dict()['result']
    assert not data['passed'] and data['eligible_transition'] is None
    assert data['audit']['diagnostics'] and data['audit']['outcome'] == 'failed'
    assert data['workspace']['cleanup'] == 'removed'
    assert inventory(tmp_path) == before


def test_native_query_and_render_read_proposed_values(tmp_path):
    from specroad.proposals import prepare_proposal_for_model
    from specroad.query import NormalizedQuery
    from support.domain import domain_value
    from support.records import record_value, block_value, ref
    from support.relations import edge
    from support.model import put
    from test_proposal_basis import project, planned_change
    doc = record_value('document')
    block = block_value('query')
    block['relations'] = []
    block['payload'] = dict(query=NormalizedQuery(filters={'type': ['goal']}, limit=10).data,
        columns=[{'field': '/statement'}], empty_policy='omit')
    doc['relations'] = [edge('contains', ref('SEC'), number=1, position=0)]
    section = record_value('section', relations=[edge('contains', ref('BLOCK'), number=2, position=0)])
    model = project(tmp_path, artifacts=[doc, section, block, domain_value('goal'), record_value('configuration')])
    from specroad.documents.tables import resolve_table_block
    basis_query = resolve_table_block(model, block['id']).data
    assert basis_query['rows'][0]['cells'] == [{'type': 'string', 'value': 'Reduce setup effort.'}]
    basis_rendered = render_document(model, doc['id'])
    assert br'Reduce setup effort\.' in basis_rendered
    assert b'Native proposed change' not in basis_rendered
    original = prepare_proposal_for_model(model, **planned_change(model)).original
    put(tmp_path, original.path, original.source_bytes)
    before = inventory(tmp_path)
    result = check_proposal_project(tmp_path, original.data['id'])
    assert result.exit_code == 0, result.as_dict()
    report = result.as_dict()['result']
    assert report['checks']['queries'][0]['result']['rows'][0]['cells'][0]['value'] == 'Native proposed change'
    target = reconstruct_proposal_target(ProposalContext(original, model))
    rendered = render_document(target, doc['id'])
    assert b'Native proposed change' in rendered
    assert rendered != basis_rendered
    assert br'Reduce setup effort\.' not in rendered
    assert report['checks']['renders'] == [dict(artifact_id=doc['id'], format='markdown',
        size=len(rendered), sha256=sha256(rendered).hexdigest())]
    assert inventory(tmp_path) == before
    assert report['audit']['changed_ids'] == [next(a['id'] for a in model.artifacts if a['artifact_type'] == 'goal')]
    assert report['checks']['impact'][0]['before'] is not None
    assert report['checks']['impact'][0]['after'] is not None
