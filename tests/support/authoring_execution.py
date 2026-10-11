"""Shared native authoring scenarios and unchanged W/R behavior oracles.

The domain adapters provide one prepared operation and its real direct call.
These fixtures do not replace production gates, authorize actors or reserve IDs.
"""
import json

from specroad.authoring.plans import preview_authoring_request
from specroad.authoring.execution import execute_authoring_plan
from specroad.authoring.creation import create_artifact, _draft
from specroad.authoring.inputs import normalize_artifact_create_input
from specroad.authoring.update import update_artifact, normalize_artifact_update_input
from specroad.authoring.lifecycle import (transition_artifact, retire_artifact,
    normalize_transition_input, normalize_retire_input)
from specroad.authoring.relations import add_relation, remove_relation
from specroad.authoring.reviews import record_relation_review
from specroad.authoring.negative_reviews import record_coupled_relation_review
from specroad.changes import ChangePlan, ChangeOperation, PublicationAuthority
from specroad.changes.relation_inputs import normalize_relation_add_input, _addition
from specroad.graph.relations import SourceRelations
from specroad.graph.review_status import RelationReviewStatuses
from specroad.model.canonical import canonical_json_bytes, canonical_json_sha256
from specroad.model.identities import IdentityInventory
from specroad.model.identity_values import ArtifactIdentity
from specroad.model.identity_tokens import encode128
from specroad.model.relation_values import RelationIdentity
from specroad.model.paths import artifact_path
from specroad.validation import ModelGate
from support.read_only import inventory as file_inventory
from test_artifact_creation import project
from test_authoring_inputs import fields
from test_relation_authoring import stored_project, inventory as relation_inventory
from test_relation_review_authoring import planned as confirmed_plan
from test_relation_review_authoring import (ACTOR as REVIEW_ACTOR, TIME as REVIEW_TIME,
    ENTROPY as REVIEW_ENTROPY, REASON as REVIEW_REASON)
from test_negative_relation_review import negative_project, operation as negative_operation
from test_negative_relation_review import (ACTOR as NEGATIVE_ACTOR, TIME as NEGATIVE_TIME,
    ENTROPY as NEGATIVE_ENTROPY, REASON as NEGATIVE_REASON)

ACTOR = {'actor_type': 'human', 'actor_id': 'plan-editor'}
TIME = '2026-10-11T09:00:00Z'
ENTROPY = b'\x31' * 16
KINDS = ('create', 'update', 'transition', 'retire', 'add', 'remove', 'confirmed', 'rejected')
ALLOW = PublicationAuthority('owned-execution-host', '1', lambda request: True)


def scenario(root, kind):
    actor, time, entropy, gates = ACTOR, TIME, ENTROPY, ()
    if kind == 'create':
        model, ids = project(root)
        prepared = normalize_artifact_create_input('need', fields('need'))
        identity = ArtifactIdentity('SR-NEED-' + encode128(entropy), 'random128-v1', 'need', 'SR')
        artifact = _draft(prepared, identity, actor, time, model.configuration)
        op = ChangeOperation({'op': 'create', 'artifact': artifact, 'result_id': identity.id})
        command = 'artifact.create'
        def direct(options): return create_artifact(model, prepared, inventory=ids, **options)
    elif kind == 'rejected':
        model, source, _, gates = negative_project(root)
        actor, time, entropy = NEGATIVE_ACTOR, NEGATIVE_TIME, NEGATIVE_ENTROPY
        op = negative_operation(model, source); command = 'relation.review'
        ids = IdentityInventory('SR', [a['id'] for a in model.artifacts], (), ())
        def direct(options):
            return record_coupled_relation_review(model, source['id'], source['relations'][0]['relation_id'],
                decision='rejected', reason=NEGATIVE_REASON, expected_revision=4, inventory=ids, **options)
    else:
        model, source, goals = stored_project(root, with_edges=kind in ('remove', 'confirmed'))
        if kind == 'update':
            op = normalize_artifact_update_input(source, expected_revision=7,
                options=[('--set', '/statement="The saved plan supplies this exact statement."')])
            command = 'artifact.update'
            def direct(options): return update_artifact(model, op, **options)
        elif kind in ('transition', 'retire'):
            op = (normalize_transition_input(source, to='retired', reason='Planned closure.')
                if kind == 'transition' else normalize_retire_input(source,
                    reason='Planned closure.', expected_revision=7))
            command = 'lifecycle.transition'
            def direct(options):
                return (transition_artifact if kind == 'transition' else retire_artifact)(model, op, **options)
        elif kind == 'add':
            intent = normalize_relation_add_input(source['id'], 'addresses', goals[0]['id'], rationale='Planned link.')
            identity = RelationIdentity('REL-' + encode128(entropy), 'random128-v1')
            op = _addition(intent, identity, actor, time); command = 'relation.add'
            def direct(options):
                return add_relation(model, source['id'], 'addresses', goals[0]['id'],
                    inventory=relation_inventory(model), rationale='Planned link.', **options)
        elif kind == 'remove':
            relation = source['relations'][0]
            op = ChangeOperation({'op': 'relation_remove', 'source': source['id'],
                'relation_id': relation['relation_id'], 'expected_sha256': canonical_json_sha256(relation),
                'reason': 'Planned removal.'})
            command = 'relation.remove'
            def direct(options):
                return remove_relation(model, source['id'], relation['relation_id'],
                    expected_sha256=canonical_json_sha256(relation), reason='Planned removal.', **options)
        else:
            actor, time, entropy = REVIEW_ACTOR, REVIEW_TIME, REVIEW_ENTROPY
            checked, _ = confirmed_plan(model, source)
            op = checked.plan.operations[0]; command = 'relation.review'
            ids = IdentityInventory('SR', [a['id'] for a in model.artifacts], (), ())
            def direct(options):
                return record_relation_review(model, source['id'], source['relations'][0]['relation_id'],
                    decision='confirmed', reason=REVIEW_REASON, expected_revision=7, inventory=ids, **options)
    options = dict(actor=actor, planned_at=time, change_plan_id='CP-preview', request_id='preview-request', gates=gates)
    return model, command, op, options, direct, entropy


def preview(model, command, op, options, **extra):
    return preview_authoring_request(model, command, [op.data], **options, **extra)


def saved(result):
    return ChangePlan(canonical_json_bytes(result['plan']))


def assert_effects(root, before, result, kind):
    planned = result['plan']['result_artifacts']
    changed = set()
    for item in planned:
        artifact = item['artifact']; path = artifact_path(artifact['artifact_type'], artifact['id'], 'SR')
        actual = json.loads((root / path).read_bytes())
        assert actual == artifact and canonical_json_sha256(actual) == item['sha256']
        changed.add(path)
    after = {row[0]: row[1:] for row in file_inventory(root)}
    for path, *value in before:
        if path not in changed: assert after[path] == tuple(value)
    artifacts = [entry['artifact'] for entry in planned]
    if kind == 'create':
        assert [(a['artifact_type'], a['revision'], a['maturity']) for a in artifacts] == [('need', 1, 'draft')]
    elif kind == 'update':
        assert artifacts[0]['statement'] == 'The saved plan supplies this exact statement.'
        assert artifacts[0]['revision'] == 8 and artifacts[0]['maturity'] == 'draft'
    elif kind in ('transition', 'retire'):
        assert artifacts[0]['revision'] == 8 and artifacts[0]['maturity'] == 'retired'
    elif kind in ('add', 'remove'):
        assert artifacts[0]['revision'] == 8 and len(artifacts[0]['relations']) == 1
    else:
        review = next(a for a in artifacts if a['artifact_type'] == 'relation_review')
        assert (review['decision'], review['review_state'], review['maturity'], review['revision']) == (kind, 'recorded', 'approved', 1)
        if kind == 'rejected':
            requirement = next(a for a in artifacts if a['artifact_type'] == 'requirement')
            assert requirement['maturity'] == 'proposed' and requirement['revision'] == 5


def execute(plan, model, command, **options):
    arguments = dict(command_id=command, transaction_id='txn-execution', authority=ALLOW)
    arguments.update(options)
    return execute_authoring_plan(plan, model, **arguments)


def assert_failed(result, plan, code, *, state='not_committed'):
    assert result['status'] == 'failed' and result['exit_code'] == code
    assert result['write_state'] == state and result['no_change'] is None
    assert result['completion'] is None and not result['current_target_verified']
    assert result['target_model_root_sha256'] is None and not result['approval_granted']
    assert not result['retry_safe'] and not result['automatic_retry'] and not result['automatic_rollback']
    audit = result['audit']
    assert audit['audit_scope'] == 'failed_plan_attempt' and audit['outcome'] == 'failed'
    assert audit['write_state'] == state and audit['diagnostic'] == result['diagnostics'][0]
    assert 'created_ids' not in audit and 'target_model_root_sha256' not in audit
    assert audit['plan_integrity_checked'] and audit['plan_sha256'] == plan.sha256
    assert audit['operations'] == plan.data['operations']
    assert audit['actor'] == plan.data['actor'] and audit['request_id'] == plan.data['request_id']
    assert audit['expected_model_root_sha256'] == plan.data['expected_result']['model_root_sha256']
    assert json.loads(canonical_json_bytes(result)) == result


def retained_review_gates(model, source, record, time):
    """Trusted fixture evidence for exactly this retirement and retained record.

    This is not an authentic history loader or a generic approval service.
    Both gates bind the complete independently expected target, including the
    unchanged recorded review; review currentness is recomputed by the core.
    """
    expected = {a['id']: a for a in model.artifacts}
    expected[source['id']] = {**source, 'maturity': 'retired', 'revision': source['revision'] + 1,
        'updated_at': time, 'updated_by': ACTOR}
    digest = canonical_json_sha256(expected)
    def check(context):
        actual = {key: context.artifact(key) for key in context.all_ids}
        if (canonical_json_sha256(actual) != digest
                or not set(context.subjects) <= {source['id'], record['id']}):
            return context.result([{'reason': 'fixture_retirement_target_mismatch', 'severity': 'error'}])
        statuses = RelationReviewStatuses(tuple(SourceRelations(canonical_json_bytes(a)) for a in actual.values()))
        if [s.status for s in statuses.statuses] != ['current']:
            return context.result([{'reason': 'fixture_retained_review_not_current', 'severity': 'error'}])
        return context.result()
    return tuple(ModelGate(name, 'fixture-exact-retained-review-v1',
        lambda c: c.dependency_result({key: list(c.all_ids) for key in c.subjects}), check, digest)
        for name in ('lifecycle', 'review_currentness'))
