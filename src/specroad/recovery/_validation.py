"""Full supported supplied-project gates, never a container-success shortcut."""
from ..archive.objects import SnapshotObject
from ..archive.verification import baseline_integrity_gate
from ..authoring._document_mutation_validation import _block_semantics
from ..bundles._payload_model import owned_payload_model
from ..changes._target_materialization import validation_resources
from ..changes.target_model import _default_scope
from ..documents.roles import assess_document_roles
from ..documents.structure import assess_document_structure
from ..documents._include_graph import _include_graph
from ..documents.includes import DocumentIncludeCycleError
from ..exchange._export_scope import export_scope, resource_identity
from ..graph.scope_descriptors import ScopeDescriptor
from ..model.paths import PathClass, classify_path
from ..storage.json_syntax import parse_json_object
from ..validation import ModelGate, validate_model
from ._sources import baseline_objects
from ._evidence_history import evidence_assessments
from ._schema_boundary import declared_files
from .values import require


def project_bytes(files):
    from ._owned_checks import checked_bytes
    return checked_bytes('restore-project', tuple(sorted(files.items())),
                         lambda: _project_bytes(files))


def _project_bytes(files):
    """Original model/manifest binding only, never current qualification."""
    from ._receipt_history import receipt_history, check_receipt_targets
    from ..model.configuration import ProjectConfiguration
    declared_files(files)
    configuration = ProjectConfiguration(parse_json_object(files['specroad.json']))
    operational, journals = receipt_history(files, configuration.project_id)
    require(all(not p.startswith('.specroad/') or p in operational for p in files),
            'restore_operational_history_provider_required')
    check_receipt_targets(journals, files)
    model = owned_payload_model({p: raw for p, raw in files.items() if p not in operational},
                                source_label='restore:owned-project')
    descriptor = ScopeDescriptor(_default_scope())
    closure, native, artifacts, _ = export_scope(model, descriptor)
    require(not closure.boundary_references and set(closure.artifact_ids) == {a['id'] for a in model.artifacts}
            and set(closure.resource_ids) == {resource_identity(r) for r in model.resources}
            and native.sha256 == model.manifest(artifacts, descriptor.data).sha256,
            'restore_project_closure_incomplete')
    return model, native.sha256


def validate_project(files, *, services=None):
    """No user-supplied success callbacks, fake reviews or gate overrides.

    Full native model and specialist checks apply to the actual stored states.
    Unavailable specialist/history providers fail closed; a plan never waives
    a current review, source observation or approval invariant.
    """
    from .services import native_services
    services = native_services(services)
    model, root = project_bytes(files)
    from ..validation.resource_semantics import check_normative_resources
    check_normative_resources(model)
    archives = {p: b for p, b in files.items() if classify_path(p, model.configuration) is PathClass.ARCHIVE_OBJECT}
    current = {a['id']: a for a in model.artifacts}
    for document in model.documents:
        if parse_json_object(document.content)['artifact_type'] == 'baseline':
            originals = baseline_objects(document.content, lambda p: _archive(archives, p))
            _archived_history(document.content, originals, current, files, model.configuration)
    # Native Evidence freshness is reported separately. Historical failed/stale
    # observations are allowed by restore-preserve-v1, never turned into passed.
    evidence_assessments(model)
    from ._specialists import (approval_checks, review_checks, configuration_checks,
                              task_gate, external_checks, proposal_checks)
    approvals = approval_checks(model, services)
    reviews = review_checks(model)
    proposals = proposal_checks(model, services)
    # Current external observations have native conflict, safety and I/O
    # classes. Run them outside the generic diagnostic gate, which otherwise
    # reduces exceptions to a failed model check. Reobserve on every call;
    # these are never cached alongside immutable original-byte checks.
    external_subjects = tuple(a['id'] for a in model.artifacts
        if a['artifact_type'] in ('source', 'code_ref') or a.get('attachments'))
    external_checks(model, services, external_subjects)

    def dependencies(context):
        return context.dependency_result({identity: list(context.all_ids) for identity in context.subjects})

    def documents(context):
        primary = assess_document_roles(model).require_primary_document()
        structure = assess_document_structure(model)
        for item in model.artifacts:
            if item['artifact_type'] == 'document':
                structure.require_document(item['id'])
            elif item['artifact_type'] == 'view':
                from ..documents.views import resolve_view
                resolve_view(model, item['id'])
        _include_graph(model.documents, DocumentIncludeCycleError)
        _block_semantics(model)
        return context.result()

    def lifecycle(context):
        # These are stored states, not new transitions or approvals. Native
        # record/domain schemas check the maturity and special-state coupling;
        # the complete model checks required relations and type-specific gates.
        from ..model.record_contracts import SPECIAL_STATES
        for identity in context.subjects:
            item = context.artifact(identity)
            if item['artifact_type'] == 'requirement' and item['maturity'] == 'approved':
                require(identity in approvals, 'restore_requirement_review_provider_required', path=identity)
            elif item['artifact_type'] == 'proposal':
                require(identity in proposals, 'restore_proposal_original_contexts_required', path=identity)
            elif item['artifact_type'] not in SPECIAL_STATES and item['maturity'] == 'superseded':
                require(any(other['artifact_type'] == item['artifact_type'] and other['id'] != identity
                    and any(edge['type'] == 'supersedes' and edge['target'] == identity
                            for edge in other['relations']) for other in model.artifacts),
                    'successor_required_in_final_model', path=identity)
        return context.result()

    def review_currentness(context):
        require(all(context.artifact(i)['artifact_type'] == 'relation_review' or i in approvals
                    for i in context.subjects), 'restore_review_specialist_required')
        # The actual native status fold and exact approval verifiers ran above.
        # Negative historical review records are retained, not a positive gate.
        return context.result()

    def configuration(context):
        configuration_checks(model)
        return context.result()

    def historical_evidence(context):
        require(all(context.artifact(i)['artifact_type'] in ('evidence', 'verification', 'test')
                    for i in context.subjects), 'restore_evidence_specialist_required')
        # Actual native subject assessments and contract/test readers ran above.
        # This is structural recovery validation, not a positive result gate.
        return context.result()

    def external(context):
        require(all(identity in external_subjects for identity in context.subjects),
                'restore_external_subject_not_checked')
        # TargetModel already verifies every attachment's original bytes and
        # exact declared size/hash; no path is opened through a supplied string.
        return context.result()

    gates = tuple(ModelGate(name, 'restore-native-project-v1', dependencies, callback,
                            model._sources_sha256) for name, callback in
                  (('document_model', documents), ('lifecycle', lifecycle), ('external_resources', external),
                   ('review_currentness', review_currentness), ('configuration', configuration),
                   ('evidence_currentness', historical_evidence)))
    gates += (baseline_integrity_gate(tuple(SnapshotObject(b) for b in archives.values())),)
    gates += task_gate(model, services)
    report = validate_model(model.documents, profile=model.profile, resources=validation_resources(model),
                            gates=gates, document_role_scope='full_project',
                            approval_contexts=tuple(pair[0] for pair in approvals.values()))
    for stage in report.data['stages']:
        if stage['status'] == 'unavailable':
            require(False, 'restore_' + stage['stage'] + '_provider_required')
        if stage['status'] == 'failed':
            diagnostic = stage['diagnostics'][0]
            require(False, diagnostic['reason'], path=diagnostic.get('path'))
    require(report.data['checks_complete'] and report.data['model_valid'] is True,
            'restore_full_project_validation_required')
    return model, root


def _archive(archives, path):
    require(path in archives, 'restore_referenced_archive_missing', path=path)
    return archives[path]


def _archived_history(raw, originals, current, files, configuration):
    """Do not let an embedded Baseline conceal published identity evidence.

    Protected original bytes are retained and published identities/revisions
    cannot disappear or regress. Current qualification runs separately.
    """
    from ..model.paths import artifact_path
    record = parse_json_object(raw)
    for row in record['manifest']:
        if row['role'] != 'artifact':
            continue
        content = originals[row['object_path']]
        value = parse_json_object(content)
        from ._history import protected_record
        if protected_record(value):
            path = artifact_path(value['artifact_type'], value['id'], configuration.id_prefix)
            require(files.get(path) == content, 'restore_archived_baseline_history_conflict',
                    path=path, exit_code=6)
            if value['artifact_type'] == 'baseline':
                _archived_history(content, originals, current, files, configuration)
            continue
        candidate = current.get(value['id'])
        require(value['maturity'] != 'approved' or candidate is not None,
                'restore_archived_approval_conflict', exit_code=6)
        require(candidate is None or candidate['revision'] >= value['revision'],
                'restore_archived_revision_conflict', exit_code=6)
