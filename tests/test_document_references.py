"""One source-owned target identity across document reference projections."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
from hashlib import sha256
import json
import shutil

import pytest

from specroad.documents import (ArtifactReferenceResolution,
    assess_document_structure, resolve_artifact_reference)
from specroad.model.canonical import canonical_json_sha256
from specroad.model.errors import ModelError
from specroad.model.paths import artifact_path
from support.domain import domain_value, relation
from support.portable import build_distribution
from support.processes import run_core, run_python
from support.read_only import inventory, no_write_attempts
from support.records import block_value, record_value, ref
from support.targets import model, SCOPE
from test_document_roles import document
from test_document_structure import contains, section


def referenced_documents(mode='summary'):
    blocks = []
    for token, edge in (('0', '4'), ('1', '5')):
        value = block_value('artifact_ref'); value['id'] = ref('BLOCK', token)
        value['payload']['render_mode'] = mode
        value['relations'][0]['relation_id'] = 'REL-' + edge * 26
        blocks.append(value)
    return [document(relations=[contains(ref('SEC'), '0')]),
        document('1', document_role='supporting', relations=[contains(ref('SEC', '1'), '1')]),
        section(relations=[contains(ref('BLOCK'), '2')]),
        section('1', relations=[contains(ref('BLOCK', '1'), '3')]),
        *blocks, domain_value('requirement')]


@pytest.mark.parametrize('mode', ['summary', 'full', 'link'])
def test_multiple_documents_resolve_the_same_actual_target_identity_without_stored_copies(mode):
    records = referenced_documents(mode); supplied = model(records); before = supplied.source_files
    with no_write_attempts():
        structure = assess_document_structure(supplied)
        document_blocks = [structure.require_document(ref('DOC', token))['preorder'][1]['artifact_id']
                           for token in ('0', '1')]
        resolved = [resolve_artifact_reference(supplied, ident) for ident in document_blocks]
    assert document_blocks == [ref('BLOCK'), ref('BLOCK', '1')]
    assert resolved[0].target_source_bytes == resolved[1].target_source_bytes
    assert resolved[0].data['target'] == resolved[1].data['target']
    assert resolved[0].target_record == resolved[1].target_record == records[-1]
    for result, block in zip(resolved, records[4:6]):
        data = result.data; target = data['target']; source_path = artifact_path('content_block', block['id'], 'SR')
        assert data['reference_resolved'] and data['render_mode'] == mode
        assert data['block']['artifact_id'] == block['id']
        assert data['block']['source_sha256'] == sha256(before[source_path]).hexdigest()
        assert result.block_source_bytes == before[source_path]
        assert data['relation']['target_id'] == target['artifact_id'] == ref()
        assert data['relation']['record'] == block['relations'][0]
        assert data['relation']['pointer'] == '/relations/0'
        assert data['relation']['record_sha256'] == canonical_json_sha256(block['relations'][0])
        assert target['revision'] == records[-1]['revision']
        assert target['record_sha256'] == canonical_json_sha256(records[-1])
        assert target['source_sha256'] == sha256(result.target_source_bytes).hexdigest()
        assert data['model_root_sha256'] == supplied.manifest(supplied.artifacts, SCOPE).sha256
        assert data['input_sha256'] == supplied._sources_sha256 and data['scope_descriptor'] == SCOPE
        assert not any(data[k] for k in ('project_files_verified', 'full_validation_passed',
            'document_structure_checked', 'document_roles_checked', 'include_graph_checked',
            'payload_semantics_evaluated', 'rendering_performed', 'write_authorized', 'approval_granted'))
        assert block['payload'] == {'render_mode': mode}
    assert supplied.source_files == before


@pytest.mark.parametrize('shift', range(7))
def test_supplied_file_order_does_not_select_a_different_reference_or_target(shift):
    records = referenced_documents(); expected = resolve_artifact_reference(model(records), ref('BLOCK'))
    moved = records[shift:] + records[:shift]
    actual = resolve_artifact_reference(model(moved), ref('BLOCK'))
    assert actual.data == expected.data and actual.sha256 == expected.sha256
    assert actual.target_source_bytes == expected.target_source_bytes


def test_reference_is_selected_by_relation_type_and_preserves_the_actual_array_pointer():
    records = referenced_documents(); block = records[4]
    provenance = dict(relation('derived_from', ref('SRC')), relation_id='REL-' + '6' * 26)
    block['relations'].insert(0, provenance); records.append(record_value('source'))
    result = resolve_artifact_reference(model(records), block['id'])
    assert result.data['relation']['pointer'] == '/relations/1'
    assert result.data['relation']['record'] == block['relations'][1]
    assert result.target_record == records[-2]


def test_resolution_is_owned_and_returned_target_values_cannot_change_its_binding():
    records = referenced_documents(); result = resolve_artifact_reference(model(records), ref('BLOCK'))
    before = result.data; original_target = deepcopy(records[-1])
    records[-1]['statement'] = 'Changed caller object'
    result.target_record['statement'] = 'Changed detached projection'
    result.data['target']['record'].clear()
    assert result.data == before and result.target_record == original_target
    with pytest.raises(FrozenInstanceError): result.target_source_bytes = b'{}'
    with pytest.raises(TypeError): bool(result)
    with pytest.raises(TypeError): ArtifactReferenceResolution()


def test_owned_snapshot_resolution_neither_reopens_nor_changes_supplied_files(tmp_path):
    supplied = model(referenced_documents()); root = tmp_path / 'project'
    for name, raw in supplied.source_files.items():
        path = root / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(raw)
    before = inventory(root)
    with no_write_attempts(): result = resolve_artifact_reference(supplied, ref('BLOCK'))
    assert inventory(root) == before
    shutil.rmtree(root)
    with no_write_attempts(): repeated = resolve_artifact_reference(supplied, ref('BLOCK'))
    assert repeated.data == result.data and repeated.target_source_bytes == result.target_source_bytes
    assert not root.exists()


@pytest.mark.parametrize('count', [0, 2])
def test_reference_block_cannot_resolve_zero_or_multiple_stored_targets(count):
    records = referenced_documents(); block = records[4]; block['relations'] *= count
    if count == 2: block['relations'][1] = dict(block['relations'][1], relation_id='REL-' + '6' * 26)
    supplied = model(records)
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        resolve_artifact_reference(supplied, block['id'])
    assert caught.value.reason == 'block_reference_cardinality' and caught.value.pointer == '/relations'
    assert caught.value.path == artifact_path('content_block', block['id'], 'SR')


def test_missing_target_is_a_bound_native_error_not_an_unresolved_success():
    records = referenced_documents(); records.pop(); supplied = model(records)
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        resolve_artifact_reference(supplied, ref('BLOCK'))
    assert caught.value.reason == 'missing_relation_target'
    assert caught.value.pointer == '/relations/0/target'
    assert caught.value.path == artifact_path('content_block', ref('BLOCK'), 'SR')


@pytest.mark.parametrize('kind', ['prose', 'page_break'])
def test_other_block_kinds_cannot_be_implicitly_promoted_to_artifact_references(kind):
    records = referenced_documents(); records[4] = block_value(kind); supplied = model(records)
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        resolve_artifact_reference(supplied, ref('BLOCK'))
    assert caught.value.reason == 'artifact_reference_block_required'
    assert caught.value.pointer == '/block_kind'


def test_a_nonblock_artifact_cannot_be_used_as_the_reference_source():
    supplied = model(referenced_documents())
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        resolve_artifact_reference(supplied, ref())
    assert caught.value.reason == 'artifact_reference_block_required' and caught.value.pointer == '/block_id'


@pytest.mark.parametrize('kind,field', [('requirement', 'statement'), ('document', 'purpose')])
def test_resolved_target_must_pass_its_own_native_type_specific_fields(kind, field):
    target = domain_value(kind) if kind == 'requirement' else record_value(kind)
    block = block_value('artifact_ref'); block['relations'][0]['target'] = target['id']; target.pop(field)
    supplied = model([block, target])
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        resolve_artifact_reference(supplied, block['id'])
    assert caught.value.path == artifact_path(kind, target['id'], 'SR')


@pytest.mark.parametrize('unbound', [None, {}, [], b'{}'])
def test_resolution_requires_actual_owned_target_model_inputs(unbound):
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        resolve_artifact_reference(unbound, ref('BLOCK'))
    assert caught.value.reason == 'document_target_model_required'


@pytest.mark.parametrize('mode', ['core', 'pyz'])
def test_reference_resolution_has_identical_source_bindings_in_isolated_core_and_pyz(tmp_path, mode):
    supplied = model(referenced_documents()); expected = resolve_artifact_reference(supplied, ref('BLOCK')).data
    body = '''import json
from specroad.changes import TargetModel
from specroad.documents import resolve_artifact_reference
from specroad.model.model_manifest import ProjectReadBinding
from specroad.profiles import ProfileResource, compose_profiles
from specroad.validation import ModelDocument
'''
    body += 'config=' + repr(supplied.configuration_bytes) + '\n'
    body += 'documents=' + repr([(d.path, d.content) for d in supplied.documents]) + '\n'
    body += 'resources=' + repr([(d.path, d.content) for d in supplied.resource_files]) + '\n'
    body += 'core_key=' + repr(supplied.profile.profile_chain[0]) + '\n'
    body += '''profile=compose_profiles([ProfileResource(raw) for path,raw in resources],core_key=core_key)
owned=TargetModel(config,ProjectReadBinding('sample','/explicit/provider',(1,2)),
 [ModelDocument(path,raw) for path,raw in documents],profile=profile,
 resource_files=[ModelDocument(path,raw) for path,raw in resources])
'''
    body += 'print(json.dumps(resolve_artifact_reference(owned,' + repr(ref('BLOCK')) + ').data,sort_keys=True))\n'
    if mode == 'core': result = run_core(body, tmp_path, capture=True)
    else:
        _, package = build_distribution(tmp_path / 'distribution')
        result = run_python(['-I', '-S', '-B', '-c',
            'import sys;sys.path.insert(0,' + repr(str(package)) + ')\n' + body], tmp_path, capture=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == expected
