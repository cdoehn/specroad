"""Inclusive stored line selections over already bound original source bytes."""
from dataclasses import dataclass, field
from hashlib import sha256

from ..model.canonical import canonical_json_bytes
from ..model.errors import ModelError
from ..storage.json_syntax import parse_json_object
from .code_references import CodeReferenceSource
from ._code_selection_cursor import stored_line_span
from ._code_selection_hash import normalized_text, selection_digest, selection_utf8


@dataclass(frozen=True, init=False)
class CodeLineSelection:
    """Owned normalized UTF-8 selection, not a reference state or write grant."""
    selection_bytes: bytes = field(repr=False)
    _encoded: bytes = field(repr=False)

    def __init__(self, *args, **kwargs):
        raise TypeError('Use select_code_lines')

    @property
    def data(self):
        return parse_json_object(self._encoded)

    @property
    def sha256(self):
        return sha256(self._encoded).hexdigest()

    def __bool__(self):
        raise TypeError('A line selection is not a reference state or approval')


def select_code_lines(source):
    """Evaluate H.2 at the stored inclusive position without reading files again.

    The source is an owned read_code_reference result. Decode strictly using
    the stored encoding, normalize only CRLF/CR, and retain LF terminators in
    selected lines. No search, relocation or H.3 state decision is performed.
    """
    if type(source) is not CodeReferenceSource:
        raise ModelError('code_reference_source_bytes_required')
    bound = source.data
    value = bound['reference']
    if value['reference_kind'] != 'line_range':
        raise ModelError('code_reference_line_range_required', pointer='/reference_kind')
    text = normalized_text(source.source_bytes, value['encoding'])
    selected_start, selected_end, line_count = stored_line_span(
        text, value['start_line'], value['end_line'])
    if selected_end is None:
        raise ModelError('code_reference_selection_missing', pointer='/end_line')
    selected = selection_utf8(text[selected_start:selected_end])
    selection_sha256 = selection_digest(selected)
    report = {'format_version': 'code-line-selection-v1',
        'validation_scope': 'code_selection_at_stored_position_only',
        'source': bound, 'source_sha256': source.sha256,
        'encoding': value['encoding'], 'start_line': value['start_line'],
        'end_line': value['end_line'], 'line_count': line_count,
        'selected_line_count': value['end_line'] - value['start_line'] + 1,
        'selection_sha256': selection_sha256,
        'expected_selection_sha256': value['selection_sha256'],
        'selection_hash_matches': selection_sha256 == value['selection_sha256'],
        'selection_evaluated': True, 'relocation_evaluated': False,
        'reference_state_evaluated': False, 'symbol_resolved': False,
        'source_code_executed': False, 'write_authorized': False}
    result = object.__new__(CodeLineSelection)
    object.__setattr__(result, 'selection_bytes', selected)
    object.__setattr__(result, '_encoded', canonical_json_bytes(report))
    return result
