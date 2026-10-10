"""Pure relation-add values for the native change planner and authoring adapter."""
from ._common import _reference
from .errors import ChangePlanError
from .request_ids import AuthoringError
from .values import ChangeOperation
from ..graph.relation_types import require_relation_type
from ..model.canonical import canonical_json_bytes
from ..model.errors import ModelError
from ..storage.json_syntax import parse_json_object


def normalize_relation_add_input(source_id, relation_type, target_id, *,
                                 rationale=None, position=None):
    """Own input fields; identity and audit values are supplied at planning."""
    try:
        _reference(source_id, '/source')
        _reference(target_id, '/target')
        require_relation_type(relation_type)
        fields = {'type': relation_type, 'target': target_id,
                  'external_identities': [], 'extensions': {}}
        if rationale is not None:
            fields['rationale'] = rationale
        if position is not None:
            fields['position'] = position
        intent = parse_json_object(canonical_json_bytes({'source': source_id, 'fields': fields}))
    except ChangePlanError:
        raise
    except ModelError as error:
        raise AuthoringError(error.reason, pointer=error.pointer, exit_code=3) from error
    return intent


def _addition(intent, identity, actor, planned_at):
    return ChangeOperation({'op': 'relation_add', 'source': intent['source'],
        'relation': {**intent['fields'], **identity.as_fields(),
                     'created_at': planned_at, 'created_by': actor}})
