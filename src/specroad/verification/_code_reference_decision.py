"""Pure H.3 decisions from admitted source and exact selection observations."""
from ..model.errors import ModelError


def decide_code_state(reference_kind, *, target_present, file_hash_matches,
                      selection_result):
    """Select the first applicable row without reading, searching or reporting.

    Inputs come only from the native source reader and H.2 locator. Their
    admission, safety and decoding errors remain outside the state decision.
    """
    if not target_present:
        return 'missing', 'target_missing', []
    if reference_kind == 'file':
        if file_hash_matches:
            return 'current', None, []
        return 'stale', 'file_changed', []
    if reference_kind not in ('line_range', 'text_anchor'):
        raise ModelError('code_reference_state_kind_unsupported', pointer='/reference_kind')
    if selection_result == 'stored_position':
        diagnostics = [] if file_hash_matches else ['file_changed_outside_selection']
        return 'current', None, diagnostics
    if selection_result == 'relocated':
        return 'relocated', None, []
    return 'stale', selection_result, []
