"""Explicit JUnit identities and passive candidates, without importing Evidence.

The strict W interface retains its all-or-nothing core-attribute contract.
The analysis interface also accepts explicitly bound external identifiers and
reports each unmapped, ambiguous or contradictory observation. Neither interface
chooses an import policy, invents a product/run binding or publishes Evidence.
"""
from dataclasses import dataclass
from hashlib import sha256
import re

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


def _read_mapping(raw, *, version, fields_supported, unique):
    if type(raw) is not bytes:
        raise JUnitMappingError('junit_mapping_bytes_required')
    if len(raw) > 4 * 1024 * 1024:
        raise JUnitMappingError('junit_mapping_byte_limit')
    value = parse_json_object(raw)
    if set(value) != {'format_version', 'identity_fields', 'bindings'}:
        raise JUnitMappingError('invalid_junit_mapping_fields')
    if value['format_version'] != version:
        raise JUnitMappingError('unsupported_junit_mapping_version', pointer='/format_version')
    fields = value['identity_fields']
    if (type(fields) is not list or not fields or
            any(type(name) is not str or name not in fields_supported for name in fields) or
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
        if unique and key in seen:
            raise JUnitMappingError('duplicate_junit_mapping_identity', pointer=pointer + '/identity')
        seen.add(key)
    return value


@dataclass(frozen=True, init=False)
class JUnitMapping:
    """An owned, versioned exact-match table; never executable mapping code."""
    source_bytes: bytes
    _encoded: bytes

    def __init__(self, raw):
        value = _read_mapping(raw, version='junit-mapping-v1', fields_supported=_FIELDS, unique=True)
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


@dataclass(frozen=True, init=False)
class JUnitMappingRules(JUnitMapping):
    """Analysis rules retain duplicate rows for diagnosis, never first-match wins."""

    def __init__(self, raw):
        value = _read_mapping(raw, version='junit-mapping-rules-v1',
                              fields_supported=_FIELDS | {'external_id'}, unique=False)
        object.__setattr__(self, 'source_bytes', raw)
        object.__setattr__(self, '_encoded', canonical_json_bytes(value))


@dataclass(frozen=True, init=False)
class JUnitExternalIdentifiers:
    """Explicit sidecar values bound to the exact XML bytes and core ordinals."""
    source_bytes: bytes
    _encoded: bytes

    def __init__(self, raw):
        if type(raw) is not bytes:
            raise JUnitMappingError('junit_external_identifiers_bytes_required')
        if len(raw) > 4 * 1024 * 1024:
            raise JUnitMappingError('junit_external_identifiers_byte_limit')
        value = parse_json_object(raw)
        if set(value) != {'format_version', 'source_sha256', 'entries'}:
            raise JUnitMappingError('invalid_junit_external_identifiers_fields')
        if value['format_version'] != 'junit-external-identifiers-v1':
            raise JUnitMappingError('unsupported_junit_external_identifiers_version',
                                    pointer='/format_version')
        if (type(value['source_sha256']) is not str or
                re.fullmatch('[0-9a-f]{64}', value['source_sha256']) is None):
            raise JUnitMappingError('invalid_junit_external_source_hash', pointer='/source_sha256')
        if type(value['entries']) is not list or len(value['entries']) > 10000:
            raise JUnitMappingError('invalid_junit_external_entries', pointer='/entries')
        seen = set()
        for number, entry in enumerate(value['entries']):
            pointer = '/entries/' + str(number)
            if type(entry) is not dict or set(entry) != {'testcase_index', 'external_id'}:
                raise JUnitMappingError('invalid_junit_external_entry', pointer=pointer)
            index = entry['testcase_index']
            if type(index) is not int or not 0 <= index < 10000:
                raise JUnitMappingError('invalid_junit_external_index', pointer=pointer + '/testcase_index')
            if type(entry['external_id']) is not str or not entry['external_id']:
                raise JUnitMappingError('invalid_junit_external_id', pointer=pointer + '/external_id')
            if index in seen:
                raise JUnitMappingError('duplicate_junit_external_index', pointer=pointer + '/testcase_index')
            seen.add(index)
        object.__setattr__(self, 'source_bytes', raw)
        object.__setattr__(self, '_encoded', canonical_json_bytes(value))

    @property
    def data(self):
        return parse_json_object(self._encoded)

    @property
    def sha256(self):
        return sha256(self._encoded).hexdigest()

    def __bool__(self):
        raise TypeError('External identifiers do not prove an executed test or approval')


@dataclass(frozen=True, init=False)
class JUnitMappingAnalysis:
    """Complete observations and diagnostics, without choosing an import policy."""
    _encoded: bytes

    def __init__(self, *args, **kwargs):
        raise TypeError('Use analyze_junit_candidates with owned input values')

    @property
    def data(self):
        return parse_json_object(self._encoded)

    @property
    def sha256(self):
        return sha256(self._encoded).hexdigest()

    def __bool__(self):
        raise TypeError('A mapping analysis is not successful verification or write authority')


def analyze_junit_candidates(document, mapping, *, targets, external_identifiers=None):
    """Account for every core occurrence; ambiguous/conflicting groups yield no candidate.

    A supplied sidecar, when selected, must bind this exact report. Unknown XML
    attributes/elements are never reinterpreted as identifiers. This analysis
    retains valid independent candidates alongside all diagnostics, but never
    selects abort/skip policy, publishes an import or authenticates an external run.
    """
    if type(document) is not JUnitDocument:
        raise JUnitMappingError('typed_junit_document_required')
    if type(mapping) not in (JUnitMapping, JUnitMappingRules):
        raise JUnitMappingError('typed_junit_mapping_required')
    document = JUnitDocument(document.source_bytes)
    mapping = type(mapping)(mapping.source_bytes)
    settings, parsed = mapping.data, document.data
    fields = settings['identity_fields']
    external, external_binding = {}, None
    if 'external_id' in fields:
        if type(external_identifiers) is not JUnitExternalIdentifiers:
            raise JUnitMappingError('typed_junit_external_identifiers_required')
        sidecar = JUnitExternalIdentifiers(external_identifiers.source_bytes)
        if sidecar.data['source_sha256'] != document.sha256:
            raise JUnitMappingError('junit_external_source_mismatch', pointer='/source_sha256')
        external = {entry['testcase_index']: entry['external_id'] for entry in sidecar.data['entries']}
        external_binding = {'sha256': sidecar.sha256, 'size': len(sidecar.source_bytes),
                            'source_sha256': sha256(sidecar.source_bytes).hexdigest()}
    elif external_identifiers is not None:
        raise JUnitMappingError('unused_junit_external_identifiers')
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
    rows, unknown_rows = {}, []
    for number, binding in enumerate(settings['bindings']):
        key = tuple(binding['identity'][name] for name in fields)
        rows.setdefault(key, []).append(number)
        if binding['target_id'] not in target_bindings:
            unknown_rows.append(number)
    cases, groups = [], {}
    pending = [(parsed['root'], '/root')]
    while pending:
        node, pointer = pending.pop()
        if node['tag'] != 'testcase':
            pending.extend((child, pointer + '/children/' + str(number))
                           for number, child in reversed(list(enumerate(node['children']))))
            continue
        index = len(cases)
        context = {name: node['attributes'].get(name) for name in ('classname', 'name', 'file')}
        context['external_id'] = external.get(index)
        identity = {name: context[name] for name in fields}
        outcomes = sorted({child['tag'] for child in node['children']
                           if child['tag'] in ('failure', 'error', 'skipped')}) or ['passed']
        cases.append({'testcase_index': index, 'testcase_pointer': pointer,
                      'identity': identity, 'context': context, 'junit_outcomes': outcomes})
        groups.setdefault(tuple(identity.values()), []).append(index)
    if any(index >= len(cases) for index in external):
        raise JUnitMappingError('junit_external_index_out_of_range', pointer='/entries')

    diagnostics, rejected = [], set()

    def diagnose(category, reason, indexes, mapping_indexes=(), missing_fields=()):
        indexes = sorted(indexes)
        rejected.update(indexes)
        code = 'SRV043' if category in ('unmapped', 'ambiguous') else 'SRV090'
        diagnostics.append({'code': code, 'severity': 'warning' if code == 'SRV043' else 'error',
                            'category': category, 'reason': reason, 'testcase_indexes': indexes,
                            'mapping_indexes': sorted(mapping_indexes), 'missing_fields': list(missing_fields)})

    # Report a bad unused mapping target as well; absence of a testcase does not
    # validate that row. This single group keeps diagnostics linear in input size.
    if unknown_rows:
        diagnose('unmapped', 'junit_mapping_target_not_found', (), unknown_rows)
    for key, mapping_indexes in rows.items():
        if key not in groups and len(mapping_indexes) > 1:
            diagnose('ambiguous', 'junit_mapping_ambiguous', (), mapping_indexes)
    for key, indexes in groups.items():
        mapping_indexes = rows.get(key, [])
        missing = [name for name, item in zip(fields, key) if item is None or item == '']
        if missing:
            diagnose('unmapped', 'junit_testcase_identity_missing', indexes, missing_fields=missing)
        elif not mapping_indexes:
            diagnose('unmapped', 'junit_testcase_unmapped', indexes)
        elif len(mapping_indexes) > 1:
            diagnose('ambiguous', 'junit_mapping_ambiguous', indexes, mapping_indexes)
        elif settings['bindings'][mapping_indexes[0]]['target_id'] not in target_bindings:
            diagnose('unmapped', 'junit_mapping_target_not_found', indexes, mapping_indexes)
        if len(indexes) > 1:
            diagnose('ambiguous', 'duplicate_junit_testcase_identity', indexes)
        contexts = {}
        for index in indexes:
            case = cases[index]
            contexts.setdefault(tuple(case['context'].values()), []).append(index)
            if len(case['junit_outcomes']) > 1:
                diagnose('contradictory', 'conflicting_junit_testcase_outcomes', [index])
        for related in contexts.values():
            if len({tuple(cases[index]['junit_outcomes']) for index in related}) > 1:
                diagnose('contradictory', 'conflicting_junit_testcase_results', related)
    candidates = []
    for case in cases:
        if case['testcase_index'] in rejected:
            continue
        key = tuple(case['identity'].values())
        row, = rows[key]
        outcome, = case['junit_outcomes']
        candidates.append({'testcase_index': case['testcase_index'],
                           'testcase_pointer': case['testcase_pointer'], 'identity': case['identity'],
                           'target': target_bindings[settings['bindings'][row]['target_id']],
                           'junit_outcome': outcome, 'result': _RESULTS[outcome], 'origin': 'imported_junit'})
    diagnostics.sort(key=lambda item: (
        item['testcase_indexes'][0] if item['testcase_indexes'] else -1,
        item['category'], item['reason'], item['mapping_indexes']))
    value = {'format_version': 'junit-mapping-analysis-v1', 'source': parsed['source'],
             'parser_profile': parsed['format_version'], 'mapping_sha256': mapping.sha256,
             'mapping_source_sha256': sha256(mapping.source_bytes).hexdigest(),
             'external_identifiers': external_binding, 'identity_fields': fields,
             'targets': [target_bindings[key] for key in sorted(target_bindings)],
             'testcase_count': len(cases), 'observations': cases, 'candidates': candidates,
             'diagnostics': diagnostics, 'rejected_testcase_indexes': sorted(rejected),
             'mapping_complete': not diagnostics, 'test_code_executed': False,
             'evidence_created': False, 'run_context_bound': False,
             'project_targets_verified': False, 'full_verification_evaluated': False,
             'write_authorized': False, 'approval_granted': False, 'import_policy_applied': False}
    result = object.__new__(JUnitMappingAnalysis)
    object.__setattr__(result, '_encoded', canonical_json_bytes(value))
    return result
