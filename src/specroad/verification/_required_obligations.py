"""Derive model obligations without accepting an evaluation or run selection.

The caller freezes this report before comparing any descriptor. All scope,
configuration and contract checks retain their existing evaluation order.
"""
from ..configurations import evaluate_applicability, resolve_configuration
from ..graph.references import RelationReferences
from ..graph.relation_types import relation_rules
from ..graph.relations import SourceRelations
from ..graph.scope_admission import ScopeConfigurationDependencyError
from ..graph.scope_descriptors import ScopeDescriptor
from ..model.canonical import canonical_json_sha256
from ..model.domain_schemas import DOMAIN_TYPES
from ..model.errors import ModelError
from ..storage.domain_artifact import DomainArtifact
from ..storage.record_artifact import RecordArtifact
from ._required_keys import _key
from .targets import resolve_verification_target
from ._required_scope import resolve_required_scope


def required_checks_report(model, *, configuration_id, scope_descriptor=None, scope_bindings=None):
    """Build the complete supplied-model obligation report before selection."""
    from ..changes.target_model import TargetModel, _default_scope
    if type(model) is not TargetModel:
        raise ModelError('verification_target_model_required')
    model = model.snapshot()
    scope = ScopeDescriptor({**_default_scope(), 'configuration_id': configuration_id})
    records = tuple(SourceRelations(item.content, path=item.path) for item in model.documents)
    RelationReferences(records)
    by_id = {record.identity.id: record for record in records}
    configuration = (None if configuration_id is None else
                     resolve_configuration(records, configuration_id))
    closure = None
    included = set(by_id)
    if scope_descriptor is not None or scope_bindings is not None:
        closure = resolve_required_scope(model, records, scope_descriptor, scope_bindings, configuration_id)
        scope = closure.seeds.descriptor
        included = set(closure.artifact_ids)
    source_types = {kind for rule in relation_rules('verified_by') for kind in rule.sources}
    subjects, contracts, checks, unresolved, without_checks = [], [], [], set(), []

    def classify(record):
        decision = evaluate_applicability(record, configuration).data
        if decision['status'] == 'potentially_applicable':
            unresolved.add(record.identity.id)
        return decision

    def dependency(source_id, target_id):
        if classify(by_id[target_id])['status'] == 'excluded':
            raise ScopeConfigurationDependencyError(source_id=source_id, target_id=target_id,
                                                     configuration_id=configuration_id)

    for source in sorted(records, key=lambda item: item.identity.id.encode('utf-8')):
        if source.identity.id not in included:
            continue
        if closure is not None:
            classify(source)
        if source.identity.artifact_type not in source_types:
            continue
        artifact = DomainArtifact if source.identity.artifact_type in DOMAIN_TYPES else RecordArtifact
        artifact(source.source_bytes, path=source.path)
        decision = classify(source)
        subjects.append(decision)
        if decision['status'] == 'excluded':
            continue
        targets = sorted({edge.target for edge in source.relations if edge.type == 'verified_by'},
                         key=lambda name: name.encode('utf-8'))
        if not targets:
            without_checks.append(source.identity.id)
        for target_id in targets:
            resolution = resolve_verification_target(model, source.identity.id, target_id)
            pair = resolution.data
            dependency(source.identity.id, target_id)
            for test in pair['tests']:
                dependency(target_id, test['artifact_id'])
            checks.extend(pair['required_checks'])
            contracts.append({'subject_artifact_id': source.identity.id, 'contract_id': target_id,
                              'resolution_sha256': resolution.sha256})
    checks.sort(key=_key)
    report = {'format_version': 'verification-required-checks-v1',
        'validation_scope': ('supplied_whole_project_required_checks' if closure is None
                             else 'supplied_scope_required_checks'),
        'project_id': model.binding.project_id, 'input_sha256': model._sources_sha256,
        'scope_descriptor': scope.data, 'scope_sha256': scope.sha256,
        'configuration_hash': None if configuration is None else configuration.sha256,
        'subjects': subjects, 'contracts': contracts, 'required_checks': checks,
        'required_checks_sha256': canonical_json_sha256(checks),
        'unresolved_applicability': sorted(unresolved, key=lambda name: name.encode('utf-8')),
        'subjects_without_checks': without_checks,
        'supplied_required_checks_complete': not (unresolved or without_checks),
        'project_files_verified': False, 'project_required_checks_complete': False,
        'run_selection_evaluated': False, 'full_verification_evaluated': False,
        'external_run_verified': False, 'release_readiness_evaluated': False,
        'test_code_executed': False, 'write_authorized': False, 'approval_granted': False}
    if closure is not None:
        report.update(scope_resolution=closure.data,
                      scope_resolution_sha256=closure.observation_sha256,
                      scope_providers_authenticated=False)
    return report
