"""Inclusive stored line selections over already bound original source bytes."""
from dataclasses import dataclass, field
from hashlib import sha256

from ..model.canonical import canonical_json_bytes
from ..model.errors import ModelError
from ..storage.json_syntax import parse_json_object
from .code_references import CodeReferenceSource


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
    try:
        text = source.source_bytes.decode(value['encoding'], errors='strict')
    except UnicodeError as error:
        raise ModelError('code_reference_decode_failed', pointer='/encoding') from error
    except (LookupError, ValueError) as error:
        raise ModelError('code_reference_encoding_unavailable', pointer='/encoding') from error
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    # Only LF separates normalized lines. str.splitlines would also split
    # other Unicode characters that H.2 explicitly requires us to preserve.
    offset = line_count = 0
    selected_start = selected_end = None
    while offset < len(text):
        line_count += 1
        if line_count == value['start_line']:
            selected_start = offset
        newline = text.find('\n', offset)
        offset = len(text) if newline == -1 else newline + 1
        if line_count == value['end_line']:
            selected_end = offset
    if selected_end is None:
        raise ModelError('code_reference_selection_missing', pointer='/end_line')
    try:
        selected = text[selected_start:selected_end].encode('utf-8')
    except UnicodeError as error:
        raise ModelError('code_reference_decode_failed', pointer='/encoding') from error
    selection_sha256 = sha256(selected).hexdigest()
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
