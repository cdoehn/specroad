"""Shared inert authorization description and exact compiled JSON shape."""
def authorization_contract(protocol):
    """Prerequisites of the registered adapter, never a permission grant."""
    inputs = protocol.work.required_inputs
    return {'source': 'trusted_host_and_native_checks', 'declaration_is_permission': False,
            'human_decision_required': 'human_decision' in inputs,
            'current_human_reviews_required': 'current_human_reviews' in inputs,
            'host_authority_required': 'host_authority' in inputs,
            'autonomous_approval': False}



def authorization_schema():
    from .result_schemas import _object
    return _object({'source': {'const': 'trusted_host_and_native_checks'},
        'declaration_is_permission': {'const': False},
        'human_decision_required': {'type': 'boolean'},
        'current_human_reviews_required': {'type': 'boolean'},
        'host_authority_required': {'type': 'boolean'}, 'autonomous_approval': {'const': False}})
