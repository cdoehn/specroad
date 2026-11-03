"""Source contract rejection, original protection and historical boundaries."""
import copy
import json
from pathlib import Path
from hashlib import sha256

import pytest
from specroad.migration.reference01 import inventory_bytes, inventory_project, SourceError
from specroad.security import SafetyViolation
from support.reference01 import (full_project, minimal, release_project, encoded, put, seal,
                                 artifact, digest, context, snapshot)


def rejects(files, reason):
    before = dict(files)
    with pytest.raises(SourceError) as caught: inventory_bytes(files)
    assert caught.value.reason == reason
    assert files == before


@pytest.mark.parametrize('change,reason', [
    ('absent', 'source_contract_required'), ('version', 'unsupported_source_contract'),
    ('id', 'unsupported_source_contract'), ('extra', 'unsupported_source_contract')])
def test_contract_selection_is_explicit_and_closed(change, reason):
    files = minimal(); config = json.loads(files['specroad.json'])
    if change == 'absent':del config['source_contract']
    elif change == 'version':config['source_contract']['contract_version'] = '1.0.0'
    elif change == 'id':config['source_contract']['contract_id'] = 'untrusted.provider'
    else:config['source_contract']['module'] = 'evil.py'
    files['specroad.json'] = encoded(config); rejects(files, reason)


@pytest.mark.parametrize('raw', [b'\xef\xbb\xbf{}', b'{"a":1,"a":2}', b'{"a":NaN}',
    b'{"a":9007199254740993}', b'{"a":"\\ud800"}', b'{} true', b'\xff'])
def test_strict_source_json_rejects_lossy_or_ambiguous_values(raw):
    files = minimal(); files['specroad.json'] = raw; rejects(files, 'source_schema_invalid')


@pytest.mark.parametrize('kind', ['goal', 'need', 'capability', 'requirement', 'scenario',
    'decision', 'risk', 'assumption', 'component', 'interface', 'release', 'milestone',
    'task', 'term', 'source', 'verification', 'test', 'evidence', 'baseline', 'proposal',
    'issue', 'document', 'section', 'content_block', 'view', 'code_ref', 'relation_review', 'configuration'])
def test_every_source_type_rejects_unknown_and_missing_fields(kind):
    for change in ('extra', 'missing'):
        files = full_project()
        name = next(p for p, raw in files.items() if p.startswith('spec/') and json.loads(raw)['artifact_type'] == kind)
        value = json.loads(files[name])
        if change == 'extra':value['executable_provider'] = 'evil'
        else:del value['title']
        files[name] = encoded(value); rejects(files, 'source_schema_invalid')


@pytest.mark.parametrize('name', ['rules/unknown.json', 'mappings/unknown.json', 'profiles/extra.json', 'spec/code.py'])
def test_unknown_normative_resources_are_not_silently_ignored(name):
    files = minimal(); files[name] = b'{}'; rejects(files, 'source_resource_unsupported')


@pytest.mark.parametrize('name', ['../outside', '/absolute', 'spec//file', 'x\\y', './relative', 'x/../y'])
def test_noncanonical_paths_fail_before_reading(name):
    files = minimal(); files[name] = b'x'; rejects(files, 'source_schema_invalid')


def test_unicode_and_case_path_aliases_are_conflicts():
    for pair in [('data/e\u0301', 'data/é'), ('data/Value', 'data/value')]:
        files = minimal(); files.update({p: b'x' for p in pair}); rejects(files, 'source_identity_conflict')


def test_current_path_and_project_identity_cannot_alias():
    files = minimal(); value = json.loads(files.pop('spec/goals/SR-GOAL-0001.json'))
    value['id'] = 'OTHER-GOAL-0001'; put(files, value); rejects(files, 'source_identity_conflict')


@pytest.mark.parametrize('fault', ['missing', 'modified', 'size', 'root'])
def test_baseline_originals_and_root_are_required(fault):
    files = full_project(); name = 'spec/baselines/SR-BASE-0001.json'; baseline = json.loads(files[name])
    row = baseline['manifest'][0]; address = 'archive/objects/' + row['byte_sha256'][:2] + '/' + row['byte_sha256']
    if fault == 'missing':del files[address]
    elif fault == 'modified':files[address] += b' '
    elif fault == 'size':row['size'] += 1; put(files, baseline)
    else:baseline['model_root_sha256'] = '0' * 64; put(files, baseline)
    rejects(files, 'source_payload_missing' if fault == 'missing' else 'source_hash_mismatch')


def test_unregistered_archive_object_cannot_replace_historical_subject():
    files = full_project(); value = json.loads(files['spec/requirements/SR-REQ-0001.json'])
    raw = files['spec/requirements/SR-REQ-0001.json']; token = sha256(raw).hexdigest()
    files['archive/objects/' + token[:2] + '/' + token] = raw
    value['revision'] = 2; value['statement'] = 'New text'; put(files, value)
    rejects(files, 'source_closure_incomplete')


@pytest.mark.parametrize('field', ['artifact_sha256', 'verification_context_sha256'])
def test_evidence_uses_source_full_and_context_hashes(field):
    files = full_project(); value = json.loads(files['spec/evidence/SR-EVD-0001.json'])
    value['subjects'][0][field] = '0' * 64; put(files, value)
    rejects(files, 'source_closure_incomplete' if field == 'artifact_sha256' else 'source_hash_mismatch')


@pytest.mark.parametrize('fault', ['missing', 'wrong_id', 'evaluation', 'working'])
def test_release_selection_never_guesses_or_uses_current_release(fault):
    files = release_project(); value = json.loads(files['spec/baselines/SR-BASE-0002.json'])
    if fault == 'missing':del value['release_id']
    elif fault == 'wrong_id':value['release_id'] = 'SR-REL-9999'
    elif fault == 'evaluation':value['verification_evaluation']['created_by']['actor_id'] = 'changed'
    else:value['baseline_kind'] = 'working'
    put(files, value)
    rejects(files, {'missing':'source_schema_invalid','wrong_id':'source_closure_incomplete',
                   'evaluation':'source_hash_mismatch','working':'source_schema_invalid'}[fault])


def test_changed_current_release_does_not_rebind_historical_snapshot():
    files = release_project(); value = json.loads(files['spec/releases/SR-REL-0002.json'])
    value['revision'] = 2; value['readiness_policy'] = {}; put(files, value)
    result = inventory_bytes(files)
    assert any(o.role == 'artifact' and o.data.get('id') == value['id'] and o.data['revision'] == 1
               for o in result.originals)


@pytest.mark.parametrize('kind', ['evidence', 'baseline', 'relation_review', 'proposal'])
def test_special_state_maturity_mismatch_is_never_qualified(kind):
    files = full_project(); name = next(p for p in files if p.startswith('spec/') and json.loads(files[p])['artifact_type'] == kind)
    value = json.loads(files[name]); value['maturity'] = 'rejected' if kind != 'proposal' else 'approved'
    files[name] = encoded(value)
    with pytest.raises(SourceError) as caught:inventory_bytes(files)
    assert caught.value.reason in ('source_state_invalid','source_schema_invalid')


def test_hierarchy_cycles_and_missing_document_parents_fail():
    files = full_project(); section = json.loads(files['spec/sections/SR-SEC-0001.json'])
    section['relations'].append({'type':'contains','target':section['id'],'position':1,'external_identities':[],'extensions':{}})
    put(files, section); rejects(files, 'source_identity_conflict')
    files = full_project(); doc = json.loads(files['spec/documents/SR-DOC-0001.json']); doc['relations'] = []; put(files,doc)
    rejects(files,'source_closure_incomplete')


def test_source_requirement_never_infers_target_language():
    files = full_project(); value = json.loads(files['spec/requirements/SR-REQ-0001.json'])
    assert 'language' not in value and 'normative_force' not in value
    value['language'] = 'en'; put(files,value); rejects(files,'source_schema_invalid')


def test_active_source_operations_block_read_only_entry(tmp_path):
    for name, raw in minimal().items():
        p=tmp_path/name; p.parent.mkdir(parents=True,exist_ok=True); p.write_bytes(raw)
    p=tmp_path/'.specroad/locks/live'; p.parent.mkdir(parents=True); p.write_bytes(b'owner')
    with pytest.raises(SourceError) as caught:inventory_project(tmp_path)
    assert caught.value.reason == 'source_state_invalid'
    assert p.read_bytes() == b'owner'


def test_symlink_payload_is_not_followed(tmp_path):
    files=full_project()
    for name,raw in files.items():
        p=tmp_path/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
    target=tmp_path/'src/reference.py';target.unlink();target.symlink_to('/etc/passwd')
    with pytest.raises(SafetyViolation):inventory_project(tmp_path)
    assert target.is_symlink()


def test_missing_code_payload_has_no_git_or_current_worktree_fallback():
    files=full_project();del files['src/reference.py'];rejects(files,'source_payload_missing')


@pytest.mark.parametrize('status,expected', [('in_review','mutable'),('approved','mutable'),
    ('applied','immutable_legacy'),('rejected','immutable_legacy'),('stale','immutable_legacy')])
def test_proposal_original_history_and_classification(status,expected):
    from support.reference01 import finish_proposal
    files=finish_proposal(full_project(),status); result=inventory_bytes(files)
    current=next(o for o in result.originals if o.snapshot_root==result.model_root_sha256
                 and o.path=='spec/proposals/SR-PROP-0001.json')
    assert current.classification==expected
    assert current.source_bytes==files[current.path]
    assert result.data['human_authority_verified'] is False


@pytest.mark.parametrize('field', ['binding','observed_revision','result_bytes_base64','from'])
def test_broken_proposal_control_originals_fail(field):
    from support.reference01 import finish_proposal
    files=finish_proposal(full_project(),'rejected'); value=json.loads(files['spec/proposals/SR-PROP-0001.json'])
    row=value['control_history'][0]
    if field=='binding':row['binding']['content_sha256']='0'*64
    elif field=='observed_revision':row['observed_revision']=999
    elif field=='result_bytes_base64':row['result_bytes_base64']='!!!!'
    else:row['from']='applied'
    put(files,value)
    with pytest.raises(SourceError):inventory_bytes(files)


@pytest.mark.parametrize('field,value', [('default_locale','no_such_tag'),('default_locale','zzzzzz')])
def test_source_configuration_language_is_bound_to_frozen_registry(field,value):
    files=minimal();config=json.loads(files['specroad.json']);config[field]=value;files['specroad.json']=encoded(config)
    with pytest.raises(SourceError):inventory_bytes(files)


def test_extensions_remain_opaque_and_unicode_is_not_normalized():
    files=minimal(); value=json.loads(files['spec/goals/SR-GOAL-0001.json'])
    value['extensions']={'例.型':{'revision':99,'path':'../../not-a-reference','code':'import os','value':'e\u0301'}}
    put(files,value); result=inventory_bytes(files)
    source=next(o for o in result.originals if o.path=='spec/goals/SR-GOAL-0001.json')
    assert source.data['extensions']==value['extensions']
    assert source.source_bytes==files[source.path]


def test_baseline_cannot_include_a_previous_record_with_its_own_identity():
    files=full_project();seal(files,1);rejects(files,'source_snapshot_cycle')


def test_colliding_parent_directories_are_rejected_even_with_distinct_filenames():
    files=minimal();files.update({'A/one':b'1','a/two':b'2'});rejects(files,'source_identity_conflict')


def test_historical_proposal_basis_is_retained_and_not_claimed_current():
    from support.reference01 import finish_proposal
    files = finish_proposal(full_project(), 'approved'); seal(files, 8)
    old = files['spec/proposals/SR-PROP-0001.json']
    current = json.loads(files['spec/goals/SR-GOAL-0001.json'])
    current['revision'] += 1; current['title'] = 'Changed current goal'; put(files, current)
    result = inventory_bytes(files)
    observed = [r for r in result.data['proposal_bindings'] if r['snapshot_root'] == result.model_root_sha256]
    assert len(observed) == 1 and observed[0]['basis_matches_observed_snapshot'] is False
    assert files['spec/proposals/SR-PROP-0001.json'] == old
    assert result.approval_granted is False


def test_proposal_basis_requires_qualified_originals_not_a_project_root():
    files = full_project(); value = json.loads(files['spec/proposals/SR-PROP-0001.json'])
    value['base']['model_root_sha256'] = snapshot(minimal())[1]
    value['change_plan']['base'] = copy.deepcopy(value['base'])
    value['change_plan']['expected_result']['model_root_sha256'] = value['base']['model_root_sha256']
    value['change_plan']['change_plan_sha256'] = digest({k:v for k,v in value['change_plan'].items() if k != 'change_plan_sha256'})
    excluded = {'revision','created_at','created_by','updated_at','updated_by','content_revision',
        'content_sha256','maturity','proposal_status','reviews','control_history'}
    value['content_sha256'] = digest({k:v for k,v in value.items() if k not in excluded})
    put(files, value); rejects(files, 'source_closure_incomplete')


def test_bound_generated_code_bytes_are_retained_without_execution():
    files = full_project(); seal(files, 2)
    value = json.loads(files['spec/code-refs/SR-CODE-0001.json'])
    value['revision'] += 1
    raw = files.pop(value['path']); value.update(path='generated/source.py', reference_kind='generated_artifact')
    files[value['path']] = raw; put(files, value)
    result = inventory_bytes(files)
    original = next(o for o in result.originals if o.path == value['path'])
    assert original.source_bytes == raw and original.classification == 'referenced_payload'


@pytest.mark.parametrize('kind', ['evidence','relation_review'])
def test_immutable_original_cannot_change_across_registered_snapshots(kind):
    files = full_project(); seal(files, 2)
    name = next(p for p in files if p.startswith('spec/') and json.loads(files[p])['artifact_type'] == kind)
    value = json.loads(files[name]); value['revision'] += 1; value['title'] = 'Changed immutable original'
    put(files, value); rejects(files, 'source_state_invalid')


def test_prose_attachment_closure_binds_original_bytes(tmp_path):
    files = full_project(); seal(files, 2)
    block = json.loads(files['spec/content-blocks/SR-BLOCK-0001.json'])
    block['revision'] += 1
    block['payload'] = {'markdown':'See [original](attachments/original.bin).'}
    put(files, block); files['attachments/original.bin'] = b'original\0bytes'
    for name, raw in files.items():
        p = tmp_path / name; p.parent.mkdir(parents=True,exist_ok=True); p.write_bytes(raw)
    result = inventory_project(tmp_path)
    original = next(o for o in result.originals if o.path == 'attachments/original.bin')
    assert original.source_bytes == files[original.path]
    assert original.classification == 'referenced_payload'
    del files['attachments/original.bin']; rejects(files, 'source_payload_missing')
