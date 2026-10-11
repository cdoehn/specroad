"""Pure semantic description from the already loaded model and check results.

No project discovery, preflight, file access, lock acquisition or repair. The
calling inspection retains responsibility for freshness and runtime blockers.
"""
from ..changes.target_model import _default_scope


def semantic_description(model, report, assessment):
    artifacts = model.artifacts
    counts = {}
    for artifact in artifacts:
        kind = artifact['artifact_type']
        counts[kind] = counts.get(kind, 0) + 1
    semantic = {'project_id': model.configuration.project_id,
        'model_root_sha256': model.manifest(artifacts, _default_scope()).sha256,
        'schema_version': model.configuration.data['schema_version'],
        'active_profiles': [{k: p[k] for k in ('profile_id', 'version')}
                            for p in model.profile.data['profiles']],
        'artifact_counts': dict(sorted(counts.items())), 'migration_needed': False,
        'diagnostic_summary': assessment.summary['diagnostics_by_severity']
                              if report.data['checks_complete'] else None,
        'primary_documents': sorted(({'id': a['id'], 'title': a['title']} for a in artifacts
            if a['artifact_type'] == 'document' and a.get('document_role') == 'primary_specification'),
            key=lambda a: a['id'])}
    return semantic
