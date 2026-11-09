"""Machine audit envelope for the isolated native Proposal check."""
def check_schema():
    from .result_schemas import _object, _nullable
    from .proposal_commands import validation_schema
    text = {'type': 'string', 'minLength': 1}
    sha = {'type': 'string', 'pattern': r'^[0-9a-f]{64}(?![\s\S])'}
    # Native diff inventories supply the IDs; use the supported schema vocabulary.
    ids = {'type': 'array', 'items': text}
    native = {'type': 'object'}
    structures = validation_schema()['properties']
    return _object(dict(format_version={'const': 'proposal-check-v1'}, passed={'type': 'boolean'},
        observed_status=structures['observed_status'], eligible_transition={'enum': [None, 'checked']},
        binding=structures['binding'], proposal_sha256=_nullable(sha), context_sha256=_nullable(sha),
        target_model_root_sha256=_nullable(sha), target_sources_sha256=_nullable(sha),
        checks={'type': 'object', 'additionalProperties': False, 'properties': {
            'validation': native, 'lint': native, 'diff': native,
            **{key: {'type': 'array', 'items': native} for key in ('queries', 'renders', 'impact')}}},
        audit=_object(dict(proposal_id=_nullable(text), base=_nullable(native), tool_version=text,
            started_at=text, ended_at=text, outcome={'enum': ['passed', 'failed']},
            diagnostics={'type': 'array', 'items': native}, created_ids=ids, changed_ids=ids, removed_ids=ids)),
        workspace=_object(dict(retained={'type': 'boolean'}, path=_nullable(text),
            cleanup={'enum': ['not_created', 'removed', 'retained', 'failed']})),
        full_semantic_validation={'type': 'boolean'}, approval_granted={'const': False},
        write_authorized={'const': False}, result_sha256=sha))
