"""Bounded JUnit XML values, without mapping, file access or test execution.

This reader accepts one complete byte document. All XML, including ignored
extensions, passes the same structural limits. Original bytes remain available
for a later explicit attachment; successful parsing is not verified Evidence.
"""
from dataclasses import dataclass, fields
from hashlib import sha256

from ..model.canonical import canonical_json_bytes
from ..model.errors import ModelError
from ..storage._xml_reader import read_bounded_xml
from ..storage.json_syntax import parse_json_object


class XmlImportError(ModelError):
    code = 'SRV083'

    def __init__(self, reason, *, exit_code=3, **location):
        super().__init__(reason, **location)
        self.exit_code = exit_code

    def diagnostic(self):
        return {**super().diagnostic(), 'code': self.code, 'exit_code': self.exit_code}


@dataclass(frozen=True)
class JUnitLimits:
    """Per-document hard limits; callers may tighten, never enlarge them."""
    max_bytes: int = 4 * 1024 * 1024
    max_depth: int = 64
    max_elements: int = 10000
    max_text_chars: int = 1024 * 1024
    max_attributes_per_element: int = 64
    max_name_chars: int = 256
    max_expanded_name_chars: int = 1024 * 1024

    def __post_init__(self):
        for field in fields(self):
            value = getattr(self, field.name)
            if type(value) is not int or not 1 <= value <= field.default:
                raise XmlImportError('invalid_xml_limits', exit_code=2)


_CHILDREN = {
    'testsuites': frozenset({'testsuite'}),
    'testsuite': frozenset({'testsuite', 'testcase', 'system-out', 'system-err'}),
    'testcase': frozenset({'failure', 'error', 'skipped', 'system-out', 'system-err'}),
    **{name: frozenset() for name in ('failure', 'error', 'skipped', 'system-out', 'system-err')},
}
_ATTRIBUTES = frozenset({'name', 'classname', 'file', 'line', 'time', 'timestamp',
                        'tests', 'failures', 'errors', 'skipped'})


def _parse(raw, limits):
    """Assemble only JUnit profile values from safety-checked XML events."""
    stack, root = [], None
    ignored_elements = ignored_attributes = 0

    def start(name, attributes, reject):
        nonlocal root, ignored_elements, ignored_attributes
        if not stack and name not in ('testsuites', 'testsuite'):
            reject('junit_root_required', exit_code=3)
        if name not in _CHILDREN or (stack and stack[-1] is None):
            ignored_elements += 1
            stack.append(None)
            return
        if stack and name not in _CHILDREN[stack[-1]['tag']]:
            reject('junit_element_placement', exit_code=3)
        known = {key: value for key, value in attributes.items() if key in _ATTRIBUTES}
        ignored_attributes += len(attributes) - len(known)
        node = {'tag': name, 'attributes': known, 'text': [], 'children': []}
        if stack:
            stack[-1]['children'].append(node)
        else:
            root = node
        stack.append(node)

    def end(_):
        node = stack.pop()
        if node is not None:
            node['text'] = ''.join(node['text'])

    def characters(text):
        if stack and stack[-1] is not None:
            stack[-1]['text'].append(text)

    read_bounded_xml(raw, limits=limits, limit_type=JUnitLimits, error_type=XmlImportError,
                     on_start=start, on_end=end, on_text=characters)
    return {'format_version': 'junit-core-v1',
            'source': {'size': len(raw), 'sha256': sha256(raw).hexdigest()},
            'root': root, 'ignored_elements': ignored_elements,
            'ignored_attributes': ignored_attributes,
            'test_code_executed': False, 'evidence_created': False}


@dataclass(frozen=True, init=False)
class JUnitDocument:
    """An owned read result; attributes are reported strings, not trusted totals."""
    source_bytes: bytes
    _encoded: bytes

    def __init__(self, raw, *, limits=None):
        value = _parse(raw, limits)
        object.__setattr__(self, 'source_bytes', raw)
        object.__setattr__(self, '_encoded', canonical_json_bytes(value))

    @property
    def data(self):
        return parse_json_object(self._encoded)

    @property
    def sha256(self):
        return sha256(self.source_bytes).hexdigest()

    def __bool__(self):
        raise TypeError('Parsed JUnit is not successful verification or write authority')
