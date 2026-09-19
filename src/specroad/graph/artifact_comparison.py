"""Compare explicit artifact sets without opening source files or judging edits."""
from ..model.canonical import canonical_json_sha256
from ..model.errors import ModelError
from .comparison_values import ComparisonInputs, ComparisonResult
from .field_comparison import field_diff


def compare_artifacts(before, after):
    """Compare supplied sets by immutable artifact ID; not a legal edit plan."""
    if type(before) is not ComparisonInputs or type(after) is not ComparisonInputs:
        raise ModelError('comparison_inputs_required')
    if before.project_id != after.project_id:
        raise ModelError('comparison_project_mismatch')
    if len({r.identity.id_prefix for r in before.records + after.records}) > 1:
        raise ModelError('mixed_project_prefix')
    left = {r.identity.id: r for r in before.records}
    right = {r.identity.id: r for r in after.records}
    changes = []
    for identity in sorted(set(left) | set(right), key=lambda value: value.encode('utf-8')):
        old, new = left.get(identity), right.get(identity)
        if old is not None and new is not None and old.identity != new.identity:
            raise ModelError('comparison_identity_changed')
        delta = field_diff(old.data if old is not None else None,
                           new.data if new is not None else None).data
        if delta['changed']:
            if old is None or new is None:
                delta['changes'][0].update(
                    operation='add' if old is None else 'remove',
                    before_present=old is not None, after_present=new is not None)
            categories = {item['category'] for item in delta['changes']}
            change_kind = 'added' if old is None else 'removed' if new is None else 'modified'
            if old is not None and new is not None:
                if old.data['maturity'] != 'retired' and new.data['maturity'] == 'retired':
                    change_kind = 'retired'
                artifact_type = new.identity.artifact_type
                fields = {item['pointer'].split('/')[1] for item in delta['changes'] if item['pointer']}
                if artifact_type in ('document', 'section', 'content_block', 'view') and fields & {
                        'relations', 'block_type', 'payload', 'content', 'query', 'render_policy'}:
                    categories.add('document_structure_changed')
                if artifact_type == 'code_ref' and fields - {'revision', 'updated_at', 'updated_by'}:
                    categories.add('code_reference_changed')
                if artifact_type in ('verification', 'test') and fields - {'revision', 'updated_at', 'updated_by'}:
                    categories.add('verification_changed')
            categories.add(change_kind)
            changes.append({'artifact_id': identity,
                'change_kind': change_kind, 'categories': sorted(categories),
                'before_sha256': canonical_json_sha256(old.data) if old is not None else None,
                'after_sha256': canonical_json_sha256(new.data) if new is not None else None,
                'fields': delta['changes']})
    return ComparisonResult({'comparison_version': 'artifact-diff-v1',
        'project_id': before.project_id, 'before_sha256': before.fingerprint,
        'after_sha256': after.fingerprint, 'changes': changes, 'changed': bool(changes),
        'validation_scope': 'supplied_artifact_sets_only', 'write_authorized': False})


