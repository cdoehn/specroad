"""Read-only relation-status query over an owned caller-supplied TargetModel."""
from ..changes.target_model import TargetModel
from ..changes.target_values import TargetError
from ..graph.relations import SourceRelations
from ..graph.review_status import RelationReviewStatuses


def relation_review_status(model, source_id, relation_id):
    if type(model) is not TargetModel:
        raise TargetError('target_model_required')
    owned = model.snapshot()
    statuses = RelationReviewStatuses(tuple(SourceRelations(document.content,
        path=document.path) for document in owned.documents))
    return {**statuses.for_relation(source_id, relation_id).as_fields(),
        'validation_scope': statuses.validation_scope,
        'approval_granted': statuses.approval_granted}
