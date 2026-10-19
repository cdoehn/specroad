"""Compiled schema providers for the built-in operation payloads."""
from ..model.artifact_schemas import MATURITIES
from ._schema_fields import obj, arr, text, digest, revision, expected, patch_schema

def create_schema():
    base = {"op": {"const": 'create'}}
    ref = text()
    blob = {"type": "object"}
    return obj({**base, 'artifact': blob, 'result_id': ref})

def update_schema():
    base = {"op": {"const": 'update'}}
    ref = text()
    blob = {"type": "object"}
    return expected({**base, 'target': ref, 'patch': patch_schema()}, ['op', 'target', 'patch'])

def relation_add_schema():
    base = {"op": {"const": 'relation_add'}}
    ref = text()
    blob = {"type": "object"}
    return obj({**base, 'source': ref, 'relation': blob})

def relation_remove_schema():
    base = {"op": {"const": 'relation_remove'}}
    ref = text()
    blob = {"type": "object"}
    return obj({**base, 'source': ref, 'relation_id': ref, 'expected_sha256': digest(), 'reason': text()})

def transition_schema():
    base = {"op": {"const": 'transition'}}
    ref = text()
    blob = {"type": "object"}
    return obj({**base, 'target': ref, 'from': {'enum': list(MATURITIES)}, 'to': {'enum': list(MATURITIES)}, 'metadata': blob})

def retire_schema():
    base = {"op": {"const": 'retire'}}
    ref = text()
    blob = {"type": "object"}
    return expected({**base, 'target': ref, 'reason': text()}, ['op', 'target', 'reason'])

def evidence_record_schema():
    base = {"op": {"const": 'evidence_record'}}
    ref = text()
    blob = {"type": "object"}
    return obj({**base, 'evidence': blob,
                'configuration_id': {'anyOf': [{'type': 'null'}, ref]}}, ['op', 'evidence'])

def attachment_add_schema():
    base = {"op": {"const": 'attachment_add'}}
    ref = text()
    blob = {"type": "object"}
    return obj({**base, 'target': ref, 'attachment': obj({'path': text(), 'media_type': text(), 'size': {'type': 'integer', 'minimum': 0}, 'sha256': digest()})})

def attachment_remove_schema():
    base = {"op": {"const": 'attachment_remove'}}
    ref = text()
    blob = {"type": "object"}
    return obj({**base, 'target': ref, 'path': text(), 'expected_sha256': digest(), 'reason': text()})

def representation_normalize_schema():
    base = {"op": {"const": 'representation_normalize'}}
    ref = text()
    blob = {"type": "object"}
    return obj({**base, 'path': text(), 'expected_byte_sha256': digest(), 'target_byte_sha256': digest()})

def relation_review_record_schema():
    base = {"op": {"const": 'relation_review_record'}}
    ref = text()
    blob = {"type": "object"}
    withdrawal = expected({'target': ref, 'reason': text()}, ['target', 'reason'])
    return obj({**base, 'record': blob, 'source': ref, 'target': ref,
        'approval_withdrawals': arr(withdrawal), 'expected_revision': revision(),
        'expected_sha256': digest()}, ['op', 'record', 'source', 'target', 'approval_withdrawals'])

def proposal_control_schema():
    base = {"op": {"const": 'proposal_control'}}
    ref = text()
    blob = {"type": "object"}
    event = obj({'from': text(), 'to': text(), 'reason': text(), 'result_sha256': digest()})
    return obj({**base, 'target': ref, 'expected_revision': revision(), 'expected_sha256': digest(), 'content_revision': revision(), 'content_sha256': digest(), 'base_model_root_sha256': digest(), 'change_plan_sha256': digest(), 'events': {'type': 'array', 'items': event, 'minItems': 1}})


def baseline_create_schema():
    return obj({'op': {'const': 'baseline_create'}, 'record': {'type': 'object'},
        'objects': arr(obj({'path': text(), 'bytes_base64': {'type': 'string'}}))})

