"""Explicit selected-configuration gate over supplied original model documents.

The existing validator retains all structural and semantic service boundaries.
This entrypoint adds stored-relation consistency, not release approval, external
provider checks or filtering of other services' artifact scopes.
"""
from ..graph.relations import SourceRelations
from ..model.canonical import canonical_json_sha256
from ..model.errors import ModelError
from .evaluation import ConfigurationEvaluationError, evaluate_configuration
from .values import resolve_configuration


def validate_configured_model(documents, *, configuration_id=None, profile=None,
                              selected_ids=None, gates=(), resources=None):
    """Require an explicit existing configuration before running the model gate.

    The same documents, IDs, revisions and references are passed to the existing
    pipeline. The configuration gate observes all supplied artifacts on every
    invocation, even when the caller selects only one validation subject.
    Missing selection/invalid configuration raises a structured SRV130 error.
    Other unavailable semantic services remain unavailable in the report.
    """
    # Keep configuration services independent of validation's import graph.
    from ..validation import ModelDocument, ModelGate, validate_model

    if type(documents) not in (list, tuple) or any(type(d) is not ModelDocument for d in documents):
        raise ModelError('validation_documents_required')
    documents = tuple(documents)
    if type(gates) not in (list, tuple):
        raise ModelError('validation_gates_required')
    try:
        sources = tuple(SourceRelations(d.content, path=d.path) for d in documents)
        selected = resolve_configuration(sources, configuration_id)
    except ModelError as error:
        raise ConfigurationEvaluationError(error) from error
    binding = canonical_json_sha256({'gate': 'selected-stored-configuration-v1',
                                    'configuration': selected.manifest})

    def dependencies(context):
        return context.dependency_result({name: list(context.all_ids) for name in context.subjects})

    def check(context):
        try:
            current = tuple(SourceRelations(d.content, path=d.path) for d in context.documents)
            evaluation = evaluate_configuration(current, selected.configuration_id).data
        except ModelError as error:
            return context.result([{**error.diagnostic(), 'code': 'SRV130', 'severity': 'error'}])
        # The configuration is always a gate subject. Unconditional origins may
        # not be; retain their identities and full paths as related evidence.
        return context.result([{'reason': 'configuration_dependency_excluded',
            'code': 'SRV131', 'severity': 'error', 'artifact_id': selected.configuration_id,
            'related_ids': [item['source_id'], item['target_id']], 'dependency': item}
            for item in evaluation['inconsistent_dependencies']])

    gate = ModelGate('configuration', 'selected-stored-configuration-v1',
                     dependencies, check, binding)
    return validate_model(documents, profile=profile, selected_ids=selected_ids,
                          gates=(*gates, gate), resources=resources)
