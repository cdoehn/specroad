"""Owned original sources for configured selection and both sorting paths."""
from ..graph.relations import SourceRelations
from ..model.errors import ModelError


def configured_sources(records, configuration_id):
    if configuration_id is None:
        return records
    from ..configurations.evaluation import ConfigurationEvaluationError
    try:
        if any(type(record) is not SourceRelations for record in records):
            raise ModelError('configuration_source_required')
        return tuple(SourceRelations(record.source_bytes, path=record.path) for record in records)
    except ModelError as error:
        raise ConfigurationEvaluationError(error) from error
