"""R-35 -> R-36 through real writers; all human/service data is synthetic."""
import pytest

from specroad.authoring.requirement_approval import approve_requirement
from specroad.authoring.review_status import relation_review_status
from specroad.changes.requirement_approval import ApprovalPrerequisiteProvider
from specroad.changes import (TargetPolicy, prepare_change_target, assess_change_target,
    lifecycle_content_sha256, LifecycleError)
from specroad.model.canonical import canonical_json_bytes
from specroad.model.paths import artifact_path
from support.requirement_approval import ready_project, registered
from support.read_only import inventory, no_write_attempts
from test_negative_relation_review import ACTOR
from test_relation_authoring import receipt

SCOPE = {'scope_version': 'scope-v1', 'scope_kind': 'project', 'selector': {},
    'configuration_id': None, 'closure_profile': 'core-closure-v1', 'boundary_policy': 'closed'}
POLICY = TargetPolicy('lifecycle.transition', '1', ())


def test_r36_reconfirmation_and_two_explicit_transitions_preserve_native_history(tmp_path):
    root = tmp_path / 'project'
    model, operation, fields, records = ready_project(root)
    source = records['source']; before = inventory(root)
    assert (source['maturity'], source['revision']) == ('approved', 4)
    assert (records['proposed']['maturity'], records['proposed']['revision']) == ('proposed', 5)
    assert records['confirmation']['review_id'] != records['negative']['review_id']
    assert records['confirmation']['approval_withdrawals'] == []
    assert (records['before']['maturity'], records['before']['revision']) == ('in_review', 6)
    status = relation_review_status(model, source['id'], source['relations'][0]['relation_id'])
    assert status['status'] == 'current'
    result = approve_requirement(model, operation, **fields)
    path = artifact_path('requirement', source['id'], 'SR')
    expected = {**records['before'], 'maturity': 'approved', 'revision': 7,
                'updated_at': fields['planned_at'], 'updated_by': ACTOR}
    assert (root / path).read_bytes() == canonical_json_bytes(expected)
    assert lifecycle_content_sha256(expected) == lifecycle_content_sha256(source)
    assert result['write_state'] == 'committed' and result['completion']['commit_completed']
    proof = receipt(root, result)
    assert proof['result_object']['published_paths'] == [path]
    assert proof['write']['operations'] == [operation.data]
    assert proof['result_object']['created_ids'] == []
    assert len(records['service_calls']) >= 2  # planner and fresh publication gate
    after = {row[0]: row[1:] for row in inventory(root)}
    for name, *original in before:
        if name != path:
            assert after[name] == tuple(original)
    assert (root / path).stat().st_mode & 0o777 == 0o640
    for previous in (records['negative'], records['confirmation'], records['in_review']):
        assert previous['completion']['commit_completed']
    retry = {**fields, 'prerequisite_provider': ApprovalPrerequisiteProvider('revoked', '2',
        lambda context: pytest.fail('Historical retry must not re-evaluate services'))}
    with no_write_attempts():
        repeated = approve_requirement(model, operation, **retry)
    assert repeated['replayed'] and repeated['completion']['receipts'] == result['completion']['receipts']


def prepare(model, operation, fields, gates):
    return prepare_change_target(model, [operation.data], policy=POLICY, gates=gates,
        change_plan_id=fields['change_plan_id'], request_id=fields['request_id'], actor=fields['actor'],
        planned_at=fields['planned_at'], scope_descriptor=SCOPE, metadata_policy_version='change-metadata-v1')


def test_direct_and_saved_target_recompute_same_approval_and_cannot_publish_without_native_gate(tmp_path):
    model, operation, fields, _ = ready_project(tmp_path / 'project')
    gates = registered(model, operation, fields)
    before = inventory(tmp_path)
    with no_write_attempts():
        direct = prepare(model, operation, fields, gates)
        direct.require_valid()
        saved = assess_change_target(direct.plan, model, policy=POLICY, gates=gates)
        saved.require_valid()
        assert saved.data == direct.data
        for values in ((), fields['gates']):
            with pytest.raises(LifecycleError, match='approval_gate_required'):
                assess_change_target(direct.plan, model, policy=POLICY, gates=values)
    assert inventory(tmp_path) == before
