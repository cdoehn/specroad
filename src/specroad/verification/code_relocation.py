"""Exact selection location on owned source bytes; no H.3 state or writes."""
from dataclasses import dataclass, field
from hashlib import sha256

from ..model.canonical import canonical_json_bytes
from ..model.errors import ModelError
from ..storage.json_syntax import parse_json_object
from .code_references import CodeReferenceSource


@dataclass(frozen=True, init=False)
class CodeSelectionLocation:
    """A unique selection's bytes (or None), with detached location evidence."""
    selection_bytes: bytes | None = field(repr=False)
    _encoded: bytes = field(repr=False)

    def __init__(self, *args, **kwargs):
        raise TypeError('Use locate_code_selection')

    @property
    def data(self):
        return parse_json_object(self._encoded)

    @property
    def sha256(self):
        return sha256(self._encoded).hexdigest()

    def __bool__(self):
        raise TypeError('A selection location is not a reference state or approval')


def locate_code_selection(source):
    """Find stored or uniquely relocated line/text/explicit byte selections.

    Text windows contain the exact stored number of inclusive whole lines.
    Byte windows contain the exact declared number of original bytes, including
    overlapping candidates. A stored match takes precedence over any duplicates.
    Unknown legacy anchor objects remain data, never inferred selectors.
    """
    if type(source) is not CodeReferenceSource:
        raise ModelError('code_reference_source_bytes_required')
    bound = source.data
    value = bound['reference']
    kind = value['reference_kind']
    if kind == 'line_range':
        mode = 'text'
        start = value['start_line'] - 1
        count = value['end_line'] - value['start_line'] + 1
    elif kind == 'text_anchor':
        anchor = value['anchor']
        if anchor.get('format_version') != 'code-anchor-v1':
            raise ModelError('code_reference_anchor_unsupported', pointer='/anchor/format_version')
        mode = anchor.get('mode')
        if mode not in ('text', 'bytes'):
            raise ModelError('code_reference_anchor_invalid', pointer='/anchor/mode')
        first, length, minimum = ('start_line', 'line_count', 1) if mode == 'text' else ('start_byte', 'byte_count', 0)
        if set(anchor) != {'format_version', 'mode', first, length}:
            raise ModelError('code_reference_anchor_invalid', pointer='/anchor')
        for name, lower in ((first, minimum), (length, 1)):
            if type(anchor[name]) is not int or anchor[name] < lower:
                raise ModelError('code_reference_anchor_invalid', pointer='/anchor/' + name)
        start = anchor[first] - minimum
        count = anchor[length]
        # Optional old top-level positions may corroborate a text selector,
        # but cannot silently override it or reinterpret byte offsets as lines.
        for name, expected in (('start_line', start + 1), ('end_line', start + count)):
            if name in value and (mode == 'bytes' or value[name] != expected):
                raise ModelError('code_reference_anchor_conflict', pointer='/' + name)
        if mode == 'bytes' and 'encoding' in value:
            raise ModelError('code_reference_anchor_conflict', pointer='/encoding')
    else:
        raise ModelError('code_reference_selection_kind_required', pointer='/reference_kind')

    encoding = None
    line_count = None
    if mode == 'text':
        if 'encoding' not in value:
            raise ModelError('code_reference_encoding_required', pointer='/encoding')
        encoding = value['encoding']
        try:
            text = source.source_bytes.decode(encoding, errors='strict')
        except UnicodeError as error:
            raise ModelError('code_reference_decode_failed', pointer='/encoding') from error
        except (LookupError, ValueError) as error:
            raise ModelError('code_reference_encoding_unavailable', pointer='/encoding') from error
        try:
            content = text.replace('\r\n', '\n').replace('\r', '\n').encode('utf-8')
        except UnicodeError as error:
            raise ModelError('code_reference_decode_failed', pointer='/encoding') from error
        # LF is the only separator. The final boundary is not a phantom line.
        boundaries = [0]
        offset = 0
        while offset < len(content):
            newline = content.find(b'\n', offset)
            offset = len(content) if newline == -1 else newline + 1
            boundaries.append(offset)
        line_count = size = len(boundaries) - 1
        stored_position = {'start_line': start + 1, 'end_line': start + count}
    else:
        content = source.source_bytes
        size = len(content)
        stored_position = {'start_byte': start, 'byte_count': count}

    view = memoryview(content)
    expected_hash = value['selection_sha256']
    stored_hash = None
    stored_span = None
    if start + count <= size:
        left, right = (boundaries[start], boundaries[start + count]) if mode == 'text' else (start, start + count)
        stored_span = (left, right)
        stored_hash = sha256(view[left:right]).hexdigest()
    stored_matches = stored_hash == expected_hash
    matched_position = new_position = None
    selected = None
    match_count = None
    if stored_matches:
        outcome = 'stored_position'
        matched_position = stored_position
        selected = bytes(view[stored_span[0]:stored_span[1]])
    else:
        match_count = 0
        match_span = match_start = None
        for candidate in range(max(0, size - count + 1)):
            if candidate == start:
                continue
            left, right = (boundaries[candidate], boundaries[candidate + count]) if mode == 'text' else (candidate, candidate + count)
            if sha256(view[left:right]).hexdigest() == expected_hash:
                match_count += 1
                if match_count == 1:
                    match_start, match_span = candidate, (left, right)
        if match_count == 1:
            outcome = 'relocated'
            matched_position = ({'start_line': match_start + 1, 'end_line': match_start + count}
                                if mode == 'text' else {'start_byte': match_start, 'byte_count': count})
            new_position = matched_position
            selected = bytes(view[match_span[0]:match_span[1]])
        else:
            outcome = 'selection_missing' if match_count == 0 else 'selection_ambiguous'

    report = {'format_version': 'code-selection-location-v1',
        'validation_scope': 'code_selection_location_only',
        'source': bound, 'source_sha256': source.sha256, 'selection_mode': mode,
        'encoding': encoding, 'source_line_count': line_count,
        'stored_position': stored_position, 'stored_selection_sha256': stored_hash,
        'stored_position_matches': stored_matches, 'expected_selection_sha256': expected_hash,
        'search_performed': not stored_matches, 'match_count': match_count,
        'selection_result': outcome, 'matched_position': matched_position, 'new_position': new_position,
        'selection_sha256': None if selected is None else sha256(selected).hexdigest(),
        'selection_evaluated': True, 'relocation_evaluated': True,
        'reference_state_evaluated': False, 'symbol_resolved': False,
        'source_code_executed': False, 'write_authorized': False}
    result = object.__new__(CodeSelectionLocation)
    object.__setattr__(result, 'selection_bytes', selected)
    object.__setattr__(result, '_encoded', canonical_json_bytes(report))
    return result
