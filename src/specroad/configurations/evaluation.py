"""Deterministic applicability and shortest required-relation explanations.

The input is a supplied complete artifact inventory. No project discovery,
resource/review provider, scope manifest or lifecycle approval is implied.
"""
from collections import deque
from dataclasses import dataclass
import json

from ..graph.hierarchies import validate_hierarchies
from ..graph.indices import RelationIndex
from ..graph.path_output import PathRecord
from ..graph.references import RelationReferences
from ..graph.relations import SourceRelations
from ..model.canonical import canonical_json_bytes
from ..model.errors import ModelError
from .applicability import evaluate_applicability
from .values import resolve_configuration


class ConfigurationEvaluationError(ModelError):
    """Preserve the underlying configuration/SRX location for SRV130."""
    code = 'SRV130'
    exit_code = 3

    def __init__(self, error):
        super().__init__(error.reason, path=error.path, pointer=error.pointer,
                         position=error.position, line=error.line, column=error.column,
                         highest_supported=error.highest_supported)


def _configuration_decisions(records, configuration_id):
    try:
        effective = resolve_configuration(records, configuration_id)
        decisions = tuple(evaluate_applicability(record, effective, require_configuration=True)
                          for record in records)
    except ModelError as error:
        raise ConfigurationEvaluationError(error) from error
    return effective, decisions


def _inconsistencies(index, applicable, excluded):
    """One shortest path per origin/endpoint, ordered by full artifact IDs,
    then relation IDs. Breadth-first discovery preserves that tie-break order.
    """
    # Import only at execution time: scope admission also consumes configuration
    # classification, while this command reuses the actual strong-edge registry.
    from ..graph.strong_closure import STRONG_RELATIONS
    if not excluded:
        return []
    identities = {item.id: item for item in index.references.sources}
    outgoing = {name: tuple(sorted((view for view in index.for_artifact(name, direction='outgoing')
                                    if view.type in STRONG_RELATIONS),
                                   key=lambda view: (view.target.id, view.relation_id))) for name in applicable}
    result = []
    for start in sorted(applicable):
        pending = deque([start])
        predecessors = {start: None}
        while pending:
            current = pending.popleft()
            for view in outgoing[current]:
                target = view.target.id
                if target in predecessors:
                    continue
                predecessors[target] = view
                # An excluded dependency terminates this path. Its own outgoing
                # dependencies are not requirements of the selected variant.
                if target in applicable:
                    pending.append(target)
        for target in sorted(excluded.intersection(predecessors)):
            reverse, current = [], target
            while current != start:
                view = predecessors[current]
                reverse.append(view)
                current = view.source.id
            path = PathRecord.from_views(identities[start], tuple(reversed(reverse)))
            result.append({'source_id': start, 'target_id': target, 'distance': len(reverse),
                           'path': path.as_dict()})
    return result


@dataclass(frozen=True, init=False)
class ConfigurationEvaluation:
    """Owned complete result within the declared stored-relation scope."""
    _encoded: bytes

    def __init__(self, records, configuration_id):
        if type(records) not in (list, tuple):
            raise ModelError('configuration_inventory_required')
        if any(type(record) is not SourceRelations for record in records):
            raise ModelError('configuration_source_required')
        records = tuple(sorted((SourceRelations(record.source_bytes, path=record.path) for record in records),
                               key=lambda record: record.identity.id.encode('utf-8')))
        effective, decisions = _configuration_decisions(records, configuration_id)
        index = RelationIndex(RelationReferences(records))
        validate_hierarchies(index.references)
        applicable = {item.artifact_id for item in decisions if item.status == 'applicable'}
        excluded = {item.artifact_id for item in decisions if item.status == 'excluded'}
        conflicts = _inconsistencies(index, applicable, excluded)
        data = {'format_version': '1.0.0',
                'configuration': {**effective.data, 'sha256': effective.sha256},
                'applicable_artifact_ids': sorted(applicable), 'excluded_artifact_ids': sorted(excluded),
                'evaluations': [{'artifact_id': item.artifact_id, 'status': item.status, 'reason': item.reason}
                                for item in sorted(decisions, key=lambda item: item.artifact_id)],
                'inconsistent_dependencies': conflicts, 'consistent': not conflicts,
                'dependency_scope': 'stored_strong_relations', 'source_count': len(records),
                'relation_count': len(index.references.relations)}
        object.__setattr__(self, '_encoded', canonical_json_bytes(data))

    @property
    def data(self):
        return json.loads(self._encoded)

    @property
    def validation_scope(self):
        return 'supplied_configuration_applicability_and_required_relations'


def evaluate_configuration(records, configuration_id):
    return ConfigurationEvaluation(records, configuration_id)
