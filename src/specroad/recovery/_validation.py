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
from .values import require


def validate_project(files):
    """No user-supplied success callbacks, fake reviews or gate overrides.

    W supports native document/block structure, draft standard artifacts,
    byte-bound attachments, recorded bound Evidence and sealed Baselines. Unavailable
    specialist/history providers fail closed; they are not waived by a plan.
    """
    model = owned_payload_model(files, source_label='restore:owned-project')
    require(not any(r.data['kind'] in ('rule', 'mapping') for r in model.resources),
            'restore_resource_semantics_provider_required')
    require(all(a['id_scheme'] == 'random128-v1' for a in model.artifacts),
            'restore_legacy_provider_required')
    archives = {p: b for p, b in files.items() if classify_path(p, model.configuration) is PathClass.ARCHIVE_OBJECT}
    current = {a['id']: a for a in model.artifacts}
    for document in model.documents:
        if parse_json_object(document.content)['artifact_type'] == 'baseline':
            originals = baseline_objects(document.content, lambda p: _archive(archives, p))
            _archived_history(document.content, originals, current, files, model.configuration)
    # Native Evidence freshness is reported separately. Historical failed/stale
    # observations are allowed by restore-preserve-v1, never turned into passed.
    evidence_assessments(model)

    def dependencies(context):
        return context.dependency_result({identity: list(context.all_ids) for identity in context.subjects})

    def documents(context):
        require(all(context.artifact(i)['artifact_type'] in ('document', 'section', 'content_block')
                    for i in context.subjects), 'restore_document_specialist_required')
        primary = assess_document_roles(model).require_primary_document()
        assess_document_structure(model).require_document(primary['artifact_id'])
        _include_graph(model.documents, DocumentIncludeCycleError)
        _block_semantics(model)
        return context.result()

    def lifecycle(context):
        # No lifecycle transition is made. Supported immutable records have
        # their native archive/subject checks above and exact stored states. A stored
        # approved standard artifact cannot self-certify its historical gates.
        require(all((context.artifact(i)['artifact_type'] == 'baseline' and
                     context.artifact(i)['baseline_state'] == 'sealed') or
                    (context.artifact(i)['artifact_type'] == 'evidence' and
                     context.artifact(i)['evidence_state'] == 'recorded') for i in context.subjects),
                'restore_stored_lifecycle_provider_required')
        return context.result()

    def historical_evidence(context):
        require(all(context.artifact(i)['artifact_type'] in ('evidence', 'verification', 'test')
                    for i in context.subjects), 'restore_evidence_specialist_required')
        # Actual native subject assessments and contract/test readers ran above.
        # This is structural recovery validation, not a positive result gate.
        return context.result()

    def external(context):
        require(all(context.artifact(i)['artifact_type'] not in ('source', 'code_ref')
                    for i in context.subjects), 'restore_external_resource_provider_required')
        # TargetModel already verifies every attachment's original bytes and
        # exact declared size/hash; no path is opened through a supplied string.
        return context.result()

    gates = tuple(ModelGate(name, 'restore-native-project-v1', dependencies, callback,
                            model._sources_sha256) for name, callback in
                  (('document_model', documents), ('lifecycle', lifecycle), ('external_resources', external),
                   ('evidence_currentness', historical_evidence)))
    gates += (baseline_integrity_gate(tuple(SnapshotObject(b) for b in archives.values())),)
    report = validate_model(model.documents, profile=model.profile, resources=validation_resources(model),
                            gates=gates, document_role_scope='full_project')
    for stage in report.data['stages']:
        if stage['status'] == 'unavailable':
            require(False, 'restore_' + stage['stage'] + '_provider_required')
        if stage['status'] == 'failed':
            diagnostic = stage['diagnostics'][0]
            require(False, diagnostic['reason'], path=diagnostic.get('path'))
    require(report.data['checks_complete'] and report.data['model_valid'] is True,
            'restore_full_project_validation_required')
    descriptor = ScopeDescriptor(_default_scope())
    closure, native, artifacts, _ = export_scope(model, descriptor)
    require(not closure.boundary_references and set(closure.artifact_ids) == {a['id'] for a in model.artifacts}
            and set(closure.resource_ids) == {resource_identity(r) for r in model.resources}
            and native.sha256 == model.manifest(artifacts, descriptor.data).sha256,
            'restore_project_closure_incomplete')
    return model, native.sha256


def _archive(archives, path):
    require(path in archives, 'restore_referenced_archive_missing', path=path)
    return archives[path]


def _archived_history(raw, originals, current, files, configuration):
    """Do not let an embedded Baseline conceal published identity evidence.

    W can compare known draft revisions, but cannot fold historical approval
    and legacy evidence. Such snapshots require 15.k even when the current
    mutable records look like a supported draft-only project.
    """
    from ..model.paths import artifact_path
    record = parse_json_object(raw)
    for row in record['manifest']:
        if row['role'] != 'artifact':
            continue
        content = originals[row['object_path']]
        value = parse_json_object(content)
        if value['artifact_type'] in ('baseline', 'evidence'):
            path = artifact_path(value['artifact_type'], value['id'], configuration.id_prefix)
            require(files.get(path) == content, 'restore_archived_baseline_history_conflict',
                    path=path, exit_code=6)
            if value['artifact_type'] == 'baseline':
                _archived_history(content, originals, current, files, configuration)
            continue
        require(value['maturity'] == 'draft' and value['id_scheme'] == 'random128-v1',
                'restore_archived_history_provider_required')
        candidate = current.get(value['id'])
        require(candidate is None or candidate['revision'] >= value['revision'],
                'restore_archived_revision_conflict', exit_code=6)
