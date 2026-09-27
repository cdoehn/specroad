"""Recompute a saved plan's whole isolated target, then validate and describe it.

No file reads, imports from data, time discovery, authorization or publication.
The initial supported scope is the unconfigured, closed current project over
an explicitly supplied inventory. Other scopes need their own complete provider.
"""
from dataclasses import dataclass
from hashlib import sha256

from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.configuration import ProjectConfiguration
from ..model.model_manifest import (ProjectReadBinding, ManifestResource,
                                     assemble_model_manifest)
from ..model.manifest_resources import project_json_resource
from ..model.paths import artifact_path, classify_path, PathClass, project_path
from ..model.attachments import AttachmentDescriptor
from ..model.language_registry import LanguageRegistry
from ..model.language_package_values import LanguagePackage
from ..profiles.values import ProfileResource
from ..profiles.composition import compose_profiles
from ..profiles.composition_values import EffectiveProfile
from ..storage.json_syntax import parse_json_object
from ..validation import ModelDocument, ModelGate, validate_model, assess_validation
from ..graph.relations import SourceRelations
from ..graph.references import RelationReferences
from ..graph.comparison_values import ComparisonInputs
from ..graph.artifact_comparison import compare_artifacts
from ..graph.direct_impact import direct_impact
from ..graph.scope_descriptors import ScopeDescriptor
from ..model.errors import ModelError
from .values import ChangePlan
from .lifecycle import prepare_plan_lifecycle, prepare_change_lifecycle
from .core import prepare_change_plan
from .target_values import TargetError, TargetPolicy, TargetAssessment, TARGET_VERSION


def _sequence(value, reason):
    if type(value) not in (tuple, list): raise TargetError(reason)
    return tuple(value)


def _project_scope(value):
    descriptor = ScopeDescriptor(value).data
    if (descriptor['scope_kind'] != 'project' or descriptor['boundary_policy'] != 'closed'
            or descriptor['configuration_id'] is not None):
        raise TargetError('target_complete_project_scope_required', pointer='/base/scope_descriptor')
    return descriptor


@dataclass(frozen=True, init=False)
class TargetModel:
    """Owned complete supplied inventory. Completeness on disk is not attested.

    Sources are real bytes, not paths to open. Resource and profile identities
    are recomputed from those bytes. Resources are unchanged by this adapter;
    resource-editing operation families remain explicitly unsupported.
    """
    configuration_bytes: bytes
    configuration: ProjectConfiguration
    binding: ProjectReadBinding
    documents: tuple
    resource_files: tuple
    resources: tuple
    profile: EffectiveProfile
    language_packages: tuple
    attachment_descriptors: tuple
    reserved_artifact_ids: tuple
    reserved_relation_ids: tuple
    previously_approved_ids: tuple
    _sources_sha256: str

    def __init__(self, configuration_bytes, binding, documents, *, profile,
                 resource_files=(), attachments=(), language_packages=(),
                 reserved_artifact_ids=(), reserved_relation_ids=(), previously_approved_ids=()):
        if type(configuration_bytes) is not bytes or type(binding) is not ProjectReadBinding:
            raise TargetError('target_configuration_bytes_and_binding_required')
        configuration = ProjectConfiguration(parse_json_object(configuration_bytes))
        if configuration.project_id != binding.project_id:
            raise TargetError('target_project_binding_mismatch')
        documents = _sequence(documents, 'target_documents_required')
        files = _sequence(resource_files, 'target_resource_files_required')
        if any(type(d) is not ModelDocument for d in documents + files):
            raise TargetError('target_document_required')
        documents = tuple(ModelDocument(d.path, d.content) for d in documents)
        files = tuple(ModelDocument(d.path, d.content) for d in files)
        paths = ['specroad.json', *(d.path for d in documents + files)]
        if len(set(p.casefold() for p in paths)) != len(paths):
            raise TargetError('target_duplicate_path')
        records, seen = [], set()
        for document in documents:
            r = SourceRelations(document.content, path=document.path)
            identity = r.identity
            if identity.id in seen: raise TargetError('target_duplicate_artifact_id')
            seen.add(identity.id)
            expected = artifact_path(identity.artifact_type, identity.id, configuration.id_prefix)
            if document.path != expected:
                raise TargetError('target_artifact_path_mismatch')
            records.append(r)
        descriptions = _sequence(attachments, 'target_attachments_required')
        if any(type(a) is not AttachmentDescriptor for a in descriptions):
            raise TargetError('target_attachment_descriptor_required')
        descriptions = tuple(AttachmentDescriptor.from_data(a.data) for a in descriptions)
        by_path = {a.path: a for a in descriptions}
        if len(by_path) != len(descriptions): raise TargetError('target_duplicate_attachment')
        registry_data = configuration.data.get('language_registry')
        registry, resources, profile_sources = None, [], []
        for document in files:
            path = project_path(document.path)
            if registry_data is not None and path == registry_data['path']:
                registry = LanguageRegistry(document.content, expected_sha256=registry_data['sha256'],
                                            expected_version=registry_data['registry_version'])
                resource = ManifestResource(binding, {'kind': 'language_registry', 'path': path,
                    'id': registry_data['registry_id'], 'version': registry.version,
                    'size': len(document.content), 'sha256': registry.sha256})
            elif path in by_path:
                a = by_path[path]
                if len(document.content) != a.size or sha256(document.content).hexdigest() != a.sha256:
                    raise TargetError('target_attachment_bytes_mismatch')
                resource = ManifestResource(binding, {'kind': 'attachment', **a.data})
            else:
                kind = classify_path(path, configuration)
                if kind not in (PathClass.PROFILE, PathClass.RULE, PathClass.MAPPING):
                    raise TargetError('target_unsupported_resource')
                resource = project_json_resource(configuration, path, document.content, binding)
                if kind is PathClass.PROFILE: profile_sources.append(ProfileResource(document.content))
            resources.append(resource)
        if not set(by_path) <= {d.path for d in files}:
            raise TargetError('target_attachment_bytes_missing')
        if registry_data is not None and registry is None:
            raise TargetError('target_registry_bytes_missing')
        if type(profile) is not EffectiveProfile or not profile.profile_chain:
            raise TargetError('target_effective_profile_required')
        packages = _sequence(language_packages, 'target_language_packages_required')
        if any(type(p) is not LanguagePackage for p in packages):
            raise TargetError('target_language_package_required')
        owned_packages = tuple(LanguagePackage(p.source_bytes) for p in packages)
        if any(a.binding() != b.binding() for a, b in zip(owned_packages, packages)):
            raise TargetError('target_language_package_binding_mismatch')
        packages = owned_packages
        # Recomposition binds actual resource bytes, not a fabricated hash label.
        rebuilt = compose_profiles(profile_sources, core_key=profile.profile_chain[0],
            cli_profiles=profile.profile_chain[1:], language_registry=registry,
            language_packages=packages)
        if rebuilt.canonical_bytes != profile.canonical_bytes:
            raise TargetError('target_profile_resource_mismatch')
        reservations = _reservations(configuration, reserved_artifact_ids,
                                     reserved_relation_ids, previously_approved_ids)
        for name, value in (('configuration_bytes', configuration_bytes), ('configuration', configuration),
                ('binding', binding), ('documents', tuple(sorted(documents, key=lambda d:d.path))),
                ('resource_files', tuple(sorted(files, key=lambda d:d.path))), ('resources', tuple(resources)),
                ('profile', rebuilt), ('language_packages', packages),
                ('attachment_descriptors', descriptions), *reservations.items()):
            object.__setattr__(self, name, value)
        # Reuse the canonical manifest's cross-resource identity checks now.
        self.manifest([r.data for r in records], _default_scope())
        object.__setattr__(self, '_sources_sha256', _source_digest(self))

    def snapshot(self):
        """Rebuild from original bytes; cached derived metadata is never authority."""
        if _source_digest(self) != self._sources_sha256:
            raise TargetError('target_sources_changed')
        return TargetModel(self.configuration_bytes, self.binding, self.documents,
            profile=self.profile, resource_files=self.resource_files,
            attachments=self.attachment_descriptors, language_packages=self.language_packages,
            **self.reservations)

    @property
    def reservations(self):
        return {name: list(getattr(self, name)) for name in
                ('reserved_artifact_ids', 'reserved_relation_ids', 'previously_approved_ids')}

    @property
    def source_files(self):
        return {'specroad.json': self.configuration_bytes,
                **{d.path:d.content for d in self.documents + self.resource_files}}

    @property
    def artifacts(self): return [parse_json_object(d.content) for d in self.documents]

    @property
    def resources_sha256(self):
        return canonical_json_sha256({'reservations': self.reservations, 'configuration_bytes': sha256(self.configuration_bytes).hexdigest(),
            'files': [{'path':d.path, 'sha256':sha256(d.content).hexdigest()} for d in self.resource_files],
            'language_packages': [p.binding() for p in self.language_packages],
            'profile': self.profile.binding()})

    def manifest(self, artifacts, descriptor):
        descriptor = _project_scope(descriptor)
        resources = list(self.resources)
        attachments = {r.data['path']:r.data for r in resources if r.data['kind'] == 'attachment'}
        for artifact in artifacts:
            for declared in artifact.get('attachments', []):
                a = AttachmentDescriptor.from_data(declared)
                if attachments.get(a.path) != {'kind':'attachment', **a.data}:
                    raise TargetError('target_referenced_attachment_unbound')
            resources.append(ManifestResource(self.binding, {'kind':'artifact', 'id':artifact['id'],
                'artifact_type':artifact['artifact_type'], 'revision':artifact['revision'],
                'sha256':canonical_json_sha256(artifact)}))
        return assemble_model_manifest(self.configuration, self.binding, resources,
            scope_descriptor=descriptor, effective_profile=self.profile.data)


def _reservations(configuration, artifacts, relations, history):
    from ._common import _reference
    from ..model.relation_values import RelationIdentity
    result = {}
    for name, values in (('reserved_artifact_ids', artifacts),
                         ('reserved_relation_ids', relations), ('previously_approved_ids', history)):
        values = _sequence(values, 'target_reservation_sequence_required')
        for item in values:
            if name == 'reserved_relation_ids':
                RelationIdentity(item, 'random128-v1')
            else:
                ident = _reference(item, '/' + name)
                if ident.id_prefix != configuration.id_prefix:
                    raise TargetError('target_reservation_project_mismatch')
        if len(set(values)) != len(values):
            raise TargetError('target_duplicate_reservation', pointer='/' + name)
        result[name] = tuple(sorted(values))
    return result


def _source_digest(model):
    return canonical_json_sha256({'files': [{'path': p, 'sha256': sha256(b).hexdigest()}
                                           for p, b in sorted(model.source_files.items())],
        'profile': model.profile.binding(), 'reservations': model.reservations,
        'packages': [sha256(p.source_bytes).hexdigest() for p in model.language_packages],
        'attachments': [a.data for a in sorted(model.attachment_descriptors, key=lambda a: a.path)]})


def _default_scope():
    return {'scope_version':'scope-v1', 'scope_kind':'project', 'selector':{},
            'configuration_id':None, 'closure_profile':'core-closure-v1', 'boundary_policy':'closed'}


def _gates(gates, policy, plan, model):
    gates = _sequence(gates, 'target_gates_required')
    if any(type(g) is not ModelGate for g in gates) or len({g.gate_id for g in gates}) != len(gates):
        raise TargetError('target_distinct_registered_gates_required')
    # Reusing an old model-only outcome cannot authorize a different plan/command.
    bound = tuple(ModelGate(g.gate_id, g.version, g.dependencies, g.check,
        canonical_json_sha256({'plan':plan.sha256, 'resources':model.resources_sha256,
            'command':policy.data(), 'gate_resources':g.resources_sha256})) for g in gates)
    required = set(policy.required_gate_ids)
    # Raw rule/mapping resources are hash-bound but their full specialized
    # semantics must be confirmed by an explicit trusted whole-target service.
    if any(r.data['kind'] in ('rule','mapping') for r in model.resources):
        required.add('extension:target-resources')
    return bound, sorted(required - {g.gate_id for g in gates})



def _empty_target_gates(report, registered, profile):
    """Command gates also run on an empty target; no vacuous resource approval.

    Reuse the model's bound context/result contracts. Ordinary artifact gates
    remain not-applicable without artifacts; whole-target extension gates do not.
    """
    from ..validation.values import GateContext, GateDependencies, GateResult, ValidationReport
    data = report.data
    if data['source_count']:
        return report
    replacements = {}
    for gate in sorted(registered, key=lambda item: item.gate_id):
        if not gate.gate_id.startswith('extension:'):
            continue
        diagnostics = []
        phase = 'dependencies'
        try:
            context = GateContext._create((), (), profile, (), gate, phase, data['input_sha256'])
            deps = gate.dependencies(context)
            if (type(deps) is not GateDependencies or deps.input_sha256 != context.input_sha256
                    or deps.by_artifact != {}):
                raise ModelError('validation_gate_dependencies_unbound_or_incomplete')
            phase = 'check'
            context = GateContext._create((), (), profile, (), gate, phase, data['input_sha256'])
            outcome = gate.check(context)
            if (type(outcome) is not GateResult or outcome.input_sha256 != context.input_sha256
                    or outcome.checked_ids != ()):
                raise ModelError('validation_gate_result_unbound_or_incomplete')
            diagnostics = list(outcome.diagnostics)
            if any(d.get('artifact_id') is not None for d in diagnostics):
                raise ModelError('validation_gate_diagnostic_outside_subjects')
        except ModelError as error:
            diagnostics = [{**error.diagnostic(), 'severity':'error'}]
        except Exception:
            diagnostics = [{'reason':'validation_gate_discovery_failed' if phase == 'dependencies'
                            else 'validation_gate_check_failed', 'severity':'error'}]
        status = 'failed' if any(d.get('severity','error') == 'error' for d in diagnostics) else 'passed'
        replacements[gate.gate_id] = {'stage':gate.gate_id, 'checked_ids':[],
                                      'status':status, 'diagnostics':diagnostics}
    data['stages'] = [replacements.get(s['stage'], s) for s in data['stages']]
    data['checks_complete'] = all(s['status'] in ('passed','failed','not_applicable') for s in data['stages'])
    data['model_valid'] = (False if any(s['status']=='failed' for s in data['stages']) else
                           True if data['checks_complete'] else None)
    return ValidationReport._create(data)


def _describe(model, artifacts):
    before = tuple(SourceRelations(d.content, path=d.path) for d in model.documents)
    after = tuple(SourceRelations(canonical_json_bytes(v)) for v in artifacts)
    diff = compare_artifacts(ComparisonInputs(model.binding.project_id, before),
                             ComparisonInputs(model.binding.project_id, after))
    changed = [c['artifact_id'] for c in diff.data['changes']]
    sides = {}
    for name, records in (('before',before), ('after',after)):
        try:
            refs = RelationReferences(records)
            ids = {r.identity.id for r in records}
            sides[name] = {'complete': True, 'items': [direct_impact(i,refs).data for i in changed if i in ids]}
        except ModelError as error:
            sides[name] = {'complete':False, 'reason':error.reason, 'items':[]}
    return diff.data, {'depth':1, 'transitive':False, **sides}


def assess_change_target(plan, model, *, policy, gates=(), strict=False):
    """Recompute every result and validate ALL target artifacts, not touched IDs.

    Failure reports can be inspected but cannot be promoted to a prepared
    transaction. Mandatory command gates and missing model services fail closed.
    """
    if type(plan) is not ChangePlan or type(model) is not TargetModel or type(policy) is not TargetPolicy:
        raise TargetError('target_plan_model_policy_required')
    if type(strict) is not bool: raise TargetError('target_strict_boolean_required')
    model = model.snapshot()
    policy = TargetPolicy(policy.command_id, policy.version, policy.required_gate_ids)
    plan = ChangePlan(plan.source_bytes)  # Enforce the unchanged self-hash again.
    value = plan.data
    scope = _project_scope(value['base']['scope_descriptor'])
    base = model.manifest(model.artifacts, scope)
    if value['base']['model_root_sha256'] != base.sha256:
        raise TargetError('target_base_root_mismatch', pointer='/base/model_root_sha256')
    folded = prepare_plan_lifecycle(plan, model.artifacts, observed_base_root=base.sha256,
        observed_scope=scope, source_files=model.source_files, **model.reservations)
    artifacts = folded.artifacts
    target = model.manifest(artifacts, scope)
    if target.sha256 != value['expected_result']['model_root_sha256']:
        raise TargetError('target_result_root_mismatch', pointer='/expected_result/model_root_sha256')
    originals = {parse_json_object(d.content)['id']:d for d in model.documents}
    documents = []
    for artifact in artifacts:
        old = originals.get(artifact['id'])
        raw = old.content if old is not None and canonical_json_sha256(parse_json_object(old.content)) == canonical_json_sha256(artifact) else canonical_json_bytes(artifact)
        documents.append(ModelDocument(artifact_path(artifact['artifact_type'],artifact['id'],model.configuration.id_prefix), raw))
    documents = tuple(sorted(documents,key=lambda d:d.path))
    registered, missing = _gates(gates,policy,plan,model)
    report = validate_model(documents, profile=model.profile, gates=registered)
    report = _empty_target_gates(report, registered, model.profile)
    assessment = assess_validation(report, fail_on=model.configuration.data['validation_policy'].get('fail_on','error'),
                                   strict=strict, documents=documents)
    diff, impact = _describe(model, artifacts)
    valid = assessment.passed and report.complete and not missing
    binding = {'version':TARGET_VERSION, 'plan_sha256':plan.sha256, 'base_model_root':base.sha256,
        'target_model_root':target.sha256, 'resources_sha256':model.resources_sha256,
        'validation_input_sha256':report.data['input_sha256'], 'command':policy.data(),
        'strict':strict, 'source_files':[{'path':p,'sha256':sha256(b).hexdigest()}
                                      for p,b in sorted(model.source_files.items())]}
    return TargetAssessment._create({'format_version':TARGET_VERSION,
        'input_sha256':canonical_json_sha256(binding), 'binding':binding,
        'base_manifest':base.data, 'target_manifest':target.data,
        'target_validated':bool(valid), 'checks_complete':report.complete and not missing,
        'missing_command_gates':missing,
        'validation':assessment.as_dict(), 'diff':diff, 'impact':impact,
        'lifecycle':{'metadata_applied':folded.metadata_applied, 'decisions':folded.decisions,
                     'history_complete':False, 'previously_approved_ids':folded.previously_approved_ids},
        'validation_scope':'complete_supplied_project_target', 'project_files_verified':False,
        'atomic_snapshot':False, 'transaction_prepared':False, 'execution_ready':False,
        'approval_granted':False, 'write_authorized':False},plan,documents)


def prepare_change_target(model, operations, *, change_plan_id, request_id, actor,
        planned_at, scope_descriptor, metadata_policy_version, policy, gates=(),
        preconditions=(), strict=False):
    """Create a regular plan from explicit inputs, then use the saved-plan path.

    No ID/time/user discovery. Both entry paths run the same full target gates.
    An invalid target can be inspected, never passed off as a prepared write.
    Operations are explicit prepared data, not raw CLI drafts: create payloads
    must satisfy the existing plan contract, including bound creation metadata.
    """
    if type(model) is not TargetModel or type(policy) is not TargetPolicy:
        raise TargetError('target_model_policy_required')
    from .values import ChangeOperation
    from ._patch_values import _snapshot
    model = model.snapshot()
    scope = _project_scope(scope_descriptor)
    operations = [ChangeOperation(v).data for v in _sequence(operations, 'target_operations_required')]
    preconditions = _snapshot(list(_sequence(preconditions, 'target_preconditions_required')), '/preconditions').data
    folded = prepare_change_lifecycle(model.artifacts, operations,
        metadata_policy_version=metadata_policy_version, actor=actor, planned_at=planned_at,
        preconditions=preconditions, source_files=model.source_files, **model.reservations)
    plan = prepare_change_plan({'format_version':'1.2.0',
        'metadata_policy_version':metadata_policy_version, 'change_plan_id':change_plan_id,
        'request_id':request_id, 'actor':actor, 'planned_at':planned_at,
        'base':{'scope_descriptor':scope, 'model_root_sha256':model.manifest(model.artifacts,scope).sha256},
        'operations':operations, 'preconditions':preconditions,
        'result_artifacts':[{'artifact':c.data, 'sha256':c.candidate_sha256} for c in folded.candidates],
        'expected_result':{'model_root_sha256':model.manifest(folded.artifacts,scope).sha256}})
    return assess_change_target(plan, model, policy=policy, gates=gates, strict=strict)
