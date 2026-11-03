"""Native source inventory acceptance; all execution belongs to Apply."""
import copy
import json
import subprocess
import sys
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch

import pytest
from specroad.migration.reference01 import inventory_bytes, inventory_project, SourceError
from support.reference01 import (CONTRACT, full_project, minimal, put, seal, snapshot,
    artifact, encoded, digest, context, scope, path)
from support.portable import build_distribution


@pytest.mark.parametrize('contract_vector', ['project', 'baseline'])
def test_literal_normative_snapshot_oracles(contract_vector):
    vectors = json.loads((CONTRACT / 'vectors.json').read_bytes())
    files = minimal()
    if contract_vector == 'baseline':
        raw = (CONTRACT / vectors['baseline']['artifact']).read_bytes()
        # Preserve the literal vector bytes: re-encoding changes its byte hash.
        record = json.loads(raw)
        files[path(record)] = raw
        for p in (CONTRACT / 'vectors/archive/objects').rglob('*'):
            if p.is_file(): files[p.relative_to(CONTRACT / 'vectors').as_posix()] = p.read_bytes()
    result = inventory_bytes(files)
    if contract_vector == 'project':
        assert result.model_root_sha256 == vectors['project']['expected_model_root_sha256']
        assert result.data['entries'] == json.loads((CONTRACT / vectors['project']['expected_inventory']).read_bytes())
    else:
        assert vectors['baseline']['expected_model_root_sha256'] in result.data['snapshot_roots']
        original = next(o for o in result.originals if o.role == 'artifact' and o.data['artifact_type'] == 'baseline')
        assert original.source_bytes == raw
        assert original.byte_sha256 == vectors['baseline']['expected_original_byte_sha256']
        assert original.canonical_sha256 == vectors['baseline']['expected_canonical_sha256']
        assert original.classification == 'immutable_legacy'


def test_all_28_types_and_complete_classification_keep_originals():
    files = full_project(); before = dict(files)
    result = inventory_bytes(files)
    current = [o for o in result.originals if o.snapshot_root == result.model_root_sha256]
    assert {o.data['artifact_type'] for o in current if o.role == 'artifact'} == set(
        json.loads((CONTRACT / 'artifact-types.json').read_bytes()))
    for original in current:
        assert original.source_bytes == before[original.path]
        expected = ('referenced_payload' if original.role == 'attachment' else 'immutable_legacy'
            if original.data.get('artifact_type') in ('baseline', 'evidence', 'relation_review') else 'mutable')
        assert original.classification == expected
    assert files == before
    assert result.write_authorized is False and result.approval_granted is False
    assert result.data['human_authority_verified'] is False
    assert result.data['current_readiness_verified'] is False
    with pytest.raises(TypeError):bool(result)


def test_transitive_historical_originals_do_not_resolve_to_current_revision():
    files = full_project(); old = json.loads(files['spec/requirements/SR-REQ-0001.json'])
    seal(files, 2)
    new = copy.deepcopy(old); new['revision'] += 1; new['statement'] = 'Different current text.'; put(files, new)
    result = inventory_bytes(files)
    copies = [o for o in result.originals if o.role == 'artifact' and o.data['id'] == old['id']]
    assert {o.data['revision'] for o in copies} == {1, 2}
    assert any(o.source_bytes == encoded(old) + b'\n' for o in copies)
    assert len(result.data['snapshot_roots']) == 3


def test_json_whitespace_changes_bytes_without_changing_model_root():
    files = minimal(); before = inventory_bytes(files)
    files['specroad.json'] = json.dumps(json.loads(files['specroad.json']), indent=2).replace('\n', '\r\n').encode()
    after = inventory_bytes(files)
    assert after.model_root_sha256 == before.model_root_sha256
    assert after.data['entries'] != before.data['entries']


def test_owned_projections_cannot_mutate_originals():
    result = inventory_bytes(full_project()); data = result.data; data['entries'].clear()
    original = next(o for o in result.originals if o.role == 'artifact')
    value = original.data; value['title'] = 'altered'
    assert result.data['entries'] and original.data['title'] != 'altered'


@pytest.mark.parametrize('selector', [
    {'kind': 'byte_range', 'start_offset': 0, 'end_offset': 5},
    {'kind': 'line_range', 'start_line': 1, 'end_line': 1, 'encoding': 'utf-8'}])
def test_source_anchor_uses_bound_original_bytes(selector):
    files = full_project(); seal(files, 2); value = json.loads(files['spec/code-refs/SR-CODE-0001.json'])
    raw = files[value['path']]
    selected = raw[:5] if selector['kind'] == 'byte_range' else raw.replace(b'\r\n', b'\n')
    value['revision'] += 1
    value.update(reference_kind='text_anchor', anchor=selector, selection_sha256=sha256(selected).hexdigest())
    put(files, value); result = inventory_bytes(files)
    assert next(o for o in result.originals if o.path == value['path']).source_bytes == raw


def test_project_read_has_no_writes_process_or_network_side_effects(tmp_path):
    files = full_project()
    for name, raw in files.items():
        p = tmp_path / name; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(raw)
    before = {p.relative_to(tmp_path).as_posix(): p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    with patch('subprocess.Popen', side_effect=AssertionError('process')), patch('socket.socket', side_effect=AssertionError('network')):
        result = inventory_project(tmp_path)
    assert result.model_root_sha256 == inventory_bytes(files).model_root_sha256
    assert before == {p.relative_to(tmp_path).as_posix(): p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    assert not (tmp_path / '.specroad').exists()


def test_core_and_pyz_reference_reader_parity_without_optional_packages(tmp_path):
    # Run only in Apply. The child imports trusted installed Core, never source project code.
    module, pyz = build_distribution(tmp_path / 'distribution')
    files = full_project(); project = tmp_path / 'project'; project.mkdir()
    for name, raw in files.items():
        p = project / name; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(raw)
    program = ('import sys,json;sys.path.insert(0,sys.argv[1]);'
        'from specroad.migration.reference01 import inventory_project;'
        'print(json.dumps(inventory_project(sys.argv[2]).data,sort_keys=True))')
    observed = []
    for package in (module, pyz):
        child = subprocess.run([sys.executable, '-I', '-S', '-B', '-c', program, str(package), str(project)],
                               capture_output=True, text=True, check=True)
        observed.append(json.loads(child.stdout))
    assert observed[0] == observed[1] == inventory_bytes(files).data


def test_release_baseline_explicit_id_binds_one_of_two_equal_evaluations():
    from support.reference01 import release_project
    files = release_project(); result = inventory_bytes(files)
    value = next(o.data for o in result.originals if o.role == 'artifact' and o.data['id'] == 'SR-BASE-0002')
    assert value['release_id'] == 'SR-REL-0002'
    assert value['baseline_kind'] == 'release'
    assert result.data['current_readiness_verified'] is False
    assert result.data['approval_granted'] is False


def test_literal_proposal_basis_oracle_and_control_records_are_separate():
    vector = json.loads((CONTRACT / 'vectors/proposal-basis.json').read_bytes())
    files = minimal(); original = inventory_bytes(files)
    assert original.data['proposal_basis_sha256'] == vector['expected_sha256']
    seal(files, 1); current = inventory_bytes(files)
    assert current.model_root_sha256 != original.model_root_sha256
    assert current.data['proposal_basis_sha256'] == original.data['proposal_basis_sha256']


def test_nonempty_original_plan_is_preserved_without_applying_operations():
    from support.reference01 import basis_root
    files = full_project(); old = json.loads(files['spec/requirements/SR-REQ-0001.json'])
    after = copy.deepcopy(old); after['revision'] += 1; after['statement'] = 'Proposed different text.'
    after['updated_at'] = '2026-11-03T00:00:00.000001Z'
    target = dict(files); put(target, after)
    value = json.loads(files['spec/proposals/SR-PROP-0001.json']); plan = value['change_plan']
    plan['operations'] = [{'op':'update','target':old['id'],'expected_revision':old['revision'],
        'patch':[{'op':'replace','path':'/statement','value':after['statement']}]}]
    plan['preconditions'] = [{'kind':'artifact','artifact_id':old['id'],
        'expected_revision':old['revision'],'expected_sha256':digest(old)}]
    plan['result_artifacts'] = [{'artifact':after,'sha256':digest(after)}]
    plan['expected_result']['model_root_sha256'] = basis_root(target)
    plan['change_plan_sha256'] = digest({k:v for k,v in plan.items() if k!='change_plan_sha256'})
    excluded = {'revision','created_at','created_by','updated_at','updated_by','content_revision',
        'content_sha256','maturity','proposal_status','reviews','control_history'}
    value['content_sha256'] = digest({k:v for k,v in value.items() if k not in excluded})
    put(files, value); before = dict(files); result = inventory_bytes(files)
    original = next(o for o in result.originals if o.path == 'spec/proposals/SR-PROP-0001.json')
    assert original.data['change_plan'] == plan
    assert files == before and json.loads(files['spec/requirements/SR-REQ-0001.json']) == old
    assert result.write_authorized is False
