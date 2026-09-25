"""Synthetic planned values. No current repository or approval is claimed."""
from copy import deepcopy
from specroad.model.canonical import canonical_json_sha256
from .domain import domain_value, relation
from .records import record_value, ref


def scope():
    return {'scope_version': 'scope-v1', 'scope_kind': 'project', 'selector': {},
            'configuration_id': None, 'closure_profile': 'core-closure-v1', 'boundary_policy': 'closed'}


def operation(kind='create'):
    goal = domain_value()
    options = {
        'create': {'artifact': goal, 'result_id': goal['id']},
        'update': {'target': goal['id'], 'expected_revision': 1,
                   'patch': [{'op': 'replace', 'path': '/statement', 'value': 'Changed.'}]},
        'relation_add': {'source': goal['id'], 'relation': relation('refines', ref('GOAL', '1'))},
        'relation_remove': {'source': goal['id'], 'relation_id': 'REL-' + '0'*26, 'expected_sha256': 'a'*64, 'reason': 'Remove obsolete relation'},
        'transition': {'target': goal['id'], 'from': 'draft', 'to': 'proposed', 'metadata': {'reason': 'Review requested'}},
        'retire': {'target': goal['id'], 'expected_sha256': 'b'*64, 'reason': 'Replace requirement'},
        'evidence_record': {'evidence': record_value('evidence')},
        'attachment_add': {'target': goal['id'], 'attachment': {'path': 'attachments/data.bin', 'media_type': 'application/octet-stream', 'size': 0, 'sha256': 'c'*64}},
        'attachment_remove': {'target': goal['id'], 'path': 'attachments/data.bin', 'expected_sha256': 'c'*64, 'reason': 'Unused data'},
        'representation_normalize': {'path': 'spec/goals/' + goal['id'] + '.json', 'expected_byte_sha256': 'd'*64, 'target_byte_sha256': 'e'*64},
        'relation_review_record': {'record': record_value('relation_review'), 'source': ref('GOAL'), 'target': ref('GOAL', '1'), 'approval_withdrawals': []},
        'proposal_control': {'target': ref('PROP'), 'expected_revision': 1, 'expected_sha256': 'a'*64,
                             'content_revision': 1, 'content_sha256': 'b'*64, 'base_model_root_sha256': 'c'*64,
                             'change_plan_sha256': 'd'*64, 'events': [{'from':'draft','to':'validated','reason':'Checked','result_sha256':'e'*64}]},
    }
    return {'op': kind, **deepcopy(options[kind])}


def result(value):
    return {'artifact': deepcopy(value), 'sha256': canonical_json_sha256(value)}


def document(operations=None, results=None):
    return {
        'format_version': '1.2.0', 'metadata_policy_version': 'change-metadata-v1',
        'change_plan_id': 'CP-0123456789ABCDEFGHJKMNPQRS', 'request_id': 'test:request:1',
        'planned_at': '2026-01-01T00:00:00Z', 'actor': {'actor_type': 'human', 'actor_id': 'synthetic-author'},
        'base': {'scope_descriptor': scope(), 'model_root_sha256': 'a'*64},
        'operations': deepcopy([operation()] if operations is None else operations),
        'preconditions': [], 'result_artifacts': deepcopy([result(domain_value())] if results is None else results),
        'expected_result': {'model_root_sha256': 'b'*64},
    }
