"""21.e1.W: saved Merge/Migration targets and native Proposal originals."""
from copy import deepcopy
from pathlib import Path
import json
import pytest
from specroad.model.errors import ModelError
from specroad.model.canonical import canonical_json_bytes as jcs
from support.force_cases import files, ALLOW
from test_force_domains import product, AI


@pytest.mark.parametrize('domain', ['merge', 'migration'])
def test_saved_domain_executes_original_target_and_binds_retry(domain, tmp_path):
    if domain == 'merge':
        from support.merge_publication import setup, apply
        root, plan, options, target = setup(tmp_path)
        expected = target.files
    else:
        from support.migration_transaction import setup, apply
        from support.migration_plans import planned_files
        root, source, plan, options = setup(tmp_path)
        expected = planned_files(source, plan)
    options.update(force=True, force_reason='Explicit saved target', expected_plan_sha256='0'*64)
    first = apply(root, plan, options)
    assert product(root) == expected
    assert first['status'] == 'forced' and not first['approval_granted']
    assert first['audit']['plan']['native_intent']['intent']['plan'] == plan.data
    assert any(row['gate_id'] == 'hash:saved_plan' for row in first['force']['overrides'])
    after = files(root)
    replay = apply(root, plan, options)
    assert replay['replayed'] and replay['plan_sha256'] == first['plan_sha256']
    assert files(root) == after
    with pytest.raises(ModelError): apply(root, plan, {**options, 'expected_plan_sha256': plan.sha256})
    assert files(root) == after


@pytest.mark.parametrize('command', ['proposal.review.start', 'proposal.review', 'proposal.apply'])
def test_proposal_force_preserves_original_reviews_and_records_actual_actor(tmp_path, command):
    from support.proposal_apply import ApplyCase
    from specroad.proposals.force import author
    case = ApplyCase(tmp_path/'project')
    root = case.root; path = case.original.path
    before = json.loads((root/path).read_bytes())
    options = dict(command=command, expected_revision=before['revision']+1, actor=AI,
        request_id='forced-control', authority=ALLOW, force=True)
    if command == 'proposal.review': options.update(decision='approved', comment='Explicit synthetic decision')
    result = author(root, before['id'], **options)
    after = json.loads((root/path).read_bytes())
    assert result['status'] == 'forced' and result['approval_granted'] is False
    assert after['reviews'] == before['reviews'] and after['control_history'] == before['control_history']
    assert after['updated_by'] == AI
    assert result['audit']['plan']['native_intent']['intent']['expected_revision'] == before['revision']+1
    assert author(root, before['id'], **options)['replayed']
