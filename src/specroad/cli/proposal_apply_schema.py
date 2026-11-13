"""Machine contract for the implemented native Proposal Apply route."""
def apply_schema():
    from .result_schemas import _object, _nullable
    from .proposal_check_schema import check_schema
    text = {'type': 'string', 'minLength': 1}
    sha = {'type': 'string', 'pattern': r'^[0-9a-f]{64}(?![\s\S])'}
    audit = check_schema()['properties']['audit']
    audit['properties']['outcome'] = {'enum': ['dry_run', 'committed', 'replayed', 'failed']}
    return _object({'format_version': {'const': 'proposal-apply-v1'}, 'proposal_id': text,
        'revision': {'type': 'integer', 'minimum': 2}, 'content_revision': {'type': 'integer', 'minimum': 1},
        'content_sha256': sha, 'base_model_root_sha256': sha, 'change_plan_sha256': sha,
        'proposal_status': {'const': 'applied'}, 'maturity': {'const': 'applied'},
        **{key: {'type': 'boolean'} for key in ('dry_run', 'replayed', 'project_writes_performed')},
        'approval_granted': {'const': False}, 'write_authorized': {'const': False},
        'completion': _nullable({'type': 'object'}), 'audit': audit})
