"""Select a closed native project using the shared configuration services.

Receives an owned complete model after identity/provider checks. This is pure
snapshot preparation, with no publication or completeness authority.
"""
from ..model.errors import ModelError


def selected_project(model, configuration_id):
    from ..changes.target_model import TargetModel
    selection = None
    if configuration_id is not None:
        from ..configurations import resolve_configuration, evaluate_configuration
        from ..graph.relations import SourceRelations
        from ..graph.references import RelationReferences
        records = tuple(SourceRelations(d.content, path=d.path) for d in model.documents)
        selection = resolve_configuration(records, configuration_id)
        evaluated = evaluate_configuration(records, configuration_id).data
        if not evaluated['consistent']:
            raise ModelError('baseline_configuration_dependency_excluded')
        retained = set(evaluated['applicable_artifact_ids'])
        if not {r['id'] for r in selection.manifest['configurations']} <= retained:
            raise ModelError('baseline_configuration_chain_not_retained')
        selected = tuple(r for r in records if r.identity.id in retained)
        # The native provider has a closed project scope. Missing non-owning
        # targets also require an explicit boundary provider; never drop edges.
        RelationReferences(selected)
        archives = {row['object_path'] for r in selected if r.identity.artifact_type == 'baseline'
                    for row in r.data.get('manifest', []) if 'object_path' in row}
        all_archives = {r.data['path'] for r in model.resources if r.data['kind'] == 'archive'}
        model = TargetModel(model.configuration_bytes, model.binding,
            tuple(d for d in model.documents if d.path in {r.path for r in selected}),
            profile=model.profile, attachments=model.attachment_descriptors,
            resource_files=tuple(d for d in model.resource_files
                                if d.path not in all_archives or d.path in archives),
            language_packages=model.language_packages)
    return model, selection
