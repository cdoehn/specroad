"""Real guarded updates and durable retry results; no presentation assertions."""
from io import BytesIO
import json
from unittest.mock import patch
import pytest
from specroad.authoring import update
from specroad.authoring.update import (normalize_artifact_update_input,
    read_artifact_update_input, update_artifact)
from specroad.changes import (AuthoringError, ChangePlanError, PublicationAuthority,
    PublicationCheckError, RequestIdConflict, inspect_project_lock,
    read_transaction_completion, lifecycle_content_sha256)
from specroad.model.canonical import canonical_json_bytes, canonical_json_sha256
from specroad.model.paths import artifact_path
from specroad.storage.project import ProjectSource
from support.domain import domain_value
from support.read_only import inventory as file_inventory, no_write_attempts
from test_artifact_creation import project

ACTOR = {'actor_type': 'human', 'actor_id': 'editor'}
TIME = '2026-10-10T14:00:00Z'
FIELDS = [('language', 'en-US'), ('normative_force', 'should'),
          ('statement', 'The workspace supports local updates.')]


def arguments(root):
    def authorize(request):
        status = inspect_project_lock(root).data
        assert status['record']['kind'] == 'writer'
        assert status['record']['transaction_id'] == 'txn-update'
        assert request.plan.operations[0].op == 'update'
        return True
    return dict(actor=ACTOR, planned_at=TIME, change_plan_id='CP-update',
        transaction_id='txn-update', request_id='update-1',
        authority=PublicationAuthority('owned-update-host', '1', authorize))


def requirement(model):
    return next(a for a in model.artifacts if a['artifact_type'] == 'requirement')


def edit(artifact, *, options=None, **guards):
    if options is None: options = [('--set', '/statement="Updated content."')]
    return normalize_artifact_update_input(artifact, options=options, **guards)


@pytest.mark.parametrize('field,value', FIELDS)
@pytest.mark.parametrize('route', ['options', 'file', 'stdin'])
@pytest.mark.parametrize('guard', ['revision', 'hash'])
def test_language_force_and_text_publish_one_native_revision(tmp_path, field, value, route, guard):
    root = tmp_path / 'project'; model, _ = project(root, 'verification')
    before_artifact = requirement(model)
    path = artifact_path('requirement', before_artifact['id'], 'SR')
    (root / path).chmod(0o640)
    before = file_inventory(root)
    guards = ({'expected_revision': before_artifact['revision']} if guard == 'revision'
              else {'expected_sha256': canonical_json_sha256(before_artifact)})
    extra = ({'deviation_conditions': 'During evaluation', 'deviation_authority': 'reviewer'}
             if field == 'normative_force' and value == 'should' else {})
    patches = [{'op': 'replace', 'path': '/' + field, 'value': value}]
    patches += [{'op': 'add', 'path': '/' + key, 'value': item} for key, item in extra.items()]
    pairs = [('--set', '/' + key + '=' + json.dumps(item)) for key, item in {field: value, **extra}.items()]
    raw = json.dumps(patches).encode()
    saved = tmp_path / 'update.json'; saved.write_bytes(raw)
    prepared = (edit(before_artifact, options=pairs, **guards)
        if route == 'options' else read_artifact_update_input(before_artifact,
            input=str(saved) if route == 'file' else '-', stdin=BytesIO(raw), **guards))
    with patch('secrets.token_bytes', side_effect=AssertionError('updates allocate no artifact ID')):
        result = update_artifact(model, prepared, **arguments(root))
    actual = json.loads((root / path).read_bytes())
    expected = {**before_artifact, field: value, **extra, 'revision': before_artifact['revision'] + 1,
                'updated_by': ACTOR, 'updated_at': TIME}
    assert actual == expected and (root / path).read_bytes() == canonical_json_bytes(expected)
    assert lifecycle_content_sha256(actual) != lifecycle_content_sha256(before_artifact)
    assert result['command_id'] == 'artifact.update' and result['artifact_id'] == actual['id']
    assert result['write_state'] == 'committed' and not result['no_change'] and not result['replayed']
    assert result['completion']['commit_completed'] and result['completion']['cleanup_completed']
    assert result['completion']['current_target_verified']
    after = {entry[0]: entry[1:] for entry in file_inventory(root)}
    for name, *old in before:
        if name != path: assert after[name] == tuple(old)
    assert (root / path).stat().st_mode & 0o777 == 0o640
    assert requirement(model) == before_artifact and saved.read_bytes() == raw
    proof = read_transaction_completion(ProjectSource(root), 'txn-update').data
    assert proof['receipt_verified'] and proof['commit_completed'] and proof['cleanup_completed']
    assert not (root / '.specroad/locks/project.json').exists()


def test_ordered_set_unset_combines_fields_into_one_revision(tmp_path):
    root = tmp_path / 'project'; model, _ = project(root, 'verification'); base = requirement(model)
    pairs = [('--set', '/rationale="Temporary"'), ('--unset', '/rationale'),
             ('--set', '/statement="First"'), ('--set', '/language="en-US"'),
             ('--set', '/normative_force="should"'), ('--set', '/statement="Final"'),
             ('--set', '/deviation_conditions="During evaluation"'),
             ('--set', '/deviation_authority="reviewer"')]
    operation = edit(base, options=pairs, expected_revision=1, expected_sha256=canonical_json_sha256(base))
    # The prepared native value owns the original intent, independent of callers.
    pairs.clear(); operation.data['patch'].clear()
    result = update_artifact(model, operation, **arguments(root))
    actual = json.loads((root / artifact_path('requirement', base['id'], 'SR')).read_bytes())
    assert actual == {**base, 'statement': 'Final', 'language': 'en-US',
        'normative_force': 'should', 'deviation_conditions': 'During evaluation',
        'deviation_authority': 'reviewer', 'revision': 2, 'updated_by': ACTOR, 'updated_at': TIME}
    assert result['completion']['commit_completed']


def test_saved_rfc_patch_executes_all_six_operations_as_one_update(tmp_path):
    root = tmp_path / 'project'; model, _ = project(root, 'verification'); base = requirement(model)
    operations = [{'op': 'test', 'path': '/revision', 'value': 1},
        {'op': 'copy', 'from': '/title', 'path': '/rationale'},
        {'op': 'move', 'from': '/rationale', 'path': '/statement'},
        {'op': 'add', 'path': '/rationale', 'value': 'Temporary'},
        {'op': 'remove', 'path': '/rationale'},
        {'op': 'replace', 'path': '/statement', 'value': 'Final RFC patch result.'}]
    operation = read_artifact_update_input(base, input='-',
        stdin=BytesIO(json.dumps(operations).encode()), expected_revision=1)
    options = arguments(root); options['request_id'] = None
    result = update_artifact(model, operation, **options)
    actual = json.loads((root / artifact_path('requirement', base['id'], 'SR')).read_bytes())
    assert actual == {**base, 'statement': 'Final RFC patch result.', 'revision': 2,
                      'updated_by': ACTOR, 'updated_at': TIME}
    assert result['completion']['receipts']['request'] is None


def test_should_update_without_deviation_metadata_is_rejected_without_write(tmp_path):
    root = tmp_path / 'project'; model, _ = project(root, 'verification'); before = file_inventory(root)
    operation = edit(requirement(model), options=[('--set', '/normative_force="should"')], expected_revision=1)
    with pytest.raises(ChangePlanError) as error:
        update_artifact(model, operation, **arguments(root))
    assert error.value.reason == 'schema_any_of' and file_inventory(root) == before


@pytest.mark.parametrize('guards', [{}, {'expected_revision': None}, {'expected_revision': True},
    {'expected_revision': 0}, {'expected_sha256': None}, {'expected_sha256': 'short'}])
def test_missing_or_invalid_guard_is_rejected_before_input_read(guards):
    stream = BytesIO(b'[]')
    with no_write_attempts(), pytest.raises(ChangePlanError) as error:
        read_artifact_update_input(domain_value('requirement'), input='-', stdin=stream, **guards)
    assert error.value.exit_code == 3 and stream.tell() == 0


@pytest.mark.parametrize('kwargs', [{}, {'patch': [], 'options': []}])
def test_input_route_must_be_explicit_and_unambiguous(kwargs):
    with no_write_attempts(), pytest.raises(AuthoringError) as error:
        normalize_artifact_update_input(domain_value('requirement'), expected_revision=1, **kwargs)
    assert error.value.reason == 'exactly_one_update_input_required' and error.value.exit_code == 2


@pytest.mark.parametrize('raw', [b'{}', b'[{"op":"replace","path":"/statement","value":NaN}]',
    b'[{"op":"replace","op":"remove","path":"/statement","value":"x"}]'])
def test_saved_patch_is_strict_json_array_data(raw):
    with no_write_attempts(), pytest.raises(ChangePlanError) as error:
        read_artifact_update_input(domain_value('requirement'), input='-', stdin=BytesIO(raw), expected_revision=1)
    assert error.value.exit_code == 3


@pytest.mark.parametrize('kind,request_id,code', [('ai', 'update-1', 7), ('ci', None, 2)])
def test_actor_policy_blocks_before_planning_and_lock(tmp_path, kind, request_id, code):
    root = tmp_path / 'project'; model, _ = project(root, 'verification'); before = file_inventory(root)
    options = arguments(root); options.update(actor={'actor_type': kind, 'actor_id': 'caller'}, request_id=request_id)
    operation = edit(requirement(model), expected_revision=1)
    with no_write_attempts(), patch.object(update, 'project_lock', side_effect=AssertionError('no lock')):
        with pytest.raises(AuthoringError) as error: update_artifact(model, operation, **options)
    assert error.value.exit_code == code and file_inventory(root) == before


def test_host_denial_preserves_normative_bytes_and_has_no_journal(tmp_path):
    root = tmp_path / 'project'; model, _ = project(root, 'verification'); before = file_inventory(root)
    options = arguments(root); options['authority'] = PublicationAuthority('deny', '1', lambda request: False)
    with pytest.raises(PublicationCheckError) as error:
        update_artifact(model, edit(requirement(model), expected_revision=1), **options)
    assert error.value.reason == 'publication_authorization_denied' and error.value.exit_code == 7
    assert file_inventory(root) == before


@pytest.mark.parametrize('changed', [False, True])
def test_confirmed_retry_precedes_new_plan_and_lock(tmp_path, changed):
    root = tmp_path / 'project'; model, _ = project(root, 'verification'); base = requirement(model)
    operation = edit(base, expected_revision=1); options = arguments(root)
    first = update_artifact(model, operation, **options); before = file_inventory(root)
    if changed: operation = edit(base, options=[('--set', '/statement="Different"')], expected_revision=1)
    options.update(planned_at='2026-10-11T00:00:00Z', transaction_id='txn-later', change_plan_id='CP-later')
    with no_write_attempts(), patch.object(update, 'prepare_change_target', side_effect=AssertionError('no replan')), \
            patch.object(update, 'project_lock', side_effect=AssertionError('no lock')):
        if changed:
            with pytest.raises(RequestIdConflict) as error: update_artifact(model, operation, **options)
            assert error.value.exit_code == 6
        else:
            repeated = update_artifact(model, operation, **options)
            assert repeated['replayed'] and repeated['write_state'] == 'committed'
            assert not repeated['completion']['current_target_verified']
            for key in ('transaction_id', 'request_id', 'target_model_root_sha256', 'receipts'):
                assert repeated['completion'][key] == first['completion'][key]
    assert file_inventory(root) == before


def test_noop_keeps_every_file_and_revision_without_receipt(tmp_path):
    root = tmp_path / 'project'; model, _ = project(root, 'verification'); base = requirement(model)
    before = file_inventory(root)
    operation = edit(base, options=[('--set', '/statement=' + json.dumps(base['statement']))], expected_revision=1)
    result = update_artifact(model, operation, **arguments(root))
    assert result['no_change'] and result['completion'] is None and result['write_state'] == 'not_committed'
    assert file_inventory(root) == before


@pytest.mark.parametrize('guards,reason', [({'expected_revision': 2}, 'expected_revision_mismatch'),
    ({'expected_sha256': '0' * 64}, 'expected_hash_mismatch')])
def test_stale_guard_cannot_publish(tmp_path, guards, reason):
    root = tmp_path / 'project'; model, _ = project(root, 'verification'); before = file_inventory(root)
    with pytest.raises(ChangePlanError) as error:
        update_artifact(model, edit(requirement(model), **guards), **arguments(root))
    assert error.value.reason == reason and file_inventory(root) == before


@pytest.mark.parametrize('pointer,value', [('/id', 'SR-REQ-' + '1' * 26), ('/maturity', 'approved')])
def test_identity_and_maturity_are_not_generic_field_options(pointer, value):
    with no_write_attempts(), pytest.raises(ChangePlanError) as error:
        edit(domain_value('requirement'), options=[('--set', pointer + '=' + json.dumps(value))], expected_revision=1)
    assert error.value.reason == 'controlled_field_mutation'


def test_invalid_other_artifact_blocks_complete_model_update(tmp_path):
    root = tmp_path / 'project'; model, _ = project(root, 'verification', broken=True)
    before = file_inventory(root)
    with pytest.raises(ChangePlanError) as error:
        update_artifact(model, edit(requirement(model), expected_revision=1), **arguments(root))
    assert error.value.reason == 'missing_field' and error.value.pointer == '/artifacts/0/statement'
    assert file_inventory(root) == before
