"""No copied targets, identity fallback or stale/fabricated reference revisions."""
from copy import deepcopy
from hashlib import sha256
import json

import pytest

from specroad.changes import TargetModel
from specroad.documents import assess_document_structure, resolve_artifact_reference
from specroad.model.errors import ModelError
from specroad.model.paths import artifact_path
from specroad.validation import ModelDocument
from support.domain import domain_value
from support.portable import build_distribution
from support.processes import run_core, run_python
from support.read_only import inventory, no_write_attempts
from support.records import block_value, record_value, ref
from support.targets import model
from test_document_references import referenced_documents


def rebuild(supplied, documents):
    return TargetModel(supplied.configuration_bytes, supplied.binding, documents,
        profile=supplied.profile, resource_files=supplied.resource_files)


@pytest.mark.parametrize('field', ['target', 'target_id', 'id', 'artifact', 'record', 'statement', 'revision'])
def test_a_matching_target_id_or_normative_copy_is_forbidden_in_the_block_payload(field):
    records = referenced_documents(); target = records[-1]; value = records[4]
    copied = {'target': target['id'], 'target_id': target['id'], 'id': target['id'],
        'artifact': deepcopy(target), 'record': deepcopy(target),
        'statement': target['statement'], 'revision': target['revision']}
    value['payload'][field] = copied[field]; supplied = model(records); before = supplied.source_files
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        resolve_artifact_reference(supplied, value['id'])
    assert caught.value.path == artifact_path('content_block', value['id'], 'SR')
    assert supplied.source_files == before and value['payload'][field] == copied[field]


def test_target_revision_change_updates_all_new_document_projections_without_revising_blocks():
    original = referenced_documents(); before_model = model(original)
    before = [resolve_artifact_reference(before_model, ref('BLOCK', token)) for token in ('0', '1')]
    changed = deepcopy(original); changed[-1]['revision'] += 1
    changed[-1]['statement'] = 'The revised artifact remains one normative source.'
    after_model = model(changed)
    with no_write_attempts(): after = [resolve_artifact_reference(after_model, ref('BLOCK', token)) for token in ('0', '1')]
    assert after[0].target_record == after[1].target_record == changed[-1]
    assert after[0].target_source_bytes == after[1].target_source_bytes
    for old, new in zip(before, after):
        assert new.data['block'] == old.data['block']
        assert new.data['relation'] == old.data['relation']
        assert new.block_source_bytes == old.block_source_bytes
        assert new.data['target']['artifact_id'] == old.data['target']['artifact_id']
        assert new.data['target']['revision'] == old.data['target']['revision'] + 1
        assert new.data['target']['record_sha256'] != old.data['target']['record_sha256']
        assert new.data['model_root_sha256'] != old.data['model_root_sha256']
        assert new.data['input_sha256'] != old.data['input_sha256']
        assert old.target_record == original[-1]
    for name, raw in before_model.source_files.items():
        if name != after[0].data['target']['path']: assert after_model.source_files[name] == raw


def test_target_byte_format_change_changes_source_binding_without_inventing_a_revision():
    supplied = model(referenced_documents()); old = resolve_artifact_reference(supplied, ref('BLOCK'))
    path = old.data['target']['path']; raw = (json.dumps(old.target_record, indent=3) + '\n').encode()
    documents = [ModelDocument(d.path, raw if d.path == path else d.content) for d in supplied.documents]
    updated = rebuild(supplied, documents)
    with no_write_attempts(): new = resolve_artifact_reference(updated, ref('BLOCK'))
    assert new.target_source_bytes == raw and new.target_source_bytes != old.target_source_bytes
    assert new.target_record == old.target_record
    assert new.data['target']['revision'] == old.data['target']['revision']
    assert new.data['target']['record_sha256'] == old.data['target']['record_sha256']
    assert new.data['target']['source_sha256'] == sha256(raw).hexdigest()
    assert new.data['target']['source_sha256'] != old.data['target']['source_sha256']
    assert new.data['model_root_sha256'] == old.data['model_root_sha256']
    assert new.data['input_sha256'] != old.data['input_sha256']
    assert new.data['block'] == old.data['block'] and new.data['relation'] == old.data['relation']


def test_one_block_occurring_in_multiple_documents_still_resolves_one_normative_target():
    records = referenced_documents(); records[3]['relations'][0]['target'] = ref('BLOCK')
    supplied = model(records); structure = assess_document_structure(supplied)
    ids = [structure.require_document(ref('DOC', token))['preorder'][1]['artifact_id'] for token in ('0', '1')]
    assert ids == [ref('BLOCK'), ref('BLOCK')]
    with no_write_attempts(): results = [resolve_artifact_reference(supplied, ident) for ident in ids]
    assert results[0].data == results[1].data and results[0].target_record == records[-1]


@pytest.mark.parametrize('different_content', [False, True])
def test_duplicate_target_identity_is_rejected_before_an_index_can_choose_a_copy(different_content):
    supplied = model(referenced_documents())
    target = next(a for a in supplied.artifacts if a['artifact_type'] == 'requirement')
    if different_content: target['statement'] = 'Conflicting second normative copy.'
    extra = ModelDocument('artifacts/requirement/second-copy.json', json.dumps(target).encode())
    with no_write_attempts(), pytest.raises(ModelError) as caught: rebuild(supplied, [*supplied.documents, extra])
    assert caught.value.reason == 'target_duplicate_artifact_id'


def test_duplicate_reference_identity_across_document_blocks_is_not_collapsed():
    records = referenced_documents(); records[5]['relations'][0]['relation_id'] = records[4]['relations'][0]['relation_id']
    supplied = model(records)
    with no_write_attempts(), pytest.raises(ModelError) as caught: resolve_artifact_reference(supplied, ref('BLOCK'))
    assert caught.value.reason == 'duplicate_relation_id'
    assert caught.value.pointer == '/relations/0/relation_id'
    assert caught.value.path == artifact_path('content_block', ref('BLOCK', '1'), 'SR')


def test_same_title_and_content_do_not_substitute_for_an_absent_target_identity():
    records = referenced_documents(); records[-1]['id'] = ref('REQ', '1'); supplied = model(records)
    with no_write_attempts(), pytest.raises(ModelError) as caught: resolve_artifact_reference(supplied, ref('BLOCK'))
    assert caught.value.reason == 'missing_relation_target'


def test_reference_relation_cannot_be_replaced_by_another_edge_type():
    records = referenced_documents(); records[4]['relations'][0]['type'] = 'derived_from'; supplied = model(records)
    with no_write_attempts(), pytest.raises(ModelError) as caught: resolve_artifact_reference(supplied, ref('BLOCK'))
    assert caught.value.reason == 'block_reference_cardinality'


def test_self_reference_is_rejected_by_the_native_endpoint_contract():
    value = block_value('artifact_ref'); value['relations'][0]['target'] = value['id']; supplied = model([value])
    with no_write_attempts(), pytest.raises(ModelError) as caught: resolve_artifact_reference(supplied, value['id'])
    assert caught.value.reason == 'self_relation_forbidden'
    assert caught.value.pointer == '/relations/0/target'


@pytest.mark.parametrize('selector', [None, True, 0, []])
def test_nonstring_block_selectors_cannot_request_a_default_or_first_block(selector):
    supplied = model(referenced_documents())
    with no_write_attempts(), pytest.raises(ModelError) as caught: resolve_artifact_reference(supplied, selector)
    assert caught.value.reason == 'content_block_id_required' and caught.value.pointer == '/block_id'


@pytest.mark.parametrize('selector', ['', 'a document title', ref('BLOCK', '2')])
def test_absent_block_selector_does_not_fall_back_to_another_reference(selector):
    supplied = model(referenced_documents())
    with no_write_attempts(), pytest.raises(ModelError) as caught: resolve_artifact_reference(supplied, selector)
    assert caught.value.reason == 'content_block_not_found' and caught.value.pointer == '/block_id'


def test_modified_owned_model_cannot_reuse_its_old_snapshot_binding():
    supplied = model(referenced_documents()); original = supplied.documents
    documents = list(original); first = documents[0]
    documents[0] = ModelDocument(first.path, first.content + b'\n')
    object.__setattr__(supplied, 'documents', tuple(documents))
    with no_write_attempts(), pytest.raises(ModelError) as caught: resolve_artifact_reference(supplied, ref('BLOCK'))
    assert caught.value.reason == 'target_sources_changed'


@pytest.mark.parametrize('kind', ['goal', 'source', 'document', 'content_block'])
def test_reference_targets_keep_their_native_type_and_identity_without_document_ownership(kind):
    target = domain_value(kind) if kind == 'goal' else record_value(kind)
    if kind == 'content_block': target['id'] = ref('BLOCK', '2')
    block = block_value('artifact_ref'); block['relations'][0]['target'] = target['id']; supplied = model([block, target])
    with no_write_attempts(): result = resolve_artifact_reference(supplied, block['id'])
    assert result.target_record == target and result.data['target']['artifact_type'] == kind
    assert not result.data['document_structure_checked'] and not result.data['rendering_performed']


def test_legacy_target_identity_is_retained_and_never_renumbered():
    target = domain_value('requirement', id='SR-REQ-0001', id_scheme='legacy-sequential-v1')
    block = block_value('artifact_ref'); block['relations'][0]['target'] = target['id']; supplied = model([block, target])
    with no_write_attempts(): result = resolve_artifact_reference(supplied, block['id'])
    assert result.target_record == target and result.data['relation']['target_id'] == 'SR-REQ-0001'
    assert result.data['target']['artifact_id'] == 'SR-REQ-0001'


def test_rejected_payload_copy_preserves_actual_files_and_revisions(tmp_path):
    records = referenced_documents(); records[4]['payload']['statement'] = records[-1]['statement']; supplied = model(records)
    for name, raw in supplied.source_files.items():
        p = tmp_path / name; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(raw)
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(ModelError): resolve_artifact_reference(supplied, ref('BLOCK'))
    assert inventory(tmp_path) == before
    assert supplied.artifacts == model(records).artifacts


@pytest.mark.parametrize('mode', ['core', 'pyz'])
def test_updated_target_projects_identically_to_both_document_references_in_core_and_pyz(tmp_path, mode):
    records = referenced_documents(); records[-1]['revision'] = 2; records[-1]['statement'] = 'One changed target.'
    supplied = model(records)
    expected = [resolve_artifact_reference(supplied, ref('BLOCK', token)).data for token in ('0', '1')]
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
    body += 'block_ids=' + repr([ref('BLOCK'), ref('BLOCK', '1')]) + '\n'
    body += '''profile=compose_profiles([ProfileResource(raw) for path,raw in resources],core_key=core_key)
owned=TargetModel(config,ProjectReadBinding('sample','/explicit/provider',(1,2)),
 [ModelDocument(path,raw) for path,raw in documents],profile=profile,
 resource_files=[ModelDocument(path,raw) for path,raw in resources])
print(json.dumps([resolve_artifact_reference(owned,ident).data for ident in block_ids],sort_keys=True))
'''
    if mode == 'core': result = run_core(body, tmp_path, capture=True)
    else:
        _, package = build_distribution(tmp_path / 'distribution')
        result = run_python(['-I', '-S', '-B', '-c',
            'import sys;sys.path.insert(0,' + repr(str(package)) + ')\n' + body], tmp_path, capture=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == expected
