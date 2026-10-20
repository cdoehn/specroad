"""Explicit JUnit identities and passive candidates, without importing Evidence.

The first mapping slice accepts exact combinations of core testcase attributes.
It rejects the entire resolution when an identity or outcome is not unique.
External identifiers, complete conflict reports and import policies are separate
steps; no implicit match, partial import, product state or run is invented here.
"""
from dataclasses import dataclass
from hashlib import sha256

from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.errors import ModelError
from ..storage.json_syntax import parse_json_object
from .contracts import VerificationContract, VerificationTest
from .junit import JUnitDocument


class JUnitMappingError(ModelError):
    code = 'SRV090'
    exit_code = 3

    def diagnostic(self):
        return {**super().diagnostic(), 'code': self.code, 'exit_code': self.exit_code}


_FIELDS = frozenset({'classname', 'name', 'file'})
_RESULTS = {'passed': 'passed', 'failure': 'failed', 'error': 'failed', 'skipped': 'skipped'}


@dataclass(frozen=True, init=False)
class JUnitMapping:
    """An owned, versioned exact-match table; never executable mapping code."""
    source_bytes: bytes
    _encoded: bytes

    def __init__(self, raw):
        if type(raw) is not bytes:
            raise JUnitMappingError('junit_mapping_bytes_required')
        if len(raw) > 4 * 1024 * 1024:
            raise JUnitMappingError('junit_mapping_byte_limit')
        value = parse_json_object(raw)
        if set(value) != {'format_version', 'identity_fields', 'bindings'}:
            raise JUnitMappingError('invalid_junit_mapping_fields')
        if value['format_version'] != 'junit-mapping-v1':
            raise JUnitMappingError('unsupported_junit_mapping_version', pointer='/format_version')
        fields = value['identity_fields']
        if (type(fields) is not list or not fields or
                any(type(name) is not str or name not in _FIELDS for name in fields) or
                len(set(fields)) != len(fields)):
            raise JUnitMappingError('invalid_junit_identity_fields', pointer='/identity_fields')
        bindings = value['bindings']
        if type(bindings) is not list or len(bindings) > 10000:
            raise JUnitMappingError('invalid_junit_mapping_bindings', pointer='/bindings')
        seen = set()
        for number, binding in enumerate(bindings):
            pointer = '/bindings/' + str(number)
            if type(binding) is not dict or set(binding) != {'identity', 'target_id'}:
                raise JUnitMappingError('invalid_junit_mapping_binding', pointer=pointer)
            identity = binding['identity']
            if (type(identity) is not dict or set(identity) != set(fields) or
                    any(type(item) is not str or not item for item in identity.values())):
                raise JUnitMappingError('invalid_junit_mapping_identity', pointer=pointer + '/identity')
            if type(binding['target_id']) is not str or not binding['target_id']:
                raise JUnitMappingError('invalid_junit_mapping_target', pointer=pointer + '/target_id')
            key = tuple(identity[name] for name in fields)
            if key in seen:
                raise JUnitMappingError('duplicate_junit_mapping_identity', pointer=pointer + '/identity')
            seen.add(key)
        object.__setattr__(self, 'source_bytes', raw)
        object.__setattr__(self, '_encoded', canonical_json_bytes(value))

    @property
    def data(self):
        return parse_json_object(self._encoded)

    @property
    def sha256(self):
        return sha256(self._encoded).hexdigest()

    def __bool__(self):
        raise TypeError('A mapping is not an observed result or write authority')


@dataclass(frozen=True, init=False)
class JUnitCandidates:
    """Bound measurements awaiting provenance, run binding and native planning."""
    _encoded: bytes

    def __init__(self, *args, **kwargs):
        raise TypeError('Use map_junit_candidates with owned input values')

    @property
    def data(self):
        return parse_json_object(self._encoded)

    @property
    def sha256(self):
        return sha256(self._encoded).hexdigest()

    def __bool__(self):
        raise TypeError('JUnit candidates are not verified or recorded Evidence')


def map_junit_candidates(document, mapping, *, targets):
    """Resolve every core testcase exactly once or return no candidate value.

    Only actual supplied Test/Verification records can be targets. Their IDs
    are looked up literally, never through titles, external IDs or source paths.
    One result is retained per testcase occurrence; targets are not aggregated.
    Missing or repeated keys and mixed outcome kinds reject this initial slice.
    """
    if type(document) is not JUnitDocument:
        raise JUnitMappingError('typed_junit_document_required')
    if type(mapping) is not JUnitMapping:
        raise JUnitMappingError('typed_junit_mapping_required')
    # Reconstruct from owned source bytes rather than trusting replaceable caches.
    document = JUnitDocument(document.source_bytes)
    mapping = JUnitMapping(mapping.source_bytes)
    if type(targets) not in (tuple, list):
        raise JUnitMappingError('typed_junit_targets_required', pointer='/targets')
    target_bindings = {}
    for number, target in enumerate(targets):
        pointer = '/targets/' + str(number)
        if type(target) not in (VerificationTest, VerificationContract):
            raise JUnitMappingError('typed_junit_target_required', pointer=pointer)
        owned = type(target)(target.source_bytes)
        value = owned.data
        if value['id'] in target_bindings:
            raise JUnitMappingError('duplicate_junit_target', pointer=pointer)
        target_bindings[value['id']] = {
            'artifact_id': value['id'], 'artifact_type': value['artifact_type'],
            'revision': value['revision'], 'source_sha256': sha256(owned.source_bytes).hexdigest(),
            'record_sha256': canonical_json_sha256(value)}
    settings = mapping.data
    fields = settings['identity_fields']
    lookup = {}
    for number, binding in enumerate(settings['bindings']):
        if binding['target_id'] not in target_bindings:
            raise JUnitMappingError('junit_mapping_target_not_found',
                                    pointer='/bindings/' + str(number) + '/target_id')
        lookup[tuple(binding['identity'][name] for name in fields)] = binding['target_id']
    parsed = document.data
    pending = [(parsed['root'], '/root')]
    candidates, seen = [], set()
    while pending:
        node, pointer = pending.pop()
        if node['tag'] != 'testcase':
            pending.extend((child, pointer + '/children/' + str(number))
                           for number, child in reversed(list(enumerate(node['children']))))
            continue
        attributes = node['attributes']
        if any(name not in attributes or not attributes[name] for name in fields):
            raise JUnitMappingError('junit_testcase_identity_missing', pointer=pointer + '/attributes')
        key = tuple(attributes[name] for name in fields)
        if key in seen:
            raise JUnitMappingError('duplicate_junit_testcase_identity', pointer=pointer)
        seen.add(key)
        if key not in lookup:
            raise JUnitMappingError('junit_testcase_unmapped', pointer=pointer)
        outcomes = {child['tag'] for child in node['children']
                    if child['tag'] in ('failure', 'error', 'skipped')}
        if len(outcomes) > 1:
            raise JUnitMappingError('conflicting_junit_testcase_outcomes', pointer=pointer)
        outcome = next(iter(outcomes)) if outcomes else 'passed'
        candidates.append({
            'testcase_index': len(candidates), 'testcase_pointer': pointer,
            'identity': {name: attributes[name] for name in fields},
            'target': target_bindings[lookup[key]], 'junit_outcome': outcome,
            'result': _RESULTS[outcome], 'origin': 'imported_junit'})
    value = {'format_version': 'junit-candidates-v1', 'source': parsed['source'],
             'parser_profile': parsed['format_version'], 'mapping_sha256': mapping.sha256,
             'mapping_source_sha256': sha256(mapping.source_bytes).hexdigest(),
             'identity_fields': fields, 'testcase_count': len(candidates), 'candidates': candidates,
             'test_code_executed': False, 'evidence_created': False,
             'run_context_bound': False, 'project_targets_verified': False,
             'full_verification_evaluated': False, 'write_authorized': False,
             'approval_granted': False}
    result = object.__new__(JUnitCandidates)
    object.__setattr__(result, '_encoded', canonical_json_bytes(value))
    return result
