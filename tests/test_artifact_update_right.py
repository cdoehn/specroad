"""Native lifecycle, ownership, refusal and interrupted update contracts."""
from io import BytesIO
import json
import os
from unittest.mock import patch
import pytest

from specroad.authoring.update import (normalize_artifact_update_input,
    read_artifact_update_input, update_artifact)
from specroad.changes import (AuthoringError, ChangeOperation, ChangePlanError,
    CommitPublicationError, ProjectLockError, PublicationAuthority,
    PublicationCheckError, TargetModel, TargetError, TargetPolicy,
    prepare_change_target, lifecycle_content_sha256, project_lock)
from specroad.changes.update_lifecycle_gate import prepare_update_lifecycle_gate
from specroad.model.canonical import canonical_json_bytes, canonical_json_sha256
from specroad.model.paths import artifact_path
from specroad.validation import ModelDocument, ModelGate
from support.domain import approved_value, domain_value
from support.project_locks import options as lock_options
from support.read_only import inventory as file_inventory, no_write_attempts
from support.targets import SCOPE
from test_artifact_creation import project
from test_artifact_update import ACTOR, TIME, arguments, requirement, edit


def stored_project(root, *, maturity='draft'):
    model, _ = project(root, 'verification')
    value = (approved_value('requirement') if maturity == 'approved'
             else domain_value('requirement', maturity=maturity))
    value['revision'] = 7
    path = artifact_path('requirement', value['id'], 'SR')
    # Intentionally valid but noncanonical bytes: a no-op must not normalize.
    raw = (json.dumps(value, ensure_ascii=False, indent=3) + '\n').encode()
    documents = [ModelDocument(d.path, raw if d.path == path else d.content) for d in model.documents]
    model = TargetModel(model.configuration_bytes, model.binding, documents,
        profile=model.profile, resource_files=model.resource_files)
    (root / path).write_bytes(raw); (root / path).chmod(0o640)
    return model, value, path


@pytest.mark.parametrize('route', ['file', 'stdin'])
@pytest.mark.parametrize('guard', ['revision', 'hash'])
def test_input_read_retains_original_target_despite_caller_mutation(tmp_path, route, guard):
    artifact = domain_value('requirement'); original_id = artifact['id']
    guards = ({'expected_revision': 1} if guard == 'revision'
              else {'expected_sha256': canonical_json_sha256(artifact)})
    raw = b'[{"op":"replace","path":"/statement","value":"Updated"}]'
    saved = tmp_path / 'update.json'; saved.write_bytes(raw)
    def mutate():
        artifact['id'] = 'SR-REQ-' + '1' * 26
        artifact['revision'] = 999
    class ChangingStream(BytesIO):
        def read(self, size):
            mutate()
            return super().read(size)
    native_read = os.read
    def read(fd, size):
        mutate()
        return native_read(fd, size)
    with no_write_attempts(), patch.object(os, 'read', side_effect=read):
        operation = read_artifact_update_input(artifact, input='update.json' if route == 'file' else '-',
            cwd=tmp_path, stdin=ChangingStream(raw), **guards)
    assert artifact['id'] != original_id and artifact['revision'] == 999
    assert operation.data == {'op': 'update', 'target': original_id,
        'patch': [{'op': 'replace', 'path': '/statement', 'value': 'Updated'}], **guards}
    assert saved.read_bytes() == raw


@pytest.mark.parametrize('change', ['language', 'normative_force', 'statement', 'remove_rationale'])
def test_approved_content_change_publishes_proposed_with_one_revision(tmp_path, change):
    root = tmp_path / 'project'; model, old, path = stored_project(root, maturity='approved')
    if change == 'remove_rationale':
        pairs = [('--unset', '/rationale')]; content = dict(old); content.pop('rationale')
    else:
        value = {'language': 'en-US', 'normative_force': 'may', 'statement': 'New proposition.'}[change]
        pairs = [('--set', '/' + change + '=' + json.dumps(value))]; content = {**old, change: value}
    before = file_inventory(root)
    operation = edit(old, options=pairs, expected_revision=7, expected_sha256=canonical_json_sha256(old))
    result = update_artifact(model, operation, **arguments(root))
    actual = json.loads((root / path).read_bytes())
    expected = {**content, 'maturity': 'proposed', 'revision': 8, 'updated_by': ACTOR, 'updated_at': TIME}
    assert actual == expected and (root / path).read_bytes() == canonical_json_bytes(expected)
    assert lifecycle_content_sha256(actual) != lifecycle_content_sha256(old)
    assert result['completion']['commit_completed'] and result['completion']['cleanup_completed']
    after = {p: rest for p, *rest in file_inventory(root)}
    for p, *rest in before:
        if p != path: assert after[p] == rest
    assert (root / path).stat().st_mode & 0o777 == 0o640


@pytest.mark.parametrize('maturity', ['draft', 'proposed'])
@pytest.mark.parametrize('kind', ['empty', 'same', 'reverted'])
def test_noop_preserves_original_noncanonical_bytes_modes_and_no_receipt(tmp_path, maturity, kind):
    root = tmp_path / 'project'; model, old, path = stored_project(root, maturity=maturity)
    pairs = [] if kind == 'empty' else [('--set', '/statement=' + json.dumps(old['statement']))]
    if kind == 'reverted': pairs.insert(0, ('--set', '/statement="Temporary"'))
    before = file_inventory(root)
    result = update_artifact(model, edit(old, options=pairs, expected_revision=7), **arguments(root))
    assert result['no_change'] and result['write_state'] == 'not_committed' and result['completion'] is None
    assert file_inventory(root) == before
    assert (root / path).read_bytes() != canonical_json_bytes(old)
    assert not (root / '.specroad/transactions').exists() and not (root / '.specroad/requests').exists()


@pytest.mark.parametrize('bad', ['revision', 'hash', 'both'])
def test_both_explicit_guards_must_match_before_any_publication(tmp_path, bad):
    root = tmp_path / 'project'; model, _ = project(root, 'verification'); old = requirement(model)
    guards = {'expected_revision': 1, 'expected_sha256': canonical_json_sha256(old)}
    if bad in ('revision', 'both'): guards['expected_revision'] = 2
    if bad in ('hash', 'both'): guards['expected_sha256'] = '0' * 64
    before = file_inventory(root)
    with pytest.raises(ChangePlanError) as error:
        update_artifact(model, edit(old, **guards), **arguments(root))
    assert error.value.reason == ('expected_hash_mismatch' if bad == 'hash' else 'expected_revision_mismatch')
    assert error.value.exit_code == 3 and file_inventory(root) == before


CONTROLLED = [('id', 'SR-REQ-' + '1' * 26), ('id_scheme', 'legacy-sequential-v1'),
              ('artifact_type', 'goal'), ('schema_version', '9.0.0'),
              ('maturity', 'approved'), ('revision', 999)]


@pytest.mark.parametrize('field,value', CONTROLLED)
@pytest.mark.parametrize('route', ['options', 'patch'])
def test_generic_inputs_cannot_change_controlled_identity_and_state(field, value, route):
    kwargs = ({'options': [('--set', '/' + field + '=' + json.dumps(value))]} if route == 'options'
        else {'patch': [{'op': 'replace', 'path': '/' + field, 'value': value}]})
    with no_write_attempts(), pytest.raises(ChangePlanError) as error:
        normalize_artifact_update_input(domain_value('requirement'), expected_revision=1, **kwargs)
    assert error.value.reason == 'controlled_field_mutation' and error.value.exit_code == 3


def test_moving_identity_or_temporarily_replacing_it_cannot_hide_a_mutation():
    value = domain_value('requirement')
    candidates = [dict(patch=[{'op': 'move', 'from': '/id', 'path': '/statement'}]),
        dict(options=[('--set', '/id="SR-REQ-' + '1' * 26 + '"'),
                      ('--set', '/id=' + json.dumps(value['id']))])]
    for kwargs in candidates:
        with no_write_attempts(), pytest.raises(ChangePlanError) as error:
            normalize_artifact_update_input(value, expected_revision=1, **kwargs)
        assert error.value.reason == 'controlled_field_mutation'


@pytest.mark.parametrize('field,value', [CONTROLLED[0], CONTROLLED[4]])
def test_writer_revalidates_forged_typed_operation_before_lock(tmp_path, field, value):
    root = tmp_path / 'project'; model, _ = project(root, 'verification'); old = requirement(model)
    forged = object.__new__(ChangeOperation)
    object.__setattr__(forged, '_encoded', canonical_json_bytes({'op': 'update', 'target': old['id'],
        'expected_revision': 1, 'patch': [{'op': 'replace', 'path': '/' + field, 'value': value}]}))
    before = file_inventory(root)
    with no_write_attempts(), pytest.raises(ChangePlanError) as error:
        update_artifact(model, forged, **arguments(root))
    assert error.value.reason == 'controlled_field_mutation' and file_inventory(root) == before


def test_noop_still_requires_actual_host_authority(tmp_path):
    root = tmp_path / 'project'; model, _ = project(root, 'verification'); before = file_inventory(root)
    options = arguments(root); options['authority'] = PublicationAuthority('deny', '1', lambda request: False)
    with pytest.raises(PublicationCheckError) as error:
        update_artifact(model, edit(requirement(model), options=[], expected_revision=1), **options)
    assert error.value.exit_code == 7 and error.value.reason == 'publication_authorization_denied'
    assert file_inventory(root) == before


@pytest.mark.parametrize('noop', [False, True])
def test_changed_physical_base_is_preserved_even_for_noop(tmp_path, noop):
    root = tmp_path / 'project'; model, _ = project(root, 'verification'); old = requirement(model)
    path = root / artifact_path('requirement', old['id'], 'SR')
    changed = canonical_json_bytes({**old, 'statement': 'Foreign edit.'}); path.write_bytes(changed)
    before = file_inventory(root)
    operation = edit(old, options=[] if noop else None, expected_revision=1)
    with pytest.raises(PublicationCheckError) as error:
        update_artifact(model, operation, **arguments(root))
    assert error.value.reason == 'publication_base_changed' and error.value.exit_code == 6
    assert file_inventory(root) == before and path.read_bytes() == changed


def test_another_writer_blocks_update_without_changing_its_state(tmp_path):
    root = tmp_path / 'project'; model, _ = project(root, 'verification')
    with project_lock(root, **lock_options()) as held:
        before = file_inventory(root)
        with pytest.raises(ProjectLockError) as error:
            update_artifact(model, edit(requirement(model), expected_revision=1), **arguments(root))
        assert error.value.reason == 'project_lock_busy' and error.value.exit_code == 5
        assert held.check() and file_inventory(root) == before


@pytest.mark.parametrize('moved', [False, True])
def test_failed_actual_replace_retains_old_or_new_bytes_and_blocks_retry(tmp_path, moved):
    root = tmp_path / 'project'; model, _ = project(root, 'verification'); old = requirement(model)
    path = artifact_path('requirement', old['id'], 'SR'); before = file_inventory(root)
    raw = (root / path).read_bytes(); native_replace = os.replace; attempts = []
    def replace(src, dst, **kwargs):
        if str(dst) == old['id'] + '.json':
            attempts.append(str(dst))
            if moved: native_replace(src, dst, **kwargs)
            raise OSError('injected target replace failure')
        return native_replace(src, dst, **kwargs)
    operation = edit(old, expected_revision=1)
    with patch.object(os, 'replace', side_effect=replace), pytest.raises(CommitPublicationError) as error:
        update_artifact(model, operation, **arguments(root))
    assert attempts == [old['id'] + '.json']
    assert error.value.reason == 'publication_io_failure' and error.value.exit_code == 5
    assert error.value.write_state == 'unknown' and error.value.mutation_possible and error.value.publication_possible
    assert error.value.published_count == 0
    if moved:
        actual = json.loads((root / path).read_bytes())
        assert actual == {**old, 'statement': 'Updated content.', 'revision': 2,
                          'updated_by': ACTOR, 'updated_at': TIME}
    else: assert (root / path).read_bytes() == raw
    journal = json.loads((root / '.specroad/transactions/txn-update/journal.json').read_bytes())
    assert journal['state'] == 'committing' and journal['published_count'] == 0
    after = {p: rest for p, *rest in file_inventory(root)}
    for p, *rest in before:
        if p != path: assert after[p] == rest
    retained = file_inventory(root)
    with pytest.raises(ProjectLockError) as retry:
        update_artifact(model, operation, **arguments(root))
    assert retry.value.reason == 'transaction_journal_blocks_lock' and retry.value.exit_code == 5
    assert file_inventory(root) == retained


@pytest.mark.parametrize('defect', ['symlink', 'closed_stream'])
def test_unsafe_or_unreadable_input_never_becomes_an_operation(tmp_path, defect):
    value = domain_value('requirement'); saved = tmp_path / 'patch.json'; saved.write_bytes(b'[]')
    linked = tmp_path / 'linked.json'; linked.symlink_to(saved)
    stream = BytesIO(b'[]'); stream.close()
    with no_write_attempts(), pytest.raises(AuthoringError) as error:
        read_artifact_update_input(value, input=str(linked) if defect == 'symlink' else '-',
            stdin=stream, expected_revision=1)
    assert error.value.exit_code == (7 if defect == 'symlink' else 5)


@pytest.mark.parametrize('subject', ['other_approved', 'target_retired'])
def test_bound_update_gate_does_not_certify_other_approvals_or_states(tmp_path, subject):
    root = tmp_path / 'project'
    model, old, _ = stored_project(root, maturity='retired' if subject == 'target_retired' else 'draft')
    if subject == 'other_approved':
        approved = approved_value('goal'); path = artifact_path('goal', approved['id'], 'SR')
        raw = canonical_json_bytes(approved)
        documents = [ModelDocument(d.path, raw if d.path == path else d.content) for d in model.documents]
        model = TargetModel(model.configuration_bytes, model.binding, documents,
            profile=model.profile, resource_files=model.resource_files)
        (root / path).write_bytes(raw)
    before = file_inventory(root)
    with pytest.raises(TargetError) as error:
        update_artifact(model, edit(old, expected_revision=7), **arguments(root))
    assert error.value.reason == 'complete_target_validation_required' and file_inventory(root) == before


def test_explicit_host_lifecycle_denial_is_not_replaced(tmp_path):
    root = tmp_path / 'project'; model, old, _ = stored_project(root, maturity='proposed')
    before = file_inventory(root)
    gate = ModelGate('lifecycle', 'host-denial-v1',
        lambda c: c.dependency_result({key: list(c.all_ids) for key in c.subjects}),
        lambda c: c.result([{'reason': 'host_lifecycle_denied', 'severity': 'error'}]))
    with pytest.raises(TargetError):
        update_artifact(model, edit(old, expected_revision=7), gates=[gate], **arguments(root))
    assert file_inventory(root) == before


def test_bound_lifecycle_gate_rejects_a_different_well_formed_target(tmp_path):
    root = tmp_path / 'project'; model, old, _ = stored_project(root, maturity='approved')
    original = edit(old, options=[('--set', '/statement="Original request"')], expected_revision=7)
    different = edit(old, options=[('--set', '/statement="Different request"')], expected_revision=7)
    bound = prepare_update_lifecycle_gate(model, original,
        metadata_policy_version='change-metadata-v1', actor=ACTOR, planned_at=TIME)
    with no_write_attempts():
        checked = prepare_change_target(model, [different.data], change_plan_id='CP-boundary',
            request_id='bound-1', actor=ACTOR, planned_at=TIME, scope_descriptor=SCOPE,
            metadata_policy_version='change-metadata-v1', policy=TargetPolicy('artifact.update', '1', ()),
            gates=[bound])
    assert not checked.target_validated
    lifecycle = next(s for s in checked.data['validation']['source_report']['stages'] if s['stage'] == 'lifecycle')
    assert lifecycle['status'] == 'failed'
    assert [d['reason'] for d in lifecycle['diagnostics']] == ['update_lifecycle_target_mismatch']
