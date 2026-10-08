"""Representation changes are byte-bound, value-preserving checked targets."""
from hashlib import sha256
import pytest
from specroad.changes import (TargetModel, TargetError, TargetPolicy,
    assess_change_target, prepare_change_target, dry_run_change,
    execute_change_request, execute_change_plan_bytes, apply_change_plan)
from specroad.model.errors import ModelError
from specroad.model.canonical import canonical_object_sha256
from specroad.validation import ModelDocument
from support.folds import goal, edit
from support.targets import POLICY, SCOPE, gate, resign
from support.publication import files, NativeGuardStorage
from support.normalization import prepared, operation, FIELDS
from support.read_only import inventory, no_write_attempts


def with_documents(model, documents):
    return TargetModel(model.configuration_bytes, model.binding, documents,
        profile=model.profile, resource_files=model.resource_files,
        attachments=model.attachment_descriptors, language_packages=model.language_packages,
        **model.reservations)


def test_target_preserves_complete_values_metadata_and_model_root(tmp_path):
    original = goal(1, revision=7, extensions={'org.test.raw': {'text': 'é e\u0301\r\n 😀',
                    'values': [True, False, None, 3, 2, 1]}})
    m, p, c = prepared(tmp_path, artifacts=[original])
    result = assess_change_target(p, m, policy=POLICY)
    assert result.target_validated and result.artifacts == [original]
    assert p.data['result_artifacts'] == []
    assert result.data['base_manifest'] == result.data['target_manifest']
    assert result.data['diff']['changes'] == []
    assert result.data['lifecycle']['metadata_applied'] is False
    before, after = m.documents[0], result.documents[0]
    assert before.content != after.content
    assert canonical_object_sha256(before.content) == canonical_object_sha256(after.content)
    op = p.data['operations'][0]
    assert sha256(before.content).hexdigest() == op['expected_byte_sha256']
    assert sha256(after.content).hexdigest() == op['target_byte_sha256']
    assert c.request.data['changed_paths'] == [before.path]
    assert c.request.documents == result.documents


def test_direct_and_saved_check_share_plan_and_are_strictly_read_only(tmp_path):
    m, p, _ = prepared(tmp_path)
    before = inventory(tmp_path)
    with no_write_attempts():
        direct = execute_change_request(m, p.data['operations'], dry_run=True,
            fail_on_change=True, policy=POLICY, **FIELDS)
        saved = execute_change_plan_bytes(p.source_bytes, m, dry_run=True,
            fail_on_change=True, policy=POLICY)
    assert direct.data == saved.data
    assert saved.data['would_change'] is True and saved.data['exit_code'] == 1
    assert saved.data['write_state'] == 'not_committed'
    assert saved.data['diff']['changes'] == []
    assert inventory(tmp_path) == before
    assert not (tmp_path / '.specroad').exists()


def test_normalized_input_has_no_byte_change_or_fail_on_change(tmp_path):
    m, p, _ = prepared(tmp_path)
    target = assess_change_target(p, m, policy=POLICY)
    current = with_documents(m, target.documents)
    ops = [operation(d) for d in current.documents]
    result = execute_change_request(current, ops, dry_run=True,
        fail_on_change=True, policy=POLICY, **FIELDS)
    assert result.data['would_change'] is False and result.data['exit_code'] == 0
    assert result.data['assessment']['representation']['changed_paths'] == []
    assert result.data['assessment']['base_manifest'] == result.data['assessment']['target_manifest']


@pytest.mark.parametrize('field', ['expected_byte_sha256', 'target_byte_sha256'])
def test_wrong_bytehash_is_rejected_even_with_a_valid_plan_self_hash(tmp_path, field):
    m, p, _ = prepared(tmp_path)
    invalid = resign(p, lambda data: data['operations'][0].update({field: '0' * 64}))
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(TargetError) as error:
        assess_change_target(invalid, m, policy=POLICY)
    assert error.value.pointer == '/operations/0/' + field
    assert inventory(tmp_path) == before


def test_semantically_identical_new_source_cannot_reuse_old_byte_precondition(tmp_path):
    m, p, _ = prepared(tmp_path)
    current = with_documents(m, [ModelDocument(d.path, b' ' + d.content) for d in m.documents])
    assert current.manifest(current.artifacts, SCOPE).sha256 == p.data['base']['model_root_sha256']
    with pytest.raises(TargetError) as error:
        assess_change_target(p, current, policy=POLICY)
    assert error.value.reason == 'normalization_source_hash_mismatch'


@pytest.mark.parametrize('which', ['base', 'target'])
def test_semantic_root_guards_still_apply(tmp_path, which):
    m, p, _ = prepared(tmp_path)
    field = 'base' if which == 'base' else 'expected_result'
    invalid = resign(p, lambda data: data[field].update(model_root_sha256='0' * 64))
    with pytest.raises(TargetError):
        assess_change_target(invalid, m, policy=POLICY)


@pytest.mark.parametrize('kind', ['artifact', 'file', 'absent'])
def test_common_preconditions_are_not_bypassed(tmp_path, kind):
    m, p, _ = prepared(tmp_path)
    condition = ({'kind': kind, 'artifact_id': m.artifacts[0]['id'], 'expected_revision': 999}
        if kind == 'artifact' else {'kind': kind, 'path': m.documents[0].path})
    if kind == 'file': condition['expected_byte_sha256'] = '0' * 64
    invalid = resign(p, lambda data: data.update(preconditions=[condition]))
    with no_write_attempts(), pytest.raises(ModelError):
        assess_change_target(invalid, m, policy=POLICY)


@pytest.mark.parametrize('path', ['specroad.json', 'profiles/core.json', 'rules/r.json', 'mappings/m.json'])
def test_resource_normalization_requires_exact_sources_without_partial_artifact_target(tmp_path, path):
    m, p, _ = prepared(tmp_path)
    ops = [*p.data['operations'], {**p.data['operations'][0], 'path': path}]
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(TargetError) as error:
        prepare_change_target(m, ops, policy=POLICY, **FIELDS)
    expected = ('normalization_source_hash_mismatch' if path in m.source_files
                else 'normalization_current_source_required')
    assert error.value.reason == expected
    assert inventory(tmp_path) == before


def test_mixed_operations_and_duplicate_paths_are_not_partially_applied(tmp_path):
    m, p, _ = prepared(tmp_path)
    for ops in ([*p.data['operations'], edit(m.artifacts[0], 'different')],
                p.data['operations'] * 2):
        with no_write_attempts(), pytest.raises(TargetError):
            prepare_change_target(m, ops, policy=POLICY, **FIELDS)
    assert files(tmp_path) == m.source_files


def test_normalization_checks_entire_target_and_all_required_command_gates(tmp_path):
    m, p, _ = prepared(tmp_path, artifacts=[goal(1), goal(2)])
    p = resign(p, lambda data: data.update(operations=data['operations'][:1]))
    seen = []
    policy = TargetPolicy('format', '1', ('extension:command',))
    def reject(context):
        seen.append(set(context.subjects))
        return context.result(diagnostics=[{'reason': 'blocked', 'severity': 'error',
                                            'artifact_id': m.artifacts[1]['id']}])
    blocked = assess_change_target(p, m, policy=policy, gates=(gate(check=reject),))
    missing = assess_change_target(p, m, policy=policy)
    assert not blocked.target_validated and not missing.target_validated
    assert seen == [{a['id'] for a in m.artifacts}]
    assert missing.data['missing_command_gates'] == ['extension:command']
    assert not (tmp_path / '.specroad').exists()


def test_existing_execution_backend_checks_normalized_bytes_on_readback(tmp_path):
    m, p, check = prepared(tmp_path)
    store = NativeGuardStorage(m, check)
    result = apply_change_plan(p, m, policy=POLICY, backend=store.backend)
    assert result.data['write_state'] == 'committed' and result.data['would_change'] is True
    assert len(store.calls) == 1
    assert files(tmp_path) == {**m.source_files, **{d.path: d.content for d in check.request.documents}}
    assert store.model.artifacts == m.artifacts
